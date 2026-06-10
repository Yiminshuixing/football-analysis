"""
中文球队名称 ↔ 英文数据库名称 映射表
用于用户在输入框输入中文队名时自动匹配到数据库中的英文名称
"""
from typing import Dict, List, Tuple

# 中文名称 → 数据库英文名称 映射
CN_NAME_MAP: Dict[str, str] = {
    # ========== 英超 ==========
    "阿森纳": "Arsenal FC",
    "阿斯顿维拉": "Aston Villa FC",
    "伯恩茅斯": "AFC Bournemouth",
    "布伦特福德": "Brentford",
    "布莱顿": "Brighton & Hove Albion FC",
    "伯恩利": "Burnley FC",
    "切尔西": "Chelsea FC",
    "水晶宫": "Crystal Palace FC",
    "埃弗顿": "Everton FC",
    "富勒姆": "Fulham FC",
    "伊普斯维奇": "Ipswich Town FC",
    "利兹联": "Leeds United FC",
    "莱斯特城": "Leicester City FC",
    "利物浦": "Liverpool FC",
    "卢顿": "Luton Town FC",
    "曼城": "Manchester City FC",
    "曼联": "Manchester United FC",
    "曼彻斯特城": "Manchester City FC",
    "曼彻斯特联": "Manchester United FC",
    "纽卡斯尔": "Newcastle United FC",
    "纽卡斯尔联": "Newcastle United FC",
    "诺维奇": "Norwich City FC",
    "诺丁汉森林": "Nottingham Forest FC",
    "谢菲尔德联": "Sheffield United FC",
    "南安普顿": "Southampton FC",
    "桑德兰": "Sunderland AFC",
    "热刺": "Tottenham Hotspur FC",
    "托特纳姆热刺": "Tottenham Hotspur FC",
    "沃特福德": "Watford FC",
    "西布朗": "West Bromwich Albion FC",
    "西布朗维奇": "West Bromwich Albion FC",
    "西汉姆联": "West Ham United FC",
    "西汉姆": "West Ham United FC",
    "狼队": "Wolverhampton Wanderers FC",
    "伍尔弗汉普顿": "Wolverhampton Wanderers FC",
    # ========== 德甲 ==========
    "奥格斯堡": "FC Augsburg",
    "拜仁慕尼黑": "FC Bayern München",
    "拜仁": "FC Bayern München",
    "比勒费尔德": "Arminia Bielefeld",
    "波鸿": "Bochum",
    "达姆施塔特": "SV Darmstadt 98",
    "多特蒙德": "Borussia Dortmund",
    "多特": "Borussia Dortmund",
    "法兰克福": "Eintracht Frankfurt",
    "科隆": "1. FC Köln",
    "弗赖堡": "SC Freiburg",
    "菲尔特": "SpVgg Greuther Fürth",
    "汉堡": "Hamburger SV",
    "海登海姆": "1. FC Heidenheim 1846",
    "柏林赫塔": "Hertha BSC",
    "霍芬海姆": "TSG 1899 Hoffenheim",
    "荷尔斯泰因基尔": "Holstein Kiel",
    "基尔": "Holstein Kiel",
    "勒沃库森": "Bayer 04 Leverkusen",
    "药厂": "Bayer 04 Leverkusen",
    "门兴格拉德巴赫": "Borussia Mönchengladbach",
    "门兴": "Borussia Mönchengladbach",
    "美因茨": "1. FSV Mainz 05",
    "RB莱比锡": "RB Leipzig",
    "莱比锡": "RB Leipzig",
    "沙尔克04": "FC Schalke 04",
    "沙尔克": "FC Schalke 04",
    "圣保利": "FC St. Pauli 1910",
    "斯图加特": "VfB Stuttgart",
    "柏林联合": "1. FC Union Berlin",
    "云达不莱梅": "SV Werder Bremen",
    "不莱梅": "SV Werder Bremen",
    "沃尔夫斯堡": "VfL Wolfsburg",
    "狼堡": "VfL Wolfsburg",
    # ========== 西甲 ==========
    "阿拉维斯": "Deportivo Alavés",
    "阿尔梅里亚": "UD Almería",
    "毕尔巴鄂竞技": "Athletic Club",
    "毕尔巴鄂": "Athletic Club",
    "马德里竞技": "Club Atlético de Madrid",
    "马竞": "Club Atlético de Madrid",
    "巴塞罗那": "FC Barcelona",
    "巴萨": "FC Barcelona",
    "贝蒂斯": "Real Betis Balompié",
    "皇家贝蒂斯": "Real Betis Balompié",
    "加的斯": "Cádiz CF",
    "塞尔塔": "RC Celta de Vigo",
    "埃瓦尔": "SD Eibar",
    "埃尔切": "Elche CF",
    "西班牙人": "RCD Espanyol de Barcelona",
    "赫塔费": "Getafe CF",
    "赫罗纳": "Girona FC",
    "格拉纳达": "Granada CF",
    "韦斯卡": "SD Huesca",
    "拉帕马斯": "UD Las Palmas",
    "拉斯帕尔马斯": "UD Las Palmas",
    "莱加内斯": "CD Leganés",
    "莱万特": "Levante UD",
    "马洛卡": "RCD Mallorca",
    "奥萨苏纳": "CA Osasuna",
    "奥维耶多": "Real Oviedo",
    "巴列卡诺": "Rayo Vallecano de Madrid",
    "皇马": "Real Madrid CF",
    "皇家马德里": "Real Madrid CF",
    "皇家社会": "Real Sociedad de Fútbol",
    "巴拉多利德": "Real Valladolid CF",
    "塞维利亚": "Sevilla FC",
    "瓦伦西亚": "Valencia CF",
    "比利亚雷亚尔": "Villarreal CF",
    "黄潜": "Villarreal CF",
    # ========== 意甲 ==========
    "亚特兰大": "Atalanta BC",
    "贝内文托": "Benevento Calcio",
    "博洛尼亚": "Bologna FC 1909",
    "卡利亚里": "Cagliari Calcio",
    "科莫": "Como 1907",
    "克雷莫纳": "US Cremonese",
    "克罗托内": "FC Crotone",
    "恩波利": "Empoli FC",
    "佛罗伦萨": "ACF Fiorentina",
    "弗罗西诺内": "Frosinone Calcio",
    "热那亚": "Genoa CFC",
    "国际米兰": "FC Internazionale Milano",
    "国米": "FC Internazionale Milano",
    "尤文图斯": "Juventus FC",
    "尤文": "Juventus FC",
    "拉齐奥": "SS Lazio",
    "莱切": "US Lecce",
    "AC米兰": "AC Milan",
    "米兰": "AC Milan",
    "蒙扎": "AC Monza",
    "那不勒斯": "SSC Napoli",
    "帕尔马": "Parma Calcio 1913",
    "比萨": "AC Pisa 1909",
    "罗马": "AS Roma",
    "萨勒尼塔纳": "US Salernitana 1919",
    "桑普多利亚": "UC Sampdoria",
    "萨索洛": "US Sassuolo Calcio",
    "斯佩齐亚": "Spezia Calcio",
    "都灵": "Torino FC",
    "乌迪内斯": "Udinese Calcio",
    "威尼斯": "Venezia FC",
    "维罗纳": "Hellas Verona FC",
    # ========== 法甲 ==========
    "阿雅克肖": "AC Ajaccio",
    "昂热": "Angers SCO",
    "欧塞尔": "AJ Auxerre",
    "波尔多": "FC Girondins de Bordeaux",
    "布雷斯特": "Stade Brestois 29",
    "克莱蒙": "Clermont Foot 63",
    "第戎": "Dijon FCO",
    "勒阿弗尔": "Le Havre AC",
    "朗斯": "Racing Club de Lens",
    "里尔": "Lille OSC",
    "洛里昂": "FC Lorient",
    "里昂": "Olympique Lyonnais",
    "马赛": "Olympique de Marseille",
    "梅斯": "FC Metz",
    "摩纳哥": "AS Monaco FC",
    "蒙彼利埃": "Montpellier HSC",
    "南特": "FC Nantes",
    "尼斯": "OGC Nice",
    "尼姆": "Nîmes Olympique",
    "巴黎FC": "Paris FC",
    "巴黎圣日耳曼": "Paris Saint-Germain FC",
    "大巴黎": "Paris Saint-Germain FC",
    "巴黎": "Paris Saint-Germain FC",
    "兰斯": "Stade de Reims",
    "雷恩": "Stade Rennais FC 1901",
    "圣埃蒂安": "AS Saint-Étienne",
    "斯特拉斯堡": "RC Strasbourg Alsace",
    "图卢兹": "Toulouse FC",
    "特鲁瓦": "ESTAC Troyes",
}


