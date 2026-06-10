"""
中超球队名称清理 — 合并同一俱乐部的重复球队

原因:
1. 跨赛季更名（Shanghai SIPG → Shanghai Port FC）
2. 中英文双语名（上海海港 = Shanghai Port FC）
"""
import json
import logging
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from backend.database import get_db_sync, Match, Team

logger = logging.getLogger(__name__)

# 中超联赛 ID
CSL_LEAGUE_ID = 2022

# 合并映射: 旧名称 → 标准名称
# 用于合并不同赛季/不同语言下同一俱乐部的记录
MERGE_MAP = {
    # ===== 上海海港 (Shanghai Port FC) =====
    "Shanghai SIPG": "Shanghai Port FC",
    "上海海港": "Shanghai Port FC",
    # ===== 上海申花 =====
    "上海申花": "Shanghai Shenhua",
    # ===== 山东泰山 (Shandong Taishan) =====
    "山东泰山": "Shandong Taishan",
    # ===== 大连英博 =====
    "Dalian Yifang FC": "Dalian Yingbo",
    "Dalian Pro": "Dalian Yingbo",
    "大连英博": "Dalian Yingbo",
    # ===== 北京国安 (Beijing Guoan) =====
    "北京国安": "Beijing Guoan",
    # ===== 天津津门虎 (Tianjin Jinmen Tiger) =====
    "Tianjin Teda": "Tianjin Jinmen Tiger",
    "天津津门虎": "Tianjin Jinmen Tiger",
    # ===== 河南 (Henan FC) =====
    "Henan Jianye": "Henan FC",
    "河南": "Henan FC",
    # ===== 浙江 (Zhejiang Professional) =====
    "浙江": "Zhejiang Professional",
    # ===== 成都蓉城 (Chengdu Rongcheng) =====
    "成都蓉城": "Chengdu Rongcheng",
    # ===== 武汉三镇 (Wuhan Three Towns) =====
    "武汉三镇": "Wuhan Three Towns",
    # ===== 云南玉昆 (Yunnan Yukun) =====
    "云南玉昆": "Yunnan Yukun",
    # ===== 青岛海牛 (Qingdao Hainiu) =====
    "青岛海牛": "Qingdao Hainiu",
    # ===== 青岛西海岸 (Qingdao West Coast) =====
    "青岛西海岸": "Qingdao West Coast",
    # ===== 深圳新鹏城 (Shenzhen Peng City) =====
    "深圳新鹏城": "Shenzhen Peng City",
}

# 需要保留的中文新球队（无英文对应记录）
NEW_CHINESE_TEAMS = {
    "辽宁铁人",   # Liaoning Iron Man
    "重庆铜梁龙", # Chongqing Tongliang Long
}


def count_csl_matches(db: Session, team_name: str) -> int:
    """统计某球队名下的中超比赛数"""
    return db.query(Match).filter(
        (Match.home_team_name == team_name) | (Match.away_team_name == team_name),
        Match.league_id == CSL_LEAGUE_ID,
    ).count()


