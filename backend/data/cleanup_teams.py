"""
数据库球队去重清理脚本

合并因 CSV 简称匹配失败而产生的重复球队：
  - "Man City" → "Manchester City FC"
  - "Man United" → "Manchester United FC"
  - "Nott'm Forest" → "Nottingham Forest FC"
  - "Wolves" → "Wolverhampton Wanderers FC"

同时更新所有关联的比赛记录，并重新计算 Elo。
"""
import logging
from sqlalchemy import text
from backend.database import get_db_sync, Match, Team
from backend.models.elo import EloRating

logger = logging.getLogger(__name__)

# 需要合并的球队对：（CSV 创建的错误球队名, 标准全称）
MERGE_PAIRS = [
    ("Man City", "Manchester City FC"),
    ("Man United", "Manchester United FC"),
    ("Nott'm Forest", "Nottingham Forest FC"),
    ("Wolves", "Wolverhampton Wanderers FC"),
]


def find_team(db, name: str) -> Team | None:
    """精确查找球队"""
    return db.query(Team).filter(Team.name == name).first()


def merge_duplicates(dry_run: bool = True) -> list[dict]:
    """合并重复球队"""
    db = get_db_sync()
    results = []

    try:
        for wrong_name, correct_name in MERGE_PAIRS:
            wrong_team = find_team(db, wrong_name)
            correct_team = find_team(db, correct_name)

            if not wrong_team:
                results.append({
                    "wrong": wrong_name,
                    "correct": correct_name,
                    "status": "skipped",
                    "reason": f"'{wrong_name}' 不存在",
                })
                continue

            if not correct_team:
                results.append({
                    "wrong": wrong_name,
                    "correct": correct_name,
                    "status": "skipped",
                    "reason": f"'{correct_name}' 不存在",
                })
                continue

            if wrong_team.id == correct_team.id:
                results.append({
                    "wrong": wrong_name,
                    "correct": correct_name,
                    "status": "skipped",
                    "reason": "已是同一球队",
                })
                continue

            # 统计
            home_cnt = db.query(Match).filter(Match.home_team_id == wrong_team.id).count()
            away_cnt = db.query(Match).filter(Match.away_team_id == wrong_team.id).count()
            total = home_cnt + away_cnt

            if dry_run:
                results.append({
                    "wrong": wrong_name,
                    "wrong_id": wrong_team.id,
                    "wrong_elo": round(wrong_team.elo_rating, 1),
                    "correct": correct_name,
                    "correct_id": correct_team.id,
                    "correct_elo": round(correct_team.elo_rating, 1),
                    "matches_to_update": total,
                    "home_matches": home_cnt,
                    "away_matches": away_cnt,
                    "status": "would_merge",
                })
                continue

            # 执行合并
            db.execute(
                text("UPDATE matches SET home_team_id = :to WHERE home_team_id = :from"),
                {"to": correct_team.id, "from": wrong_team.id},
            )
            db.execute(
                text("UPDATE matches SET away_team_id = :to WHERE away_team_id = :from"),
                {"to": correct_team.id, "from": wrong_team.id},
            )

            # 删除空壳球队
            db.delete(wrong_team)
            db.commit()

            results.append({
                "wrong": wrong_name,
                "wrong_id": wrong_team.id,
                "correct": correct_name,
                "correct_id": correct_team.id,
                "matches_updated": total,
                "status": "merged",
            })
            logger.info(f"  ✅ 合并 '{wrong_name}' (ID={wrong_team.id}) → '{correct_name}' (ID={correct_team.id}), {total} 场比赛已更新")

    finally:
        db.close()

    return results