def cn_to_en(chinese_name: str) -> Tuple[str, bool]:
    """中文队名 → 英文队名

    Returns:
        (英文队名, 是否找到匹配)
    """
    name = chinese_name.strip()
    if name in CN_NAME_MAP:
        return CN_NAME_MAP[name], True
    # 尝试部分匹配
    for cn, en in CN_NAME_MAP.items():
        if cn in name or name in cn:
            return en, True
    return name, False


def search_teams(query: str) -> List[Tuple[str, str, str]]:
    """搜索球队，返回 (中文名, 英文名, 联赛) 列表"""
    results = []
    q = query.strip().lower()
    if not q:
        return results
    for cn_name, en_name in CN_NAME_MAP.items():
        if q in cn_name or q in en_name.lower():
            # 确定联赛
            league = "英超"
            if en_name in ["FC Augsburg", "FC Bayern München", "Arminia Bielefeld", "Bochum",
                           "SV Darmstadt 98", "Borussia Dortmund", "Eintracht Frankfurt",
                           "1. FC Köln", "SC Freiburg", "SpVgg Greuther Fürth", "Hamburger SV",
                           "1. FC Heidenheim 1846", "Hertha BSC", "TSG 1899 Hoffenheim",
                           "Holstein Kiel", "Bayer 04 Leverkusen", "Borussia Mönchengladbach",
                           "1. FSV Mainz 05", "RB Leipzig", "FC Schalke 04", "FC St. Pauli 1910",
                           "VfB Stuttgart", "1. FC Union Berlin", "SV Werder Bremen", "VfL Wolfsburg"]:
                league = "德甲"
            elif en_name in ["Deportivo Alavés", "UD Almería", "Athletic Club", "Club Atlético de Madrid",
                             "FC Barcelona", "Real Betis Balompié", "Cádiz CF", "RC Celta de Vigo",
                             "SD Eibar", "Elche CF", "RCD Espanyol de Barcelona", "Getafe CF",
                             "Girona FC", "Granada CF", "SD Huesca", "UD Las Palmas", "CD Leganés",
                             "Levante UD", "RCD Mallorca", "CA Osasuna", "Real Oviedo",
                             "Rayo Vallecano de Madrid", "Real Madrid CF", "Real Sociedad de Fútbol",
                             "Real Valladolid CF", "Sevilla FC", "Valencia CF", "Villarreal CF"]:
                league = "西甲"
            elif en_name in ["Atalanta BC", "Benevento Calcio", "Bologna FC 1909", "Cagliari Calcio",
                             "Como 1907", "US Cremonese", "FC Crotone", "Empoli FC", "ACF Fiorentina",
                             "Frosinone Calcio", "Genoa CFC", "FC Internazionale Milano",
                             "Juventus FC", "SS Lazio", "US Lecce", "AC Milan", "AC Monza",
                             "SSC Napoli", "Parma Calcio 1913", "AC Pisa 1909", "AS Roma",
                             "US Salernitana 1919", "UC Sampdoria", "US Sassuolo Calcio",
                             "Spezia Calcio", "Torino FC", "Udinese Calcio", "Venezia FC",
                             "Hellas Verona FC"]:
                league = "意甲"
            elif en_name in ["AC Ajaccio", "Angers SCO", "AJ Auxerre", "FC Girondins de Bordeaux",
                             "Stade Brestois 29", "Clermont Foot 63", "Dijon FCO", "Le Havre AC",
                             "Racing Club de Lens", "Lille OSC", "FC Lorient", "Olympique Lyonnais",
                             "Olympique de Marseille", "FC Metz", "AS Monaco FC", "Montpellier HSC",
                             "FC Nantes", "OGC Nice", "Nîmes Olympique", "Paris FC",
                             "Paris Saint-Germain FC", "Stade de Reims", "Stade Rennais FC 1901",
                             "AS Saint-Étienne", "RC Strasbourg Alsace", "Toulouse FC",
                             "ESTAC Troyes"]:
                league = "法甲"

            entry = (cn_name, en_name, league)
            if entry not in results:
                results.append(entry)
    return results[:20]


