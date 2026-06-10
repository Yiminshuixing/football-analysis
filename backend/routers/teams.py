"""球队数据 API 路由"""
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db, Team, Match, League
from backend.schemas import TeamInfo, TeamDetail, LeagueStanding

router = APIRouter()

# 中文队名 → 英文队名 映射（用于搜索）
CN_TEAM_NAMES = {
    "阿森纳": "Arsenal", "阿斯顿维拉": "Aston Villa", "伯恩茅斯": "Bournemouth",
    "布伦特福德": "Brentford", "布莱顿": "Brighton", "伯恩利": "Burnley",
    "切尔西": "Chelsea", "水晶宫": "Crystal Palace", "埃弗顿": "Everton",
    "富勒姆": "Fulham", "伊普斯维奇": "Ipswich", "利兹联": "Leeds",
    "莱斯特城": "Leicester", "利物浦": "Liverpool", "卢顿": "Luton",
    "曼城": "Man City", "曼联": "Man United",
    "曼彻斯特城": "Man City", "曼彻斯特联": "Man United",
    "纽卡斯尔": "Newcastle", "纽卡斯尔联": "Newcastle",
    "诺维奇": "Norwich", "诺丁汉森林": "Nott'm Forest",
    "谢菲尔德联": "Sheffield United", "南安普顿": "Southampton",
    "桑德兰": "Sunderland", "热刺": "Tottenham",
    "托特纳姆热刺": "Tottenham", "沃特福德": "Watford",
    "西布朗": "West Brom", "西布朗维奇": "West Brom",
    "西汉姆联": "West Ham", "西汉姆": "West Ham",
    "狼队": "Wolves", "伍尔弗汉普顿": "Wolves",
    # 德甲
    "奥格斯堡": "Augsburg", "拜仁慕尼黑": "Bayern Munich", "拜仁": "Bayern Munich",
    "比勒费尔德": "Bielefeld", "波鸿": "Bochum", "达姆施塔特": "Darmstadt",
    "多特蒙德": "Dortmund", "多特": "Dortmund", "法兰克福": "Ein Frankfurt",
    "科隆": "FC Koln", "弗赖堡": "Freiburg", "菲尔特": "Greuther Furth",
    "汉堡": "Hamburg", "海登海姆": "Heidenheim", "柏林赫塔": "Hertha",
    "霍芬海姆": "Hoffenheim", "荷尔斯泰因基尔": "Holstein Kiel", "基尔": "Holstein Kiel",
    "勒沃库森": "Leverkusen", "药厂": "Leverkusen",
    "门兴格拉德巴赫": "M'gladbach", "门兴": "M'gladbach",
    "美因茨": "Mainz", "RB莱比锡": "RB Leipzig", "莱比锡": "RB Leipzig",
    "沙尔克04": "Schalke 04", "沙尔克": "Schalke 04",
    "圣保利": "St Pauli", "斯图加特": "Stuttgart", "柏林联合": "Union Berlin",
    "云达不莱梅": "Werder Bremen", "不莱梅": "Werder Bremen",
    "沃尔夫斯堡": "Wolfsburg", "狼堡": "Wolfsburg",
    # 西甲
    "阿拉维斯": "Alaves", "阿尔梅里亚": "Almeria",
    "毕尔巴鄂竞技": "Ath Bilbao", "毕尔巴鄂": "Ath Bilbao",
    "马德里竞技": "Ath Madrid", "马竞": "Ath Madrid",
    "巴塞罗那": "Barcelona", "巴萨": "Barcelona",
    "贝蒂斯": "Betis", "皇家贝蒂斯": "Betis",
    "加的斯": "Cadiz", "塞尔塔": "Celta", "埃瓦尔": "Eibar",
    "埃尔切": "Elche", "西班牙人": "Espanol", "赫塔费": "Getafe",
    "赫罗纳": "Girona", "格拉纳达": "Granada", "韦斯卡": "Huesca",
    "拉帕马斯": "Las Palmas", "拉斯帕尔马斯": "Las Palmas",
    "莱加内斯": "Leganes", "莱万特": "Levante", "马洛卡": "Mallorca",
    "奥萨苏纳": "Osasuna", "奥维耶多": "Oviedo", "巴列卡诺": "Vallecano",
    "皇马": "Real Madrid", "皇家马德里": "Real Madrid",
    "皇家社会": "Sociedad", "巴拉多利德": "Valladolid",
    "塞维利亚": "Sevilla", "瓦伦西亚": "Valencia",
    "比利亚雷亚尔": "Villarreal", "黄潜": "Villarreal",
    # 意甲
    "亚特兰大": "Atalanta", "贝内文托": "Benevento", "博洛尼亚": "Bologna",
    "卡利亚里": "Cagliari", "科莫": "Como", "克雷莫纳": "Cremonese",
    "克罗托内": "Crotone", "恩波利": "Empoli", "佛罗伦萨": "Fiorentina",
    "弗罗西诺内": "Frosinone", "热那亚": "Genoa",
    "国际米兰": "Inter", "国米": "Inter",
    "尤文图斯": "Juventus", "尤文": "Juventus",
    "拉齐奥": "Lazio", "莱切": "Lecce", "AC米兰": "Milan", "米兰": "Milan",
    "蒙扎": "Monza", "那不勒斯": "Napoli", "帕尔马": "Parma",
    "比萨": "Pisa", "罗马": "Roma", "萨勒尼塔纳": "Salernitana",
    "桑普多利亚": "Sampdoria", "萨索洛": "Sassuolo", "斯佩齐亚": "Spezia",
    "都灵": "Torino", "乌迪内斯": "Udinese", "威尼斯": "Venezia",
    "维罗纳": "Verona",
    # 法甲
    "阿雅克肖": "Ajaccio", "昂热": "Angers", "欧塞尔": "Auxerre",
    "波尔多": "Bordeaux", "布雷斯特": "Brest", "克莱蒙": "Clermont",
    "第戎": "Dijon", "勒阿弗尔": "Le Havre", "朗斯": "Lens",
    "里尔": "Lille", "洛里昂": "Lorient", "里昂": "Lyon",
    "马赛": "Marseille", "梅斯": "Metz", "摩纳哥": "Monaco",
    "蒙彼利埃": "Montpellier", "南特": "Nantes", "尼斯": "Nice",
    "尼姆": "Nimes", "巴黎FC": "Paris FC", "巴黎圣日耳曼": "Paris SG",
    "大巴黎": "Paris SG", "巴黎": "Paris SG",
    "兰斯": "Reims", "雷恩": "Rennes", "圣埃蒂安": "St Etienne",
    "斯特拉斯堡": "Strasbourg", "图卢兹": "Toulouse", "特鲁瓦": "Troyes",
    # 中超
    "上海海港": "Shanghai Port FC", "上海申花": "Shanghai Shenhua",
    "山东泰山": "Shandong Taishan", "北京国安": "Beijing Guoan",
    "成都蓉城": "Chengdu Rongcheng", "河南": "Henan FC",
    "河南队": "Henan FC", "天津津门虎": "Tianjin Jinmen Tiger",
    "武汉三镇": "Wuhan Three Towns", "浙江": "Zhejiang Professional",
    "浙江队": "Zhejiang Professional", "云南玉昆": "Yunnan Yukun",
    "大连英博": "Dalian Yingbo", "青岛海牛": "Qingdao Hainiu",
    "青岛西海岸": "Qingdao West Coast", "深圳新鹏城": "Shenzhen Peng City",
    "梅州客家": "Meizhou Hakka", "长春亚泰": "Changchun Yatai",
    "重庆铜梁龙": "Chongqing Tongliang Long", "辽宁铁人": "Liaoning Iron Man",
    # 国家队
    "中国": "China", "日本": "Japan", "韩国": "South Korea",
    "朝鲜": "North Korea", "澳大利亚": "Australia", "沙特": "Saudi Arabia",
    "伊朗": "Iran", "伊拉克": "Iraq", "卡塔尔": "Qatar",
    "阿联酋": "United Arab Emirates", "乌兹别克斯坦": "Uzbekistan",
    "阿曼": "Oman", "约旦": "Jordan", "叙利亚": "Syria",
    "泰国": "Thailand", "越南": "Vietnam", "印尼": "Indonesia",
    "阿根廷": "Argentina", "巴西": "Brazil", "乌拉圭": "Uruguay",
    "哥伦比亚": "Colombia", "智利": "Chile", "厄瓜多尔": "Ecuador",
    "秘鲁": "Peru", "巴拉圭": "Paraguay", "英格兰": "England",
    "法国": "France", "德国": "Germany", "西班牙": "Spain",
    "意大利": "Italy", "荷兰": "Netherlands", "葡萄牙": "Portugal",
    "比利时": "Belgium", "克罗地亚": "Croatia", "瑞士": "Switzerland",
    "丹麦": "Denmark", "瑞典": "Sweden", "挪威": "Norway",
    "波兰": "Poland", "奥地利": "Austria", "土耳其": "Turkey",
    "捷克": "Czech Republic", "乌克兰": "Ukraine", "塞尔维亚": "Serbia",
    "希腊": "Greece", "罗马尼亚": "Romania", "苏格兰": "Scotland",
    "威尔士": "Wales", "爱尔兰": "Ireland", "冰岛": "Iceland",
    "墨西哥": "Mexico", "美国": "USA", "加拿大": "Canada",
    "尼日利亚": "Nigeria", "埃及": "Egypt", "摩洛哥": "Morocco",
    "塞内加尔": "Senegal", "加纳": "Ghana", "喀麦隆": "Cameroon",
    "突尼斯": "Tunisia", "阿尔及利亚": "Algeria", "科特迪瓦": "Ivory Coast",
}


