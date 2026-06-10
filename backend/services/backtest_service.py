"""
模型回测服务
按时间顺序逐场比赛模拟预测，对比实际结果，计算准确率指标。
"""
import json
import math
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict
from sqlalchemy.orm import Session

from backend.database import get_db_sync, Match, Team
from backend.models.poisson import PoissonPredictor
from backend.models.elo import EloRating
from backend.models.ml_predictor import MLPredictor


class BacktestService:
    """回测服务"""

    def __init__(self, db: Session = None):
        self.db = db or get_db_sync()

    def run_backtest(self, league_id: int, test_season: str = "2025-26",
                     train_seasons: List[str] = None) -> dict:
        """
        对指定联赛运行回测

        流程:
        1. 用训练赛季数据初始化 Elo 评分
        2. 对测试赛季的每场比赛（按时间顺序）:
           a. 用当前 Elo + 近期比赛数据预测
           b. 记录预测结果 vs 实际结果
           c. 用实际结果更新 Elo
        3. 统计准确率
        """
        if train_seasons is None:
            train_seasons = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]

        # --- 阶段 1: 训练 Elo ---
        train_matches = self.db.query(Match).filter(
            Match.league_id == league_id,
            Match.season.in_(train_seasons),
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        ).order_by(Match.utc_date.asc()).all()

        # 初始化 Elo
        elo = EloRating(self.db)
        team_ratings = {}  # team_id -> rating

        # 收集出现的球队
        team_ids = set()
        for m in train_matches:
            team_ids.add(m.home_team_id)
            team_ids.add(m.away_team_id)

        for tid in team_ids:
            team_ratings[tid] = elo.initial_rating

        # 逐场比赛训练 Elo
        for m in train_matches:
            home_r = team_ratings.get(m.home_team_id, elo.initial_rating)
            away_r = team_ratings.get(m.away_team_id, elo.initial_rating)
            new_home, new_away = elo.update_ratings(
                home_r, away_r, m.score_home, m.score_away
            )
            team_ratings[m.home_team_id] = new_home
            team_ratings[m.away_team_id] = new_away

        # --- 阶段 2: 回测 ---
        test_matches = self.db.query(Match).filter(
            Match.league_id == league_id,
            Match.season == test_season,
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        ).order_by(Match.utc_date.asc()).all()

        if not test_matches:
            return {"error": f"联赛 {league_id} 赛季 {test_season} 没有已完成的比赛"}

        # 获取所有比赛（用于 Poisson 计算近期状态）
        all_matches_for_league = self.db.query(Match).filter(
            Match.league_id == league_id,
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        ).order_by(Match.utc_date.asc()).all()

        # 用于跟踪近期比赛（比测试比赛更早的）
        poisson = PoissonPredictor(self.db)

        results = []
        correct_count = 0
        total_count = 0

        # 按置信度分桶
        confidence_buckets = {
            "high": {"correct": 0, "total": 0, "label": "高置信度 (≥70%)"},
            "medium": {"correct": 0, "total": 0, "label": "中置信度 (50-70%)"},
            "low": {"correct": 0, "total": 0, "label": "低置信度 (<50%)"},
        }

        # 比分预测统计
        exact_score_correct = 0

        # 价值投注统计（预测概率 vs 赔率）
        value_bets = {"total": 0, "won": 0, "roi": 0.0}
        simulated_bankroll = 1000.0

        for i, match in enumerate(test_matches):
            try:
                home_r = team_ratings.get(match.home_team_id, elo.initial_rating)
                away_r = team_ratings.get(match.away_team_id, elo.initial_rating)

                # --- Elo 预测 ---
                elo_probs = elo.predict_match_probs(home_r, away_r)

                # --- Poisson 预测（使用赛季数据提高联赛均值精度）---
                poisson_result = poisson.predict_match(
                    match.home_team_id, match.away_team_id, match.league_id,
                    season=test_season,
                )

                # --- 融合 ---
                pw, ew = 0.55, 0.45
                home_w = (poisson_result["home_win_prob"] * pw +
                         elo_probs["home_win_prob"] * ew)
                draw_p = (poisson_result["draw_prob"] * pw +
                         elo_probs["draw_prob"] * ew)
                away_w = (poisson_result["away_win_prob"] * pw +
                         elo_probs["away_win_prob"] * ew)

                total_p = home_w + draw_p + away_w
                home_w /= total_p
                draw_p /= total_p
                away_w /= total_p

                # 预测结果
                probs = [("HOME", home_w), ("DRAW", draw_p), ("AWAY", away_w)]
                predicted = max(probs, key=lambda x: x[1])
                predicted_outcome = predicted[0]
                max_prob = predicted[1]

                # 实际结果
                if match.winner == "HOME_TEAM":
                    actual = "HOME"
                elif match.winner == "AWAY_TEAM":
                    actual = "AWAY"
                else:
                    actual = "DRAW"

                # 模型一致性（计算置信度用）
                poisson_outcome = max(
                    ("HOME", poisson_result["home_win_prob"]),
                    ("DRAW", poisson_result["draw_prob"]),
                    ("AWAY", poisson_result["away_win_prob"]),
                    key=lambda x: x[1]
                )[0]
                elo_outcome = max(
                    ("HOME", elo_probs["home_win_prob"]),
                    ("DRAW", elo_probs["draw_prob"]),
                    ("AWAY", elo_probs["away_win_prob"]),
                    key=lambda x: x[1]
                )[0]
                agreement = 1.0 if poisson_outcome == elo_outcome else 0.5
                confidence = min(95, round((max_prob * 0.7 + agreement * 0.3) * 100, 1))

                # 是否猜对
                is_correct = predicted_outcome == actual
                if is_correct:
                    correct_count += 1
                total_count += 1

                # 比分预测
                pred_h = poisson_result["predicted_home_score"]
                pred_a = poisson_result["predicted_away_score"]
                if pred_h == match.score_home and pred_a == match.score_away:
                    exact_score_correct += 1

                # 置信度分桶
                if confidence >= 70:
                    bucket = "high"
                elif confidence >= 50:
                    bucket = "medium"
                else:
                    bucket = "low"
                confidence_buckets[bucket]["total"] += 1
                if is_correct:
                    confidence_buckets[bucket]["correct"] += 1

                # --- 价值投注检测 ---
                # 从 extra_data 读取赔率
                if match.extra_data:
                    try:
                        extra = json.loads(match.extra_data)
                        # 找最佳可用赔率 (MaxH/MaxD/MaxA 或 B365H/B365D/B365A)
                        if "MaxH" in extra:
                            odds_h = float(extra["MaxH"]) if extra["MaxH"] else 0
                            odds_d = float(extra["MaxD"]) if extra["MaxD"] else 0
                            odds_a = float(extra["MaxA"]) if extra["MaxA"] else 0
                        elif "B365H" in extra:
                            odds_h = float(extra["B365H"]) if extra["B365H"] else 0
                            odds_d = float(extra["B365D"]) if extra["B365D"] else 0
                            odds_a = float(extra["B365A"]) if extra["B365A"] else 0
                        else:
                            odds_h = odds_d = odds_a = 0

                        if odds_h > 0 and odds_d > 0 and odds_a > 0:
                            # 找价值投注：模型概率 > 赔率隐含概率
                            implied_h = 1.0 / odds_h
                            implied_d = 1.0 / odds_d
                            implied_a = 1.0 / odds_a
                            imp_total = implied_h + implied_d + implied_a

                            # 归一化隐含概率
                            implied_h_norm = implied_h / imp_total
                            implied_d_norm = implied_d / imp_total
                            implied_a_norm = implied_a / imp_total

                            # 检查哪个有正期望值
                            outcomes = [
                                ("HOME", home_w, odds_h, implied_h_norm),
                                ("DRAW", draw_p, odds_d, implied_d_norm),
                                ("AWAY", away_w, odds_a, implied_a_norm),
                            ]

                            for outcome, model_prob, odd, implied_prob in outcomes:
                                if model_prob > implied_prob * 1.1 and odd > 2.0:
                                    # 模型认为比市场更高的概率
                                    value_bets["total"] += 1
                                    stake = 10.0  # 每注 10 元
                                    if outcome == actual:
                                        value_bets["won"] += 1
                                        profit = stake * (odd - 1)
                                        simulated_bankroll += profit
                                        value_bets["roi"] += profit
                                    else:
                                        simulated_bankroll -= stake
                                        value_bets["roi"] -= stake
                                    break
                    except:
                        pass

                # --- 更新 Elo ---
                new_home, new_away = elo.update_ratings(
                    home_r, away_r, match.score_home, match.score_away
                )
                team_ratings[match.home_team_id] = new_home
                team_ratings[match.away_team_id] = new_away

                results.append({
                    "match_id": match.id,
                    "home_team": match.home_team_name,
                    "away_team": match.away_team_name,
                    "date": match.utc_date.isoformat() if match.utc_date else None,
                    "actual_score": f"{match.score_home}:{match.score_away}",
                    "actual": actual,
                    "predicted": predicted_outcome,
                    "home_prob": round(home_w, 3),
                    "draw_prob": round(draw_p, 3),
                    "away_prob": round(away_w, 3),
                    "predicted_score": f"{pred_h}:{pred_a}",
                    "confidence": confidence,
                    "correct": is_correct,
                    "exact_score": (pred_h == match.score_home and pred_a == match.score_away),
                })

            except Exception as e:
                continue

        # --- 统计汇总 ---
        accuracy = correct_count / total_count * 100 if total_count > 0 else 0
        exact_accuracy = exact_score_correct / total_count * 100 if total_count > 0 else 0

        # 按联赛统计
        league = self.db.query(Match).filter(Match.league_id == league_id).first()

        return {
            "league_id": league_id,
            "test_season": test_season,
            "train_seasons": train_seasons,
            "total_matches": total_count,
            "correct_predictions": correct_count,
            "overall_accuracy": round(accuracy, 2),
            "exact_score_accuracy": round(exact_accuracy, 2),
            "confidence_buckets": confidence_buckets,
            "value_betting": {
                "total_bets": value_bets["total"],
                "won_bets": value_bets["won"],
                "roi": round(value_bets["roi"], 2),
                "final_bankroll": round(simulated_bankroll, 2),
                "win_rate": round(value_bets["won"] / value_bets["total"] * 100, 2) if value_bets["total"] > 0 else 0,
            },
            "recent_results": results[-50:],  # 最近 50 场
            "summary": {
                "league_name": league.home_team_name if league else f"League {league_id}",
            }
        }

    def run_backtest_ml(self, league_id: int, test_season: str = "2025-26",
                        train_seasons: List[str] = None) -> dict:
        """
        ML 融合回测 — 用 ML 模型 + Poisson + Elo 做预测

        与 run_backtest 结构相同，便于对比。
        """
        if train_seasons is None:
            train_seasons = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]

        # 训练 ML 模型
        ml = MLPredictor(self.db)
        # 用所有5大联赛数据训练（跨联赛学习）
        all_league_ids = [2021, 2002, 2014, 2019, 2015]
        success = ml.train(train_seasons, all_league_ids)
        if not success:
            return {"error": "ML 模型训练失败"}

        # 获取测试比赛
        test_matches = self.db.query(Match).filter(
            Match.league_id == league_id,
            Match.season == test_season,
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        ).order_by(Match.utc_date.asc()).all()

        if not test_matches:
            return {"error": f"联赛 {league_id} 赛季 {test_season} 没有已完成的比赛"}

        # 初始化 Elo（用训练数据训练）
        elo = EloRating(self.db)
        team_ratings = defaultdict(lambda: 1500.0)

        train_matches = self.db.query(Match).filter(
            Match.league_id == league_id,
            Match.season.in_(train_seasons),
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        ).order_by(Match.utc_date.asc()).all()

        for m in train_matches:
            home_r = team_ratings[m.home_team_id]
            away_r = team_ratings[m.away_team_id]
            new_h, new_a = elo.update_ratings(home_r, away_r, m.score_home, m.score_away)
            team_ratings[m.home_team_id] = new_h
            team_ratings[m.away_team_id] = new_a

        # 回测
        poisson = PoissonPredictor(self.db)
        correct_count = 0
        total_count = 0
        buckets = {"high": {"correct": 0, "total": 0, "label": "高置信度 (≥70%)"},
                   "medium": {"correct": 0, "total": 0, "label": "中置信度 (50-70%)"},
                   "low": {"correct": 0, "total": 0, "label": "低置信度 (<50%)"}}
        exact_correct = 0

        for match in test_matches:
            try:
                # Poisson预测
                poi = poisson.predict_match(match.home_team_id, match.away_team_id,
                                            match.league_id, season=test_season)
                # Elo预测
                home_r = team_ratings.get(match.home_team_id, 1500.0)
                away_r = team_ratings.get(match.away_team_id, 1500.0)
                elo_pred = elo.predict_match_probs(home_r, away_r)
                # ML预测
                ml_pred = ml.predict_proba(match, team_ratings)

                # 融合 (ML 权重 0.40, Poisson 0.35, Elo 0.25)
                if ml_pred:
                    hw = (poi["home_win_prob"] * 0.35 + elo_pred["home_win_prob"] * 0.25 +
                          ml_pred["home_win_prob"] * 0.40)
                    dp = (poi["draw_prob"] * 0.35 + elo_pred["draw_prob"] * 0.25 +
                          ml_pred["draw_prob"] * 0.40)
                    aw = (poi["away_win_prob"] * 0.35 + elo_pred["away_win_prob"] * 0.25 +
                          ml_pred["away_win_prob"] * 0.40)
                else:
                    hw = poi["home_win_prob"] * 0.55 + elo_pred["home_win_prob"] * 0.45
                    dp = poi["draw_prob"] * 0.55 + elo_pred["draw_prob"] * 0.45
                    aw = poi["away_win_prob"] * 0.55 + elo_pred["away_win_prob"] * 0.45

                total_p = hw + dp + aw
                hw, dp, aw = hw/total_p, dp/total_p, aw/total_p

                predicted = max([("HOME", hw), ("DRAW", dp), ("AWAY", aw)], key=lambda x: x[1])
                pred_outcome = predicted[0]
                max_prob = predicted[1]

                if match.winner == "HOME_TEAM":
                    actual = "HOME"
                elif match.winner == "AWAY_TEAM":
                    actual = "AWAY"
                else:
                    actual = "DRAW"

                # 置信度
                poisson_outcome = max(
                    ("HOME", poi["home_win_prob"]), ("DRAW", poi["draw_prob"]),
                    ("AWAY", poi["away_win_prob"]), key=lambda x: x[1])[0]
                elo_outcome = max(
                    ("HOME", elo_pred["home_win_prob"]), ("DRAW", elo_pred["draw_prob"]),
                    ("AWAY", elo_pred["away_win_prob"]), key=lambda x: x[1])[0]
                agreement = 1.0 if poisson_outcome == elo_outcome else 0.5
                confidence = min(95, round((max_prob * 0.7 + agreement * 0.3) * 100, 1))

                is_correct = pred_outcome == actual
                if is_correct:
                    correct_count += 1
                total_count += 1

                if poi["predicted_home_score"] == match.score_home and poi["predicted_away_score"] == match.score_away:
                    exact_correct += 1

                bucket = "high" if confidence >= 70 else "medium" if confidence >= 50 else "low"
                buckets[bucket]["total"] += 1
                if is_correct:
                    buckets[bucket]["correct"] += 1

                # 更新 Elo
                new_h, new_a = elo.update_ratings(home_r, away_r, match.score_home, match.score_away)
                team_ratings[match.home_team_id] = new_h
                team_ratings[match.away_team_id] = new_a

            except Exception:
                continue

        acc = correct_count / total_count * 100 if total_count > 0 else 0
        exact_acc = exact_correct / total_count * 100 if total_count > 0 else 0

        return {
            "model": "ML Fusion (Logistic Regression + Poisson + Elo)",
            "league_id": league_id,
            "test_season": test_season,
            "total_matches": total_count,
            "correct_predictions": correct_count,
            "overall_accuracy": round(acc, 2),
            "exact_score_accuracy": round(exact_acc, 2),
            "confidence_buckets": buckets,
        }

    def run_all(self, test_season: str = "2025-26") -> dict:
        """所有联赛回测"""
        leagues = [2021, 2002, 2014, 2019, 2015]
        league_names = {2021: "英超", 2002: "德甲", 2014: "西甲", 2019: "意甲", 2015: "法甲"}

        results = {}
        for lid in leagues:
            result = self.run_backtest(lid, test_season)
            if "error" not in result:
                results[league_names.get(lid, str(lid))] = result

        # 综合统计
        all_total = sum(r["total_matches"] for r in results.values())
        all_correct = sum(r["correct_predictions"] for r in results.values())
        all_exact = sum(r["exact_score_accuracy"] * r["total_matches"] / 100 for r in results.values())

        return {
            "test_season": test_season,
            "leagues": results,
            "summary": {
                "total_matches": all_total,
                "correct_predictions": all_correct,
                "overall_accuracy": round(all_correct / all_total * 100, 2) if all_total > 0 else 0,
                "exact_score_accuracy": round(all_exact / all_total * 100, 2) if all_total > 0 else 0,
            }
        }
