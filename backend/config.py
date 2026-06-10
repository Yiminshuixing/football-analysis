"""应用配置"""
from pydantic_settings import BaseSettings
from typing import List, Dict
import os


class Settings(BaseSettings):
    # Football-Data.org API
    football_api_key: str = ""
    football_api_base_url: str = "https://api.football-data.org/v4"

    # 关注的联赛
    league_ids: str = "2021,2002,2014,2019,2015"

    # 数据库
    database_url: str = "sqlite:///data/football.db"

    # 预测参数（全局默认值）
    poisson_recent_matches: int = 5  # Poisson模型考虑的近期场次数
    elo_initial_rating: float = 1500.0
    elo_home_advantage: float = 100.0  # 默认主场优势
    elo_k_factor: float = 32.0

    # 联赛特定参数表
    # 基于 2020-21 ~ 2025-26 六赛季数据校准
    league_params: Dict[int, dict] = {
        # 英超 — 中等主场优势，高平局率
        2021: {
            "name": "Premier League",
            "elo_home_advantage": 80,
            "dixon_coles_rho": 0.18,
            "poisson_weight": 0.55,
        },
        # 德甲 — 高进球，强主场优势
        2002: {
            "name": "Bundesliga",
            "elo_home_advantage": 115,
            "dixon_coles_rho": 0.14,
            "poisson_weight": 0.60,
        },
        # 西甲 — 强主场优势，偏低进球
        2014: {
            "name": "La Liga",
            "elo_home_advantage": 115,
            "dixon_coles_rho": 0.15,
            "poisson_weight": 0.55,
        },
        # 意甲 — 弱主场优势，低进球，高平局
        2019: {
            "name": "Serie A",
            "elo_home_advantage": 60,
            "dixon_coles_rho": 0.17,
            "poisson_weight": 0.50,
        },
        # 法甲 — 略弱主场优势
        2015: {
            "name": "Ligue 1",
            "elo_home_advantage": 75,
            "dixon_coles_rho": 0.14,
            "poisson_weight": 0.55,
        },
    }

    @property
    def league_id_list(self) -> List[int]:
        return [int(x.strip()) for x in self.league_ids.split(",") if x.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 如果 .env 不存在，尝试从环境变量读取
if not settings.football_api_key:
    settings.football_api_key = os.getenv("FOOTBALL_API_KEY", "")
