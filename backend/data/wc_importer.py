"""
世界杯数据导入器 — 从 WorldCup2026.xlsx 导入

Sheet 说明:
  - WorldCup2026Qualifiers (889场): 预选赛，含赔率、统计、xG
  - WorldCup2022 (64场): 正赛
  - WorldCup2018 (64场): 正赛
  - WorldCup2014 (64场): 正赛

用法:
    python -c "from backend.data.wc_importer import import_all_wc; import_all_wc()"
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict

import pandas as pd
from sqlalchemy.orm import Session

from backend.database import get_db_sync, Match, Team, League
from backend.data.csv_importer import _ensure_team

logger = logging.getLogger(__name__)

EXCEL_PATH = "/home/ai/桌面/WorldCup2026.xlsx"

# 联赛映射: (code, name)
LEAGUES = {
    "qualifiers": ("WCQ", "世界杯预选赛"),
    "wc2022": ("WC2022", "2022世界杯"),
    "wc2018": ("WC2018", "2018世界杯"),
    "wc2014": ("WC2014", "2014世界杯"),
}


def _ensure_league(db: Session, code: str, name: str) -> int:
    """确保联赛存在，返回 league_id"""
    league = db.query(League).filter(League.code == code).first()
    if not league:
        league = League(name=name, code=code)
        db.add(league)
        db.commit()
        db.refresh(league)
        logger.info(f"  🆕 新建联赛: {league.name} (id={league.id}, code={league.code})")
    return league.id


def _parse_date(date_val) -> Optional[datetime]:
    """解析 Excel 中的日期"""
    if pd.isna(date_val):
        return None
    try:
        # pandas Timestamp or datetime
        if hasattr(date_val, 'to_pydatetime'):
            return date_val.to_pydatetime()
        return datetime.combine(date_val, datetime.min.time())
    except:
        try:
            return datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
        except:
            return None


def import_qualifiers(db: Session = None) -> dict:
    """导入世界杯预选赛数据"""
    return _import_sheet(db, "WorldCup2026Qualifiers", "qualifiers",
                         odds_cols=("H_Max", "D_Max", "A_Max"),
                         stat_cols=["HS","AS","HST","AST","HF","AF","HC","AC","HY","AY","HR","AR"],
                         xg_cols=["HxG","AxG"])


def import_wc_tournament(db: Session = None, sheet: str = "WorldCup2022",
                          league_key: str = "wc2022") -> dict:
    """导入世界杯正赛数据"""
    return _import_sheet(db, sheet, league_key,
                         odds_cols=("bet365-H", "bet365-D", "bet365-A"),
                         stat_cols=["HS","AS","HST","AST","HF","AF","HC","AC","HY","AY","HR","AR"])


def import_all_tournaments(db: Session = None) -> dict:
    """导入所有世界杯正赛 (2022/2018/2014)"""
    results = {}
    tournaments = [
        ("WorldCup2022", "wc2022"),
        ("WorldCup2018", "wc2018"),
        ("WorldCup2014", "wc2014"),
    ]
    for sheet, key in tournaments:
        print(f"\n--- {LEAGUES[key][1]} ---")
        try:
            r = import_wc_tournament(db, sheet, key)
            results[key] = r
            print(f"  新增 {r['new']} 场, 跳过 {r['skipped']} 场(重复)")
        except Exception as e:
            logger.error(f"{sheet} 导入失败: {e}")
            print(f"  ❌ 失败: {e}")
    return results


def _import_sheet(db, sheet_name: str, league_key: str,
                  odds_cols: tuple = None,
                  stat_cols: list = None,
                  xg_cols: list = None) -> dict:
    """通用 Excel sheet 导入器"""
    close_db = False
    if db is None:
        db = get_db_sync()
        close_db = True

    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name)
        league_code, league_name = LEAGUES[league_key]
        league_id = _ensure_league(db, league_code, league_name)
        league_id_int = league_id

        # 推断赛季
        dates = df["Date"].dropna()
        if len(dates) > 0:
            first = _parse_date(dates.iloc[0])
            last = _parse_date(dates.iloc[-1])
            season = f"{first.year}" if first else "unknown"
        else:
            season = "unknown"

        new_count = 0
        for _, row in df.iterrows():
            try:
                home = str(row.get("Home", row.get("team1", ""))).strip()
                away = str(row.get("Away", row.get("team2", ""))).strip()
                date_val = row.get("Date")

                if not home or not away or home == "nan" or away == "nan":
                    continue

                # 比分
                hg_col = "HG" if "HG" in df.columns else "HGFT"
                ag_col = "AG" if "AG" in df.columns else "AGFT"
                score_h = int(row[hg_col]) if pd.notna(row.get(hg_col)) else None
                score_a = int(row[ag_col]) if pd.notna(row.get(ag_col)) else None

                # 日期
                utc_date = _parse_date(date_val)
                if not utc_date:
                    continue

                # 去重检测
                date_str = utc_date.strftime("%d/%m/%Y")
                if _match_exists_wc(db, home, away, date_str, league_id_int):
                    continue

                # 赛果
                winner = None
                if score_h is not None and score_a is not None:
                    if score_h > score_a:
                        winner = "HOME_TEAM"
                    elif score_h < score_a:
                        winner = "AWAY_TEAM"
                    else:
                        winner = "DRAW"

                status = "FINISHED" if score_h is not None else "SCHEDULED"

                # 确保球队
                home_team_obj = _ensure_team(db, home, league_id_int)
                away_team_obj = _ensure_team(db, away, league_id_int)
                home_team_id = home_team_obj.id if home_team_obj else 0
                away_team_id = away_team_obj.id if away_team_obj else 0

                # 构建 extra_data
                extra = {"source": f"WorldCup2026.xlsx/{sheet_name}"}

                # 赔率
                if odds_cols:
                    h_odds = row.get(odds_cols[0])
                    d_odds = row.get(odds_cols[1])
                    a_odds = row.get(odds_cols[2])
                    if pd.notna(h_odds): extra[odds_cols[0]] = float(h_odds)
                    if pd.notna(d_odds): extra[odds_cols[1]] = float(d_odds)
                    if pd.notna(a_odds): extra[odds_cols[2]] = float(a_odds)

                # 统计数据
                if stat_cols:
                    for col in stat_cols:
                        if col in row and pd.notna(row[col]):
                            try:
                                extra[col] = int(float(row[col]))
                            except:
                                extra[col] = float(row[col]) if pd.notna(row[col]) else None

                # xG 数据
                if xg_cols:
                    for col in xg_cols:
                        if col in row and pd.notna(row[col]):
                            extra[col] = round(float(row[col]), 2)

                # 比赛记录
                match = Match(
                    league_id=league_id_int,
                    season=season,
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
                logger.warning(f"  行导入失败: {e}")
                continue

        db.commit()
        total_rows = len(df)
        logger.info(f"  ✅ {league_name}: 新增 {new_count}, 跳过 {total_rows - new_count} 场(重复)")

        return {
            "new": new_count,
            "skipped": total_rows - new_count,
            "total_in_csv": total_rows,
            "season": season,
        }

    finally:
        if close_db:
            db.close()


def _match_exists_wc(db: Session, home: str, away: str, date_str: str,
                      league_id: int) -> bool:
    """世界杯专用去重检测"""
    try:
        day, month, year = date_str.split("/")
        match_date = datetime(int(year), int(month), int(day))
    except:
        return False

    existing = db.query(Match).filter(
        Match.home_team_name == home,
        Match.away_team_name == away,
        Match.league_id == league_id,
    ).all()

    for m in existing:
        if m.utc_date and abs((m.utc_date - match_date).days) <= 2:
            return True
    return False


def import_all_wc(db: Session = None) -> dict:
    """导入所有世界杯数据（预选赛 + 正赛）"""
    close_db = False
    if db is None:
        db = get_db_sync()
        close_db = True

    try:
        results = {}

        print(f"\n{'='*50}")
        print(f"🌍 导入世界杯数据")
        print(f"{'='*50}")

        # 预选赛
        print(f"\n--- {LEAGUES['qualifiers'][1]} ---")
        r = import_qualifiers(db)
        results["qualifiers"] = r
        print(f"  新增 {r['new']} 场, 跳过 {r['skipped']} 场(重复)")

        # 正赛
        for sheet, key in [("WorldCup2022", "wc2022"),
                            ("WorldCup2018", "wc2018"),
                            ("WorldCup2014", "wc2014")]:
            print(f"\n--- {LEAGUES[key][1]} ---")
            try:
                r2 = import_wc_tournament(db, sheet, key)
                results[key] = r2
                print(f"  新增 {r2['new']} 场, 跳过 {r2['skipped']} 场(重复)")
            except Exception as e:
                logger.error(f"{sheet} 失败: {e}")
                print(f"  ❌ 失败: {e}")

        total = sum(v["new"] for v in results.values())
        print(f"\n{'='*50}")
        print(f"📊 世界杯总计新增: {total} 场比赛")
        print(f"{'='*50}")

        return {"total_new": total, "leagues": results}

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import_all_wc()
