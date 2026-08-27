"""
🏆 欧洲五大联赛数据自动更新脚本 — 从 Football-Data.org API 拉新赛季数据

自动检测当前赛季（现在 = 2026-27），从 API 拉取五大联赛（英超/德甲/西甲/意甲/法甲）
全部赛程，合并进 docs/data/matches_{league_id}.json；并在现有 teams.json 的 Elo
基础上，按时间序走一遍新赛季已完赛比赛，更新 Elo。

用法:
    FOOTBALL_API_KEY=xxx python3 backend/data/league_data_updater.py
    python3 backend/data/league_data_updater.py              # 从 .env 读 key
    python3 backend/data/league_data_updater.py --dry-run     # 试运行不写文件

GitHub Actions 用:
    FOOTBALL_API_KEY=${{ secrets.FOOTBALL_API_KEY }} python3 backend/data/league_data_updater.py
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "docs" / "data"
ENV_FILE = BASE_DIR / ".env"

BASE = "https://api.football-data.org/v4"

# 内部 league_id -> Football-Data.org 竞赛 code
# （docs/data/matches_{league_id}.json 的命名用内部 league_id）
LEAGUES = {
    2021: "PL",    # 英超 Premier League
    2002: "BL1",   # 德甲 Bundesliga
    2014: "PD",    # 西甲 Primera División
    2019: "SA",    # 意甲 Serie A
    2015: "FL1",   # 法甲 Ligue 1
}


def current_season():
    """返回 (FD API season 参数, 内部 season 标签)。

    欧洲跨年赛季：8 月及以后属于新赛季（如 2026-08 → ("2026", "2026-27")），
    与 backend/routers/matches.py 的 _current_season() 逻辑一致。
    """
    now = datetime.now(timezone.utc)
    y = now.year
    if now.month >= 8:
        return str(y), f"{y}-{str(y + 1)[-2:]}"
    return str(y - 1), f"{y - 1}-{str(y)[-2:]}"


def get_api_key() -> str:
    """从环境变量或 .env 读 API key"""
    env_key = os.environ.get("FOOTBALL_API_KEY")
    if env_key:
        return env_key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("FOOTBALL_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("❌ 设 FOOTBALL_API_KEY 环境变量，或创建 .env 文件")


def fetch(path: str, key: str) -> dict:
    """发送 GET 请求"""
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": key})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def load_json(path: Path):
    """读 JSON，不存在返回 None"""
    if path.exists():
        return json.loads(path.read_text())
    return None


def walk_elo(finished, initial_ratings, hfa_map):
    """在现有 Elo 基础上，按时间序走完赛比赛更新 Elo。

    hfa_map: {league_id: home_advantage}，主队有效分 = rating + hfa。
    K = 32，净胜球系数：差≥3 → 1.5，差≥2 → 1.25，否则 1.0。
    """
    K = 32.0
    ratings = dict(initial_ratings)
    finished_sorted = sorted(finished, key=lambda m: m.get('utc_date', ''))
    for m in finished_sorted:
        h_id = m['home_team_id']
        a_id = m['away_team_id']
        if not h_id or not a_id:
            continue
        h_r = ratings.get(h_id, 1500.0)
        a_r = ratings.get(a_id, 1500.0)
        hfa = hfa_map.get(m['league_id'], 100.0)
        e_h = 1.0 / (1.0 + 10 ** ((a_r - (h_r + hfa)) / 400.0))
        sh, sa = m['score_home'], m['score_away']
        if sh > sa:   a_h, a_a = 1.0, 0.0
        elif sh < sa: a_h, a_a = 0.0, 1.0
        else:         a_h, a_a = 0.5, 0.5
        gd = abs(sh - sa)
        gf = 1.0 + (0.25 if gd == 2 else (0.5 if gd >= 3 else 0.0))
        ratings[h_id] = h_r + K * gf * (a_h - e_h)
        ratings[a_id] = a_r + K * gf * (a_a - (1.0 - e_h))
    return ratings


def main(dry_run: bool = False):
    key = get_api_key()
    fd_season, season_label = current_season()
    print(f"🌍 当前赛季: {season_label}（FD season={fd_season}）")

    # 每联赛主场优势（docs/data/leagues.json，预测参数文件）
    hfa_map = {}
    leagues_path = DATA_DIR / "leagues.json"
    if leagues_path.exists():
        for l in json.loads(leagues_path.read_text()):
            if l.get('elo_home_advantage') is not None:
                hfa_map[l['id']] = l['elo_home_advantage']
    print(f"  主场优势: { {c: hfa_map.get(lid) for lid, c in LEAGUES.items()} }")

    # 现有 teams.json（含所有联赛球队 + Elo）
    teams_path = DATA_DIR / "teams.json"
    old_teams = load_json(teams_path) or []
    old_team_ids = {t['id'] for t in old_teams}

    all_finished = []      # 跨联赛新赛季已完赛（Elo 用）
    new_teams_by_id = {}   # 本次新出现的球队
    merged_by_league = {}  # league_id -> 合并后的比赛列表

    total_added = 0
    total_updated = 0

    for league_id, code in LEAGUES.items():
        matches_path = DATA_DIR / f"matches_{league_id}.json"
        old_matches = load_json(matches_path) or []
        old_by_id = {m['id']: i for i, m in enumerate(old_matches)}

        print(f"\n⚽ {code}（league_id={league_id}）...")
        time.sleep(1.0)  # 防 API 限流（免费档 10 次/分钟）
        try:
            data = fetch(f"/competitions/{code}/matches?season={fd_season}", key)
        except Exception as e:
            print(f"  ❌ API 请求失败: {e}")
            continue
        matches_raw = data.get('matches', [])
        valid = [m for m in matches_raw
                 if m.get('homeTeam', {}).get('id') and m.get('awayTeam', {}).get('id')]
        print(f"  原始 {len(matches_raw)} 场，有效 {len(valid)} 场")

        new_matches = []
        for m in valid:
            try:
                dt = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00'))
                utc = dt.strftime("%Y-%m-%d %H:%M:%S.000000")
            except Exception:
                utc = m['utcDate'].replace('T', ' ') + ".000000"

            score = (m.get('score') or {}).get('fullTime') or {}
            score_h = score.get('home')
            score_a = score.get('away')

            winner = None
            if score_h is not None and score_a is not None:
                if score_h > score_a:      winner = "HOME_TEAM"
                elif score_h < score_a:    winner = "AWAY_TEAM"
                else:                      winner = "DRAW"

            fd_status = m.get('status', '')
            status = 'FINISHED' if fd_status == 'FINISHED' else 'SCHEDULED'

            h_id = m['homeTeam']['id']
            a_id = m['awayTeam']['id']

            rec = {
                "id": m['id'],
                "league_id": league_id,
                "season": season_label,
                "utc_date": utc,
                "status": status,
                "home_team_id": h_id,
                "away_team_id": a_id,
                "home_team_name": m['homeTeam']['name'],
                "away_team_name": m['awayTeam']['name'],
                "score_home": score_h,
                "score_away": score_a,
                "winner": winner,
            }
            new_matches.append(rec)
            if status == 'FINISHED' and score_h is not None and score_a is not None:
                all_finished.append(rec)

            # 收集新球队
            for side in ('homeTeam', 'awayTeam'):
                t = m[side]
                if t['id'] not in old_team_ids and t['id'] not in new_teams_by_id:
                    new_teams_by_id[t['id']] = {"id": t['id'], "n": t['name'], "elo": 1500.0}

        new_matches.sort(key=lambda x: x['utc_date'])

        # 合并进旧文件（旧文件含历史所有赛季）：同 id 用最新数据替换，新 id 追加
        merged = list(old_matches)
        old_by_id = {m['id']: i for i, m in enumerate(merged)}
        added = 0
        updated = 0
        for nm in new_matches:
            idx = old_by_id.get(nm['id'])
            if idx is not None:
                om = merged[idx]
                if (om.get('score_home') != nm['score_home']
                        or om.get('score_away') != nm['score_away']
                        or om.get('status') != nm['status']):
                    updated += 1
                merged[idx] = nm
            else:
                old_by_id[nm['id']] = len(merged)
                merged.append(nm)
                added += 1

        finished_count = sum(1 for m in new_matches if m['status'] == 'FINISHED')
        print(f"  新赛季 {len(new_matches)} 场（{finished_count} 已完）| 新增 {added} | 更新 {updated}")

        total_added += added
        total_updated += updated
        merged_by_league[league_id] = merged

    # ===== Elo 更新 =====
    print("\n📈 更新 Elo（现有 teams.json 基础上走新赛季已完赛比赛）...")
    involved_ids = set()
    for m in all_finished:
        involved_ids.add(m['home_team_id'])
        involved_ids.add(m['away_team_id'])
    involved_ids.update(new_teams_by_id)

    initial_ratings = {}
    for t in old_teams + list(new_teams_by_id.values()):
        if t['id'] in involved_ids:
            initial_ratings[t['id']] = t.get('elo', 1500.0)

    elo_before = dict(initial_ratings)
    ratings = walk_elo(all_finished, initial_ratings, hfa_map)

    all_teams = list(old_teams)
    seen = set(t['id'] for t in all_teams)
    for t in new_teams_by_id.values():
        if t['id'] not in seen:
            all_teams.append(t)
            seen.add(t['id'])

    elo_changes = 0
    for t in all_teams:
        if t['id'] in ratings:
            new_elo = round(ratings[t['id']], 1)
            if t.get('elo', 1500.0) != new_elo:
                t['elo'] = new_elo
                elo_changes += 1

    changed = [(t['n'], elo_before.get(t['id'], 1500.0), t['elo'])
               for t in all_teams
               if t['id'] in elo_before and abs(elo_before[t['id']] - t['elo']) > 0.5]
    changed.sort(key=lambda x: -abs(x[2] - x[1]))
    print(f"  Elo 变化 {len(changed)} 队")
    for name, old_e, new_e in changed[:10]:
        arrow = "↑" if new_e > old_e else "↓"
        print(f"    {name:32s} {old_e:7.1f} → {new_e:7.1f}  {arrow}")
    if len(changed) > 10:
        print(f"    ... 及 {len(changed) - 10} 队")

    if new_teams_by_id:
        print(f"  🏃 新球队（{len(new_teams_by_id)}）: {[t['n'] for t in new_teams_by_id.values()]}")

    print(f"\n✅ 总览: 新增 {total_added} 场，更新 {total_updated} 场，Elo 变化 {elo_changes} 队")

    if dry_run:
        print("\n🔍 DRY RUN — 不写任何文件")
        return

    # ===== 写文件 =====
    for league_id, merged in merged_by_league.items():
        with open(DATA_DIR / f"matches_{league_id}.json", 'w') as f:
            json.dump(merged, f, ensure_ascii=False, indent=1)
        print(f"  ✏️  docs/data/matches_{league_id}.json（{len(merged)} 场）")

    with open(teams_path, 'w') as f:
        json.dump(all_teams, f, ensure_ascii=False, indent=1)
    print(f"  ✏️  docs/data/teams.json（{len(all_teams)} 队）")

    print("\n📌 提交建议:")
    print("  git add docs/data/")
    print('  git commit -m "auto: 🏆 欧洲联赛数据更新"')
    print("  git push")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印不写")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