def rebuild_elo():
    """合并后重新计算所有 Elo 评分"""
    from datetime import datetime
    from backend.database import get_db_sync, Match
    from backend.models.elo import EloRating
    from backend.config import settings

    logger.info("🔄 重新计算 Elo 评分...")
    db = get_db_sync()
    try:
        elo = EloRating(db)
        leagues = [2021, 2002, 2014, 2019, 2015]

        for league_id in leagues:
            matches = db.query(Match).filter(
                Match.league_id == league_id,
                Match.status == "FINISHED",
                Match.score_home.isnot(None),
                Match.score_away.isnot(None),
            ).order_by(Match.utc_date.asc()).all()

            team_ratings = {}
            for m in matches:
                r_h = team_ratings.get(m.home_team_id, elo.initial_rating)
                r_a = team_ratings.get(m.away_team_id, elo.initial_rating)
                new_h, new_a = elo.update_ratings(r_h, r_a, m.score_home, m.score_away)
                team_ratings[m.home_team_id] = new_h
                team_ratings[m.away_team_id] = new_a

            # 写回数据库
            for team_id, rating in team_ratings.items():
                team = db.query(Team).filter(Team.id == team_id).first()
                if team:
                    team.elo_rating = rating
            db.commit()
            logger.info(f"  联赛 {league_id}: {len(team_ratings)} 支球队已更新")

        logger.info("✅ Elo 重新计算完成")
    finally:
        db.close()


def fix_display_names():
    """修复比赛表中 CSV 简称显示名 → 标准全称"""
    from backend.database import get_db_sync, Match

    db = get_db_sync()
    try:
        mapping = {
            # CSV 简称 → 标准全称（与 NAME_MAPPING 一致，加上模糊匹配有效的也统一）
            "Man City": "Manchester City FC",
            "Man United": "Manchester United FC",
            "Nott'm Forest": "Nottingham Forest FC",
            "Wolves": "Wolverhampton Wanderers FC",
            "Arsenal": "Arsenal FC",
            "Aston Villa": "Aston Villa FC",
            "Bournemouth": "AFC Bournemouth",
            "Brighton": "Brighton & Hove Albion FC",
            "Burnley": "Burnley FC",
            "Chelsea": "Chelsea FC",
            "Crystal Palace": "Crystal Palace FC",
            "Everton": "Everton FC",
            "Fulham": "Fulham FC",
            "Leeds": "Leeds United FC",
            "Liverpool": "Liverpool FC",
            "Newcastle": "Newcastle United FC",
            "Sunderland": "Sunderland AFC",
            "Tottenham": "Tottenham Hotspur FC",
            "West Ham": "West Ham United FC",
        }

        updated_home = 0
        updated_away = 0

        for short_name, full_name in mapping.items():
            r = db.execute(
                text("UPDATE matches SET home_team_name = :full WHERE home_team_name = :short"),
                {"full": full_name, "short": short_name},
            )
            updated_home += r.rowcount
            r = db.execute(
                text("UPDATE matches SET away_team_name = :full WHERE away_team_name = :short"),
                {"full": full_name, "short": short_name},
            )
            updated_away += r.rowcount

        db.commit()
        logger.info(f"✅ 显示名修复: home_team_name {updated_home} 行, away_team_name {updated_away} 行")
        return updated_home + updated_away
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    import sys

    # 先 dry-run 预览
    print("\n🔍 预览：将合并的重复球队\n")
    preview = merge_duplicates(dry_run=True)
    for p in preview:
        if p["status"] == "would_merge":
            print(f"  ⚠️  '{p['wrong']}' (ID={p['wrong_id']}, Elo={p['wrong_elo']}) → "
                  f"'{p['correct']}' (ID={p['correct_id']}, Elo={p['correct_elo']})")
            print(f"      影响 {p['matches_to_update']} 场比赛 ({p['home_matches']}主 + {p['away_matches']}客)")
        else:
            print(f"  ✅ {p['status']}: {p.get('reason', '')}")

    if "--dry-run" in sys.argv:
        print("\n💡 添加 --execute 参数执行合并")
        sys.exit(0)

    if "--execute" in sys.argv:
        print("\n🚀 执行合并...\n")
        results = merge_duplicates(dry_run=False)
        for r in results:
            if r["status"] == "merged":
                print(f"  ✅ {r['wrong']} → {r['correct']}: {r['matches_updated']} 场比赛已更新")
            else:
                print(f"  ℹ️  {r['status']}: {r.get('reason', '')}")

        # 修复显示名
        print("\n🎨 修复比赛显示名...")
        cnt = fix_display_names()
        print(f"  ✅ {cnt} 行已更新")

        # 重新计算 Elo
        rebuild_elo()

        print("\n🎉 全部完成！")
