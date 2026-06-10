"""Football-Data.org API 客户端"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db_sync, DataCache, League, Team, Match

logger = logging.getLogger(__name__)

# 联赛名称映射
LEAGUE_NAMES = {
    2021: "Premier League",
    2002: "Bundesliga",
    2014: "La Liga",
    2019: "Serie A",
    2015: "Ligue 1",
    2003: "Eredivisie",
    2016: "Championship",
    2000: "FIFA World Cup",
    2001: "UEFA Champions League",
}


def get_headers() -> dict:
    """获取API请求头"""
    if not settings.football_api_key:
        logger.warning("未设置 FOOTBALL_API_KEY，请配置 .env 文件")
    return {
        "X-Auth-Token": settings.football_api_key,
    }


class FootballDataFetcher:
    """Football-Data.org 数据获取器"""

    def __init__(self):
        self.base_url = settings.football_api_base_url
        self.headers = get_headers()
        self.client = httpx.Client(timeout=30.0)

    def _get(self, path: str, params: dict = None) -> Optional[dict]:
        """发送 GET 请求"""
        url = f"{self.base_url}{path}"
        try:
            resp = self.client.get(url, headers=self.headers, params=params)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                logger.warning("API 速率限制达到，请稍后再试")
                return None
            elif resp.status_code == 403:
                logger.warning("API Key 无效或未授权")
                return None
            else:
                logger.warning(f"API 请求失败: {url} -> {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"API 请求异常: {e}")
            return None

    def fetch_league_matches(self, league_id: int, date_from: str = None, date_to: str = None) -> Optional[List[dict]]:
        """获取联赛的所有比赛，使用日期范围过滤"""
        params = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if not date_from and not date_to:
            # 默认获取最近 3 个月
            from datetime import datetime, timedelta
            params["dateFrom"] = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
            params["dateTo"] = datetime.utcnow().strftime("%Y-%m-%d")
        data = self._get(f"/competitions/{league_id}/matches", params)
        if data and "matches" in data:
            return data["matches"]
        return None

    def fetch_league_standings(self, league_id: int) -> Optional[dict]:
        """获取联赛积分榜"""
        data = self._get(f"/competitions/{league_id}/standings")
        if data and "standings" in data:
            return data["standings"]
        return None

    def fetch_team_matches(self, team_id: int, limit: int = 50) -> Optional[List[dict]]:
        """获取球队近期比赛"""
        params = {"limit": limit}
        data = self._get(f"/teams/{team_id}/matches", params)
        if data and "matches" in data:
            return data["matches"]
        return None

    def fetch_league_info(self, league_id: int) -> Optional[dict]:
        """获取联赛信息"""
        return self._get(f"/competitions/{league_id}")

    def close(self):
        self.client.close()


class DataSyncService:
    """数据同步服务：从API获取数据并写入本地数据库"""

    def __init__(self, db: Session = None):
        self.fetcher = FootballDataFetcher()
        self.db = db or get_db_sync()

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        cache = self.db.query(DataCache).filter(DataCache.cache_key == cache_key).first()
        if cache and cache.expires_at > datetime.utcnow():
            return True
        return False

    def _set_cache(self, cache_key: str, data_type: str, ttl_minutes: int = 60):
        """设置缓存标记"""
        cache = self.db.query(DataCache).filter(DataCache.cache_key == cache_key).first()
        now = datetime.utcnow()
        if cache:
            cache.fetched_at = now
            cache.expires_at = now + timedelta(minutes=ttl_minutes)
        else:
            cache = DataCache(
                cache_key=cache_key,
                data_type=data_type,
                fetched_at=now,
                expires_at=now + timedelta(minutes=ttl_minutes),
            )
            self.db.add(cache)
        self.db.commit()

    def sync_league_info(self, league_id: int) -> bool:
        """同步联赛信息"""
        cache_key = f"league_info_{league_id}"
        data = self.fetcher.fetch_league_info(league_id)
        if not data:
            return False

        league = self.db.query(League).filter(League.id == league_id).first()
        if not league:
            league = League(id=league_id)

        league.name = data.get("name", LEAGUE_NAMES.get(league_id, f"League {league_id}"))
        league.code = data.get("code", "")
        league.emblem_url = (data.get("emblem") or
                            (data.get("area") or {}).get("flag") or "")
        league.current_matchday = (data.get("currentSeason") or {}).get("currentMatchday", 0)
        self.db.merge(league)
        self.db.commit()
        return True

    def sync_matches(self, league_id: int) -> int:
        """同步指定联赛的比赛数据，返回同步的比赛数量"""
        cache_key = f"matches_{league_id}"
        if self._is_cache_valid(cache_key):
            return 0

        # 获取这个赛季的完整数据
        # 2025-26 赛季约从 2025-08 到 2026-05
        from datetime import datetime
        current_year = datetime.utcnow().year
        date_from = f"{current_year - 1}-08-01"
        date_to = datetime.utcnow().strftime("%Y-%m-%d")

        matches = self.fetcher.fetch_league_matches(league_id, date_from, date_to)
        if not matches:
            logger.warning(f"无法获取联赛 {league_id} 的比赛数据")
            return 0

        count = 0
        for match_data in matches:
            try:
                match_id = match_data["id"]
                home_team = match_data.get("homeTeam", {})
                away_team = match_data.get("awayTeam", {})
                score = match_data.get("score", {})
                full_time = score.get("fullTime", {}) if score else {}

                # 确保球队存在
                self._ensure_team(home_team)
                self._ensure_team(away_team)

                # 更新或创建比赛
                match = self.db.query(Match).filter(Match.id == match_id).first()
                if not match:
                    match = Match(id=match_id)

                match.league_id = league_id
                match.season = match_data.get("season", {}).get("startDate", "")[:4] if match_data.get("season") else season
                match.matchday = match_data.get("matchday")
                match.status = match_data.get("status", "SCHEDULED")

                # 日期解析
                date_str = match_data.get("utcDate", "")
                try:
                    match.utc_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except:
                    match.utc_date = datetime.utcnow()

                match.home_team_id = home_team.get("id", 0)
                match.away_team_id = away_team.get("id", 0)
                match.home_team_name = home_team.get("name") or home_team.get("shortName")
                match.away_team_name = away_team.get("name") or away_team.get("shortName")

                if full_time:
                    match.score_home = full_time.get("home")
                    match.score_away = full_time.get("away")
                    if match.score_home is not None and match.score_away is not None:
                        if match.score_home > match.score_away:
                            match.winner = "HOME_TEAM"
                        elif match.score_home < match.score_away:
                            match.winner = "AWAY_TEAM"
                        else:
                            match.winner = "DRAW"

                # 序列化额外数据
                import json
                extra = {}
                for key in ["referees", "odds", "stage", "group"]:
                    if key in match_data:
                        extra[key] = match_data[key]
                match.extra_data = json.dumps(extra, ensure_ascii=False) if extra else None

                self.db.merge(match)
                count += 1
            except Exception as e:
                logger.error(f"处理比赛数据出错: {e}")
                continue

        self.db.commit()
        # 缓存标记，比赛数据 TTL 为 6 小时
        self._set_cache(cache_key, "matches", ttl_minutes=360)
        logger.info(f"联赛 {league_id} 同步完成，共 {count} 场比赛")
        return count

    def _ensure_team(self, team_data: dict):
        """确保球队存在于数据库中"""
        if not team_data or "id" not in team_data:
            return
        team_id = team_data["id"]
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            team = Team(id=team_id)
            team.name = team_data.get("name") or team_data.get("shortName") or f"Team {team_id}"
            team.short_name = team_data.get("shortName")
            team.tla = team_data.get("tla")
            team.crest_url = team_data.get("crest") or team_data.get("crestUrl")
            team.venue = (team_data.get("venue") or
                         (team_data.get("address") or ""))
            self.db.add(team)
            self.db.commit()

    def sync_all_leagues(self) -> Dict[int, int]:
        """同步所有关注联赛，返回 {league_id: match_count}"""
        results = {}
        for league_id in settings.league_id_list:
            self.sync_league_info(league_id)
            count = self.sync_matches(league_id)
            results[league_id] = count
        return results

    def close(self):
        self.fetcher.close()
        self.db.close()
