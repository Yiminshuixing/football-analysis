"""
CSV 赔率数据导入脚本
从 football-data.co.uk 格式的 CSV 导入比赛数据+赔率到 SQLite
"""
import csv
import json
import os
import re
from datetime import datetime
from typing import Optional

from backend.database import get_db_sync, Team, Match, League

# CSV 联赛码 → 内部 League ID
LEAGUE_MAP = {
    "E0": 2021,   # Premier League
    "D1": 2002,   # Bundesliga
    "SP1": 2014,  # La Liga
    "I1": 2019,   # Serie A
    "F1": 2015,   # Ligue 1
}

LEAGUE_NAMES = {
    2021: "Premier League",
    2002: "Bundesliga",
    2014: "Primera Division",
    2019: "Serie A",
    2015: "Ligue 1",
}

# 赛季码 → season 标签
SEASON_MAP = {
    "2021": "2020-21",
    "2122": "2021-22",
    "2223": "2022-23",
    "2324": "2023-24",
    "2425": "2024-25",
    "2526": "2025-26",
}

# CSV 球队名 → 数据库球队名 映射
TEAM_NAME_MAP = {
    "Arsenal": "Arsenal FC",
    "Aston Villa": "Aston Villa FC",
    "Bournemouth": "AFC Bournemouth",
    "Brighton": "Brighton & Hove Albion FC",
    "Burnley": "Burnley FC",
    "Chelsea": "Chelsea FC",
    "Crystal Palace": "Crystal Palace FC",
    "Everton": "Everton FC",
    "Fulham": "Fulham FC",
    "Ipswich": "Ipswich Town FC",
    "Leeds": "Leeds United FC",
    "Leicester": "Leicester City FC",
    "Liverpool": "Liverpool FC",
    "Luton": "Luton Town FC",
    "Man City": "Manchester City FC",
    "Man United": "Manchester United FC",
    "Newcastle": "Newcastle United FC",
    "Norwich": "Norwich City FC",
    "Nott'm Forest": "Nottingham Forest FC",
    "Sheffield United": "Sheffield United FC",
    "Southampton": "Southampton FC",
    "Sunderland": "Sunderland AFC",
    "Tottenham": "Tottenham Hotspur FC",
    "Watford": "Watford FC",
    "West Brom": "West Bromwich Albion FC",
    "West Ham": "West Ham United FC",
    "Wolves": "Wolverhampton Wanderers FC",
    "Bayern Munich": "FC Bayern München",
    "Dortmund": "Borussia Dortmund",
    "RB Leipzig": "RB Leipzig",
    "Leverkusen": "Bayer 04 Leverkusen",
    "M'gladbach": "Borussia Mönchengladbach",
    "Ein Frankfurt": "Eintracht Frankfurt",
    "Wolfsburg": "VfL Wolfsburg",
    "FC Koln": "1. FC Köln",
    "Mainz": "1. FSV Mainz 05",
    "Bielefeld": "Arminia Bielefeld",
    "Union Berlin": "1. FC Union Berlin",
    "Stuttgart": "VfB Stuttgart",
    "Werder Bremen": "SV Werder Bremen",
    "Freiburg": "SC Freiburg",
    "Hoffenheim": "TSG 1899 Hoffenheim",
    "Augsburg": "FC Augsburg",
    "Heidenheim": "1. FC Heidenheim 1846",
    "Darmstadt": "SV Darmstadt 98",
    "Schalke 04": "FC Schalke 04",
    "St Pauli": "FC St. Pauli 1910",
    "Hertha": "Hertha BSC",
    "Hamburg": "Hamburger SV",
    "Holstein Kiel": "Holstein Kiel",
    "Greuther Furth": "SpVgg Greuther Fürth",
    "Pisa": "AC Pisa 1909",
    "Barcelona": "FC Barcelona",
    "Real Madrid": "Real Madrid CF",
    "Ath Madrid": "Club Atlético de Madrid",
    "Ath Bilbao": "Athletic Club",
    "Sociedad": "Real Sociedad de Fútbol",
    "Betis": "Real Betis Balompié",
    "Villarreal": "Villarreal CF",
    "Valencia": "Valencia CF",
    "Sevilla": "Sevilla FC",
    "Celta": "RC Celta de Vigo",
    "Vallecano": "Rayo Vallecano de Madrid",
    "Osasuna": "CA Osasuna",
    "Getafe": "Getafe CF",
    "Mallorca": "RCD Mallorca",
    "Granada": "Granada CF",
    "Cadiz": "Cádiz CF",
    "Almeria": "UD Almería",
    "Elche": "Elche CF",
    "Espanol": "RCD Espanyol de Barcelona",
    "Alaves": "Deportivo Alavés",
    "Girona": "Girona FC",
    "Valladolid": "Real Valladolid CF",
    "Las Palmas": "UD Las Palmas",
    "Leganes": "CD Leganés",
    "Eibar": "SD Eibar",
    "Huesca": "SD Huesca",
    "Huesca": "SD Huesca",
    "Oviedo": "Real Oviedo",
    "Levante": "Levante UD",
    "Inter": "FC Internazionale Milano",
    "Milan": "AC Milan",
    "Juventus": "Juventus FC",
    "Napoli": "SSC Napoli",
    "Roma": "AS Roma",
    "Atalanta": "Atalanta BC",
    "Lazio": "SS Lazio",
    "Fiorentina": "ACF Fiorentina",
    "Torino": "Torino FC",
    "Bologna": "Bologna FC 1909",
    "Udinese": "Udinese Calcio",
    "Sampdoria": "UC Sampdoria",
    "Sassuolo": "US Sassuolo Calcio",
    "Genoa": "Genoa CFC",
    "Cagliari": "Cagliari Calcio",
    "Verona": "Hellas Verona FC",
    "Spezia": "Spezia Calcio",
    "Salernitana": "US Salernitana 1919",
    "Empoli": "Empoli FC",
    "Venezia": "Venezia FC",
    "Lecce": "US Lecce",
    "Cremonese": "US Cremonese",
    "Monza": "AC Monza",
    "Frosinone": "Frosinone Calcio",
    "Como": "Como 1907",
    "Parma": "Parma Calcio 1913",
    "Benevento": "Benevento Calcio",
    "Crotone": "FC Crotone",
    "Paris SG": "Paris Saint-Germain FC",
    "Marseille": "Olympique de Marseille",
    "Lyon": "Olympique Lyonnais",
    "Monaco": "AS Monaco FC",
    "Lille": "Lille OSC",
    "Nice": "OGC Nice",
    "Rennes": "Stade Rennais FC 1901",
    "Lens": "Racing Club de Lens",
    "Strasbourg": "RC Strasbourg Alsace",
    "Nantes": "FC Nantes",
    "Montpellier": "Montpellier HSC",
    "Toulouse": "Toulouse FC",
    "Angers": "Angers SCO",
    "Brest": "Stade Brestois 29",
    "Reims": "Stade de Reims",
    "Metz": "FC Metz",
    "Lorient": "FC Lorient",
    "Clermont": "Clermont Foot 63",
    "Ajaccio": "AC Ajaccio",
    "Auxerre": "AJ Auxerre",
    "Troyes": "ESTAC Troyes",
    "Bordeaux": "FC Girondins de Bordeaux",
    "Lille": "Lille OSC",
    "Nimes": "Nîmes Olympique",
    "Dijon": "Dijon FCO",
    "St Etienne": "AS Saint-Étienne",
    "Le Havre": "Le Havre AC",
    "Paris FC": "Paris FC",
}


