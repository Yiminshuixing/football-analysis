"""
🔮 足彩预测全流程演示
========================
演示从原始数据到最终预测的完整流水线。

预测: Arsenal FC (主) vs Manchester City FC (客)
"""
import math
import numpy as np
from scipy.stats import poisson
from datetime import datetime, timedelta
from collections import defaultdict

from backend.database import get_db_sync, Match, Team, League
from backend.models.poisson import PoissonPredictor
from backend.models.elo import EloRating

db = get_db_sync()
home_name = "Arsenal FC"
away_name = "Manchester City FC"
league_id = 2021  # 英超

# =====================================================================
# 第一步：查数据 — 球队信息和当前 Elo
# =====================================================================
print("=" * 60)
print("📡 第一步：加载球队数据")
print("=" * 60)

home_team = db.query(Team).filter(Team.name == home_name).first()
away_team = db.query(Team).filter(Team.name == away_name).first()

print(f"  主队: {home_team.name}")
print(f"    数据库 ID: {home_team.id}")
print(f"    当前 Elo: {home_team.elo_rating:.1f}")
print(f"  客队: {away_team.name}")
print(f"    数据库 ID: {away_team.id}")
print(f"    当前 Elo: {away_team.elo_rating:.1f}")

# 联赛基准
league_avg = db.query(Match).filter(
    Match.league_id == league_id,
    Match.status == "FINISHED",
    Match.score_home.isnot(None),
    Match.score_away.isnot(None),
    Match.utc_date >= datetime.utcnow() - timedelta(days=180),
).all()
avg_goals = sum((m.score_home or 0) + (m.score_away or 0) for m in league_avg) / len(league_avg) if league_avg else 2.5
print(f"  英超近半年场均总进球: {avg_goals:.2f}")

# =====================================================================
# 第二步：近期状态 — 加权场均进球/失球
# =====================================================================
print("\n" + "=" * 60)
print("📊 第二步：近期加权状态（指数衰减，半衰期=5场）")
print("=" * 60)

def get_weighted_stats(team_id, league_id, venue=None, n=5):
    """计算加权场均进球和失球（分主客场）"""
    query = db.query(Match).filter(
        Match.league_id == league_id,
        Match.status == "FINISHED",
        Match.score_home.isnot(None),
        Match.score_away.isnot(None),
        Match.utc_date < datetime.utcnow(),
    )
    if venue == "home":
        query = query.filter(Match.home_team_id == team_id)
    elif venue == "away":
        query = query.filter(Match.away_team_id == team_id)
    else:
        query = query.filter(
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
        )

    matches = query.order_by(Match.utc_date.desc()).limit(n).all()

    venue_label = {"home": "主场", "away": "客场", None: "全部"}
    half_life = 5.0
    decay = math.log(2) / half_life

    team_name = db.query(Team).filter(Team.id == team_id).first().name
    print(f"\n  {team_name} 近{n}场 {venue_label[venue]}:")
    total_w_scored = 0.0
    total_w_conceded = 0.0
    total_w = 0.0

    for i, m in enumerate(matches):
        weight = math.exp(-decay * i)
        if m.home_team_id == team_id:
            scored, conceded = m.score_home, m.score_away
        else:
            scored, conceded = m.score_away, m.score_home
        total_w_scored += weight * scored
        total_w_conceded += weight * conceded
        total_w += weight
        print(f"    #{n-i:2d}: {'主' if m.home_team_id == team_id else '客'} {m.home_team_name} {m.score_home}-{m.score_away} {m.away_team_name}  (权重={weight:.3f})")

    avg_scored = total_w_scored / total_w if total_w > 0 else 1.2
    avg_conceded = total_w_conceded / total_w if total_w > 0 else 1.2
    print(f"    加权场均进球: {avg_scored:.3f}  |  加权场均失球: {avg_conceded:.3f}")
    return avg_scored, avg_conceded

# 主队只看主场，客队只看客场
home_scored, home_conceded = get_weighted_stats(home_team.id, league_id, venue="home")
away_scored, away_conceded = get_weighted_stats(away_team.id, league_id, venue="away")

