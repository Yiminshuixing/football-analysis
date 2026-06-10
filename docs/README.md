# ⚽ 足彩泊松分析 — 静态版

纯前端静态版本，使用 Poisson 分布 + Elo 评分 + Dixon-Coles 校正进行足球比赛预测。

## 部署到 GitHub Pages

1. **推送代码到 GitHub**
   ```bash
   git add docs/
   git commit -m "添加静态前端版本"
   git push
   ```

2. **在 GitHub 仓库设置中开启 Pages**
   - Settings → Pages → Source: **Deploy from a branch**
   - Branch: `main` → `/docs` 文件夹
   - Save

3. 等待 1-2 分钟，访问 `https://<你的用户名>.github.io/football-analysis/` 即可

## 更新数据

数据文件位于 `docs/data/` 目录下：
- `leagues.json` — 联赛信息
- `teams.json` — 球队信息（含 Elo 评分）
- `team_names.json` — 中英文队名映射
- `matches_{leagueId}.json` — 各联赛比赛数据

### 更新步骤

```bash
# 1. 运行 Python 后端导入新数据
cd /home/ai/football-analysis
python3 -c "from backend.data.csv_importer import import_all_leagues; import_all_leagues()"

# 2. 重新导出为 JSON
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/football.db')
conn.row_factory = sqlite3.Row

# 导出联赛
leagues = []
for r in conn.execute('SELECT id, name, code FROM leagues ORDER BY id'):
    leagues.append(dict(r))
with open('docs/data/leagues.json', 'w') as f:
    json.dump(leagues, f, ensure_ascii=False)

# 导出球队（含 Elo）
teams = []
for r in conn.execute('SELECT id, name, elo_rating FROM teams ORDER BY id'):
    teams.append({'id': r['id'], 'n': r['name'], 'elo': round(r['elo_rating'], 1)})
with open('docs/data/teams.json', 'w') as f:
    json.dump(teams, f, ensure_ascii=False)

# 导出各联赛比赛
fields = ['id', 'league_id', 'season', 'utc_date', 'status',
          'home_team_id', 'away_team_id', 'home_team_name', 'away_team_name',
          'score_home', 'score_away', 'winner']
for lid in [2021, 2002, 2014, 2019, 2015, 2022, 2023, 2024, 2025, 2026]:
    matches = []
    for r in conn.execute(f\"SELECT {','.join(fields)} FROM matches WHERE league_id=? ORDER BY utc_date\", (lid,)):
        m = {k: r[k] for k in fields}
        if m['utc_date']: m['utc_date'] = str(m['utc_date'])
        matches.append(m)
    with open(f'docs/data/matches_{lid}.json', 'w') as f:
        json.dump(matches, f, ensure_ascii=False)
    print(f'League {lid}: {len(matches)} matches')
conn.close()
"

# 3. 提交并推送
git add docs/data/
git commit -m "更新比赛数据"
git push
```

## 技术栈

- **前端**: 纯 HTML + CSS + JavaScript（无框架）
- **预测模型**: Poisson 分布 | Elo 评分 | Dixon-Coles 校正 | 融合模型
- **数据源**: 本地 JSON 文件（从 SQLite 导出）
- **赔率**: The Odds API（免费层）
- **部署**: GitHub Pages（静态托管）

## 功能

- ✅ 10 个联赛/赛事支持（英超、德甲、西甲、意甲、法甲、中超、世预赛、2014-2022世界杯）
- ✅ 中文/英文球队搜索
- ✅ Poisson + Elo 融合模型预测
- ✅ Dixon-Coles ρ 校正
- ✅ 赔率分析 + 凯利公式
- ✅ 积分榜
- ✅ 球队详情（近期状态、Elo 评分）
- ✅ 移动端优化
- ✅ PWA 支持
