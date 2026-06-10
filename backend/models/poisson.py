"""Poisson 分布预测模型（改进版）

改进:
1. 加权近期状态 — 越近的比赛权重越高（指数衰减）
2. Dixon-Coles 调整 — 修正低比分平局概率
"""
import math
import numpy as np
from scipy.stats import poisson
from typing import Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import Match
from backend.config import settings


class PoissonPredictor:
    """Poisson 分布比分预测器（改进版）"""

    def __init__(self, db: Session, recent_matches: int = None, rho: float = None):
        self.db = db
        self.recent_matches = recent_matches or settings.poisson_recent_matches
        # Dixon-Coles 参数 (rho)，用于修正低比分平局概率
        # 正值表示低比分平局比标准 Poisson 更常见
        # 典型值 0.10~0.20
        self.rho = rho if rho is not None else 0.15

    def get_team_weighted_goals(self, team_id: int, league_id: int = None,
                                 venue: str = None) -> Tuple[float, float]:
        """获取球队加权场均进球和失球

        越近的比赛权重越高（指数衰减，半衰期=5场）

        Args:
            team_id: 球队 ID
            league_id: 联赛 ID（可选）
            venue: "home" = 只看主场, "away" = 只看客场, None = 全部

        返回: (weighted_avg_scored, weighted_avg_conceded)
        """
        query = self.db.query(Match).filter(
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

        if league_id:
            query = query.filter(Match.league_id == league_id)

        query = query.order_by(Match.utc_date.desc()).limit(self.recent_matches)
        matches = query.all()

        if not matches:
            return (1.2, 1.2)  # 默认值

        # 指数衰减权重（半衰期=5场）
        # 第0场（最新）权重=1.0, 第5场权重=0.5, 第10场权重=0.25
        half_life = 5.0
        decay = math.log(2) / half_life

        total_weight_scored = 0.0
        total_weight_conceded = 0.0
        total_weight = 0.0

        for i, m in enumerate(matches):
            weight = math.exp(-decay * i)
            if m.home_team_id == team_id:
                total_weight_scored += weight * m.score_home
                total_weight_conceded += weight * m.score_away
            else:
                total_weight_scored += weight * m.score_away
                total_weight_conceded += weight * m.score_home
            total_weight += weight

        if total_weight == 0:
            return (1.2, 1.2)

        return (total_weight_scored / total_weight, total_weight_conceded / total_weight)

    def get_league_average_goals(self, league_id: int, season: str = None) -> float:
        """获取联赛场均总进球数"""
        query = self.db.query(Match).filter(
            Match.league_id == league_id,
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        )

        if season:
            query = query.filter(Match.season == season)
        else:
            three_months_ago = datetime.utcnow() - timedelta(days=180)
            query = query.filter(Match.utc_date >= three_months_ago)

        matches = query.all()

        if not matches:
            return 2.5

        total_goals = sum((m.score_home or 0) + (m.score_away or 0) for m in matches)
        return total_goals / len(matches)

    def dixon_coles_adjust(self, score_probs: dict, home_xg: float, away_xg: float) -> dict:
        """Dixon-Coles 调整：修正标准 Poisson 对低比分平局的低估

        在足球中，0-0 和 1-1 比纯 Poisson 分布预测的更常见。
        这通过调整因子 τ(h,a) 实现修正。
        """
        rho = self.rho
        adjusted = {}

        for (h, a), prob in score_probs.items():
            tau = 1.0
            # Dixon-Coles 调整仅应用于低比分区域
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

                # 防止负概率
                tau = max(tau, 0.01)

            adjusted[(h, a)] = prob * tau

        return adjusted

    def predict_match(
        self, home_team_id: int, away_team_id: int, league_id: int = None,
        season: str = None, rho: float = None,
    ) -> dict:
        """预测单场比赛（改进版）

        Args:
            home_team_id: 主队 ID
            away_team_id: 客队 ID
            league_id: 联赛 ID
            season: 赛季（可选）
            rho: Dixon-Coles ρ 覆盖值，None 则从联赛配置读取

        Returns:
            预测结果 dict
        """
        # 联赛特定 ρ 值
        if rho is not None:
            self.rho = rho
        elif league_id and league_id in settings.league_params:
            self.rho = settings.league_params[league_id]["dixon_coles_rho"]

        # 获取主客队加权进攻/防守数据（分主客场）
        # 主队只看其主场表现，客队只看其客场表现
        home_attack, home_defense = self.get_team_weighted_goals(home_team_id, league_id, venue="home")
        away_attack, away_defense = self.get_team_weighted_goals(away_team_id, league_id, venue="away")

        # 获取联赛平均进球数（用指定赛季的数据）
        league_avg = self.get_league_average_goals(league_id, season) if league_id else 2.5

        # 计算双方攻击/防守系数
        home_attack_strength = home_attack / league_avg if league_avg > 0 else 1.0
        away_defense_strength = away_defense / league_avg if league_avg > 0 else 1.0
        away_attack_strength = away_attack / league_avg if league_avg > 0 else 1.0
        home_defense_strength = home_defense / league_avg if league_avg > 0 else 1.0

        # 预期进球 (xG)
        # 场地效应已包含在 venue-specific 统计数据中，不再额外乘系数
        home_xg = league_avg * home_attack_strength * away_defense_strength
        away_xg = league_avg * away_attack_strength * home_defense_strength

        # 防止极端值
        home_xg = max(0.3, min(home_xg, 5.0))
        away_xg = max(0.3, min(away_xg, 5.0))

        # 使用 Poisson 分布计算各比分概率
        max_goals = 10
        raw_probs = {}

        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                prob = poisson.pmf(h, home_xg) * poisson.pmf(a, away_xg)
                if prob > 0.0005:
                    raw_probs[(h, a)] = prob

        # Dixon-Coles 调整
        adjusted_probs = self.dixon_coles_adjust(raw_probs, home_xg, away_xg)

        # 归一化
        total_prob = sum(adjusted_probs.values())
        if total_prob > 0:
            for k in adjusted_probs:
                adjusted_probs[k] /= total_prob

        # 计算胜平负概率
        home_win_prob = sum(p for (h, a), p in adjusted_probs.items() if h > a)
        draw_prob = sum(p for (h, a), p in adjusted_probs.items() if h == a)
        away_win_prob = sum(p for (h, a), p in adjusted_probs.items() if h < a)

        # 最可能比分
        predicted_score = max(adjusted_probs, key=adjusted_probs.get) if adjusted_probs else (0, 0)

        # Top 10 最可能比分
        sorted_scores = sorted(adjusted_probs.items(), key=lambda x: x[1], reverse=True)[:10]
        score_prob_list = [
            {"home": h, "away": a, "probability": round(p, 4)}
            for (h, a), p in sorted_scores
        ]

        return {
            "home_win_prob": round(home_win_prob, 4),
            "draw_prob": round(draw_prob, 4),
            "away_win_prob": round(away_win_prob, 4),
            "predicted_home_score": predicted_score[0],
            "predicted_away_score": predicted_score[1],
            "home_xg": round(home_xg, 2),
            "away_xg": round(away_xg, 2),
            "score_probabilities": score_prob_list,
            "model": "poisson_v2",
        }
