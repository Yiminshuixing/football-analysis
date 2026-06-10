"""数据库连接与模型定义"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

from backend.config import settings

# 确保数据目录存在
os.makedirs("data", exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite 需要
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------- 数据表模型 ----------

class League(Base):
    """联赛"""
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    code = Column(String(10))
    emblem_url = Column(String(500))
    current_matchday = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Team(Base):
    """球队"""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    short_name = Column(String(50))
    tla = Column(String(5))  # 三字母缩写
    crest_url = Column(String(500))
    venue = Column(String(200))
    elo_rating = Column(Float, default=1500.0)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Match(Base):
    """比赛"""
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, nullable=False)
    season = Column(String(20))
    matchday = Column(Integer)
    utc_date = Column(DateTime, nullable=False)
    status = Column(String(20), default="SCHEDULED")  # SCHEDULED, FINISHED, etc.

    home_team_id = Column(Integer, nullable=False)
    away_team_id = Column(Integer, nullable=False)
    home_team_name = Column(String(200))
    away_team_name = Column(String(200))

    score_home = Column(Integer, nullable=True)
    score_away = Column(Integer, nullable=True)

    winner = Column(String(10), nullable=True)  # HOME_TEAM, AWAY_TEAM, DRAW

    # 缓存额外数据 (JSON)
    extra_data = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Prediction(Base):
    """预测结果"""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, nullable=False, unique=True)

    # 概率
    home_win_prob = Column(Float, default=0.0)
    draw_prob = Column(Float, default=0.0)
    away_win_prob = Column(Float, default=0.0)

    # 最可能比分
    predicted_home_score = Column(Integer, default=0)
    predicted_away_score = Column(Integer, default=0)

    # 置信度 (0-100)
    confidence = Column(Float, default=0.0)

    # 模型详情 (JSON)
    model_details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DataCache(Base):
    """API数据缓存跟踪"""
    __tablename__ = "data_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(200), unique=True, nullable=False)
    data_type = Column(String(50), nullable=False)  # matches, standings, teams
    fetched_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_sync():
    """同步获取数据库会话（非依赖注入用）"""
    db = SessionLocal()
    return db