def normalize_team_name(csv_name: str) -> str:
    """将 CSV 球队名映射到数据库名"""
    name = csv_name.strip()
    if name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[name]
    # 模糊匹配：去掉空格和特殊字符
    for csv_key, db_name in TEAM_NAME_MAP.items():
        if csv_key.lower().replace(" ", "").replace("-", "") == name.lower().replace(" ", "").replace("-", ""):
            return db_name
    return name


def get_or_create_team(db, team_name: str) -> Team:
    """根据名称查找或创建球队"""
    # 先精确匹配
    team = db.query(Team).filter(Team.name == team_name).first()
    if team:
        return team

    # 模糊匹配（去掉 FC、后缀等）
    base = re.sub(r'\s+(FC|CF|SC|SV|US|AC|AS)\s*$', '', team_name).strip()
    if base != team_name:
        team = db.query(Team).filter(Team.name.like(f"%{base}%")).first()
        if team:
            return team

    # 创建新球队
    max_id = db.query(Team).order_by(Team.id.desc()).first()
    new_id = (max_id.id + 1) if max_id else 10000
    team = Team(
        id=new_id,
        name=team_name,
        short_name=team_name[:20],
        elo_rating=1500.0,
    )
    db.add(team)
    db.commit()
    return team


def parse_date(date_str: str) -> Optional[datetime]:
    """解析 DD/MM/YYYY 格式日期"""
    try:
        parts = date_str.strip().split("/")
        if len(parts) == 3:
            return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
    except:
        pass
    return None