# =====================================================================
# 第三步：计算攻击/防守系数
# =====================================================================
print("\n" + "=" * 60)
print("🧮 第三步：攻击力与防守力系数")
print("=" * 60)

# 攻击力 = 球队场均进球 / 联赛场均进球
# 防守力 = 球队场均失球 / 联赛场均进球
home_attack = home_scored / avg_goals
home_defense = home_conceded / avg_goals
away_attack = away_scored / avg_goals
away_defense = away_conceded / avg_goals

print(f"  联赛基准 (λ): {avg_goals:.3f} 球/场")
print(f"")
print(f"  {home_name}:")
print(f"    攻击力 = {home_scored:.3f} / {avg_goals:.3f} = {home_attack:.3f}")
print(f"    防守力 = {home_conceded:.3f} / {avg_goals:.3f} = {home_defense:.3f}")
print(f"")
print(f"  {away_name}:")
print(f"    攻击力 = {away_scored:.3f} / {avg_goals:.3f} = {away_attack:.3f}")
print(f"    防守力 = {away_conceded:.3f} / {avg_goals:.3f} = {away_defense:.3f}")

# =====================================================================
# 第四步：计算预期进球 (xG)
# =====================================================================
print("\n" + "=" * 60)
print("🎯 第四步：预期进球 xG 计算")
print("=" * 60)

# 主队 xG = λ × 主队攻击力 × 客队防守力
# 场地效应已包含在 venue-specific 统计数据中
home_xg = avg_goals * home_attack * away_defense
# 客队 xG = λ × 客队攻击力 × 主队防守力
away_xg = avg_goals * away_attack * home_defense

# 防止极端值
home_xg = max(0.3, min(home_xg, 5.0))
away_xg = max(0.3, min(away_xg, 5.0))

print(f"  {home_name} xG = {avg_goals:.3f} × {home_attack:.3f}(主场攻) × {away_defense:.3f}(客场守)")
print(f"         = {home_xg:.3f}")
print(f"")
print(f"  {away_name} xG = {avg_goals:.3f} × {away_attack:.3f}(客场攻) × {home_defense:.3f}(主场守)")
print(f"         = {away_xg:.3f}")

# =====================================================================
# 第五步：Poisson 分布展开
# =====================================================================
print("\n" + "=" * 60)
print("📈 第五步：Poisson 分布 → 各比分概率")
print("=" * 60)

max_goals = 10
raw_probs = {}

print(f"  λ_home = {home_xg:.3f},  λ_away = {away_xg:.3f}")
print()

for h in range(0, 6):
    for a in range(0, 6):
        prob = poisson.pmf(h, home_xg) * poisson.pmf(a, away_xg)
        if prob > 0.005:
            raw_probs[(h, a)] = prob

print("  Top 比分概率 (原始 Poisson):")
sorted_raw = sorted(raw_probs.items(), key=lambda x: x[1], reverse=True)[:8]
for (h, a), p in sorted_raw:
    bar = "█" * int(p * 200)
    print(f"    {h}:{a}  {p:.2%}  {bar}")

# Dixon-Coles 修正
print(f"\n  --- Dixon-Coles 修正 (ρ=0.15) ---")
rho = 0.15
dc_probs = {}
for (h, a), prob in raw_probs.items():
    tau = 1.0
    if h <= 2 and a <= 2:
        if h == 0 and a == 0:
            tau = 1.0 - home_xg * away_xg * rho
        elif h == 0 and a == 1:
            tau = 1.0 + home_xg * rho
        elif h == 1 and a == 0:
            tau = 1.0 + away_xg * rho
        elif h == 1 and a == 1:
            tau = 1.0 - rho
        elif h == 0 and a == 2:
            tau = 1.0 - 0.5 * home_xg * rho
        elif h == 2 and a == 0:
            tau = 1.0 - 0.5 * away_xg * rho
        elif h == 2 and a == 1:
            tau = 1.0 + 0.5 * rho
        elif h == 1 and a == 2:
            tau = 1.0 + 0.5 * rho
    tau = max(tau, 0.01)
    dc_probs[(h, a)] = prob * tau

