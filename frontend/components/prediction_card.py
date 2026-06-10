"""预测结果卡片组件"""
import streamlit as st
from typing import Dict, Any
from frontend.utils import get_outcome_label, get_outcome_emoji, format_match_time


def render_prediction_card(pred: Dict[str, Any]):
    """渲染单场预测卡片"""
    emoji = get_outcome_emoji(pred.get("predicted_outcome", ""))
    label = get_outcome_label(pred.get("predicted_outcome", ""))
    confidence = pred.get("confidence", 0)

    # 置信度颜色
    if confidence >= 70:
        conf_color = "🟢"
    elif confidence >= 50:
        conf_color = "🟡"
    else:
        conf_color = "🔴"

    match_date = pred.get("match_date")
    date_str = ""
    if match_date:
        date_str = format_match_time(str(match_date))

    league = pred.get("league_name", "")

    with st.container():
        cols = st.columns([2, 1, 1, 1])
        with cols[0]:
            st.markdown(f"**{pred.get('home_team', '?')}** vs **{pred.get('away_team', '?')}**")
            st.caption(f"{league} | {date_str}" if league else date_str)

        with cols[1]:
            st.markdown(f"### {emoji} {label}")
            st.caption(f"比分预测: {pred.get('predicted_home_score', '?')}:{pred.get('predicted_away_score', '?')}")

        with cols[2]:
            # 概率显示
            st.markdown(f"🏠 {pred.get('home_win_prob', 0):.0%}")
            st.markdown(f"🤝 {pred.get('draw_prob', 0):.0%}")
            st.markdown(f"✈️ {pred.get('away_win_prob', 0):.0%}")

        with cols[3]:
            st.markdown(f"{conf_color} 置信度: **{confidence:.0f}%**")

        st.divider()


def render_high_confidence_predictions(predictions: List[Dict[str, Any]]):
    """渲染高置信度预测列表"""
    if not predictions:
        st.info("当前没有高置信度的预测，请先同步数据。")
        return

    st.subheader("🎯 高置信度推荐")
    st.caption("以下比赛预测置信度较高，且概率优势明显，可供投注参考")

    for pred in predictions:
        render_prediction_card(pred)


def render_all_predictions(predictions: List[Dict[str, Any]]):
    """渲染所有预测"""
    if not predictions:
        st.info("暂无预测数据，请先同步比赛数据。")
        return

    st.subheader("📊 全部预测")
    for pred in predictions:
        render_prediction_card(pred)
