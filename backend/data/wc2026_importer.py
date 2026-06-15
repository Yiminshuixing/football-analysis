"""
🌍 2026 世界杯数据导入器 — 从 Football-Data.org API 拉数据
写入 docs/data/，给 GitHub Pages 静态版用

用法:
    python3 backend/data/wc2026_importer.py
    python3 backend/data/wc2026_importer.py --dry-run   # 只打印不写
"""
import json
import os
import sys
import argparse
import urllib.request
from pathlib import Path
from datetime import datetime

# ========== 配置 ==========
COMP_ID = 2000          # FIFA World Cup
SEASON = 2026
NEW_LEAGUE_ID = 2027    # 下一个空闲 ID
DATA_DIR = Path(__file__).resolve().parents[2] / "docs" / "data"
APP_JS = Path(__file__).resolve().parents[2] / "docs" / "js" / "app.js"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

BASE = "https://api.football-data.org/v4"


def get_api_key() -> str:
    """从 .env 读 FOOTBALL_API_KEY"""
    if not ENV_FILE.exists():
        sys.exit("❌ .env 不存在")
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("FOOTBALL_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("❌ .env 里没找到 FOOTBALL_API_KEY")


def fetch(path: str, key: str) -> dict:
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": key})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fix_league_meta():
    """修 app.js 里的 LEAGUE_META 名字错位 bug + 加 2027"""
    src = APP_JS.read_text()

    # Bug 1: 2024 写的是 2014世界杯 (实际数据是 2022 WC)
    # Bug 2: 2026 写的是 2022世界杯 (实际数据是 2014 WC)
    old_2024 = "2024: { code: 'WC2022', name: '2014世界杯', abbr: '2014世界杯' },"
    new_2024 = "2024: { code: 'WC2022', name: '2022世界杯', abbr: '2022世界杯' },"
    old_2026 = "2026: { code: 'WC2022', name: '2022世界杯', abbr: '2022世界杯' },"
    new_2026 = "2026: { code: 'WC2014', name: '2014世界杯', abbr: '2014世界杯' },"

    if old_2024 in src:
        src = src.replace(old_2024, new_2024)
        print("  ✅ 修 LEAGUE_META 2024 (2014→2022)")
    elif "2024: { code: 'WC2022', name: '2022世界杯'" in src:
        print("  ⏭️  LEAGUE_META 2024 已正确")
    else:
        print("  ⚠️  没找到 LEAGUE_META 2024 旧值（可能已修过）")

    if old_2026 in src:
        src = src.replace(old_2026, new_2026)
        print("  ✅ 修 LEAGUE_META 2026 (2022→2014)")
    elif "2026: { code: 'WC2014', name: '2014世界杯'" in src:
        print("  ⏭️  LEAGUE_META 2026 已正确")
    else:
        print("  ⚠️  没找到 LEAGUE_META 2026 旧值（可能已修过）")

    # 加 2027 (2026 WC)
    new_entry_meta = "    2027: { code: 'WC2026', name: '2026世界杯', abbr: '2026世界杯' },"
    new_entry_params = "    2027: { eloHomeAdv: 0, dixonColesRho: 0.15, poissonWeight: 0.55 },"

    if "2027: { code: 'WC2026'" not in src:
        # 在 LEAGUE_META 末尾的 } 前插入
        # 找到 "2026: { ... }," 后的位置
        src = src.replace(
            "    2026: { code: 'WC2014', name: '2014世界杯', abbr: '2014世界杯' },\n};\n\nconst LEAGUE_PARAMS",
            f"    2026: {{ code: 'WC2014', name: '2014世界杯', abbr: '2014世界杯' }},\n{new_entry_meta}\n}};\n\nconst LEAGUE_PARAMS"
        )
        src = src.replace(
            "    2026: { eloHomeAdv: 0, dixonColesRho: 0.15, poissonWeight: 0.50 },\n};",
            f"    2026: {{ eloHomeAdv: 0, dixonColesRho: 0.15, poissonWeight: 0.50 }},\n{new_entry_params}\n}};"
        )
        print("  ✅ 加 LEAGUE_META 2027 + LEAGUE_PARAMS 2027")
    else:
        print("  ⏭️  LEAGUE_META 2027 已存在")

    APP_JS.write_text(src)


def main(dry_run=False):
    key = get_api_key()

    print("🌍 拉 2026 世界杯数据...")
    teams_raw = fetch(f"/competitions/{COMP_ID}/teams?season={SEASON}", key)['teams']
    matches_raw = fetch(f"/competitions/{COMP_ID}/matches?season={SEASON}", key)['matches']

    # 过滤有真队的比赛（淘汰赛对阵还没生成）
    matches = [m for m in matches_raw
               if m.get('homeTeam', {}).get('id') and m.get('awayTeam', {}).get('id')]
    skipped = len(matches_raw) - len(matches)
    print(f"  球队 {len(teams_raw)} 支")
    print(f"  比赛 {len(matches)} 场（跳过 {skipped} 场 knockout 未确定对阵）")

    # 1. 加载现有 teams.json
    teams_path = DATA_DIR / "teams.json"
    with open(teams_path) as f:
        existing_teams = json.load(f)
    existing_ids = {t['id'] for t in existing_teams}

    # 2. 添加新队（用 FD id，跳过已有的）
    #    初 始 Elo 走 2023 世预赛 + 已踢 WC 算出，比 1500 平庸值准多了
    new_teams = []
    new_team_ids = set()
    for t in teams_raw:
        if t['id'] not in existing_ids:
            new_team_ids.add(t['id'])
            new_teams.append({
                "id": t['id'],
                "n": t['name'],
                "elo": 1500.0,  # 稍后会被世预赛走出的 Elo 覆盖
            })

    # 2.5 走 2023 世预赛 Elo，给 48 支队一个准的初始值
    #     注意：qualifiers 用的是老 ID（同名不同 ID），需要名字映射
    qual_path = DATA_DIR / "matches_2023.json"
    if qual_path.exists():
        with open(qual_path) as f:
            qual_matches = json.load(f)
        # 同队名在 teams.json 可能有多条 ID (老 qualifiers ID + 新 FD ID)
        name_to_ids = {}
        for t in existing_teams + new_teams:
            name_to_ids.setdefault(t['n'], []).append(t['id'])
        # 只在 2023 qualifiers 里出现过的 ID
        qual_team_ids = set()
        for m in qual_matches:
            qual_team_ids.add(m.get('home_team_id'))
            qual_team_ids.add(m.get('away_team_id'))
        # 按名字挑出老 qualifiers ID (在 qualifiers 里出现过)
        name_to_qual_id = {}
        for name, ids in name_to_ids.items():
            qids = [i for i in ids if i in qual_team_ids and i not in new_team_ids]
            if qids:
                name_to_qual_id[name] = qids[0]

        # 过滤 qualifiers 中只含 2026 WC 队的比赛（用老 ID 匹配）
        wc_qual_team_ids = set(name_to_qual_id.values())
        qual_for_wc = [m for m in qual_matches
                       if m.get('home_team_id') in wc_qual_team_ids
                       and m.get('away_team_id') in wc_qual_team_ids]
        qual_for_wc.sort(key=lambda m: m.get('utc_date', ''))
        print(f"  📈 用 2023 世预赛 ({len(qual_for_wc)} 场含 WC 队的) walk Elo...")

        # 复刻前端 JS 的 Elo walk 逻辑
        K = 32.0
        HFA = 0.0
        ratings = {}  # 老 ID -> Elo
        for m in qual_for_wc:
            if m.get('status') != 'FINISHED' or m.get('score_home') is None:
                continue
            h_id = m['home_team_id']
            a_id = m['away_team_id']
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

        # 把走出的 Elo（按老 ID）映射回新 ID
        # 名字 -> Elo（取该名字下任何老 ID 的最终 Elo）
        name_to_elo = {}
        for name, qid in name_to_qual_id.items():
            if qid in ratings:
                name_to_elo[name] = ratings[qid]
        updated = 0
        for nt in new_teams:
            if nt['n'] in name_to_elo:
                nt['elo'] = round(name_to_elo[nt['n']], 1)
                updated += 1
        # 打印 Top/Bottom 5 看看分布
        sorted_new = sorted(new_teams, key=lambda t: t['elo'], reverse=True)
        print(f"     → 更新 {updated}/{len(new_teams)} 队 Elo（来自世预赛）")
        print(f"     Top 5: {[(t['n'], t['elo']) for t in sorted_new[:5]]}")
        print(f"     Bot 5: {[(t['n'], t['elo']) for t in sorted_new[-5:]]}")
    else:
        print("  ⚠️  找不到 matches_2023.json，跳过 Elo 初始化")

    all_teams = existing_teams + new_teams
    print(f"  teams.json: {len(existing_teams)} → {len(all_teams)} (+{len(new_teams)} 新队)")

    # 3. 转换比赛格式
    matches_out = []
    for m in matches:
        # FD: "2026-06-11T19:00:00Z" → "2026-06-11 19:00:00.000000"
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
            if score_h > score_a:
                winner = "HOME_TEAM"
            elif score_h < score_a:
                winner = "AWAY_TEAM"
            else:
                winner = "DRAW"

        status = "FINISHED" if m.get('status') == 'FINISHED' else "SCHEDULED"

        rec = {
            "id": m['id'],
            "league_id": NEW_LEAGUE_ID,
            "season": "2026",
            "utc_date": utc,
            "status": status,
            "home_team_id": m['homeTeam']['id'],
            "away_team_id": m['awayTeam']['id'],
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
        matches_out.append(rec)

    finished = sum(1 for m in matches_out if m['status'] == 'FINISHED')
    print(f"  matches_{NEW_LEAGUE_ID}.json: {len(matches_out)} 场 ({finished} 已完 + {len(matches_out)-finished} 待踢)")

    # 4. 转换 team_names (新队 + 别名)
    tn_path = DATA_DIR / "team_names.json"
    with open(tn_path) as f:
        tn = json.load(f)
    cn_to_en = tn.get('cn_to_en', {})
    en_to_cn = tn.get('en_to_cn', {})

    new_cn_map = {
        "United States": "美国",
        "Czechia": "捷克",
        "Bosnia-Herzegovina": "波黑",
        "Congo DR": "刚果民主共和国",
        "Curaçao": "库拉索",
        "Cape Verde Islands": "佛得角",
    }
    added_cn = 0
    for en, cn in new_cn_map.items():
        if en not in en_to_cn:
            en_to_cn[en] = cn
            added_cn += 1
        if cn not in cn_to_en:
            cn_to_en[cn] = en

    # FD 用的别名跟现有映射合并
    aliases = {
        "Côte d'Ivoire": ("科特迪瓦", en_to_cn.get("Ivory Coast", "Ivory Coast")),
        "Korea Republic": ("韩国", en_to_cn.get("South Korea", "South Korea")),
    }
    for en, (cn, canonical_en) in aliases.items():
        if en not in en_to_cn:
            en_to_cn[en] = cn
            added_cn += 1

    tn['cn_to_en'] = cn_to_en
    tn['en_to_cn'] = en_to_cn

    # 5. 转换 leagues.json
    leagues_path = DATA_DIR / "leagues.json"
    with open(leagues_path) as f:
        leagues = json.load(f)
    new_league = {"id": NEW_LEAGUE_ID, "name": "2026世界杯", "code": "WC2026"}
    if not any(l['id'] == NEW_LEAGUE_ID for l in leagues):
        leagues.append(new_league)

    if dry_run:
        print("\n🔍 DRY RUN — 不写任何文件")
        print(f"\n  新增球队 ({len(new_teams)}):")
        for t in new_teams:
            print(f"    {t['id']:>4}  {t['n']}")
        print(f"\n  新增 CN 名 ({added_cn}):")
        for en, cn in new_cn_map.items():
            print(f"    {en} → {cn}")
        print(f"\n  头 3 场:")
        for m in matches_out[:3]:
            print(f"    {m['utc_date']}  {m['home_team_name']} vs {m['away_team_name']}  [{m['status']}]")
        return

    # 写文件
    with open(teams_path, 'w') as f:
        json.dump(all_teams, f, ensure_ascii=False, indent=1)
    print(f"  ✏️  {teams_path.relative_to(DATA_DIR.parent.parent)}")

    matches_path = DATA_DIR / f"matches_{NEW_LEAGUE_ID}.json"
    with open(matches_path, 'w') as f:
        json.dump(matches_out, f, ensure_ascii=False, indent=1)
    print(f"  ✏️  docs/data/{matches_path.name}")

    with open(leagues_path, 'w') as f:
        json.dump(leagues, f, ensure_ascii=False, indent=1)
    print(f"  ✏️  docs/data/leagues.json")

    with open(tn_path, 'w') as f:
        json.dump(tn, f, ensure_ascii=False, indent=1)
    print(f"  ✏️  docs/data/team_names.json")

    # 修 app.js
    print(f"\n🔧 修 docs/js/app.js:")
    fix_league_meta()

    print(f"\n✅ 全部完成。下一步:")
    print(f"  1. 本地起 server 测试 (python3 -m http.server -d docs 8765)")
    print(f"  2. 在浏览器打开 http://localhost:8765 选「2026世界杯」")
    print(f"  3. 输入 Brazil/France 等球队验证")
    print(f"  4. git add -A && git commit && git push (触发 GitHub Pages 部署)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印不写")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
