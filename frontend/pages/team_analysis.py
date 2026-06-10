"""球队分析页面"""
import streamlit as st
from frontend.utils import api_get
from frontend.components.charts import plot_team_form


def render():
    st.title("🏟️ 球队分析")
    st.caption("查看球队赛季表现、近期状态和实力评分")

    # 选择联赛和球队
    leagues = {
        "2021": "Premier League",
        "2002": "Bundesliga",
        "2014": "La Liga",
        "2019": "Serie A",
        "2015": "Ligue 1",
    }

    col1, col2 = st.columns(2)
    with col1:
        selected_league = st.selectbox(
            "选择联赛",
            options=list(leagues.keys()),
            format_func=lambda x: f"{leagues.get(x, x)} ({x})",
            key="team_league",
        )

    # 获取球队列表
    with st.spinner("加载球队列表..."):
        teams = api_get("/teams/", {"league_id": int(selected_league)})

    if not teams:
        st.warning("暂无球队数据，请先刷新比赛数据。")
        if st.button("🔄 刷新数据"):
            api_post("/matches/refresh", {"league_id": int(selected_league)})
            st.rerun()
        return

    with col2:
        team_options = {t["id"]: f"{t['name']} (Elo: {t.get('elo_rating', 1500):.0f})"
                       for t in teams}
        selected_team_id = st.selectbox(
            "选择球队",
            options=list(team_options.keys()),
            format_func=lambda x: team_options.get(x, str(x)),
        )

    st.divider()

    if selected_team_id:
        with st.spinner("加载球队详情..."):
            team_detail = api_get(f"/teams/{selected_team_id}")
            standings = api_get(f"/teams/standings/{int(selected_league)}")

        if team_detail:
            team = team_detail.get("team", {})

            # 球队头部信息
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.subheader(team.get("name", "?"))
                if team.get("venue"):
                    st.caption(f"🏟️ 主场: {team.get('venue')}")
            with col2:
                st.metric("Elo 评分", f"{team.get('elo_rating', 1500):.0f}")
            with col3:
                recent = team_detail.get("recent_form", [])
                wins = recent.count("W")
                st.metric("近期胜率", f"{wins}/{len(recent)}" if recent else "N/A")
            with col4:
                if standings:
                    team_standing = next(
                        (s for s in standings.get("standings", [])
                         if s["team_id"] == selected_team_id),
                        None,
                    )
                    if team_standing:
                        st.metric("联赛排名", f"第 {team_standing['position']} 名")

            st.divider()

            # 近期状态
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📈 近期状态")
                recent_form = team_detail.get("recent_form", [])
                if recent_form:
                    plot_team_form(recent_form)
                else:
                    st.info("暂无近期比赛数据")

            with col2:
                st.subheader("📊 联赛积分榜 Top 10")
                if standings and standings.get("standings"):
                    top10 = standings["standings"][:10]
                    for s in top10:
                        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(s["position"], f"{s['position']}.")
                        is_selected = s["team_id"] == selected_team_id
                        if is_selected:
                            st.markdown(
                                f"**{medal} {s['team_name']}** - "
                                f"{s['points']}pts ({s['won']}W/{s['drawn']}D/{s['lost']}L, "
                                f"GD: {s['goal_difference']:+d})"
                            )
                        else:
                            st.markdown(
                                f"{medal} {s['team_name']} - {s['points']}pts "
                                f"({s['won']}W/{s['drawn']}D/{s['lost']}L)"
                            )
                else:
                    st.info("暂无积分榜数据")

            # 近期比赛详情
            st.divider()
            st.subheader("📋 近期比赛")
            recent_matches = team_detail.get("recent_matches", [])
            if recent_matches:
                for m in recent_matches[:10]:
                    is_home = m["home_team_id"] == selected_team_id
                    opponent = m["away_team_name"] if is_home else m["home_team_name"]
                    score = f"{m['score_home']}:{m['score_away']}"
                    result_emoji = "🟢" if (
                        (is_home and m["score_home"] > m["score_away"]) or
                        (not is_home and m["score_away"] > m["score_home"])
                    ) else "🔴" if (
                        (is_home and m["score_home"] < m["score_away"]) or
                        (not is_home and m["score_away"] < m["score_home"])
                    ) else "🟡"

                    from frontend.utils import format_match_time
                    date_str = format_match_time(str(m["utc_date"]))

                    cols = st.columns([2, 1, 1, 2])
                    with cols[0]:
                        st.markdown(f"{result_emoji} {'🏠' if is_home else '✈️'} vs **{opponent}**")
                    with cols[1]:
                        st.markdown(f"**{score}**")
                    with cols[2]:
                        status = "已结束" if m["status"] == "FINISHED" else m["status"]
                        st.caption(status)
                    with cols[3]:
                        st.caption(date_str)
                    st.divider()
            else:
                st.info("暂无近期比赛数据")

        else:
            st.error("获取球队详情失败")