def import_csv_files(csv_folder: str):
    """导入所有 CSV 文件"""
    db = get_db_sync()

    # 清空旧比赛数据
    db.query(Match).delete()
    db.commit()

    total = 0
    errors = 0

    csv_files = sorted([f for f in os.listdir(csv_folder) if f.endswith('.csv')])

    for filename in csv_files:
        # 从文件名解析赛季和联赛
        parts = filename.replace('.csv', '').split('_')
        if len(parts) != 2:
            print(f"  ⏭️ 跳过: {filename} (文件名格式不对)")
            continue

        season_code, league_code = parts
        if league_code not in LEAGUE_MAP:
            print(f"  ⏭️ 跳过: {filename} (未知联赛码 {league_code})")
            continue

        league_id = LEAGUE_MAP[league_code]
        season = SEASON_MAP.get(season_code, season_code)

        # 确保联赛存在
        league = db.query(League).filter(League.id == league_id).first()
        if not league:
            league = League(
                id=league_id,
                name=LEAGUE_NAMES.get(league_id, f"League {league_id}"),
                code=league_code,
            )
            db.add(league)
            db.commit()

        filepath = os.path.join(csv_folder, filename)
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            file_count = 0

            for row in reader:
                try:
                    home_name = normalize_team_name(row.get('HomeTeam', ''))
                    away_name = normalize_team_name(row.get('AwayTeam', ''))

                    if not home_name or not away_name:
                        continue

                    home_team = get_or_create_team(db, home_name)
                    away_team = get_or_create_team(db, away_name)

                    utc_date = parse_date(row.get('Date', ''))
                    if not utc_date:
                        continue

                    # 比分
                    fthg = row.get('FTHG')
                    ftag = row.get('FTAG')
                    score_home = int(fthg) if fthg and fthg.isdigit() else None
                    score_away = int(ftag) if ftag and ftag.isdigit() else None

                    ftr = row.get('FTR', '')
                    if ftr == 'H':
                        winner = 'HOME_TEAM'
                    elif ftr == 'A':
                        winner = 'AWAY_TEAM'
                    elif ftr == 'D':
                        winner = 'DRAW'
                    else:
                        winner = None

                    status = 'FINISHED' if score_home is not None else 'SCHEDULED'

                    # 收集所有赔率/统计数据到 extra_data
                    non_basic_keys = {'Div','Date','Time','HomeTeam','AwayTeam','FTHG','FTAG','FTR',
                                      'HTHG','HTAG','HTR','Referee','HS','AS','HST','AST',
                                      'HF','AF','HC','AC','HY','AY','HR','AR',
                                      'B365H','B365D','B365A','BWH','BWD','BWA',
                                      'PSH','PSD','PSA',
                                      'BFDH','BFDD','BFDA','BVH','BVD','BVA',
                                      'CLH','CLD','CLA','LBH','LBD','LBA',
                                      'MaxH','MaxD','MaxA','AvgH','AvgD','AvgA',
                                      'BFEH','BFED','BFEA',
                                      'B365>2.5','B365<2.5','P>2.5','P<2.5',
                                      'Max>2.5','Max<2.5','Avg>2.5','Avg<2.5',
                                      'BFE>2.5','BFE<2.5',
                                      'AHh','B365AHH','B365AHA','PAHH','PAHA',
                                      'MaxAHH','MaxAHA','AvgAHH','AvgAHA',
                                      'BFEAHH','BFEAHA',
                                      'B365CH','B365CD','B365CA',
                                      'BFDCH','BFDCD','BFDCA',
                                      'BMGMCH','BMGMCD','BMGMCA',
                                      'BVCH','BVCD','BVCA',
                                      'BWCH','BWCD','BWCA',
                                      'CLCH','CLCD','CLCA',
                                      'LBCH','LBCD','LBCA',
                                      'PSCH','PSCD','PSCA',
                                      'MaxCH','MaxCD','MaxCA',
                                      'AvgCH','AvgCD','AvgCA',
                                      'BFECH','BFECD','BFECA',
                                      'B365C>2.5','B365C<2.5','PC>2.5','PC<2.5',
                                      'MaxC>2.5','MaxC<2.5','AvgC>2.5','AvgC<2.5',
                                      'BFEC>2.5','BFEC<2.5',
                                      'AHCh','B365CAHH','B365CAHA','PCAHH','PCAHA',
                                      'MaxCAHH','MaxCAHA','AvgCAHH','AvgCAHA',
                                      'BFECAHH','BFECAHA',
                                      'BMGMH','BMGMD','BMGMA', 'B365H','B365D','B365A',
                    }

                    extra_data = {}
                    for k, v in row.items():
                        if k and v and v.strip():
                            clean_k = k.strip().lstrip('﻿')
                            extra_data[clean_k] = v.strip()

                    # 使用时间戳生成唯一 match_id
                    match_id = int(utc_date.strftime('%y%m%d')) * 100000 + hash(f"{home_team.id}{away_team.id}{utc_date.isoformat()}") % 100000

                    match = Match(
                        id=match_id,
                        league_id=league_id,
                        season=season,
                        matchday=None,
                        utc_date=utc_date,
                        status=status,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        home_team_name=home_team.name,
                        away_team_name=away_team.name,
                        score_home=score_home,
                        score_away=score_away,
                        winner=winner,
                        extra_data=json.dumps(extra_data, ensure_ascii=False),
                    )
                    db.add(match)
                    file_count += 1
                    total += 1

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"      错误: {e}")
                    continue

            db.commit()
            print(f"  ✅ {filename:20s} {file_count:4d} 场比赛")

    db.close()
    print(f"\n{'='*50}")
    print(f"导入完成: 共 {total} 场比赛")
    if errors:
        print(f"错误: {errors} 条（已跳过）")


if __name__ == "__main__":
    csv_folder = "/media/ai/02E613486F0D401B/real_odds/"
    print("开始导入 CSV 赔率数据...\n")
    import_csv_files(csv_folder)
