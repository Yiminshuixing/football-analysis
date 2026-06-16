"""
⚽ 2026 世界杯数据自动更新脚本 — 从 Football-Data.org API 拉最新比分 & Elo

用法:
    FOOTBALL_API_KEY=xxx python3 backend/data/wc_data_updater.py
    python3 backend/data/wc_data_updater.py              # 从 .env 读 key
    python3 backend/data/wc_data_updater.py --dry-run     # 试运行不写文件

GitHub Actions 用:
    FOOTBALL_API_KEY=${{ secrets.FOOTBALL_API_KEY }} python3 backend/data/wc_data_updater.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

# ========== 路径 ==========
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "docs" / "data"
ENV_FILE = BASE_DIR / ".env"

COMP_ID = 2000          # FIFA World Cup
SEASON = 2026
WC_LEAGUE_ID = 2027

BASE = "https://api.football-data.org/v4"


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
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": key})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def walk_wc_elo(wc_finished, initial_ratings):
    """
    在现有 Elo 基础上，走一遍世界杯已完赛场次来更新 Elo
    返回 { team_id: elo } 字典
    """
    K = 32.0
    HFA = 0.0
    ratings = dict(initial_ratings)  # 从已有 Elo 起步

    wc_finished_sorted = sorted(wc_finished, key=lambda m: m.get('utc_date', ''))

    for m in wc_finished_sorted:
        h_id = m['home_team_id']
        a_id = m['away_team_id']
        if not h_id or not a_id:
            continue

        h_r = ratings.get(h_id, 1500.0)
        a_r = ratings.get(a_id, 1500.0)
        e_h = 1.0 / (1.0 + 10 ** ((a_r - h_r - HFA) / 400.0))
        sh, sa = m['score_home'], m['score_away']
        if sh > sa:   a_h, a_a = 1.0, 0.0
        elif sh < sa: a_h, a_a = 0.0, 1.0
        else:         a_h, a_a = 0.5, 0.5
        gd = abs(sh - sa)
        gf = 1.0 + (0.25 if gd == 2 else (0.5 if gd >= 3 else 0.0))
        ratings[h_id] = h_r + K * gf * (a_h - e_h)
        ratings[a_id] = a_r + K * gf * (a_a - (1.0 - e_h))

    return ratings


def main(dry_run=False):
    key = get_api_key()

    # 1. 拉 FD 数据
    print("🌍 拉 Football-Data.org API...")
    matches_raw = fetch(f"/competitions/{COMP_ID}/matches?season={SEASON}", key)['matches']
    print(f"  原始 {len(matches_raw)} 场")

    # 过滤出有真队的比赛
    valid_matches = [m for m in matches_raw
                     if m.get('homeTeam', {}).get('id') and m.get('awayTeam', {}).get('id')]
    skipped = len(matches_raw) - len(valid_matches)
    print(f"  有效 {len(valid_matches)} 场（跳过 {skipped} 场对阵未定）")

    # 2. 读取现有数据
    old_matches_path = DATA_DIR / f"matches_{WC_LEAGUE_ID}.json"
    old_matches = []
    if old_matches_path.exists():
        with open(old_matches_path) as f:
            old_matches = json.load(f)
    old_by_id = {m['id']: m for m in old_matches}

    old_teams_path = DATA_DIR / "teams.json"
    with open(old_teams_path) as f:
        old_teams = json.load(f)
    old_team_map = {t['id']: t for t in old_teams}
    old_team_ids = {t['id'] for t in old_teams}

    # 3. 转换新比赛格式
    wc_team_ids = set()
    new_matches = []
    for m in valid_matches:
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

        # FD status → 本地 status
        fd_status = m.get('status', '')
        if fd_status == 'FINISHED':
            status = 'FINISHED'
        else:
            status = 'SCHEDULED'

        h_id = m['homeTeam']['id']
        a_id = m['awayTeam']['id']
        wc_team_ids.add(h_id)
        wc_team_ids.add(a_id)

        rec = {
            "id": m['id'],
            "league_id": WC_LEAGUE_ID,
            "season": "2026",
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
        if m.get('group'):
            rec['group'] = m['group']
        if m.get('stage'):
            rec['stage'] = m['stage']
        new_matches.append(rec)
    new_matches.sort(key=lambda x: x['utc_date'])

    # 统计变化
    new_ids = {m['id'] for m in new_matches}
    old_ids = set(old_by_id.keys())
    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids

    updated_scores = []
    for nm in new_matches:
        om = old_by_id.get(nm['id'])
        if om and (om.get('score_home') != nm['score_home'] or om.get('score_away') != nm['score_away']):
            old_sc = f"{om.get('score_home','?')}-{om.get('score_away','?')}"
            new_sc = f"{nm.get('score_home','?')}-{nm.get('score_away','?')}"
            if old_sc != 'None-None' and old_sc != '?-?':
                updated_scores.append((nm['id'], nm['home_team_name'], nm['away_team_name'], old_sc, new_sc))
            elif new_sc != 'None-None':
                updated_scores.append((nm['id'], nm['home_team_name'], nm['away_team_name'], '未赛', new_sc))

    finished_count = sum(1 for m in new_matches if m['status'] == 'FINISHED')
    print(f"\n📊 数据对比:")
    print(f"  旧 matches_{WC_LEAGUE_ID}.json: {len(old_matches)} 场 ({sum(1 for m in old_matches if m['status']=='FINISHED')} 已完)")
    print(f"  新 matches_{WC_LEAGUE_ID}.json: {len(new_matches)} 场 ({finished_count} 已完)")
    if added_ids:
        print(f"  新增: {len(added_ids)} 场")
    if removed_ids:
        print(f"  移除: {len(removed_ids)} 场")
    if updated_scores:
        print(f"  比分更新: {len(updated_scores)} 场")
        for _, hn, an, old_sc, new_sc in updated_scores:
            print(f"    {hn} vs {an}: {old_sc} → {new_sc}")

    # 4. 处理球队 — 有新队则追加
    new_teams = []
    for m in valid_matches:
        for side in ('homeTeam', 'awayTeam'):
            t = m[side]
            if t['id'] not in old_team_ids:
                new_teams.append({
                    "id": t['id'],
                    "n": t['name'],
                    "elo": 1500.0,
                })
                old_team_ids.add(t['id'])

    if new_teams:
        print(f"\n🏃 新球队 ({len(new_teams)}): {[t['n'] for t in new_teams]}")

    # 5. 更新 Elo（在现有 Elo 基础上走 WC 已完赛）
    print("\n📈 更新 Elo（在现有 teams.json 基础上走 WC 比赛）...")

    all_teams_list = old_teams + new_teams

    # 初始化 ratings：用 teams.json 已有 Elo
    initial_ratings = {}
    for t in all_teams_list:
        if t['id'] in wc_team_ids:
            initial_ratings[t['id']] = t.get('elo', 1500.0)

    # 只取 WC 已完赛
    wc_finished = [m for m in new_matches
                   if m['status'] == 'FINISHED'
                   and m.get('score_home') is not None
                   and m.get('away_team_id')]

    # 记录更新前的 Elo（用于对比）
    wc_team_elo_before = dict(initial_ratings)

    ratings = walk_wc_elo(wc_finished, initial_ratings)

    # 回写 teams.json
    elo_updates = 0
    for t in all_teams_list:
        if t['id'] in wc_team_ids and t['id'] in ratings:
            new_elo = round(ratings[t['id']], 1)
            if t.get('elo', 1500.0) != new_elo:
                t['elo'] = new_elo
                elo_updates += 1

    # 打印 Elo 变化
    changed_elos = []
    for t in all_teams_list:
        if t['id'] in wc_team_ids:
            old_elo = wc_team_elo_before.get(t['id'], 1500.0)
            new_elo = t.get('elo', 1500.0)
            if abs(old_elo - new_elo) > 0.5:
                changed_elos.append((t['n'], old_elo, new_elo, new_elo - old_elo))
    changed_elos.sort(key=lambda x: -abs(x[3]))

    if changed_elos:
        print(f"  Elo 变化 ({len(changed_elos)} 队):")
        for name, old_e, new_e, diff in changed_elos[:10]:
            arrow = "↑" if diff > 0 else "↓"
            print(f"    {name:30s}  {old_e:.0f} → {new_e:.0f}  {arrow}{abs(diff):.1f}")
        if len(changed_elos) > 10:
            print(f"    ... 及 {len(changed_elos)-10} 队")
    else:
        print("  无 Elo 变化")

    final_finished = sum(1 for m in new_matches if m['status'] == 'FINISHED')
    print(f"\n✅ 总览: matches_{WC_LEAGUE_ID}.json = {len(new_matches)} 场 ({final_finished} 已完)")

    if dry_run:
        print("\n🔍 DRY RUN — 不写任何文件")
        return

    # 6. 写文件
    with open(old_matches_path, 'w') as f:
        json.dump(new_matches, f, ensure_ascii=False, indent=1)
    print(f"  ✏️  docs/data/matches_{WC_LEAGUE_ID}.json")

    with open(old_teams_path, 'w') as f:
        json.dump(all_teams_list, f, ensure_ascii=False, indent=1)
    print(f"  ✏️  docs/data/teams.json  ({len(all_teams_list)} 队)")

    # 7. 自动 git commit 提示
    print("\n📌 提交建议:")
    print(f"  git add docs/data/matches_{WC_LEAGUE_ID}.json docs/data/teams.json")
    print(f'  git commit -m "auto: 更新世界杯数据 ({final_finished} 场已完)"')
    print("  git push")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印不写")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
