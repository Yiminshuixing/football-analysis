"""设置页面（更新版 — 基于 football-data.co.uk CSV 导入）"""
import streamlit as st
from frontend.utils import api_get, api_post


def render():
    st.title("⚙️ 设置")
    st.caption("数据管理、系统状态")

    st.divider()

    # 数据源说明
    with st.expander("📖 数据说明", expanded=True):
        st.markdown("""
        ### 数据来源：Football-Data.co.uk

        **完全免费，无需 API Key**

        - 数据通过 CSV 文件从 football-data.co.uk 自动下载
        - 包含五大联赛：英超、德甲、西甲、意甲、法甲
        - 每场比赛包含：比分、射门、角球、红黄牌统计 + 多家博彩公司赔率

        ### 更新方式
        - **赛季进行时** — 每轮结束后 1-2 天，点击"刷新数据"即可获取最新赛果
        - **休赛期**（6-7月）— 无需操作，等待 8 月新赛季开始
        - 数据自动跳过已有比赛，只新增未导入的

        ### 使用流程
        1. 点击 **"刷新比赛数据"** 从 football-data.co.uk 下载最新 CSV
        2. 系统自动导入数据库，更新 Elo 评分
        3. 在 Dashboard 和比赛分析页面查看预测
        """)

    st.divider()

    # 数据管理
    st.subheader("📦 数据管理")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 从 football-data.co.uk 刷新数据", use_container_width=True):
            with st.spinner("正在下载并导入最新 CSV 数据..."):
                result = api_post("/matches/refresh", {"source": "csv"})
                if result:
                    total = result.get("total_synced", result.get("matches_synced", 0))
                    st.success(f"✅ 刷新完成！导入 {total} 场比赛")
                else:
                    st.error("刷新失败，请稍后重试")

    with col2:
        if st.button("📊 刷新全部预测", use_container_width=True):
            with st.spinner("正在重新计算预测..."):
                result = api_post("/predictions/refresh")
                if result:
                    st.success(f"✅ 已生成 {result.get('predictions_generated', 0)} 场预测")
                else:
                    st.error("预测刷新失败")

    st.divider()

    # 系统状态
    st.subheader("📡 系统状态")

    health = api_get("/health")
    if health:
        st.success("✅ 后端服务运行正常")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("数据源", "football-data.co.uk (CSV)")
    with col2:
        st.metric("需 API Key", "❌ 不需要")

    # 关注联赛
    st.divider()
    st.subheader("🏆 关注的联赛")
    st.markdown("""
    | 联赛 | 状态 |
    |------|------|
    | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 **Premier League** (2021) | ✅ |
    | 🇩🇪 **Bundesliga** (2002) | ✅ |
    | 🇪🇸 **La Liga** (2014) | ✅ |
    | 🇮🇹 **Serie A** (2019) | ✅ |
    | 🇫🇷 **Ligue 1** (2015) | ✅ |
    """)

    st.divider()
    st.caption("v1.1.0 | 数据源: Football-Data.co.uk")
