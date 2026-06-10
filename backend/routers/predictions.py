"""预测结果 API 路由"""
import json
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, Prediction, Match, Team, League
from backend.schemas import PredictionResult
from backend.services.prediction_service import PredictionService
from backend.models.poisson import PoissonPredictor
from backend.models.elo import EloRating
from backend.config import settings

router = APIRouter()


# ========== 手动预测相关 ==========

class ManualPredictRequest(BaseModel):
    """手动预测请求体"""
    home_team: str       # 主队英文名
    away_team: str       # 客队英文名
    home_odds: float | None = None   # 用户输入的主胜赔率
    draw_odds: float | None = None   # 用户输入的平局赔率
    away_odds: float | None = None   # 用户输入的客胜赔率
    league_id: int | None = None     # 可选，自动推断联赛


def get_team_recent_form(db: Session, team_id: int, venue: str, limit: int = 5) -> List[dict]:
    """获取球队近期指定主/客场的比赛成绩"""
    query = db.query(Match).filter(
        Match.status == "FINISHED",
        Match.score_home.isnot(None),
        Match.score_away.isnot(None),
        Match.utc_date < datetime.utcnow(),
    )

    if venue == "home":
        query = query.filter(Match.home_team_id == team_id)
    elif venue == "away":
        query = query.filter(Match.away_team_id == team_id)

    query = query.order_by(Match.utc_date.desc()).limit(limit)
    matches = query.all()

    results = []
    for m in matches:
        is_home = (m.home_team_id == team_id)
        opponent = m.away_team_name if is_home else m.home_team_name
        score = f"{m.score_home}:{m.score_away}"
        if is_home:
            result = "W" if m.score_home > m.score_away else "L" if m.score_home < m.score_away else "D"
        else:
            result = "W" if m.score_away > m.score_home else "L" if m.score_away < m.score_home else "D"

        results.append({
            "opponent": opponent,
            "score": score,
            "result": result,
            "date": m.utc_date.isoformat() if m.utc_date else None,
            "venue": "home" if is_home else "away",
            "league_id": m.league_id,
        })

    return results


def infer_league_id(db: Session, home_team_id: int, away_team_id: int) -> int | None:
    """根据两队的历史比赛推断联赛 ID"""
    for tid in [home_team_id, away_team_id]:
        match = db.query(Match).filter(
            (Match.home_team_id == tid) | (Match.away_team_id == tid)
        ).order_by(Match.utc_date.desc()).first()
        if match:
            return match.league_id
    return None


