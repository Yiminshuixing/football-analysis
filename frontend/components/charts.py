"""图表组件"""
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from typing import List, Dict, Any


def plot_prediction_gauge(home_prob: float, draw_prob: float, away_prob: float):
    """绘制胜平负概率仪表图"""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=["主胜", "平局", "客胜"],
        y=[home_prob * 100, draw_prob * 100, away_prob * 100],
        marker_color=["#2ecc71", "#f39c12", "#e74c3c"],
        text=[f"{home_prob:.1%}", f"{draw_prob:.1%}", f"{away_prob:.1%}"],
        textposition="outside",
    ))

    fig.update_layout(
        title="胜平负概率预测",
        yaxis_title="概率 (%)",
        yaxis_range=[0, 100],
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_score_probabilities(score_probs: List[Dict], top_n: int = 10):
    """绘制最可能比分分布图"""
    if not score_probs:
        st.info("暂无比分概率数据")
        return

    scores = score_probs[:top_n]
    labels = [f"{s['home']}:{s['away']}" for s in scores]
    probs = [s["probability"] * 100 for s in scores]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=probs,
        marker_color="#3498db",
        text=[f"{p:.1f}%" for p in probs],
        textposition="outside",
    ))

    fig.update_layout(
        title="最可能比分",
        xaxis_title="比分",
        yaxis_title="概率 (%)",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_team_form(form_list: List[str]):
    """绘制球队近期状态（W/D/L 色块）"""
    colors = {"W": "#2ecc71", "D": "#f39c12", "L": "#e74c3c"}
    labels = {"W": "胜", "D": "平", "L": "负"}

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(form_list))),
        y=[1] * len(form_list),
        mode="markers+text",
        marker=dict(
            size=40,
            color=[colors.get(f, "#95a5a6") for f in form_list],
            symbol="square",
        ),
        text=[labels.get(f, f) for f in form_list],
        textfont=dict(color="white", size=14, weight="bold"),
        hovertext=[f"第{i+1}场: {labels.get(f, f)}" for i, f in enumerate(form_list)],
        hoverinfo="text",
    ))

    fig.update_layout(
        title="近期状态",
        xaxis=dict(showticklabels=False, showgrid=False, range=[-0.5, len(form_list) - 0.5]),
        yaxis=dict(showticklabels=False, showgrid=False, range=[0.5, 1.5]),
        height=120,
        margin=dict(l=20, r=20, t=30, b=10),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_elo_history(history: List[dict]):
    """绘制 Elo 评分变化趋势"""
    if not history:
        st.info("暂无 Elo 历史数据")
        return

    dates = [h.get("date", "") for h in history]
    ratings = [h.get("rating", 1500) for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=ratings,
        mode="lines+markers",
        name="Elo 评分",
        line=dict(color="#9b59b6", width=2),
        marker=dict(size=6),
    ))

    fig.update_layout(
        title="Elo 评分变化趋势",
        xaxis_title="日期",
        yaxis_title="评分",
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)
