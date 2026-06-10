"""比赛数据 API 路由"""
import json
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db, Match, League, Team
from backend.schemas import MatchInfo
from backend.data.fetcher import DataSyncService

router = APIRouter()


def _match_to_dict(match: Match) -> dict:
    """将 Match 对象转为 dict，包含解析后的 odds 数据"""
    result = {
        "id": match.id,
        "league_id": match.league_id,
        "season": match.season,
        "matchday": match.matchday,
        "utc_date": match.utc_date.isoformat() if match.utc_date else None,
        "status": match.status,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        "home_team_name": match.home_team_name,
        "away_team_name": match.away_team_name,
        "score_home": match.score_home,
        "score_away": match.score_away,
        "winner": match.winner,
    }
    # 解析赔率数据
    if match.extra_data:
        try:
            extra = json.loads(match.extra_data)
            # 提取关键赔率
            odds = {}
            for bk in ["B365H","B365D","B365A","PSH","PSD","PSA",
                       "BWH","BWD","BWA","MaxH","MaxD","MaxA",
                       "AvgH","AvgD","AvgA"]:
                if bk in extra and extra[bk]:
                    odds[bk] = extra[bk]
            if odds:
                result["odds"] = odds
        except:
            pass
    return result


@router.get("/upcoming")
def get_upcoming_matches(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db),
):
    """获取即将到来的比赛"""
    query = db.query(Match).filter(
        Match.status == "SCHEDULED",
        Match.utc_date >= datetime.utcnow(),
    ).order_by(Match.utc_date.asc())

    if league_id:
        query = query.filter(Match.league_id == league_id)

    matches = query.limit(limit).all()
    return [_match_to_dict(m) for m in matches]


@router.get("/results")
def get_match_results(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    days: int = Query(90, description="最近N天"),
    limit: int = Query(50, description="返回数量"),
    db: Session = Depends(get_db),
):
    """获取历史比赛结果"""
    since = datetime.utcnow() - timedelta(days=days)

    query = db.query(Match).filter(
        Match.status == "FINISHED",
        Match.utc_date >= since,
    ).order_by(Match.utc_date.desc())

    if league_id:
        query = query.filter(Match.league_id == league_id)

    matches = query.limit(limit).all()
    return [_match_to_dict(m) for m in matches]


@router.get("/odds")
def get_matches_with_odds(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    season: str = Query("2025-26", description="赛季"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db),
):
    """获取包含赔率数据的比赛"""
    query = db.query(Match).filter(
        Match.season == season,
        Match.status == "FINISHED",
        Match.extra_data.isnot(None),
    )

    if league_id:
        query = query.filter(Match.league_id == league_id)

    matches = query.order_by(Match.utc_date.desc()).limit(limit).all()
    return [_match_to_dict(m) for m in matches if m.extra_data]


@router.get("/matchdays")
def get_matchdays(db: Session = Depends(get_db)):
    """获取各联赛当前轮次和比赛总数"""
    from sqlalchemy import func
    result = {}
    league_names = {2021: "英超", 2002: "德甲", 2014: "西甲", 2019: "意甲", 2015: "法甲"}
    for lid, lname in league_names.items():
        max_md = db.query(func.max(Match.matchday)).filter(
            Match.league_id == lid,
            Match.status == "FINISHED",
        ).scalar()
        total = db.query(Match).filter(
            Match.league_id == lid,
            Match.status == "FINISHED",
        ).count()
        result[lname] = {"matchday": max_md or 0, "total_matches": total}
    return result


@router.get("/{match_id}")
def get_match_detail(match_id: int, db: Session = Depends(get_db)):
    """获取单场比赛详情"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛未找到")
    return _match_to_dict(match)


@router.post("/refresh")
def refresh_data(
    league_id: Optional[int] = Query(None, description="联赛ID，留空刷新所有"),
    source: str = Query("auto", description="数据源: auto/csv/api"),
):
    """手动触发数据刷新

    默认使用 CSV (football-data.co.uk) 获取数据，无需 API Key。
    """
    from backend.data.csv_importer import import_all, import_league as csv_import_league
    from backend.database import get_db_sync, Match
    from sqlalchemy import func

    db = get_db_sync()

    def _get_matchday_info() -> dict:
        """获取各联赛最新轮次信息"""
        info = {}
        for lid, lname in [(2021, "英超"), (2002, "德甲"), (2014, "西甲"),
                           (2019, "意甲"), (2015, "法甲")]:
            max_md = db.query(func.max(Match.matchday)).filter(
                Match.league_id == lid,
                Match.status == "FINISHED",
            ).scalar()
            total = db.query(Match).filter(
                Match.league_id == lid,
                Match.status == "FINISHED",
            ).count()
            info[lname] = {"matchday": max_md or 0, "total_matches": total}
        return info

    try:
        before = _get_matchday_info()

        if source == "csv" or source == "auto":
            if league_id:
                season = _current_season()
                result = csv_import_league(db=db, league_id=league_id, season=season)
                after = _get_matchday_info()
                return {
                    "message": f"联赛 {league_id} 刷新完成",
                    "total_synced": result.get("new", 0),
                    "source": "csv",
                    "import_details": {str(league_id): result},
                    "leagues": {lname: after[lname] for lname in after
                                if after[lname] != before.get(lname)},
                }
            else:
                result = import_all(db=db)
                after = _get_matchday_info()
                return {
                    "message": "所有联赛刷新完成",
                    "total_synced": result["total_new"],
                    "source": "csv",
                    "import_details": result["leagues"],
                    "leagues": after,
                }
        else:
            return {"message": "未知数据源", "source": source}
    finally:
        if db:
            db.close()


@router.post("/upload")
def upload_csv_file(
    league_code: str = Query(..., description="联赛代码: E0/D1/SP1/I1/F1"),
    season: str = Query(None, description="赛季如 2025-26，默认当前赛季"),
):
    """上传 CSV 文件并导入数据库"""
    import json
    from fastapi import UploadFile, File
    # FastAPI 的 UploadFile 需要异步，这里用同步方式
    # 实际通过 request body 接收 raw text
    from backend.data.csv_importer import import_csv_to_db
    from backend.database import get_db_sync
    from sqlalchemy import func

    # 这个端点需要在 Streamlit 端通过 api_post 传 CSV 文本内容
    # 实际实现：Streamlit 读取文件后调用
    return {"error": "请使用 /api/matches/upload/csv 端点上传文件"}


@router.post("/upload/csv")
def upload_csv_raw(body: dict):
    """上传 CSV 文本内容并导入"""
    from backend.data.csv_importer import import_csv_text_to_db, LEAGUE_CSV_MAP
    from backend.database import get_db_sync

    league_code = body.get("league_code", "")
    csv_text = body.get("csv_text", "")
    season = body.get("season") or _current_season()

    if league_code not in LEAGUE_CSV_MAP:
        raise HTTPException(status_code=400, detail=f"无效的联赛代码: {league_code}")
    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="CSV 内容为空")

    db = get_db_sync()
    try:
        result = import_csv_text_to_db(db, league_code, season, csv_text)
        return {
            "message": "导入完成",
            "matches_imported": result.get("new", 0),
            "skipped": result.get("skipped", 0),
            "total_in_csv": result.get("total_in_csv", 0),
            "league_code": league_code,
            "league_name": LEAGUE_CSV_MAP[league_code][1],
            "season": season,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def _current_season() -> str:
    """根据当前日期返回赛季名"""
    from datetime import datetime
    now = datetime.now()
    if now.month >= 8:
        return f"{now.year}-{str(now.year + 1)[2:]}"
    return f"{now.year - 1}-{str(now.year)[2:]}"