@router.post("/manual")
def manual_predict(req: ManualPredictRequest, db: Session = Depends(get_db)):
    """手动输入球队和赔率进行预测"""
    # 查找球队
    home_team = db.query(Team).filter(Team.name.ilike(req.home_team)).first()
    away_team = db.query(Team).filter(Team.name.ilike(req.away_team)).first()

    if not home_team:
        raise HTTPException(status_code=404, detail=f"找不到主队: {req.home_team}")
    if not away_team:
        raise HTTPException(status_code=404, detail=f"找不到客队: {req.away_team}")

    # 获取联赛参数
    league_id = req.league_id or infer_league_id(db, home_team.id, away_team.id) or 2021
    lp = settings.league_params.get(league_id, {})
    league_name = lp.get("name", f"League {league_id}")

    # 获取近期主客场比赛成绩
    home_recent = get_team_recent_form(db, home_team.id, venue="home", limit=5)
    away_recent = get_team_recent_form(db, away_team.id, venue="away", limit=5)

    # Poisson 预测
    poisson = PoissonPredictor(db)
    poisson_result = poisson.predict_match(
        home_team.id, away_team.id, league_id,
        rho=lp.get("dixon_coles_rho", 0.15),
    )

    # Elo 预测
    elo_hfa = lp.get("elo_home_advantage", 100)
    elo = EloRating(db, home_advantage=elo_hfa)
    elo_result = elo.predict_match_probs(home_team.elo_rating, away_team.elo_rating)

    # 融合
    poisson_weight = lp.get("poisson_weight", 0.55)
    elo_weight = 1.0 - poisson_weight

    home_win = poisson_result["home_win_prob"] * poisson_weight + elo_result["home_win_prob"] * elo_weight
    draw = poisson_result["draw_prob"] * poisson_weight + elo_result["draw_prob"] * elo_weight
    away_win = poisson_result["away_win_prob"] * poisson_weight + elo_result["away_win_prob"] * elo_weight
    total = home_win + draw + away_win
    home_win, draw, away_win = home_win / total, draw / total, away_win / total

    # 预测结果判定
    predicted_outcome = "HOME" if home_win > draw and home_win > away_win else \
                        "AWAY" if away_win > home_win and away_win > draw else "DRAW"

    # 置信度
    max_prob = max(home_win, draw, away_win)
    poisson_outcome = max(
        ("HOME", poisson_result["home_win_prob"]),
        ("DRAW", poisson_result["draw_prob"]),
        ("AWAY", poisson_result["away_win_prob"]),
        key=lambda x: x[1],
    )[0]
    elo_outcome = max(
        ("HOME", elo_result["home_win_prob"]),
        ("DRAW", elo_result["draw_prob"]),
        ("AWAY", elo_result["away_win_prob"]),
        key=lambda x: x[1],
    )[0]
    agreement = 1.0 if poisson_outcome == elo_outcome else 0.5
    confidence = min(95, round((max_prob * 0.7 + agreement * 0.3) * 100, 1))

    # 赔率分析（如果用户提供了赔率）
    odds_analysis = None
    if req.home_odds and req.draw_odds and req.away_odds:
        implied_h = 1.0 / req.home_odds
        implied_d = 1.0 / req.draw_odds
        implied_a = 1.0 / req.away_odds
        implied_total = implied_h + implied_d + implied_a

        odds_analysis = {
            "odds_home_prob": round(implied_h / implied_total, 4),
            "odds_draw_prob": round(implied_d / implied_total, 4),
            "odds_away_prob": round(implied_a / implied_total, 4),
            "model_home_prob": round(home_win, 4),
            "model_draw_prob": round(draw, 4),
            "model_away_prob": round(away_win, 4),
        }

        # 价值投注判断
        value_bets = []
        model_probs = [("home", home_win), ("draw", draw), ("away", away_win)]
        implied_probs = [implied_h / implied_total, implied_d / implied_total, implied_a / implied_total]
        odds_values = [req.home_odds, req.draw_odds, req.away_odds]
        labels = ["home", "draw", "away"]

        for i, label in enumerate(labels):
            if model_probs[i][1] > implied_probs[i] * 1.05 and odds_values[i] > 1.5:
                value_bets.append({
                    "type": label,
                    "model_prob": round(model_probs[i][1], 4),
                    "odds_prob": round(implied_probs[i], 4),
                    "odds": odds_values[i],
                    "expected_value": round(model_probs[i][1] * odds_values[i] - 1, 4),
                })

        odds_analysis["value_bets"] = value_bets

    return {
        "home_team": {"id": home_team.id, "name": home_team.name, "elo_rating": round(home_team.elo_rating, 1)},
        "away_team": {"id": away_team.id, "name": away_team.name, "elo_rating": round(away_team.elo_rating, 1)},
        "league_id": league_id,
        "league_name": league_name,
        "home_recent_form": home_recent,
        "away_recent_form": away_recent,
        "prediction": {
            "home_win_prob": round(home_win, 4),
            "draw_prob": round(draw, 4),
            "away_win_prob": round(away_win, 4),
            "predicted_home_score": poisson_result["predicted_home_score"],
            "predicted_away_score": poisson_result["predicted_away_score"],
            "predicted_outcome": predicted_outcome,
            "confidence": confidence,
            "home_xg": poisson_result["home_xg"],
            "away_xg": poisson_result["away_xg"],
            "score_probabilities": poisson_result["score_probabilities"],
            "poisson_home_win": round(poisson_result["home_win_prob"], 4),
            "poisson_draw": round(poisson_result["draw_prob"], 4),
            "poisson_away_win": round(poisson_result["away_win_prob"], 4),
            "elo_home_win": round(elo_result["home_win_prob"], 4),
            "elo_draw": round(elo_result["draw_prob"], 4),
            "elo_away_win": round(elo_result["away_win_prob"], 4),
            "fusion_weights": {"poisson": poisson_weight, "elo": elo_weight},
            "league_params": {
                "elo_home_advantage": elo_hfa,
                "dixon_coles_rho": lp.get("dixon_coles_rho", 0.15),
                "poisson_weight": poisson_weight,
            },
        },
        "odds_analysis": odds_analysis,
    }


@router.get("/", response_model=List[PredictionResult])
def get_predictions(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    min_confidence: float = Query(0.0, description="最低置信度"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db),
):
    """获取所有比赛预测"""
    svc = PredictionService(db)
    results = svc.predict_upcoming_matches(league_id)

    # 按置信度过滤
    if min_confidence > 0:
        results = [r for r in results if r["confidence"] >= min_confidence]

    return results[:limit]


@router.get("/high-confidence", response_model=List[PredictionResult])
def get_high_confidence_predictions(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    threshold: float = Query(60.0, description="置信度阈值"),
    limit: int = Query(10, description="返回数量"),
    db: Session = Depends(get_db),
):
    """获取高置信度预测（用于投注参考）"""
    svc = PredictionService(db)
    all_results = svc.predict_upcoming_matches(league_id)

    # 筛选高置信度且预测明确的比赛
    high_conf = []
    for r in all_results:
        if r["confidence"] >= threshold:
            probs = [r["home_win_prob"], r["draw_prob"], r["away_win_prob"]]
            max_prob = max(probs)
            # 最大概率 > 50% 且明显高于其他选项
            if max_prob > 0.45 and max_prob - sorted(probs)[-2] > 0.1:
                high_conf.append(r)

    high_conf.sort(key=lambda x: x["confidence"], reverse=True)
    return high_conf[:limit]


@router.get("/{match_id}", response_model=PredictionResult)
def get_match_prediction(match_id: int, db: Session = Depends(get_db)):
    """获取单场比赛预测"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛未找到")

    svc = PredictionService(db)
    result = svc.predict_match(match)
    svc.save_prediction(result)
    return result


@router.post("/refresh")
def refresh_predictions(
    league_id: Optional[int] = Query(None, description="联赛ID"),
):
    """刷新预测结果（重新计算）"""
    from backend.database import get_db_sync
    db = get_db_sync()
    svc = PredictionService(db)
    try:
        # 先更新 Elo 评分
        elo = svc.elo
        elo.recalculate_all_ratings(league_id)

        results = svc.predict_upcoming_matches(league_id)
        return {
            "message": f"预测刷新完成",
            "predictions_generated": len(results),
        }
    finally:
        db.close()
