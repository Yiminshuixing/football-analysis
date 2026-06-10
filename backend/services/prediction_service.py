"""预测服务 - 综合多种模型生成预测"""
import json
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.database import Match, Prediction, Team, League, get_db_sync
from backend.models.poisson import PoissonPredictor
from backend.models.elo import EloRating
from backend.config import settings

logger = logging.getLogger(__name__)


class PredictionService:
    """综合预测服务，融合 Poisson 和 Elo 模型"""

    def __init__(self, db: Session = None):
        self.db = db or get_db_sync()
        self.poisson = PoissonPredictor(self.db)
        # Elo 使用默认主场优势，具体联赛的调整在 predict_match 中查表覆盖
        self.elo = EloRating(self.db)

    def _league_params(self, league_id: int) -> dict:
        """获取联赛特定参数，不存在则返回默认值"""
        if league_id and league_id in settings.league_params:
            return settings.league_params[league_id]
        return {"elo_home_advantage": 100, "poisson_weight": 0.55, "dixon_coles_rho": 0.15}

    def predict_match(self, match: Match) -> dict:
        """对单场比赛进行综合预测

        Args:
            match: Match 对象

        Returns:
            预测结果 dict
        """
        lp = self._league_params(match.league_id)

        # Poisson 模型预测（传入联赛特定 ρ）
        poisson_result = self.poisson.predict_match(
            match.home_team_id, match.away_team_id, match.league_id,
            rho=lp["dixon_coles_rho"],
        )

        # Elo 模型预测（用联赛特定主场优势）
        home_team = self.db.query(Team).filter(Team.id == match.home_team_id).first()
        away_team = self.db.query(Team).filter(Team.id == match.away_team_id).first()

        home_elo = home_team.elo_rating if home_team else 1500.0
        away_elo = away_team.elo_rating if away_team else 1500.0

        # 联赛特定主场优势创建临时 Elo 预测器
        elo_hfa = lp["elo_home_advantage"]
        elo_pred = EloRating(self.db, home_advantage=elo_hfa)
        elo_result = elo_pred.predict_match_probs(home_elo, away_elo)

        # 综合两种模型（联赛特定权重）
        poisson_weight = lp["poisson_weight"]
        elo_weight = 1.0 - poisson_weight

        home_win = (poisson_result["home_win_prob"] * poisson_weight +
                    elo_result["home_win_prob"] * elo_weight)
        draw = (poisson_result["draw_prob"] * poisson_weight +
                elo_result["draw_prob"] * elo_weight)
        away_win = (poisson_result["away_win_prob"] * poisson_weight +
                    elo_result["away_win_prob"] * elo_weight)

        # 归一化
        total = home_win + draw + away_win
        home_win /= total
        draw /= total
        away_win /= total

        # 预测比分（使用 Poisson 的最可能比分）
        predicted_home = poisson_result["predicted_home_score"]
        predicted_away = poisson_result["predicted_away_score"]

        # 确定预测结果
        if home_win > draw and home_win > away_win:
            predicted_outcome = "HOME"
        elif away_win > home_win and away_win > draw:
            predicted_outcome = "AWAY"
        else:
            predicted_outcome = "DRAW"

        # 置信度计算：基于最大概率和模型一致性
        max_prob = max(home_win, draw, away_win)
        # 模型一致性：两个模型预测相同结果的概率
        poisson_outcome = max(
            ("HOME", poisson_result["home_win_prob"]),
            ("DRAW", poisson_result["draw_prob"]),
            ("AWAY", poisson_result["away_win_prob"]),
            key=lambda x: x[1]
        )[0]
        elo_outcome = max(
            ("HOME", elo_result["home_win_prob"]),
            ("DRAW", elo_result["draw_prob"]),
            ("AWAY", elo_result["away_win_prob"]),
            key=lambda x: x[1]
        )[0]
        model_agreement = 1.0 if poisson_outcome == elo_outcome else 0.5

        confidence = min(95, round((max_prob * 0.7 + model_agreement * 0.3) * 100, 1))

        model_details = {
            "poisson": poisson_result,
            "elo": elo_result,
            "weights": {"poisson": poisson_weight, "elo": elo_weight},
            "league_params": {
                "elo_home_advantage": elo_hfa,
                "dixon_coles_rho": lp["dixon_coles_rho"],
                "poisson_weight": poisson_weight,
            },
        }

        # 获取联赛名
        league = self.db.query(League).filter(League.id == match.league_id).first()
        league_name = league.name if league else None

        return {
            "match_id": match.id,
            "home_team": match.home_team_name or f"Team {match.home_team_id}",
            "away_team": match.away_team_name or f"Team {match.away_team_id}",
            "home_win_prob": round(home_win, 4),
            "draw_prob": round(draw, 4),
            "away_win_prob": round(away_win, 4),
            "predicted_home_score": predicted_home,
            "predicted_away_score": predicted_away,
            "predicted_outcome": predicted_outcome,
            "confidence": confidence,
            "league_name": league_name,
            "match_date": match.utc_date,
            "model_details": model_details,
        }

    def save_prediction(self, result: dict):
        """保存预测结果到数据库"""
        pred = self.db.query(Prediction).filter(
            Prediction.match_id == result["match_id"]
        ).first()

        if not pred:
            pred = Prediction(match_id=result["match_id"])

        pred.home_win_prob = result["home_win_prob"]
        pred.draw_prob = result["draw_prob"]
        pred.away_win_prob = result["away_win_prob"]
        pred.predicted_home_score = result["predicted_home_score"]
        pred.predicted_away_score = result["predicted_away_score"]
        pred.confidence = result["confidence"]

        if "model_details" in result:
            pred.model_details = json.dumps(result["model_details"], ensure_ascii=False)

        pred.updated_at = datetime.utcnow()
        self.db.merge(pred)
        self.db.commit()

    def predict_upcoming_matches(self, league_id: Optional[int] = None) -> List[dict]:
        """预测所有未开始的比赛"""
        query = self.db.query(Match).filter(
            Match.status == "SCHEDULED",
            Match.utc_date >= datetime.utcnow(),
        ).order_by(Match.utc_date.asc())

        if league_id:
            query = query.filter(Match.league_id == league_id)

        # 限制最多预测 50 场
        matches = query.limit(50).all()
        results = []

        for match in matches:
            try:
                # 检查是否已有预测
                existing = self.db.query(Prediction).filter(
                    Prediction.match_id == match.id
                ).first()
                if existing and existing.updated_at:
                    # 如果预测是在最近1小时内生成的，直接返回缓存
                    if (datetime.utcnow() - existing.updated_at).seconds < 3600:
                        results.append(self._prediction_to_dict(existing, match))
                        continue

                result = self.predict_match(match)
                self.save_prediction(result)
                results.append(result)
            except Exception as e:
                logger.error(f"预测比赛 {match.id} 时出错: {e}")
                continue

        return results

    def _prediction_to_dict(self, pred: Prediction, match: Match) -> dict:
        """将数据库中的 Prediction 转为 dict"""
        league = self.db.query(League).filter(League.id == match.league_id).first()
        return {
            "match_id": pred.match_id,
            "home_team": match.home_team_name or f"Team {match.home_team_id}",
            "away_team": match.away_team_name or f"Team {match.away_team_id}",
            "home_win_prob": pred.home_win_prob,
            "draw_prob": pred.draw_prob,
            "away_win_prob": pred.away_win_prob,
            "predicted_home_score": pred.predicted_home_score,
            "predicted_away_score": pred.predicted_away_score,
            "predicted_outcome": (
                "HOME" if pred.home_win_prob > pred.draw_prob and pred.home_win_prob > pred.away_win_prob
                else "AWAY" if pred.away_win_prob > pred.home_win_prob and pred.away_win_prob > pred.draw_prob
                else "DRAW"
            ),
            "confidence": pred.confidence,
            "league_name": league.name if league else None,
            "match_date": match.utc_date,
        }
