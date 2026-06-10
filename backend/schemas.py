"""Pydantic 数据模型（API schema）"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TeamInfo(BaseModel):
    id: int
    name: str
    short_name: Optional[str] = None
    tla: Optional[str] = None
    crest_url: Optional[str] = None
    elo_rating: float = 1500.0

    class Config:
        from_attributes = True


class MatchInfo(BaseModel):
    id: int
    league_id: int
    season: Optional[str] = None
    matchday: Optional[int] = None
    utc_date: datetime
    status: str
    home_team_id: int
    away_team_id: int
    home_team_name: Optional[str] = None
    away_team_name: Optional[str] = None
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    winner: Optional[str] = None
    odds: Optional[dict] = None  # 赔率数据

    class Config:
        from_attributes = True


class PredictionResult(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_home_score: int
    predicted_away_score: int
    confidence: float
    predicted_outcome: str  # HOME, DRAW, AWAY
    league_name: Optional[str] = None
    match_date: Optional[datetime] = None


class LeagueStanding(BaseModel):
    position: int
    team_id: int
    team_name: str
    crest_url: Optional[str] = None
    played_games: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class TeamDetail(BaseModel):
    team: TeamInfo
    recent_form: List[str]  # W, D, L 列表
    recent_matches: List[MatchInfo]
    elo_history: List[dict]  # [{date, rating}]
