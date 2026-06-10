"""比赛分析页面（历史分析 + 赛前预测双模式）"""
import streamlit as st
from frontend.utils import api_get, format_match_time, get_outcome_label, api_post
from frontend.components.charts import plot_prediction_gauge, plot_score_probabilities


def render():
    st.title("📊 比赛分析")
    st.caption("历史比赛数据分析 | 即将到来的比赛预测")

    leagues = {
        "2021": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
        "2002": "🇩🇪 Bundesliga",
        "2014": "🇪🇸 La Liga",
        "2019": "🇮🇹 Serie A",
        "2015": "🇫🇷 Ligue 1",
    }
    seasons = ["2025-26", "2024-25", "2023-24", "2022-23", "2021-22", "2020-21"]

    # =====================================================================
    # 模式切换
    # =====================================================================
    mode = st.radio(
        "分析模式",
        options=["historical", "upcoming"],
        format_func=lambda x: {
            "historical": "📋 历史比赛分析（含赔率、预测回测）",
            "upcoming": "🔮 赛前预测（未开始的比赛）",
        }.get(x, x),
        horizontal=True,
    )

    # =====================================================================
    # 赛前预测模式
    # =====================================================================
    if mode == "upcoming":
        render_upcoming_mode(leagues, seasons)
    else:
        render_historical_mode(leagues, seasons)


# =========================================================================
# 赛前预测模式
# =========================================================================
def render_upcoming_mode(leagues, seasons):
    """赛前预测视图 — 展示即将到来比赛的预测结果"""
    col1, col2 = st.columns([2, 1])
    with col1:
        league_filter = st.selectbox(
            "选择联赛",
            options=["all"] + list(leagues.keys()),
            format_func=lambda x: "全部联赛" if x == "all" else leagues.get(x, x),
            key="upcoming_league",
        )

    with col2:
        if st.button("🔄 刷新预测", use_container_width=True):
            with st.spinner("正在重新计算预测..."):
                r = api_post("/predictions/refresh")
                if r:
                    st.success(f"已生成 {r.get('predictions_generated', 0)} 场预测")
                else:
                    st.error("刷新失败")

    # 获取赛前预测
    params = {}
    if league_filter != "all":
        params["league_id"] = int(league_filter)

    with st.spinner("加载预测数据..."):
        predictions = api_get("/predictions/", {**params, "limit": 50})

    if not predictions:
        from datetime import datetime
        now = datetime.now()
        if now.month < 8 or now.month == 12:
            st.info("🏖️ **当前为休赛期，暂无赛程数据。** 新赛季开始后自动生成预测。")
        else:
            st.info("🔮 暂无即将到来的比赛。可能是赛季已结束，或数据尚未刷新。")
            if st.button("🔄 尝试刷新数据"):
                api_post("/matches/refresh", {"source": "csv"})
                st.rerun()
        return

    # 按联赛分组展示
    from collections import defaultdict
    by_league = defaultdict(list)
    for p in predictions:
        by_league[p.get("league_name", "未知联赛")].append(p)

    for lname, preds in by_league.items():
        with st.expander(f"🏆 {lname}（{len(preds)} 场）", expanded=True):
            for pred in preds:
                render_upcoming_card(pred)