# 归一化
total_prob = sum(dc_probs.values())
for k in dc_probs:
    dc_probs[k] /= total_prob

# 比分修正对比 (用 sorted_raw 的比分键查)
print(f"  {'比分':>6} | {'Poisson':>8} | {'DC修正':>8} | {'变化':>6}")
print(f"  {'─'*6}-├─{'─'*8}-├─{'─'*8}-├─{'─'*6}")
for h, a in [k for (k, _) in sorted_raw]:
    raw_p = raw_probs.get((h, a), 0)
    dc_p = dc_probs.get((h, a), 0)
    if raw_p > 0:
        change = dc_p - raw_p
        print(f"  {h}:{a:>3} | {raw_p:>7.2%} | {dc_p:>7.2%} | {'+' if change>0 else ''}{change:.2%}")

# 完整比分概率
full_dc_probs = {}
for h in range(max_goals + 1):
    for a in range(max_goals + 1):
        prob = poisson.pmf(h, home_xg) * poisson.pmf(a, away_xg)
        if prob > 0.0001:
            tau = 1.0
            if h <= 2 and a <= 2:
                if h == 0 and a == 0:
                    tau = 1.0 - home_xg * away_xg * rho
                elif h == 0 and a == 1:
                    tau = 1.0 + home_xg * rho
                elif h == 1 and a == 0:
                    tau = 1.0 + away_xg * rho
                elif h == 1 and a == 1:
                    tau = 1.0 - rho
                elif h == 0 and a == 2:
                    tau = 1.0 - 0.5 * home_xg * rho
                elif h == 2 and a == 0:
                    tau = 1.0 - 0.5 * away_xg * rho
                elif h == 2 and a == 1:
                    tau = 1.0 + 0.5 * rho
                elif h == 1 and a == 2:
                    tau = 1.0 + 0.5 * rho
            tau = max(tau, 0.01)
            full_dc_probs[(h, a)] = prob * tau

total_p = sum(full_dc_probs.values())
for k in full_dc_probs:
    full_dc_probs[k] /= total_p

# == 从 Poisson 模型得出胜平负 ==
poisson_home = sum(p for (h, a), p in full_dc_probs.items() if h > a)
poisson_draw = sum(p for (h, a), p in full_dc_probs.items() if h == a)
poisson_away = sum(p for (h, a), p in full_dc_probs.items() if h < a)
best_score = max(full_dc_probs, key=full_dc_probs.get)

print(f"\n  Poisson 模型结果:")
print(f"    {home_name} 胜: {poisson_home:.1%}")
print(f"    平局:        {poisson_draw:.1%}")
print(f"    {away_name} 胜: {poisson_away:.1%}")
print(f"    最可能比分: {best_score[0]}:{best_score[1]} ({full_dc_probs[best_score]:.1%})")

# =====================================================================
# 第六步：Elo 模型
# =====================================================================
print("\n" + "=" * 60)
print("⭐ 第六步：Elo 评分模型")
print("=" * 60)

home_elo = home_team.elo_rating
away_elo = away_team.elo_rating

# 含主场优势的 Elo 分差
HFA = 100  # 主场优势
effective_home = home_elo + HFA

# 预期胜率
elo_expected_home = 1.0 / (1.0 + 10 ** ((away_elo - effective_home) / 400))
elo_expected_away = 1.0 / (1.0 + 10 ** ((effective_home - away_elo) / 400))
elo_expected_draw = 1.0 - elo_expected_home - elo_expected_away

# Elo 经验修正：平局概率 = 原始平局 × 调整
draw_base = 0.25  # 足球基准平局率约25%
elo_draw = draw_base * (1 - abs(elo_expected_home - elo_expected_away)) / draw_base
elo_draw = min(max(elo_draw, 0.15), 0.35)  # 限制范围

# 重新归一化
remaining = 1.0 - elo_draw
scale_f = remaining / (elo_expected_home + elo_expected_away)
elo_home = elo_expected_home * scale_f
elo_away = elo_expected_away * scale_f

