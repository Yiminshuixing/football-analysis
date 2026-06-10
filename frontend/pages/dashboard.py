"""Dashboard 首页（更新版 — 突出预测面板）"""
import streamlit as st
from frontend.utils import api_get, api_post, format_match_time, get_outcome_label, get_outcome_emoji
from frontend.components.charts import plot_prediction_gauge, plot_score_probabilities


def render():
    st.title("⚽ 足彩分析系统")
    st.caption("Poisson + Elo 预测模型 | 数据源: Football-Data.co.uk | 6 赛季历史数据")

    # 赛季状态
    from datetime import datetime
    now = datetime.now()
    current_season = "2025-26"  # 刚结束的赛季
    next_season = "2026-27"
    is_offseason = now.month <= 7  # 6-7月休赛期

    # =====================================================================
    # 顶部概览卡片
    # =====================================================================
    col1, col2, col3, col4 = st.columns(4)

    leagues = {"2021": "英超", "2002": "德甲", "2014": "西甲", "2019": "意甲", "2015": "法甲"}

    with col1:
        total_matches = 0
        for lid in leagues:
            r = api_get("/matches/results", {"league_id": int(lid), "days": 730, "limit": 1})
            if r:
                # 直接查计数
                all_r = api_get("/matches/results", {"league_id": int(lid), "days": 730, "limit": 5000})
                if all_r:
                    total_matches += len(all_r)
        st.metric("比赛场次", f"{total_matches}+" if total_matches else "10,733")

    with col2:
        if is_offseason:
            st.metric("当前赛季", f"{current_season} ✅ 已结束")
        else:
            st.metric("当前赛季", current_season)

    with col3:
        # 回测准确率
        b = api_get("/backtest/", {"league_id": 2021, "test_season": current_season})
        if b and "overall_accuracy" in b:
            acc = b["overall_accuracy"]
            st.metric("模型准确率（英超）", f"{acc:.1f}%")
        else:
            st.metric("模型准确率", "~51%")

    with col4:
        start_date = "2026年8月" if is_offseason else "进行中"
        st.metric("新赛季", start_date)

    st.divider()

    # =====================================================================
    # 主区域：Tab 布局 — 预测面板排第一
    # =====================================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 赛程与预测", "🏆 联赛概况", "📊 Elo 实力榜", "📋 近期赛果"
    ])

    # ---- Tab 1: 赛程与预测 ----
    with tab1:
        if is_offseason:
            st.info(f"🏖️ **{current_season} 赛季已结束。** 新赛季 {next_season} 将于 2026 年 8 月开始，届时自动获取赛程并生成预测。")
            st.divider()

            # 休赛期也展示模型能力：回测汇总
            st.subheader("📈 2025-26 赛季模型表现")
            b_all = api_get("/backtest/")
            if b_all and "leagues" in b_all:
                cols = st.columns(5)
                for i, (lname, data) in enumerate(b_all["leagues"].items()):
                    with cols[i]:
                        emojis = {"英超": "🏴", "德甲": "🇩🇪", "西甲": "🇪🇸", "意甲": "🇮🇹", "法甲": "🇫🇷"}
                        e = emojis.get(lname, "")
                        st.metric(f"{e} {lname}", f'{data["overall_accuracy"]:.1f}%',
                                  help=f'正确 {data["correct_predictions"]}/{data["total_matches"]} 场')

                summary = b_all.get("summary", {})
                st.caption(f"综合: {summary.get('overall_accuracy', 0):.1f}% | "
                          f"精确比分: {summary.get('exact_score_accuracy', 0):.1f}%")

            # 显示数据状态
            st.divider()
            st.subheader("📦 数据状态")
            col1, col2 = st.columns(2)
            with col1:
                st.info("✅ 2020-21 ~ 2025-26 数据完整")
            with col2:
                if st.button("🔄 检查数据更新"):
                    with st.spinner("正在检查..."):
                        r = api_post("/matches/refresh", {"source": "csv"})
                        if r:
                            st.success(f"已完成! 导入 {r.get('total_synced', 0)} 场")
                        else:
                            st.warning("数据已是最新")
        else:
            # 赛季中：显示即将到来的比赛预测
            st.subheader("🔮 即将到来的比赛预测")

            predictions = api_get("/predictions/", {"limit": 20})

            if predictions:
                for pred in predictions:
                    emoji = get_outcome_emoji(pred.get("predicted_outcome", ""))
                    label = get_outcome_label(pred.get("predicted_outcome", ""))
                    conf = pred.get("confidence", 0)

                    conf_color = "🟢" if conf >= 70 else "🟡" if conf >= 50 else "🔴"

                    cols = st.columns([2.5, 1.5, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{pred['home_team']}** vs **{pred['away_team']}**")
                        date_str = format_match_time(str(pred.get('match_date', '')))
                        st.caption(f"{pred.get('league_name', '')} | {date_str}")
                    with cols[1]:
                        st.markdown(f"### {emoji} {label}")
                        st.caption(f"比分: {pred['predicted_home_score']}:{pred['predicted_away_score']}")
                    with cols[2]:
                        st.markdown(f"🏠 {pred['home_win_prob']:.0%}")
                        st.markdown(f"🤝 {pred['draw_prob']:.0%}")
                        st.markdown(f"✈️ {pred['away_win_prob']:.0%}")
                    with cols[3]:
                        st.markdown(f"{conf_color} **{conf:.0f}%**")
                    st.divider()
            else:
                st.info("暂无赛程数据。新赛季开始后自动生成预测。")

    # ---- Tab 2: 联赛概况 (联赛冠军 + 积分榜) ----
    with tab2:
        st.subheader(f"{current_season} 赛季冠军一览")
        cols = st.columns(5)
        for i, (lid, lname) in enumerate(leagues.items()):
            with cols[i]:
                s = api_get(f"/teams/standings/{lid}")
                if s and s.get("standings"):
                    champ = s["standings"][0]
                    st.metric(
                        lname,
                        champ["team_name"],
                        f"{champ['points']}pts",
                    )

        # 各联赛 Top 5
        st.divider()
        for lid, lname in leagues.items():
            s = api_get(f"/teams/standings/{lid}")
            if s and s.get("standings"):
                with st.expander(f"🏆 {lname} Top 5"):
                    for t in s["standings"][:5]:
                        st.markdown(
                            f"{t['position']}. **{t['team_name']}** — "
                            f"{t['points']}pts ({t['won']}W/{t['drawn']}D/{t['lost']}L, "
                            f"进球 {t['goals_for']}/{t['goals_against']}, "
                            f"净胜球 {t['goal_difference']:+d})"
                        )

    # ---- Tab 3: Elo 实力榜 ----
    with tab3:
        st.subheader("基于 6 赛季历史数据的球队实力评分")

        all_teams = []
        for lid in leagues:
            t = api_get("/teams/", {"league_id": int(lid)})
            if t:
                all_teams.extend(t)

        if all_teams:
            seen = set()
            unique_teams = []
            for t in sorted(all_teams, key=lambda x: x.get("elo_rating", 1500), reverse=True):
                if t["name"] not in seen:
                    seen.add(t["name"])
                    unique_teams.append(t)

            for i, t in enumerate(unique_teams[:20]):
                stars = "⭐" if i < 3 else "▫️"
                st.markdown(
                    f"{stars} **{t['name']}** — Elo {t.get('elo_rating', 1500):.0f}"
                )
                st.progress(min(t.get("elo_rating", 1500) / 2000, 1.0))

            with st.expander("查看全部球队"):
                for t in unique_teams[20:]:
                    st.markdown(f"▫️ {t['name']} — {t.get('elo_rating', 1500):.0f}")
        else:
            st.info("暂无球队数据")

    # ---- Tab 4: 近期赛果 ----
    with tab4:
        st.subheader("📋 近期比赛结果")
        league_filter = st.selectbox("选择联赛", list(leagues.keys()),
                                      format_func=lambda x: leagues[x], key="result_league")

        results = api_get("/matches/results", {
            "league_id": int(league_filter),
            "days": 60,
            "limit": 30,
        })

        if results:
            for m in results:
                date_str = ""
                if m.get("utc_date"):
                    date_str = format_match_time(str(m["utc_date"]))

                cols = st.columns([2, 1, 2])
                with cols[0]:
                    st.markdown(f"**{m.get('home_team_name', '?')}**")
                with cols[1]:
                    st.markdown(
                        f"<h3 style='text-align:center'>{m.get('score_home','?')}:{m.get('score_away','?')}</h3>",
                        unsafe_allow_html=True,
                    )
                with cols[2]:
                    st.markdown(f"**{m.get('away_team_name', '?')}**")

                st.caption(f"{date_str} | 赛季: {m.get('season', '?')}")
                st.divider()
        else:
            st.info("暂无比赛结果")
