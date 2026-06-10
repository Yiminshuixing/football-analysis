"""比赛预测页面 — 输入球队+赔率，获取预测结果（移动端适配）"""
import streamlit as st
from frontend.utils import api_get, api_post
from frontend.team_names import CN_NAME_MAP


def render():
    # ===== 页面级 CSS =====
    st.markdown("""
    <style>
        /* 返回按钮行 - 移动端紧凑 */
        .back-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }
        .back-row .stButton button {
            min-height: 36px;
            padding: 4px 16px;
            font-size: 0.9rem !important;
            min-width: auto;
            width: auto;
        }

        /* 比分预测大卡片 - 移动端缩放 */
        .score-card {
            text-align: center;
            padding: 24px 16px;
            border-radius: 16px;
            border: 2px solid #4CAF50;
            background: linear-gradient(135deg, rgba(76,175,80,0.08), rgba(76,175,80,0.02));
        }
        .score-card h2 { margin: 4px 0; font-size: 1.2rem; }
        .score-card .score {
            font-size: 3.5rem;
            font-weight: 800;
            margin: 8px 0;
            letter-spacing: 6px;
        }
        .score-card .outcome {
            font-size: 1.1rem;
            margin-top: 8px;
        }
        .score-card .confidence {
            font-size: 0.9rem;
            color: gray;
        }

        /* 比分概率格子 */
        .score-grid-item {
            text-align: center;
            padding: 10px 6px;
            border-radius: 10px;
            border: 1px solid rgba(128,128,128,0.2);
            margin: 4px;
            background: rgba(255,255,255,0.03);
            transition: transform 0.15s ease;
        }
        .score-grid-item:active {
            transform: scale(0.95);
        }
        .score-grid-item .score-num {
            font-size: 1.3rem;
            font-weight: 700;
        }
        .score-grid-item .score-prob {
            font-size: 0.8rem;
            color: gray;
        }
        .score-grid-item .prob-bar {
            height: 4px;
            background: rgba(128,128,128,0.15);
            border-radius: 2px;
            margin-top: 4px;
            overflow: hidden;
        }
        .score-grid-item .prob-fill {
            height: 100%;
            background: #2ecc71;
            border-radius: 2px;
        }

        /* 近期成绩条目 */
        .form-item {
            padding: 6px 10px;
            border-radius: 8px;
            border: 1px solid rgba(128,128,128,0.12);
            margin: 4px 0;
            font-size: 0.9rem;
        }

        /* 价值投注建议 */
        .value-bet {
            padding: 10px 14px;
            border-radius: 10px;
            border-left: 4px solid #f39c12;
            background: rgba(243,156,18,0.08);
            margin: 6px 0;
            font-size: 0.9rem;
        }

        /* 移动端适配 */
        @media (max-width: 480px) {
            .score-card .score { font-size: 2.8rem; }
            .score-card { padding: 16px 10px; }
            .score-grid-item .score-num { font-size: 1.1rem; }
            .score-grid-item { padding: 8px 4px; margin: 2px; }
        }
    </style>
    """, unsafe_allow_html=True)

    # ===== 返回按钮 =====
    st.markdown('<div class="back-row">', unsafe_allow_html=True)
    if st.button("← 返回", key="pred_back"):
        st.session_state.page = "home"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.title("🎯 比赛预测")
    st.caption("输入球队名称（中文/英文）和赔率，系统自动预测")

    # ===== 输入区域 =====
    with st.container(border=True):
        st.markdown("##### 比赛信息")

        col1, col2 = st.columns(2)
        with col1:
            home_input = st.text_input(
                "🏠 主队名称",
                placeholder="例：曼城、利物浦、巴萨",
                key="home_input",
            )
            home_odds = st.number_input(
                "主胜赔率", min_value=1.01, max_value=100.0,
                value=1.80, step=0.05, format="%.2f",
            )

        with col2:
            away_input = st.text_input(
                "✈️ 客队名称",
                placeholder="例：阿森纳、皇马、拜仁",
                key="away_input",
            )
            away_odds = st.number_input(
                "客胜赔率", min_value=1.01, max_value=100.0,
                value=3.50, step=0.05, format="%.2f",
            )

        draw_odds = st.number_input(
            "🤝 平局赔率", min_value=1.01, max_value=100.0,
            value=3.20, step=0.05, format="%.2f",
        )

        # 预测按钮 - 独立一行全宽
        predict_btn = st.button(
            "🔮 开始预测", type="primary", use_container_width=True
        )

    # ===== 预测结果 =====
    if not predict_btn:
        return

    if not home_input.strip() or not away_input.strip():
        st.error("请输入主队和客队名称")
        return

    # ----- 查找球队 -----
    with st.status("🔍 正在匹配球队...", expanded=False) as status:
        home_result = api_get("/teams/search", {"q": home_input.strip()})
        away_result = api_get("/teams/search", {"q": away_input.strip()})

        # 尝试中文映射兜底
        if not home_result:
            en_name = CN_NAME_MAP.get(home_input.strip())
            if en_name:
                home_result = api_get("/teams/search", {"q": en_name})
        if not away_result:
            en_name = CN_NAME_MAP.get(away_input.strip())
            if en_name:
                away_result = api_get("/teams/search", {"q": en_name})

        if not home_result:
            status.update(label="❌ 未找到主队", state="error")
            st.error(f'找不到球队 "{home_input}"，请检查名称')
            return
        if not away_result:
            status.update(label="❌ 未找到客队", state="error")
            st.error(f'找不到球队 "{away_input}"，请检查名称')
            return

        home_team = home_result[0]
        away_team = away_result[0]
        status.update(
            label=f"✅ {home_team['name']} vs {away_team['name']}",
            state="complete",
        )

    # ----- 调用预测 API -----
    with st.spinner("🧮 计算预测中..."):
        pred_result = api_post("/predictions/manual", json_body={
            "home_team": home_team["name"],
            "away_team": away_team["name"],
            "home_odds": home_odds,
            "draw_odds": draw_odds,
            "away_odds": away_odds,
        })

    if not pred_result:
        st.error("预测计算失败，请稍后重试")
        return

    p = pred_result["prediction"]
    odds_analysis = pred_result.get("odds_analysis")

    # ===== 结果显示 =====
    st.divider()
    st.markdown("## 📊 预测结果")

    # 比分预测大卡片
    home_name = pred_result["home_team"]["name"]
    away_name = pred_result["away_team"]["name"]
    pred_h = p["predicted_home_score"]
    pred_a = p["predicted_away_score"]
    outcome_labels = {"HOME": "主胜 ✅", "DRAW": "平局 🤝", "AWAY": "客胜 ✅"}
    outcome = p["predicted_outcome"]

    st.markdown(
        f"""
        <div class="score-card">
            <h2>{home_name}</h2>
            <div class="score">{pred_h} : {pred_a}</div>
            <h2>{away_name}</h2>
            <div class="outcome">🎯 {outcome_labels.get(outcome, outcome)}</div>
            <div class="confidence">置信度: <strong>{p['confidence']}%</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # ----- 概率条 -----
    st.markdown("##### 🎲 胜平负概率")
    h_prob = p["home_win_prob"]
    d_prob = p["draw_prob"]
    a_prob = p["away_win_prob"]
    total_prob = h_prob + d_prob + a_prob

    if total_prob > 0:
        h_pct = h_prob / total_prob
        d_pct = d_prob / total_prob
        a_pct = a_prob / total_prob

        st.markdown(
            f"""
            <div style="display:flex; height:36px; border-radius:18px; overflow:hidden; margin:10px 0;">
                <div style="flex:{h_pct:.3f}; background:#2ecc71; text-align:center; color:white;
                     font-size:13px; line-height:36px; font-weight:bold;">
                    {'🏠 ' + f'{h_prob:.0%}' if h_pct > 0.1 else ''}
                </div>
                <div style="flex:{d_pct:.3f}; background:#95a5a6; text-align:center; color:white;
                     font-size:13px; line-height:36px; font-weight:bold;">
                    {'🤝 ' + f'{d_prob:.0%}' if d_pct > 0.1 else ''}
                </div>
                <div style="flex:{a_pct:.3f}; background:#e74c3c; text-align:center; color:white;
                     font-size:13px; line-height:36px; font-weight:bold;">
                    {'✈️ ' + f'{a_prob:.0%}' if a_pct > 0.1 else ''}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 三个概率数值
    prob_cols = st.columns(3)
    with prob_cols[0]:
        st.metric("🏠 主胜", f"{h_prob:.1%}", delta_color="off")
    with prob_cols[1]:
        st.metric("🤝 平局", f"{d_prob:.1%}", delta_color="off")
    with prob_cols[2]:
        st.metric("✈️ 客胜", f"{a_prob:.1%}", delta_color="off")

    st.caption(f"预期进球 (xG): 主队 {p['home_xg']:.2f} — 客队 {p['away_xg']:.2f}")

    st.divider()

    # ----- 比分概率分布 -----
    st.markdown("##### 比分概率分布")
    score_probs = p.get("score_probabilities", [])
    if score_probs:
        cols = st.columns(4)
        for i, sp in enumerate(score_probs[:8]):
            with cols[i % 4]:
                bar_pct = min(sp['probability'] * 100, 100)
                st.markdown(
                    f"""
                    <div class="score-grid-item">
                        <div class="score-num">{sp['home']}:{sp['away']}</div>
                        <div class="score-prob">{sp['probability']:.1%}</div>
                        <div class="prob-bar"><div class="prob-fill" style="width:{bar_pct:.1f}%;"></div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()

    # ----- 近期主客场成绩 -----
    st.markdown("##### 📋 近期成绩（模型计算依据）")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**🏠 {home_name} 近期 5 场主场比赛**")
        home_form = pred_result.get("home_recent_form", [])
        if home_form:
            for m in home_form:
                r_emoji = {"W": "✅", "D": "➖", "L": "❌"}
                st.markdown(
                    f'<div class="form-item">'
                    f'{r_emoji.get(m["result"], "❓")} '
                    f'<strong>{m["score"]}</strong> vs {m["opponent"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("暂无主场比赛数据")

    with col2:
        st.markdown(f"**✈️ {away_name} 近期 5 场客场比赛**")
        away_form = pred_result.get("away_recent_form", [])
        if away_form:
            for m in away_form:
                r_emoji = {"W": "✅", "D": "➖", "L": "❌"}
                st.markdown(
                    f'<div class="form-item">'
                    f'{r_emoji.get(m["result"], "❓")} '
                    f'<strong>{m["score"]}</strong> vs {m["opponent"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("暂无客场比赛数据")

    st.divider()

    # ----- 赔率对比分析 -----
    if odds_analysis:
        st.markdown("##### 💰 赔率分析（用户输入 vs 模型预测）")

        od_cols = st.columns(3)
        outcomes_zh = {"home": "主胜", "draw": "平局", "away": "客胜"}
        for i, key in enumerate(["home", "draw", "away"]):
            with od_cols[i]:
                model_p = odds_analysis[f"model_{key}_prob"]
                odds_p = odds_analysis[f"odds_{key}_prob"]
                diff = model_p - odds_p
                st.metric(
                    outcomes_zh[key],
                    f"模型 {model_p:.0%}",
                    delta=f"市场 {odds_p:.0%} ({'+' if diff > 0 else ''}{diff:.0%})",
                    delta_color="normal" if diff > 0 else "inverse",
                )

        if odds_analysis.get("value_bets"):
            st.markdown("**💰 价值投注建议**")
            for vb in odds_analysis["value_bets"]:
                st.markdown(
                    f'<div class="value-bet">'
                    f'<strong>{outcomes_zh.get(vb["type"], vb["type"])}</strong> — '
                    f'模型 {vb["model_prob"]:.0%} vs 市场 {vb["odds_prob"]:.0%}，'
                    f'赔率 {vb["odds"]:.2f}，期望值 {vb["expected_value"]:.2f}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.divider()

    # ----- 模型分解 -----
    with st.expander("🔬 模型详情（Poisson + Elo 分解）"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Poisson 模型**")
            st.metric("主胜概率", f"{p['poisson_home_win']:.1%}")
            st.metric("平局概率", f"{p['poisson_draw']:.1%}")
            st.metric("客胜概率", f"{p['poisson_away_win']:.1%}")
            st.caption(f"xG: 主 {p['home_xg']:.2f} / 客 {p['away_xg']:.2f}")

        with col2:
            st.markdown("**Elo 模型**")
            st.metric("主胜概率", f"{p['elo_home_win']:.1%}")
            st.metric("平局概率", f"{p['elo_draw']:.1%}")
            st.metric("客胜概率", f"{p['elo_away_win']:.1%}")
            st.caption(
                f"{home_name}: Elo {pred_result['home_team']['elo_rating']:.0f}  |  "
                f"{away_name}: Elo {pred_result['away_team']['elo_rating']:.0f}"
            )

        lp = p.get("league_params", {})
        st.caption(
            f"融合权重: Poisson {p['fusion_weights']['poisson']:.0%} + Elo {p['fusion_weights']['elo']:.0%}  |  "
            f"联赛参数: HFA={lp.get('elo_home_advantage', '-')} ρ={lp.get('dixon_coles_rho', '-')}"
        )