print(f"  {home_name} Elo: {home_elo:.1f}")
print(f"  {away_name} Elo: {away_elo:.1f}")
print(f"  主场优势加分: +{HFA}")
print(f"  有效 Elo: {home_name} {effective_home:.1f} vs {away_name} {away_elo:.1f}")
print(f"  分差: {effective_home - away_elo:.1f}")
print(f"")
print(f"  Elo 预期:")
print(f"    {home_name} 胜: {elo_home:.1%}")
print(f"    平局:        {elo_draw:.1%}")
print(f"    {away_name} 胜: {elo_away:.1%}")

# =====================================================================
# 第七步：融合输出
# =====================================================================
print("\n" + "=" * 60)
print("🔮 第七步：模型融合 — 最终预测")
print("=" * 60)

pw = 0.55  # Poisson 权重
ew = 0.45  # Elo 权重

final_home = poisson_home * pw + elo_home * ew
final_draw = poisson_draw * pw + elo_draw * ew
final_away = poisson_away * pw + elo_away * ew

# 归一化
total = final_home + final_draw + final_away
final_home /= total
final_draw /= total
final_away /= total

# 置信度
max_prob = max(final_home, final_draw, final_away)
poisson_outcome = "HOME" if poisson_home > poisson_draw and poisson_home > poisson_away else \
                  "AWAY" if poisson_away > poisson_home and poisson_away > poisson_draw else "DRAW"
elo_outcome = "HOME" if elo_home > elo_draw and elo_home > elo_away else \
              "AWAY" if elo_away > elo_home and elo_away > elo_draw else "DRAW"
agreement = 1.0 if poisson_outcome == elo_outcome else 0.5
confidence = min(95, round((max_prob * 0.7 + agreement * 0.3) * 100, 1))

print(f"  {'模型':>12} | {'主胜':>8} | {'平局':>8} | {'客胜':>8} | {'预测':>6}")
print(f"  {'─'*12}-├─{'─'*8}-├─{'─'*8}-├─{'─'*8}-├─{'─'*6}")
print(f"  {'Poisson':>12} | {poisson_home:>7.1%} | {poisson_draw:>7.1%} | {poisson_away:>7.1%} | {poisson_outcome:>6}")
print(f"  {'Elo':>12} | {elo_home:>7.1%} | {elo_draw:>7.1%} | {elo_away:>7.1%} | {elo_outcome:>6}")
print(f"  {'─'*12}-├─{'─'*8}-├─{'─'*8}-├─{'─'*8}-├─{'─'*6}")
print(f"  {'加权融合':>12} | {final_home:>7.1%} | {final_draw:>7.1%} | {final_away:>7.1%} | {'HOME' if final_home > final_draw and final_home > final_away else 'AWAY' if final_away > final_home and final_away > final_draw else 'DRAW':>6}")
print()

# 综合结果
outcome = "HOME" if final_home > final_draw and final_home > final_away else \
          "AWAY" if final_away > final_home and final_away > final_draw else "DRAW"
outcome_text = {"HOME": f"{home_name} 胜", "DRAW": "平局", "AWAY": f"{away_name} 胜"}
emoji = {"HOME": "🏠", "DRAW": "🤝", "AWAY": "✈️"}

# 最终比分概率前五
top_scores = sorted(full_dc_probs.items(), key=lambda x: x[1], reverse=True)[:5]

print(f"  {emoji[outcome]} 最终推荐: {outcome_text[outcome]}")
print(f"    置信度: {confidence:.1f}%")
print(f"    最可能比分: {best_score[0]}:{best_score[1]}")
print(f"    模型一致性: {'✅ 一致' if agreement == 1.0 else '⚠️ 分歧'}")
print(f"")
print(f"  Top 5 最可能比分:")
for (h, a), p in top_scores:
    bar = "█" * int(p * 150)
    print(f"    {h}:{a}  {p:.1%}  {bar}")

print(f"\n  Poisson 权重: {pw:.0%} | Elo 权重: {ew:.0%}")
print(f"  权重比 = Poisson:E lo = {pw/ew:.2f}:1")

db.close()
