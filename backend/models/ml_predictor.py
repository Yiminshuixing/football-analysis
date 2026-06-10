"""
ML 预测模型 — Logistic Regression
基于历史数据特征训练，融合 Poisson+Elo 提升准确率。
"""
import numpy as np
import json
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from datetime import datetime
from sqlalchemy.orm import Session
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.calibration import CalibratedClassifierCV

from backend.database import get_db_sync, Match, Team
from backend.models.elo import EloRating


class FeatureEngine:
    """特征工程 — 为每场比赛计算预测特征"""

    def __init__(self, db: Session):
        self.db = db

    def compute_features(self, match: Match,
                         team_ratings: Dict[int, float],
                         ) -> Optional[np.ndarray]:
        """为单场比赛计算特征向量

        特征:
        1. elo_home: 主队 Elo
        2. elo_away: 客队 Elo
        3. elo_diff: 主队 Elo - 客队 Elo + 主场优势
        4. home_scored_avg: 主队近5场场均进球
        5. home_conceded_avg: 主队近5场场均失球
        6. away_scored_avg: 客队近5场场均进球
        7. away_conceded_avg: 客队近5场场均失球
        8. home_win_rate: 主队近5场胜率
        9. away_win_rate: 客队近5场胜率
        10. total_avg_goals: 联赛场均总进球
        """
        home_elo = team_ratings.get(match.home_team_id, 1500.0)
        away_elo = team_ratings.get(match.away_team_id, 1500.0)
        elo_diff = home_elo - away_elo + 100.0  # 包含主场优势

        # 计算近5场数据
        home_stats = self._recent_stats(match.home_team_id, match.utc_date, match.league_id, 5)
        away_stats = self._recent_stats(match.away_team_id, match.utc_date, match.league_id, 5)

        # 联赛场均进球
        league_avg = self._league_avg_goals(match.league_id, match.utc_date)

        if home_stats is None or away_stats is None:
            return None

        return np.array([
            home_elo,
            away_elo,
            elo_diff,
            home_stats["scored_avg"],
            home_stats["conceded_avg"],
            away_stats["scored_avg"],
            away_stats["conceded_avg"],
            home_stats["win_rate"],
            away_stats["win_rate"],
            league_avg,
        ])

    def _recent_stats(self, team_id: int, before_date: datetime,
                      league_id: int, n: int = 5) -> Optional[dict]:
        """计算球队在指定日期前的 N 场比赛统计"""
        matches = self.db.query(Match).filter(
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
            Match.league_id == league_id,
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
            Match.utc_date < before_date,
        ).order_by(Match.utc_date.desc()).limit(n).all()

        if not matches:
            return None

        total_scored = 0
        total_conceded = 0
        wins = 0
        count = 0

        for m in matches:
            if m.home_team_id == team_id:
                total_scored += m.score_home
                total_conceded += m.score_away
                if m.score_home > m.score_away:
                    wins += 1
            else:
                total_scored += m.score_away
                total_conceded += m.score_home
                if m.score_away > m.score_home:
                    wins += 1
            count += 1

        if count == 0:
            return None

        return {
            "scored_avg": total_scored / count,
            "conceded_avg": total_conceded / count,
            "win_rate": wins / count,
        }

    def _league_avg_goals(self, league_id: int, before_date: datetime) -> float:
        """联赛场均进球"""
        from datetime import timedelta
        six_months = before_date - timedelta(days=180)
        matches = self.db.query(Match).filter(
            Match.league_id == league_id,
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
            Match.utc_date.between(six_months, before_date),
        ).all()

        if not matches:
            return 2.5

        total = sum((m.score_home or 0) + (m.score_away or 0) for m in matches)
        return total / len(matches)