def get_all_teams_cn() -> List[Tuple[str, str, str]]:
    """获取所有球队的中文名→英文名映射列表"""
    seen = set()
    results = []
    league_map = {}
    # 用上面的规则反推联赛
    for en_name in set(CN_NAME_MAP.values()):
        if en_name in ["FC Augsburg", "FC Bayern München", "Arminia Bielefeld", "Bochum",
                       "SV Darmstadt 98", "Borussia Dortmund", "Eintracht Frankfurt",
                       "1. FC Köln", "SC Freiburg", "SpVgg Greuther Fürth", "Hamburger SV",
                       "1. FC Heidenheim 1846", "Hertha BSC", "TSG 1899 Hoffenheim",
                       "Holstein Kiel", "Bayer 04 Leverkusen", "Borussia Mönchengladbach",
                       "1. FSV Mainz 05", "RB Leipzig", "FC Schalke 04", "FC St. Pauli 1910",
                       "VfB Stuttgart", "1. FC Union Berlin", "SV Werder Bremen", "VfL Wolfsburg"]:
            league_map[en_name] = "德甲"
        elif en_name in ["Deportivo Alavés", "UD Almería", "Athletic Club", "Club Atlético de Madrid",
                         "FC Barcelona", "Real Betis Balompié", "Cádiz CF", "RC Celta de Vigo",
                         "SD Eibar", "Elche CF", "RCD Espanyol de Barcelona", "Getafe CF",
                         "Girona FC", "Granada CF", "SD Huesca", "UD Las Palmas", "CD Leganés",
                         "Levante UD", "RCD Mallorca", "CA Osasuna", "Real Oviedo",
                         "Rayo Vallecano de Madrid", "Real Madrid CF", "Real Sociedad de Fútbol",
                         "Real Valladolid CF", "Sevilla FC", "Valencia CF", "Villarreal CF"]:
            league_map[en_name] = "西甲"
        elif en_name in ["Atalanta BC", "Benevento Calcio", "Bologna FC 1909", "Cagliari Calcio",
                         "Como 1907", "US Cremonese", "FC Crotone", "Empoli FC", "ACF Fiorentina",
                         "Frosinone Calcio", "Genoa CFC", "FC Internazionale Milano",
                         "Juventus FC", "SS Lazio", "US Lecce", "AC Milan", "AC Monza",
                         "SSC Napoli", "Parma Calcio 1913", "AC Pisa 1909", "AS Roma",
                         "US Salernitana 1919", "UC Sampdoria", "US Sassuolo Calcio",
                         "Spezia Calcio", "Torino FC", "Udinese Calcio", "Venezia FC",
                         "Hellas Verona FC"]:
            league_map[en_name] = "意甲"
        elif en_name in ["AC Ajaccio", "Angers SCO", "AJ Auxerre", "FC Girondins de Bordeaux",
                         "Stade Brestois 29", "Clermont Foot 63", "Dijon FCO", "Le Havre AC",
                         "Racing Club de Lens", "Lille OSC", "FC Lorient", "Olympique Lyonnais",
                         "Olympique de Marseille", "FC Metz", "AS Monaco FC", "Montpellier HSC",
                         "FC Nantes", "OGC Nice", "Nîmes Olympique", "Paris FC",
                         "Paris Saint-Germain FC", "Stade de Reims", "Stade Rennais FC 1901",
                         "AS Saint-Étienne", "RC Strasbourg Alsace", "Toulouse FC",
                         "ESTAC Troyes"]:
            league_map[en_name] = "法甲"
        else:
            league_map[en_name] = "英超"

    for cn_name, en_name in CN_NAME_MAP.items():
        key = (cn_name, en_name)
        if key not in seen:
            seen.add(key)
            results.append((cn_name, en_name, league_map.get(en_name, "英超")))
    return results
