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
    # ========== 中超 ==========
    "上海海港": "Shanghai Port FC",
    "上海申花": "Shanghai Shenhua",
    "山东泰山": "Shandong Taishan",
    "北京国安": "Beijing Guoan",
    "成都蓉城": "Chengdu Rongcheng",
    "河南": "Henan FC",
    "河南队": "Henan FC",
    "天津津门虎": "Tianjin Jinmen Tiger",
    "武汉三镇": "Wuhan Three Towns",
    "浙江": "Zhejiang Professional",
    "浙江队": "Zhejiang Professional",
    "云南玉昆": "Yunnan Yukun",
    "大连英博": "Dalian Yingbo",
    "青岛海牛": "Qingdao Hainiu",
    "青岛西海岸": "Qingdao West Coast",
    "深圳新鹏城": "Shenzhen Peng City",
    "梅州客家": "Meizhou Hakka",
    "长春亚泰": "Changchun Yatai",
    "沧州雄狮": "Shijiazhuang Ever Bright",
    "重庆铜梁龙": "Chongqing Tongliang Long",
    "辽宁铁人": "Liaoning Iron Man",
    # 历史名称 - 同队不同名
    "广州队": "Guangzhou Evergrande",
    "广州恒大": "Guangzhou Evergrande",
    "广州富力": "Guangzhou R&F",
    "天津泰达": "Tianjin Teda",
    # ========== 世界杯国家队 ==========
    "中国": "China",
    "中国男足": "China",
    "日本": "Japan",
    "韩国": "South Korea",
    "朝鲜": "North Korea",
    "澳大利亚": "Australia",
    "沙特": "Saudi Arabia",
    "沙特阿拉伯": "Saudi Arabia",
    "伊朗": "Iran",
    "伊拉克": "Iraq",
    "卡塔尔": "Qatar",
    "阿联酋": "United Arab Emirates",
    "乌兹别克斯坦": "Uzbekistan",
    "阿曼": "Oman",
    "巴林": "Bahrain",
    "约旦": "Jordan",
    "叙利亚": "Syria",
    "泰国": "Thailand",
    "越南": "Vietnam",
    "印尼": "Indonesia",
    "马来西亚": "Malaysia",
    "菲律宾": "Philippines",
    "阿根廷": "Argentina",
    "巴西": "Brazil",
    "乌拉圭": "Uruguay",
    "哥伦比亚": "Colombia",
    "智利": "Chile",
    "厄瓜多尔": "Ecuador",
    "秘鲁": "Peru",
    "巴拉圭": "Paraguay",
    "委内瑞拉": "Venezuela",
    "玻利维亚": "Bolivia",
    "英格兰": "England",
    "法国": "France",
    "德国": "Germany",
    "西班牙": "Spain",
    "意大利": "Italy",
    "荷兰": "Netherlands",
    "葡萄牙": "Portugal",
    "比利时": "Belgium",
    "克罗地亚": "Croatia",
    "瑞士": "Switzerland",
    "丹麦": "Denmark",
    "瑞典": "Sweden",
    "挪威": "Norway",
    "波兰": "Poland",
    "奥地利": "Austria",
    "土耳其": "Turkey",
    "捷克": "Czech Republic",
    "乌克兰": "Ukraine",
    "俄罗斯": "Russia",
    "塞尔维亚": "Serbia",
    "希腊": "Greece",
    "罗马尼亚": "Romania",
    "苏格兰": "Scotland",
    "威尔士": "Wales",
    "爱尔兰": "Ireland",
    "北爱尔兰": "Northern Ireland",
    "冰岛": "Iceland",
    "匈牙利": "Hungary",
    "斯洛伐克": "Slovakia",
    "保加利亚": "Bulgaria",
    "墨西哥": "Mexico",
    "美国": "United States",
    "加拿大": "Canada",
    "哥斯达黎加": "Costa Rica",
    "牙买加": "Jamaica",
    "巴拿马": "Panama",
    "洪都拉斯": "Honduras",
    "萨尔瓦多": "El Salvador",
    "海地": "Haiti",
    "尼日利亚": "Nigeria",
    "埃及": "Egypt",
    "摩洛哥": "Morocco",
    "塞内加尔": "Senegal",
    "加纳": "Ghana",
    "喀麦隆": "Cameroon",
    "突尼斯": "Tunisia",
    "阿尔及利亚": "Algeria",
    "科特迪瓦": "Ivory Coast",
    "南非": "South Africa",
    "民主刚果": "D.R. Congo",
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
            elif en_name in ["Shanghai Port FC", "Shanghai Shenhua", "Shandong Taishan",
                             "Beijing Guoan", "Chengdu Rongcheng", "Henan FC",
                             "Tianjin Jinmen Tiger", "Wuhan Three Towns", "Zhejiang Professional",
                             "Yunnan Yukun", "Dalian Yingbo", "Qingdao Hainiu",
                             "Qingdao West Coast", "Shenzhen Peng City", "Meizhou Hakka",
                             "Changchun Yatai", "Guangzhou Evergrande", "Guangzhou R&F",
                             "Wuhan Zall FC", "Hebei China Fortune", "Chongqing Lifan",
                             "Henan Jianye", "Dalian Yifang FC", "Jiāngsū Sūníng",
                             "Tianjin Teda", "Tianjin Tianhai", "Beijing Renhe FC",
                             "Shenzhen FC", "Shanghai SIPG", "Qingdao Huanghai",
                             "Dalian Pro", "Shijiazhuang Ever Bright",
                             "Chongqing Tongliang Long", "Liaoning Iron Man"]:
                league = "中超"

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
        elif en_name in ["Shanghai Port FC", "Shanghai Shenhua", "Shandong Taishan",
                         "Beijing Guoan", "Chengdu Rongcheng", "Henan FC",
                         "Tianjin Jinmen Tiger", "Wuhan Three Towns", "Zhejiang Professional",
                         "Yunnan Yukun", "Dalian Yingbo", "Qingdao Hainiu",
                         "Qingdao West Coast", "Shenzhen Peng City", "Meizhou Hakka",
                         "Changchun Yatai", "Guangzhou Evergrande", "Guangzhou R&F",
                         "Wuhan Zall FC", "Hebei China Fortune", "Chongqing Lifan",
                         "Henan Jianye", "Dalian Yifang FC", "Jiāngsū Sūníng",
                         "Tianjin Teda", "Tianjin Tianhai", "Beijing Renhe FC",
                         "Shenzhen FC", "Shanghai SIPG", "Qingdao Huanghai",
                         "Dalian Pro", "Shijiazhuang Ever Bright",
                         "Chongqing Tongliang Long", "Liaoning Iron Man"]:
            league_map[en_name] = "中超"
        else:
            league_map[en_name] = "英超"

    for cn_name, en_name in CN_NAME_MAP.items():
        key = (cn_name, en_name)
        if key not in seen:
            seen.add(key)
            results.append((cn_name, en_name, league_map.get(en_name, "英超")))
    return results
