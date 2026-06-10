"""模型回测 API"""
from typing import Optional
from fastapi import APIRouter, Query
from backend.services.backtest_service import BacktestService

router = APIRouter()


@router.get("/")
def get_backtest(
    league_id: Optional[int] = Query(None, description="联赛ID，留空回测所有"),
    test_season: str = Query("2025-26", description="测试赛季"),
):
    """运行原始模型回测 (Poisson + Elo)"""
    svc = BacktestService()
    if league_id:
        result = svc.run_backtest(league_id, test_season)
        if "error" in result:
            return result
        return result
    else:
        return svc.run_all(test_season)


@router.get("/ml")
def get_backtest_ml(
    league_id: int = Query(2021, description="联赛ID"),
    test_season: str = Query("2025-26", description="测试赛季"),
):
    """运行 ML 融合回测 (Logistic Regression + Poisson + Elo)"""
    svc = BacktestService()
    result = svc.run_backtest_ml(league_id, test_season)
    return result


@router.get("/compare")
def compare_models(
    league_id: int = Query(2021, description="联赛ID"),
    test_season: str = Query("2025-26", description="测试赛季"),
):
    """对比原始模型 vs 改进模型 vs ML融合"""
    svc = BacktestService()
    r1 = svc.run_backtest(league_id, test_season)
    r2 = svc.run_backtest_ml(league_id, test_season)

    return {
        "test_season": test_season,
        "league_id": league_id,
        "models": {
            "original (Poisson+Elo)": {
                "accuracy": r1.get("overall_accuracy", 0),
                "exact_score": r1.get("exact_score_accuracy", 0),
                "total": r1.get("total_matches", 0),
                "correct": r1.get("correct_predictions", 0),
            },
            "ml_fusion (ML+Poisson+Elo)": {
                "accuracy": r2.get("overall_accuracy", 0),
                "exact_score": r2.get("exact_score_accuracy", 0),
                "total": r2.get("total_matches", 0),
                "correct": r2.get("correct_predictions", 0),
            },
        },
    }