def _cn_to_en_search(name: str) -> str:
    """中文名转英文搜索关键词"""
    for cn, en in CN_TEAM_NAMES.items():
        if cn in name or name in cn:
            return en
    # 尝试部分匹配
    for cn, en in CN_TEAM_NAMES.items():
        if any(c in name for c in cn):
            return en
    return name


@router.get("/", response_model=List[TeamInfo])
def get_all_teams(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    db: Session = Depends(get_db),
):
    """获取所有球队"""
    query = db.query(Team)

    if league_id:
        # 获取该联赛中出现的球队
        team_ids = set()
        matches = db.query(Match).filter(
            Match.league_id == league_id
        ).limit(500).all()
        for m in matches:
            team_ids.add(m.home_team_id)
            team_ids.add(m.away_team_id)
        query = query.filter(Team.id.in_(team_ids))

    teams = query.order_by(Team.name).all()
    return teams


@router.get("/search")
def search_teams(
    q: str = Query(..., description="球队名称（支持中文/英文/模糊搜索）"),
    db: Session = Depends(get_db),
):
    """搜索球队（按名称模糊匹配，支持中文）"""
    if not q or len(q.strip()) < 1:
        return []

    query = q.strip()

    # 中文 → 英文 搜索词转换
    en_query = _cn_to_en_search(query)
    if en_query != query:
        query = en_query

    seen_ids = set()
    results = []

    def _add(t):
        if t and t.id not in seen_ids:
            seen_ids.add(t.id)
            results.append({
                "id": t.id, "name": t.name, "elo_rating": round(t.elo_rating, 1),
                "league": _get_team_league(db, t.id),
            })

    # 1. 精确匹配
    for t in db.query(Team).filter(Team.name.ilike(query)).all():
        _add(t)

    # 2. 模糊匹配
    if not results:
        for t in db.query(Team).filter(Team.name.ilike(f"%{query}%")).order_by(Team.elo_rating.desc()).limit(20).all():
            _add(t)

    # 3. 分词匹配
    if not results:
        parts = query.replace("-", " ").replace(".", " ").replace("'", " ").split()
        for part in parts:
            if len(part) < 2:
                continue
            for t in db.query(Team).filter(Team.name.ilike(f"%{part}%")).limit(10).all():
                _add(t)

    # 4. 中文名全表匹配（兜底）
    if not results:
        for cn, en in CN_TEAM_NAMES.items():
            if query in cn or cn in query:
                for t in db.query(Team).filter(Team.name.ilike(f"%{en}%")).all():
                    _add(t)
                break

    return results[:20]


