"""Elo 评分系统

用于评估球队相对实力，基于每场比赛结果动态更新评分。
"""
import math
from datetime import datetime
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from backend.database import Match, Team
from backend.config import settings


class EloRating:
    """Elo 评分计算器"""

    def __init__(self, db: Session, home_advantage: float = None):
        self.db = db
        self.k_factor = settings.elo_k_factor
        self.home_advantage = home_advantage if home_advantage is not None else settings.elo_home_advantage
        self.initial_rating = settings.elo_initial_rating

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """计算 A 队对 B 队的预期得分 (0-1)"""
        return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))

    def update_ratings(
        self, home_rating: float, away_rating: float,
        home_score: int, away_score: int,
    ) -> Tuple[float, float]:
        """根据比赛结果更新两队 Elo 评分

        Returns:
            (new_home_rating, new_away_rating)
        """
        # 主场优势
        home_effective = home_rating + self.home_advantage

        expected_home = self.expected_score(home_effective, away_rating)
        expected_away = 1.0 - expected_home

        # 实际结果（胜=1，平=0.5，负=0）
        if home_score > away_score:
            actual_home, actual_away = 1.0, 0.0
        elif home_score < away_score:
            actual_home, actual_away = 0.0, 1.0
        else:
            actual_home, actual_away = 0.5, 0.5

        # 根据比分差调整 K 因子（大比分胜利获得更多分数）
        goal_diff = abs(home_score - away_score)
        goal_factor = 1.0
        if goal_diff >= 3:
            goal_factor = 1.5
        elif goal_diff >= 2:
            goal_factor = 1.25

        new_home = home_rating + self.k_factor * goal_factor * (actual_home - expected_home)
        new_away = away_rating + self.k_factor * goal_factor * (actual_away - expected_away)

        return (new_home, new_away)

    def predict_match_probs(self, home_rating: float, away_rating: float) -> dict:
        """基于 Elo 评分预测比赛概率

        Returns:
            {"home_win_prob": float, "draw_prob": float, "away_win_prob": float}
        """
        home_effective = home_rating + self.home_advantage
        expected_home = self.expected_score(home_effective, away_rating)
        expected_away = 1.0 - expected_home

        # Elo 本身给出的是胜率预期，将平局概率按比例分配
        # 平局概率在实力接近时较高
        rating_diff = abs(home_effective - away_rating)
        draw_base = 0.34 * math.exp(-rating_diff / 400.0)

        # 从预期胜率中分配平局
        home_win = expected_home * (1.0 - draw_base) + draw_base * 0.5
        away_win = expected_away * (1.0 - draw_base) + draw_base * 0.5
        draw_prob = draw_base

        total = home_win + draw_prob + away_win
        return {
            "home_win_prob": round(home_win / total, 4),
            "draw_prob": round(draw_prob / total, 4),
            "away_win_prob": round(away_win / total, 4),
        }

    def recalculate_all_ratings(self, league_id: Optional[int] = None):
        """重新计算所有球队的 Elo 评分

        遍历历史比赛（从远到近），每场比赛后更新两队评分。
        """
        # 重置所有球队评分为初始值
        query = self.db.query(Team)
        if league_id:
            # 获取该联赛中出现的球队
            team_ids = set()
            matches = self.db.query(Match).filter(
                Match.league_id == league_id,
                Match.status == "FINISHED",
            ).all()
            for m in matches:
                team_ids.add(m.home_team_id)
                team_ids.add(m.away_team_id)
            query = query.filter(Team.id.in_(team_ids))

        teams = query.all()
        ratings = {t.id: self.initial_rating for t in teams}

        # 获取所有已完成的比赛，按时间排序
        match_query = self.db.query(Match).filter(
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        )
        if league_id:
            match_query = match_query.filter(Match.league_id == league_id)

        finished_matches = match_query.order_by(Match.utc_date.asc()).all()

        # 逐场比赛更新评分
        for m in finished_matches:
            home_rating = ratings.get(m.home_team_id, self.initial_rating)
            away_rating = ratings.get(m.away_team_id, self.initial_rating)

            new_home, new_away = self.update_ratings(
                home_rating, away_rating,
                m.score_home, m.score_away,
            )
            ratings[m.home_team_id] = new_home
            ratings[m.away_team_id] = new_away

        # 写回数据库
        for team in teams:
            team.elo_rating = round(ratings.get(team.id, self.initial_rating), 1)
        self.db.commit()

        return ratings