def merge_csl_teams(dry_run: bool = True, db: Session = None) -> List[dict]:
    """合并中超重复球队

    Args:
        dry_run: True=只预览，False=实际执行
        db: 数据库会话

    Returns:
        [{"from": 旧名, "to": 标准名, "matches": N}]
    """
    close_db = False
    if db is None:
        db = get_db_sync()
        close_db = True

    try:
        operations = []

        for old_name, canonical_name in MERGE_MAP.items():
            # 检查旧名称是否存在
            old_team = db.query(Team).filter(Team.name == old_name).first()
            if not old_team:
                continue

            # 检查标准名称是否存在
            canonical_team = db.query(Team).filter(Team.name == canonical_name).first()
            if not canonical_team:
                # 标准名称不存在 → 直接重命名旧球队
                match_count = count_csl_matches(db, old_name)
                if match_count == 0:
                    continue
                operations.append({
                    "from": old_name, "to": canonical_name,
                    "action": "rename", "matches": match_count,
                })
                if not dry_run:
                    old_team.name = canonical_name
                    # 更新 match 表中的 team_name
                    for m in db.query(Match).filter(
                        Match.league_id == CSL_LEAGUE_ID,
                        (Match.home_team_name == old_name) | (Match.away_team_name == old_name),
                    ).all():
                        if m.home_team_name == old_name:
                            m.home_team_name = canonical_name
                        if m.away_team_name == old_name:
                            m.away_team_name = canonical_name
                continue

            # 两个都存在 → 合并
            match_count = count_csl_matches(db, old_name)
            if match_count == 0:
                continue
            operations.append({
                "from": old_name, "to": canonical_name,
                "action": "merge", "matches": match_count,
            })

            if not dry_run:
                # 更新 match 表中的 team_name
                for m in db.query(Match).filter(
                    Match.league_id == CSL_LEAGUE_ID,
                    (Match.home_team_name == old_name) | (Match.away_team_name == old_name),
                ).all():
                    if m.home_team_name == old_name:
                        m.home_team_name = canonical_name
                        m.home_team_id = canonical_team.id
                    if m.away_team_name == old_name:
                        m.away_team_name = canonical_name
                        m.away_team_id = canonical_team.id

                # 删除旧球队
                db.delete(old_team)

        if not dry_run:
            db.commit()

        return operations

    finally:
        if close_db:
            db.close()


def print_merge_report(operations: List[dict], dry_run: bool = True):
    """打印合并报告"""
    if not operations:
        print("没有需要合并的球队 ✅")
        return

    mode = "🔍 预览模式（dry-run）" if dry_run else "✂️ 实际执行"
    print(f"\n{'='*50}")
    print(f"📋 中超球队合并报告 ({mode})")
    print(f"{'='*50}")

    by_action = {"rename": [], "merge": []}
    total_matches = 0
    for op in operations:
        by_action[op["action"]].append(op)
        total_matches += op["matches"]

    if by_action["rename"]:
        print(f"\n📝 需重命名 ({len(by_action['rename'])} 项):")
        for op in by_action["rename"]:
            print(f"  {op['from']:30s} → {op['to']:25s} ({op['matches']} 场)")

    if by_action["merge"]:
        print(f"\n🔗 需合并 ({len(by_action['merge'])} 项):")
        for op in by_action["merge"]:
            print(f"  {op['from']:30s} → {op['to']:25s} ({op['matches']} 场)")

    print(f"\n总计: {len(operations)} 项操作, 涉及 {total_matches} 场比赛")
    print(f"{'='*50}")


def rebuild_csl_elo(db: Session = None):
    """重新计算中超球队的 Elo 评分"""
    from backend.models.elo import EloRating
    from backend.database import Match

    close_db = False
    if db is None:
        db = get_db_sync()
        close_db = True

    try:
        # 获取所有中超比赛
        matches = db.query(Match).filter(
            Match.league_id == CSL_LEAGUE_ID,
            Match.status == "FINISHED",
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        ).order_by(Match.utc_date.asc()).all()

        elo = EloRating(db=db, home_advantage=0)

        for m in matches:
            home_team = db.query(Team).filter(Team.id == m.home_team_id).first()
            away_team = db.query(Team).filter(Team.id == m.away_team_id).first()
            if not home_team or not away_team:
                continue

            home_elo = home_team.elo_rating or 1500
            away_elo = away_team.elo_rating or 1500

            new_home_elo, new_away_elo = elo.update_ratings(
                home_elo, away_elo,
                m.score_home, m.score_away,
            )

            home_team.elo_rating = new_home_elo
            away_team.elo_rating = new_away_elo

        db.commit()
        logger.info("  ✅ 中超 Elo 重算完成")
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="中超球队名称清理")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="预览模式（不实际修改）")
    parser.add_argument("--execute", action="store_true",
                        help="实际执行合并")
    parser.add_argument("--rebuild-elo", action="store_true",
                        help="合并后重算 Elo")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    dry_run = not args.execute
    ops = merge_csl_teams(dry_run=dry_run)
    print_merge_report(ops, dry_run=dry_run)

    if not dry_run and args.rebuild_elo:
        print("\n🔄 重算 Elo 评分...")
        rebuild_csl_elo()
