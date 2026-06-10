"""
Football-Data.co.uk CSV 导入器

从 football-data.co.uk 下载 CSV 并写入本地 SQLite 数据库。
支持增量更新（已有比赛跳过，新增比赛插入）。

用法:
    python -c "from backend.data.csv_importer import import_all; import_all()"

新赛季开始后，CSV 链接中的 2526 改为 2627 即可。
"""
import csv
import io
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from urllib.request import urlopen

from sqlalchemy.orm import Session

from backend.database import get_db_sync, Match, Team
from backend.config import settings

logger = logging.getLogger(__name__)

# 联赛代码映射: CSV 代码 → (联赛ID, 联赛名称)
LEAGUE_CSV_MAP = {
    # 英超
    "E0": (2021, "Premier League"),
    # 德甲
    "D1": (2002, "Bundesliga"),
    # 西甲
    "SP1": (2014, "La Liga"),
    # 意甲
    "I1": (2019, "Serie A"),
    # 法甲
    "F1": (2015, "Ligue 1"),
}

# CSV 简称 → 数据库标准全称 映射表
# football-data.co.uk 使用简称（"Man City"），数据库使用全称（"Manchester City FC"）
# 这些映射弥补模糊匹配（ilike）无法处理的简称 → 全称转换
NAME_MAPPING = {
    # ========== 英超 (E0) ==========
    "Man City": "Manchester City FC",
    "Man United": "Manchester United FC",
    "Nott'm Forest": "Nottingham Forest FC",
    "Wolves": "Wolverhampton Wanderers FC",
    # ========== 德甲 (D1) ==========
    "Bayern Munich": "FC Bayern München",
    "Ein Frankfurt": "Eintracht Frankfurt",
    "FC Koln": "1. FC Köln",
    "M'gladbach": "Borussia Mönchengladbach",
    "St Pauli": "FC St. Pauli 1910",
    "Greuther Furth": "SpVgg Greuther Fürth",
    # ========== 西甲 (SP1) ==========
    "Ath Bilbao": "Athletic Club",
    "Ath Madrid": "Club Atlético de Madrid",
    # ========== 意甲 (I1) ==========
    # （所有 CSV 简称均可被 ilike 模糊匹配到）
    # ========== 法甲 (F1) ==========
    "Paris SG": "Paris Saint-Germain FC",
    "St Etienne": "AS Saint-Étienne",
}

# CSV 列的映射关系
# 标准格式字段名 → 含义
REQUIRED_COLUMNS = [
    "Div", "Date", "HomeTeam", "AwayTeam",
    "FTHG", "FTAG", "FTR",  # Full Time Home/Away Goals, Result
]


def _season_code(season: str) -> str:
    """赛季名 '2025-26' → 短代码 '2526'"""
    parts = season.split("-")
    return parts[0][-2:] + parts[1]


def _infer_season(date_str: str) -> str:
    """根据日期推断赛季名，如 '15/08/2025' → '2025-26'"""
    day, month, year = date_str.split("/")
    y = int(year)
    # 8月及以后 → 当前年-下一年
    if int(month) >= 8:
        return f"{y}-{str(y+1)[2:]}"
    else:
        return f"{y-1}-{str(y)[2:]}"


def download_csv(league_code: str, season: str) -> Optional[str]:
    """从 football-data.co.uk 下载 CSV 文本

    Args:
        league_code: CSV 代码 (E0, D1, SP1, I1, F1)
        season: 赛季名 '2025-26'

    Returns:
        CSV 文本内容，失败返回 None
    """
    sc = _season_code(season)
    url = f"https://www.football-data.co.uk/mmz4281/{sc}/{league_code}.csv"
    try:
        logger.info(f"  下载: {url}")
        resp = urlopen(url, timeout=30)
        raw = resp.read()
        # 尝试多种编码
        for enc in ["utf-8-sig", "iso-8859-1", "cp1252"]:
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"  下载失败: {e}")
        return None