def _get_team_league(db: Session, team_id: int) -> str | None:
    """获取球队所属联赛名称"""
    match = db.query(Match).filter(
        (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
    ).order_by(Match.utc_date.desc()).first()
    if match:
        league = db.query(League).filter(League.id == match.league_id).first()
        if league:
            return league.name
    return None


@router.get("/{team_id}", response_model=TeamDetail)
def get_team_detail(
    team_id: int,
    db: Session = Depends(get_db),
):
    """获取球队详细信息（含近期状态和 Elo 变化）"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="球队未找到")

    # 近期比赛
    recent = db.query(Match).filter(
        (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
        Match.status == "FINISHED",
        Match.score_home.isnot(None),
    ).order_by(Match.utc_date.desc()).limit(10).all()

    # 近期状态（W/D/L）
    recent_form = []
    recent_matches = []
    for m in recent:
        if m.home_team_id == team_id:
            if m.score_home > m.score_away:
                recent_form.append("W")
            elif m.score_home < m.score_away:
                recent_form.append("L")
            else:
                recent_form.append("D")
        else:
            if m.score_away > m.score_home:
                recent_form.append("W")
            elif m.score_away < m.score_home:
                recent_form.append("L")
            else:
                recent_form.append("D")
        recent_matches.append(m)

    recent_form = recent_form or []
    recent_matches = recent_matches or []

    return {
        "team": team,
        "recent_form": recent_form,
        "recent_matches": recent_matches,
        "elo_history": [],  # 简化实现，可按需扩展
    }


@router.get("/standings/{league_id}")
def get_league_standings(
    league_id: int,
    db: Session = Depends(get_db),
):
    """获取联赛积分榜（基于本地数据计算）"""
    # 获取该联赛本赛季已完成比赛（取最近 380 场覆盖整个赛季）
    matches = db.query(Match).filter(
        Match.league_id == league_id,
        Match.status == "FINISHED",
        Match.score_home.isnot(None),
    ).order_by(Match.utc_date.desc()).limit(380).all()

    # 统计各队数据
    stats = {}
    for m in matches:
        for team_id, team_name, is_home in [
            (m.home_team_id, m.home_team_name, True),
            (m.away_team_id, m.away_team_name, False),
        ]:
            if team_id not in stats:
                stats[team_id] = {
                    "team_id": team_id,
                    "team_name": team_name or f"Team {team_id}",
                    "played": 0, "won": 0, "drawn": 0, "lost": 0,
                    "goals_for": 0, "goals_against": 0, "points": 0,
                }
            s = stats[team_id]
            s["played"] += 1
            if is_home:
                gf, ga = m.score_home, m.score_away
            else:
                gf, ga = m.score_away, m.score_home
            s["goals_for"] += gf
            s["goals_against"] += ga
            if gf > ga:
                s["won"] += 1
                s["points"] += 3
            elif gf < ga:
                s["lost"] += 1
            else:
                s["drawn"] += 1
                s["points"] += 1

    # 排序并添加排名
    sorted_teams = sorted(
        stats.values(),
        key=lambda x: (-x["points"], -(x["goals_for"] - x["goals_against"]), -x["goals_for"]),
    )

    standings = []
    for i, t in enumerate(sorted_teams, 1):
        team = db.query(Team).filter(Team.id == t["team_id"]).first()
        standings.append({
            "position": i,
            "team_id": t["team_id"],
            "team_name": t["team_name"],
            "crest_url": team.crest_url if team else None,
            "played_games": t["played"],
            "won": t["won"],
            "drawn": t["drawn"],
            "lost": t["lost"],
            "goals_for": t["goals_for"],
            "goals_against": t["goals_against"],
            "goal_difference": t["goals_for"] - t["goals_against"],
            "points": t["points"],
        })

    league = db.query(League).filter(League.id == league_id).first()
    return {
        "league_id": league_id,
        "league_name": league.name if league else f"League {league_id}",
        "standings": standings,
    }
