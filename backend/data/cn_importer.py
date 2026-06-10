"""
中超数据导入器 — 从 github.com/Yiminshuixing/football.json 导入 cn.1.json

数据格式:
    { "name": "China | Super League 2025",
      "matches": [
        { "round": "Matchday 1",
          "date": "2025-02-22", "time": "19:35",
          "team1": "Chengdu Rongcheng", "team2": "Wuhan Three Towns",
          "score": { "ft": [1, 0], "ht": [0, 0] }
        }, ...
      ]
    }

用法:
    python -c "from backend.data.cn_importer import import_all_csl; import_all_csl()"
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict

from sqlalchemy.orm import Session

from backend.database import get_db_sync, Match, Team, League
from backend.data.csv_importer import _ensure_team, match_exists

logger = logging.getLogger(__name__)

# 本地克隆的 football.json 仓库路径
JSON_REPO_PATH = "/tmp/football_json"

CSL_CODE = "CN1"
CSL_NAME = "中超"

# 中文球队名 → 英文标准名映射（防止 2026 数据创建重复中文球队）
CN_NAME_MAP = {
    "上海海港": "Shanghai Port FC",
    "上海申花": "Shanghai Shenhua",
    "山东泰山": "Shandong Taishan",
    "北京国安": "Beijing Guoan",
    "天津津门虎": "Tianjin Jinmen Tiger",
    "河南": "Henan FC",
    "浙江": "Zhejiang Professional",
    "成都蓉城": "Chengdu Rongcheng",
    "大连英博": "Dalian Yingbo",
    "武汉三镇": "Wuhan Three Towns",
    "云南玉昆": "Yunnan Yukun",
    "青岛海牛": "Qingdao Hainiu",
    "青岛西海岸": "Qingdao West Coast",
    "深圳新鹏城": "Shenzhen Peng City",
    # 新球队（暂无英文名，保留中文）
    # "辽宁铁人" — keep as-is
    # "重庆铜梁龙" — keep as-is
}

# 跨赛季更名映射（旧英文名 → 新英文名）
EN_NAME_MAP = {
    "Shanghai SIPG": "Shanghai Port FC",
    "Dalian Yifang FC": "Dalian Yingbo",
    "Dalian Pro": "Dalian Yingbo",
    "Tianjin Teda": "Tianjin Jinmen Tiger",
    "Henan Jianye": "Henan FC",
}


def _canonical_team_name(name: str) -> str:
    """将中文名/旧英文名统一为标准英文名"""
    return CN_NAME_MAP.get(name, EN_NAME_MAP.get(name, name))


def _parse_round(round_str: str) -> int:
    """'Matchday 5' → 5"""
    try:
        return int(round_str.replace("Matchday", "").strip())
    except:
        return 0


def _ensure_csl_league(db: Session) -> int:
    """确保 中超 联赛在数据库中存在，返回 league_id"""
    league = db.query(League).filter(League.code == CSL_CODE).first()
    if not league:
        league = League(name=CSL_NAME, code=CSL_CODE)
        db.add(league)
        db.commit()
        db.refresh(league)
        logger.info(f"  🆕 新建联赛: {league.name} (id={league.id}, code={league.code})")
    return league.id


def import_csl_json(db: Session, json_path: str, season: str) -> dict:
    """导入单个 cn.1.json 文件

    Args:
        db: 数据库会话
        json_path: cn.1.json 文件路径
        season: 赛季名，如 "2025"

    Returns:
        dict: {"new": 新增数, "skipped": 跳过数, "total_in_csv": JSON总场次, "season": 赛季}
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    matches = data.get("matches", [])
    league_id = _ensure_csl_league(db)
    league_id_int = league_id

    logger.info(f"  📄 {data['name']} — {len(matches)} 场比赛")

    if not matches:
        return {"new": 0, "skipped": 0, "total_in_csv": 0, "season": season}

    new_count = 0
    for m in matches:
        try:
            home = _canonical_team_name(m["team1"].strip())
            away = _canonical_team_name(m["team2"].strip())
            date_str = m["date"]  # "2025-02-22"
            time_str = m.get("time", "20:00")

            if not home or not away or not date_str:
                continue

            # JSON 日期是 YYYY-MM-DD，转成 match_exists 期望的 DD/MM/YYYY 格式
            date_parts = date_str.split("-")
            date_for_dedup = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"

            # 去重
            if match_exists(db, home, away, date_for_dedup, league_id_int):
                continue

            # 解析比分
            score = m.get("score", {})
            ft = score.get("ft", [None, None])
            ht = score.get("ht", [None, None])

            score_h = int(ft[0]) if ft[0] is not None else None
            score_a = int(ft[1]) if ft[1] is not None else None

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

            # 解析日期
            try:
                utc_date = datetime(
                    int(date_parts[0]), int(date_parts[1]), int(date_parts[2]),
                    int(time_str.split(":")[0]), int(time_str.split(":")[1]),
                )
            except:
                utc_date = datetime(
                    int(date_parts[0]), int(date_parts[1]), int(date_parts[2]), 20, 0, 0
                )

            # 轮次
            matchday = _parse_round(m.get("round", ""))

            # 确保球队存在
            home_team_obj = _ensure_team(db, home, league_id_int)
            away_team_obj = _ensure_team(db, away, league_id_int)
            home_team_id = home_team_obj.id if home_team_obj else 0
            away_team_id = away_team_obj.id if away_team_obj else 0

            # extra_data — 存半场比分等额外信息
            extra = {
                "half_time_score": f"{ht[0]}-{ht[1]}" if ht[0] is not None else None,
                "source": "football.json (中超)",
                "round": m.get("round", ""),
            }
            extra = {k: v for k, v in extra.items() if v is not None}

            # 比赛记录
            match = Match(
                league_id=league_id_int,
                season=season,
                matchday=matchday,
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
    logger.info(f"  ✅ 新增 {new_count} 场，跳过 {len(matches) - new_count} 场(重复)")
    return {
        "new": new_count,
        "skipped": len(matches) - new_count,
        "total_in_csv": len(matches),
        "season": season,
    }


def import_all_csl(json_repo: str = None, db: Session = None) -> dict:
    """导入所有赛季的中超数据

    Args:
        json_repo: football.json 仓库路径，默认 /tmp/football_json

    Returns:
        dict: {"total_new": 总新增, "seasons": {赛季: {导入结果}}}
    """
    if json_repo is None:
        json_repo = JSON_REPO_PATH

    cn_files = sorted(
        os.path.join(root, f)
        for root, _, files in os.walk(json_repo)
        for f in files
        if f == "cn.1.json"
    )

    close_db = False
    if db is None:
        db = get_db_sync()
        close_db = True

    try:
        total_new = 0
        season_results = {}

        print(f"\n{'='*50}")
        print(f"⚽ 导入中超数据 (football.json)")
        print(f"{'='*50}")

        for fp in cn_files:
            # 从路径推断赛季
            rel = os.path.relpath(fp, json_repo)
            season_dir = os.path.dirname(rel)  # "2025", "2026", "2019", "2020"
            season = season_dir  # 中超使用自然年赛季

            print(f"\n--- 赛季 {season} ---")
            try:
                result = import_csl_json(db, fp, season)
                total_new += result["new"]
                season_results[season] = result
                print(f"  新增 {result['new']} 场, 跳过 {result['skipped']} 场(重复)")
            except Exception as e:
                logger.error(f"赛季 {season} 导入失败: {e}")
                print(f"  ❌ 失败: {e}")
                season_results[season] = {"new": 0, "skipped": 0,
                                           "total_in_csv": 0, "error": str(e)}

        print(f"\n{'='*50}")
        print(f"📊 中超总计新增: {total_new} 场比赛")
        print(f"{'='*50}")

        return {
            "total_new": total_new,
            "leagues": {CSL_NAME: {"new": total_new}},
            "seasons": season_results,
        }

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import_all_csl()