def parse_csv(text: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """解析 CSV 文本，返回 (列名列表, 行数据列表)"""
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    return reader.fieldnames or [], rows


def match_exists(db: Session, home_team: str, away_team: str,
                 date_str: str, league_id: int) -> bool:
    """检查比赛是否已存在于数据库（按主客队名+日期+联赛去重）"""
    try:
        day, month, year = date_str.split("/")
        match_date = datetime(int(year), int(month), int(day))
    except:
        return False

    existing = db.query(Match).filter(
        Match.home_team_name.ilike(f"%{home_team}%"),
        Match.away_team_name.ilike(f"%{away_team}%"),
        Match.league_id == league_id,
    ).all()

    for m in existing:
        if m.utc_date and abs((m.utc_date - match_date).days) <= 2:
            return True
    return False


def _ensure_team(db: Session, name: str, league_id: int) -> Optional[Team]:
    """确保球队在 Team 表中存在，返回 Team 对象

    查找顺序:
      1. NAME_MAPPING 表（CSV 简称 → 标准全称）
      2. 精确匹配
      3. 模糊匹配（ilike）
      4. 创建新球队
    """
    if not name:
        return None

    # 1️⃣ 查名称映射表（解决 "Man City" → "Manchester City FC" 等简称问题）
    canonical = NAME_MAPPING.get(name)
    if canonical:
        name = canonical

    # 2️⃣ 精确匹配
    team = db.query(Team).filter(Team.name == name).first()
    if team:
        return team

    # 3️⃣ 模糊匹配
    team = db.query(Team).filter(Team.name.ilike(f"%{name}%")).first()
    if team:
        return team

    # 4️⃣ 建新球队（用 CSV 里的名字）
    team = Team(
        name=name,
        short_name=name[:3].upper(),
        elo_rating=1500.0,
    )
    db.add(team)
    db.commit()
    logger.info(f"  🆕 新建球队: {name}")
    return team


def import_csv_to_db(db: Session, league_code: str, season: str) -> dict:
    """将单个 CSV 导入数据库

    Args:
        db: 数据库会话
        league_code: CSV 代码 (E0, D1, SP1, I1, F1)
        season: 赛季名 '2025-26'

    Returns:
        dict: {"new": 新增数, "skipped": 跳过数, "total_in_csv": CSV总行数, "season": 赛季}
    """
    league_id, league_name = LEAGUE_CSV_MAP[league_code]

    # 检查是否已有数据（330+ 场 ≈ 完整赛季）
    existing_count = db.query(Match).filter(
        Match.league_id == league_id,
        Match.season == season,
        Match.status == "FINISHED",
    ).count()
    if existing_count > 330:
        logger.info(f"  ⏭️ 赛季 {season} 已有 {existing_count} 场，跳过导入")
        return {"new": 0, "skipped": existing_count, "total_in_csv": existing_count,
                "season": season, "skipped_reason": "complete_season"}

    # 下载
    text = download_csv(league_code, season)
    if not text:
        return {"new": 0, "skipped": 0, "total_in_csv": 0,
                "season": season, "skipped_reason": "download_failed"}

    return import_csv_text_to_db(db, league_code, season, text)


def import_csv_text_to_db(db: Session, league_code: str, season: str,
                           csv_text: str,
                           league_id: Optional[int] = None,
                           league_name: Optional[str] = None) -> dict:
    """将 CSV 文本内容导入数据库

    与 import_csv_to_db 相同，但接受已下载的文本（用于手动上传）。

    Args:
        db: 数据库会话
        league_code: CSV 代码 (E0, D1, SP1, I1, F1)，若 league_id 已指定可为任意标识
        season: 赛季名 '2025-26'
        csv_text: CSV 文本内容
        league_id: 联赛 ID（覆盖 LEAGUE_CSV_MAP 查找，用于新建联赛）
        league_name: 联赛名称（覆盖 LEAGUE_CSV_MAP 查找，用于新建联赛）

    Returns:
        dict: {"new": 新增数, "skipped": 跳过数, "total_in_csv": CSV总行数, "season": 赛季}
    """
    # 解析联赛信息：支持传入值覆盖硬编码映射（用于新建联赛）
    if league_id is not None and league_name is not None:
        # 使用调用方传入的联赛信息（新建联赛场景）
        pass
    else:
        # 从硬编码映射查找（五大联赛场景）
        league_id, league_name = LEAGUE_CSV_MAP[league_code]

    # 解析
    fieldnames, rows = parse_csv(csv_text)
    logger.info(f"  CSV 列数: {len(fieldnames)}, 行数: {len(rows)}")

    if not rows:
        return {"new": 0, "skipped": 0, "total_in_csv": 0, "season": season}

    new_count = 0
    for row in rows:
        try:
            home = row.get("HomeTeam", "").strip()
            away = row.get("AwayTeam", "").strip()
            date_str = row.get("Date", "").strip()
            if not home or not away or not date_str:
                continue

            # 去重
            if match_exists(db, home, away, date_str, league_id):
                continue

            # 解析结果
            fthg = row.get("FTHG", "").strip()
            ftag = row.get("FTAG", "").strip()
            ftr = row.get("FTR", "").strip()

            # 构建 extra_data（存所有原始 CSV 字段，包括赔率、统计等）
            extra = dict(row)
            # 清理空值
            extra = {k: v for k, v in extra.items() if v and v.strip()}

            # 日期解析
            try:
                day, month, year = date_str.split("/")
                utc_date = datetime(int(year), int(month), int(day), 20, 0, 0)
            except:
                utc_date = datetime.now()

            # 确保球队存在
            home_team_obj = _ensure_team(db, home, league_id)
            away_team_obj = _ensure_team(db, away, league_id)
            home_team_id = home_team_obj.id if home_team_obj else 0
            away_team_id = away_team_obj.id if away_team_obj else 0

            # 比分
            score_h = int(fthg) if fthg and fthg.isdigit() else None
            score_a = int(ftag) if ftag and ftag.isdigit() else None

            # 赛果判定
            winner = None
            if score_h is not None and score_a is not None:
                if score_h > score_a:
                    winner = "HOME_TEAM"
                elif score_h < score_a:
                    winner = "AWAY_TEAM"
                else:
                    winner = "DRAW"

            status = "FINISHED" if score_h is not None else "SCHEDULED"

            # 推断赛季（如果 CSV 没有按赛季分文件夹的话）
            match_season = season
            if not match_season or match_season == "unknown":
                match_season = _infer_season(date_str)

            # 新建比赛记录（用自动 ID）
            match = Match(
                league_id=league_id,
                season=match_season,
                matchday=0,
                utc_date=utc_date,
                status=status,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                home_team_name=home,
                away_team_name=away,
                score_home=score_h,
                score_away=score_a,
                winner=winner,
                extra_data=json.dumps(extra, ensure_ascii=False),
            )
            db.add(match)
            new_count += 1

        except Exception as e:
            logger.warning(f"  导入行失败: {e}")
            continue

    db.commit()
    logger.info(f"  ✅ 新增 {new_count} 场比赛")
    # 同时返回跳过（重复）数和总数
    return {
        "new": new_count,
        "skipped": len(rows) - new_count,
        "total_in_csv": len(rows),
        "season": season,
    }


def import_league(db: Session, league_id: int, season: str) -> dict:
    """按联赛 ID 导入

    Args:
        db: 数据库会话
        league_id: 内部联赛 ID (2021, 2002, ...)
        season: 赛季名 '2025-26'

    Returns:
        dict: {"new": 新增数, "skipped": 跳过数, "total_in_csv": CSV总行数, "season": 赛季}
    """
    # 查找 CSV 代码
    league_code = None
    for code, (lid, _) in LEAGUE_CSV_MAP.items():
        if lid == league_id:
            league_code = code
            break

    if not league_code:
        logger.warning(f"联赛 {league_id} 没有对应的 CSV 代码")
        return {"new": 0, "skipped": 0, "total_in_csv": 0, "season": season}

    return import_csv_to_db(db, league_code, season)


def import_all(season: str = None, db: Session = None) -> dict:
    """导入所有五大联赛的最新数据

    Args:
        season: 赛季名，None 则根据当前日期推断
        db: 数据库会话，None 则自动创建

    Returns:
        dict: {
            "total_new": 总新增数,
            "season": 赛季,
            "leagues": {联赛名: {"new": 新增, "skipped": 跳过, "total": CSV总行数}},
        }
    """
    if season is None:
        now = datetime.now()
        season = f"{now.year}-{str(now.year+1)[2:]}" if now.month >= 8 \
            else f"{now.year-1}-{str(now.year)[2:]}"

    close_db = False
    if db is None:
        db = get_db_sync()
        close_db = True

    try:
        total_new = 0
        league_results = {}
        league_names = {2021: "英超", 2002: "德甲", 2014: "西甲", 2019: "意甲", 2015: "法甲"}

        print(f"\n{'='*50}")
        print(f"📥 导入 Football-Data.co.uk 数据")
        print(f"   赛季: {season}")
        print(f"{'='*50}")

        for lid, lname in league_names.items():
            print(f"\n--- {lname} ---")
            try:
                result = import_league(db, lid, season)
                league_results[lname] = result
                total_new += result["new"]
                print(f"  {lname}: 新增 {result['new']} 场, 跳过 {result['skipped']} 场(重复)")
            except Exception as e:
                logger.error(f"{lname} 导入失败: {e}")
                print(f"  ❌ {lname}: 失败 - {e}")
                league_results[lname] = {"new": 0, "skipped": 0,
                                          "total": 0, "error": str(e)}

        print(f"\n{'='*50}")
        print(f"📊 总计新增: {total_new} 场比赛")
        print(f"{'='*50}")
        return {
            "total_new": total_new,
            "season": season,
            "leagues": league_results,
        }

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import_all()