def render_upcoming_card(pred: dict):
    """单场赛前预测卡片"""
    emoji_map = {"HOME": "🏠", "DRAW": "🤝", "AWAY": "✈️"}
    label_map = {"HOME": "主胜", "DRAW": "平局", "AWAY": "客胜"}
    outcome = pred.get("predicted_outcome", "")
    emoji = emoji_map.get(outcome, "❓")
    label = label_map.get(outcome, outcome)
    conf = pred.get("confidence", 0)

    conf_color = "🟢" if conf >= 70 else "🟡" if conf >= 50 else "🔴"

    with st.container(border=True):
        # 第一行：球队 + 预测
        cols = st.columns([3, 1.5, 1.5, 1])
        with cols[0]:
            st.markdown(f"### {pred.get('home_team', '?')} vs {pred.get('away_team', '?')}")
            date_str = ""
            if pred.get("match_date"):
                date_str = format_match_time(str(pred["match_date"]))
            st.caption(f"🕐 {date_str}")

        with cols[1]:
            st.markdown(f"### {emoji} {label}")
            st.markdown(
                f"比分: **{pred.get('predicted_home_score', '?')}:{pred.get('predicted_away_score', '?')}**"
            )

        with cols[2]:
            st.markdown(f"🏠 {pred.get('home_win_prob', 0):.0%}")
            st.markdown(f"🤝 {pred.get('draw_prob', 0):.0%}")
            st.markdown(f"✈️ {pred.get('away_win_prob', 0):.0%}")

        with cols[3]:
            st.markdown(f"{conf_color} **{conf:.0f}%**")
            st.caption("置信度")

        # 第二行：概率条
        prob_cols = st.columns([pred.get("home_win_prob", 0), pred.get("draw_prob", 0),
                                pred.get("away_win_prob", 0)])
        total_prob = pred.get("home_win_prob", 0) + pred.get("draw_prob", 0) + pred.get("away_win_prob", 0)
        if total_prob > 0:
            h_pct = pred.get("home_win_prob", 0) / total_prob
            d_pct = pred.get("draw_prob", 0) / total_prob
            a_pct = pred.get("away_win_prob", 0) / total_prob

            # 概率条
            st.markdown(
                f"""
                <div style="display:flex; height:24px; border-radius:12px; overflow:hidden; margin:8px 0;">
                    <div style="flex:{h_pct:.3f}; background:#2ecc71; text-align:center; color:white; font-size:12px; line-height:24px;">
                        {'🏠' if h_pct > 0.15 else ''}
                    </div>
                    <div style="flex:{d_pct:.3f}; background:#95a5a6; text-align:center; color:white; font-size:12px; line-height:24px;">
                        {'🤝' if d_pct > 0.15 else ''}
                    </div>
                    <div style="flex:{a_pct:.3f}; background:#e74c3c; text-align:center; color:white; font-size:12px; line-height:24px;">
                        {'✈️' if a_pct > 0.15 else ''}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 第三行：详细展开
        with st.expander("详情"):
            show_prediction_detail(pred)


# =========================================================================
# 历史比赛模式
# =========================================================================
def render_historical_mode(leagues, seasons):
    """历史比赛分析视图"""
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_league = st.selectbox(
            "联赛", options=list(leagues.keys()),
            format_func=lambda x: leagues.get(x, x),
        )
    with col2:
        selected_season = st.selectbox("赛季", options=seasons)
    with col3:
        data_mode = st.selectbox(
            "数据模式",
            options=["historical", "odds"],
            format_func=lambda x: {"historical": "📋 赛果浏览", "odds": "🎲 查看赔率"}.get(x, x),
        )

    if data_mode == "odds":
        st.info("📊 以下比赛包含多家博彩公司赔率数据（Bet365、Pinnacle 等）")

    # 获取比赛
    with st.spinner("加载比赛数据..."):
        if data_mode == "odds":
            matches = api_get("/matches/odds", {
                "league_id": int(selected_league),
                "season": selected_season,
                "limit": 50,
            })
        else:
            matches = api_get("/matches/results", {
                "league_id": int(selected_league),
                "days": 365 * 2,
                "limit": 50,
            })

    if not matches:
        st.warning("暂无比赛数据")
        return

    # 比赛选择
    if data_mode == "odds":
        match_options = {
            m["id"]: f"{m.get('home_team_name', '?')} vs {m.get('away_team_name', '?')} "
                     f"({m.get('score_home', '?')}:{m.get('score_away', '?')})"
            for m in matches if m
        }
    else:
        match_options = {
            m["id"]: f"{m.get('home_team_name', '?')} vs {m.get('away_team_name', '?')} "
                     f"({m.get('score_home', '?')}:{m.get('score_away', '?')}) | "
                     f"{format_match_time(str(m.get('utc_date', '')))}"
            for m in matches if m
        }

    selected_match_id = st.selectbox(
        "选择比赛",
        options=list(match_options.keys()),
        format_func=lambda x: match_options.get(x, str(x)),
    )

    st.divider()

    if selected_match_id:
        match = api_get(f"/matches/{selected_match_id}")

        if not match:
            st.error("无法获取比赛详情")
            return

        col1, col2 = st.columns([3, 2])

        with col1:
            # 比赛基本信息
            st.subheader(
                f"{match.get('home_team_name', '?')} vs {match.get('away_team_name', '?')}"
            )
            score_h = match.get("score_home", "?")
            score_a = match.get("score_away", "?")
            st.markdown(f"## {score_h} : {score_a}")

            winner = match.get("winner", "")
            if winner == "HOME_TEAM":
                st.success(f"🏠 {match.get('home_team_name', '')} 胜")
            elif winner == "AWAY_TEAM":
                st.success(f"✈️ {match.get('away_team_name', '')} 胜")
            elif winner == "DRAW":
                st.info("🤝 平局")

            st.caption(
                f"🕐 {format_match_time(str(match.get('utc_date', '')))} | "
                f"赛季: {match.get('season', '?')}"
            )

            # 预测分析
            st.divider()
            st.subheader("🎯 模型预测分析")
            with st.spinner("计算预测..."):
                prediction = api_get(f"/predictions/{selected_match_id}")

            if prediction:
                plot_prediction_gauge(
                    prediction.get("home_win_prob", 0),
                    prediction.get("draw_prob", 0),
                    prediction.get("away_win_prob", 0),
                )

                plot_score_probabilities(
                    prediction.get("model_details", {})
                    .get("poisson", {})
                    .get("score_probabilities", []),
                )

                # 预测 vs 实际结果
                st.divider()
                st.markdown("##### 📊 预测 vs 实际")
                pred_outcome = prediction.get("predicted_outcome", "")
                actual_outcome = {"HOME_TEAM": "HOME", "AWAY_TEAM": "AWAY", "DRAW": "DRAW"}.get(winner, "")
                if pred_outcome == actual_outcome:
                    st.success("✅ 预测正确！")
                elif actual_outcome:
                    st.error("❌ 预测错误")

                st.caption(
                    f"预测: {get_outcome_label(pred_outcome)} | "
                    f"实际: {get_outcome_label(actual_outcome) if actual_outcome else '未开始'} | "
                    f"置信度: {prediction.get('confidence', 0):.0f}%"
                )

            else:
                st.warning("暂无预测数据")

        with col2:
            show_odds_section(match)
            show_prediction_detail(prediction if 'prediction' in locals() else None)


# =========================================================================
# 共享组件
# =========================================================================
def show_odds_section(match: dict):
    """展示赔率数据"""
    odds = match.get("odds")
    if odds:
        st.subheader("🎲 博彩公司赔率")

        # Bet365
        if "B365H" in odds:
            st.markdown("**Bet365**")
            bcols = st.columns(3)
            with bcols[0]:
                st.metric("主胜", odds["B365H"])
            with bcols[1]:
                st.metric("平局", odds["B365D"])
            with bcols[2]:
                st.metric("客胜", odds["B365A"])

            b365_h = float(odds["B365H"])
            b365_d = float(odds["B365D"])
            b365_a = float(odds["B365A"])
            implied_total = 1/b365_h + 1/b365_d + 1/b365_a
            st.caption(
                f"隐含概率: 主{1/b365_h/implied_total:.0%} / "
                f"平{1/b365_d/implied_total:.0%} / "
                f"客{1/b365_a/implied_total:.0%}"
            )

        # Pinnacle
        if "PSH" in odds:
            st.markdown("**Pinnacle**")
            pcols = st.columns(3)
            with pcols[0]:
                st.metric("主胜", odds["PSH"])
            with pcols[1]:
                st.metric("平局", odds["PSD"])
            with pcols[2]:
                st.metric("客胜", odds["PSA"])

        # 市场平均
        if "AvgH" in odds:
            st.markdown("**市场平均**")
            acols = st.columns(3)
            with acols[0]:
                st.metric("主胜", odds["AvgH"])
            with acols[1]:
                st.metric("平局", odds["AvgD"])
            with acols[2]:
                st.metric("客胜", odds["AvgA"])

        # 最高赔率
        if "MaxH" in odds:
            st.divider()
            st.markdown("**💰 最高赔率（价值投注参考）**")
            mcols = st.columns(3)
            with mcols[0]:
                st.metric("主胜", odds["MaxH"])
            with mcols[1]:
                st.metric("平局", odds["MaxD"])
            with mcols[2]:
                st.metric("客胜", odds["MaxA"])
    else:
        st.info("本场比赛无赔率数据")


def show_prediction_detail(prediction):
    """展示预测详情（共享给两种模式）"""
    if not prediction:
        st.warning("暂无预测数据")
        return

    st.divider()
    st.subheader("📈 预测详情")

    st.markdown("##### 概率")
    st.metric("🏠 主胜", f"{prediction['home_win_prob']:.1%}")
    st.metric("🤝 平局", f"{prediction['draw_prob']:.1%}")
    st.metric("✈️ 客胜", f"{prediction['away_win_prob']:.1%}")

    st.divider()

    st.markdown("##### 预测比分")
    h = prediction.get("predicted_home_score", 0)
    a = prediction.get("predicted_away_score", 0)
    st.markdown(
        f"<h1 style='text-align:center'>{h} : {a}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='text-align:center'>推荐: <strong>{get_outcome_label(prediction.get('predicted_outcome', ''))}</strong> | "
        f"置信度: {prediction.get('confidence', 0):.0f}%</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    # 模型分解
    st.markdown("##### 模型分解")
    md = prediction.get("model_details", {})
    poisson_data = md.get("poisson", {})
    elo_data = md.get("elo", {})

    if poisson_data:
        st.markdown("**Poisson 模型**")
        st.caption(f"xG: 主{poisson_data.get('home_xg', 0):.2f} / 客{poisson_data.get('away_xg', 0):.2f}")

    if elo_data:
        st.markdown("**Elo 模型**")
        st.caption(f"主胜: {elo_data.get('home_win_prob', 0):.0%}")
        st.caption(f"平局: {elo_data.get('draw_prob', 0):.0%}")
        st.caption(f"客胜: {elo_data.get('away_win_prob', 0):.0%}")

    # 联赛参数
    league_params = md.get("league_params", {})
    if league_params:
        st.divider()
        st.markdown("**联赛参数**")
        st.caption(f"主场优势 (Elo): {league_params.get('elo_home_advantage', '默认')}")
        st.caption(f"Dixon-Coles ρ: {league_params.get('dixon_coles_rho', '默认')}")
        st.caption(f"Poisson 权重: {league_params.get('poisson_weight', '默认')}")