class MLPredictor:
    """Logistic Regression 预测器"""

    def __init__(self, db: Session = None):
        self.db = db or get_db_sync()
        self.fe = FeatureEngine(self.db)
        self.model = None
        self.is_trained = False

    def build_training_data(self, train_seasons: List[str],
                            league_ids: List[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        """构建训练数据集

        为每个训练赛季的每场比赛计算特征，并收集标签。
        """
        if league_ids is None:
            league_ids = [2021, 2002, 2014, 2019, 2015]

        query = self.db.query(Match).filter(
            Match.season.in_(train_seasons),
            Match.league_id.in_(league_ids),
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        ).order_by(Match.league_id, Match.utc_date.asc())

        all_matches = query.all()
        if not all_matches:
            # Fallback: 用所有数据
            all_matches = self.db.query(Match).filter(
                Match.league_id.in_(league_ids),
                Match.status == "FINISHED",
                Match.score_home.isnot(None),
                Match.score_away.isnot(None),
            ).order_by(Match.utc_date.asc()).limit(5000).all()

        # 计算 Elo 评分（按时间顺序）
        elo_calc = EloRating(self.db)
        team_ratings = defaultdict(lambda: 1500.0)

        # 先初始化所有球队
        teams = self.db.query(Team).all()
        for t in teams:
            team_ratings[t.id] = 1500.0

        features = []
        labels = []

        for m in all_matches:
            # 计算特征
            feat = self.fe.compute_features(m, team_ratings)
            if feat is None:
                # 更新 Elo 继续
                self._update_elo(team_ratings, elo_calc, m)
                continue

            features.append(feat)

            # 标签
            if m.winner == "HOME_TEAM":
                labels.append(0)
            elif m.winner == "AWAY_TEAM":
                labels.append(2)
            else:
                labels.append(1)

            # 更新 Elo
            self._update_elo(team_ratings, elo_calc, m)

        X = np.array(features)
        y = np.array(labels)

        print(f"  训练数据: {len(X)} 条, 特征维度: {X.shape[1]}")
        print(f"  类别分布: HOME={sum(y==0)}, DRAW={sum(y==1)}, AWAY={sum(y==2)}")
        return X, y

    def _update_elo(self, team_ratings: dict, elo_calc: EloRating, match: Match):
        """更新 Elo 评分"""
        home_r = team_ratings[match.home_team_id]
        away_r = team_ratings[match.away_team_id]
        new_h, new_a = elo_calc.update_ratings(home_r, away_r, match.score_home, match.score_away)
        team_ratings[match.home_team_id] = new_h
        team_ratings[match.away_team_id] = new_a

    def train(self, train_seasons: List[str] = None,
              league_ids: List[int] = None):
        """训练模型"""
        if train_seasons is None:
            train_seasons = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]

        print(f"🔄 训练 ML 模型...")
        X, y = self.build_training_data(train_seasons, league_ids)

        if len(X) < 100:
            print("  ❌ 训练数据不足")
            return False

        # 训练 Logistic Regression (多分类)
        self.model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                solver='lbfgs',
                C=1.0,
                max_iter=1000,
                class_weight='balanced',
                random_state=42,
            ),
        )
        self.model.fit(X, y)
        self.is_trained = True
        print(f"  ✅ 模型训练完成, 特征数: {X.shape[1]}")
        return True

    def predict_proba(self, match: Match,
                      team_ratings: Dict[int, float]) -> Optional[Dict[str, float]]:
        """返回 ML 模型的概率预测"""
        if not self.is_trained:
            return None

        feat = self.fe.compute_features(match, team_ratings)
        if feat is None:
            return None

        probs = self.model.predict_proba([feat])[0]

        # 模型可能在训练时没见过某个类别
        # probs 顺序: [HOME, DRAW, AWAY] (0, 1, 2)
        if len(probs) == 3:
            return {
                "home_win_prob": round(float(probs[0]), 4),
                "draw_prob": round(float(probs[1]), 4),
                "away_win_prob": round(float(probs[2]), 4),
            }
        else:
            return None

    def get_feature_names(self) -> List[str]:
        return [
            "elo_home", "elo_away", "elo_diff",
            "home_scored_avg", "home_conceded_avg",
            "away_scored_avg", "away_conceded_avg",
            "home_win_rate", "away_win_rate",
            "league_avg_goals",
        ]
