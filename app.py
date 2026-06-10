"""
足彩分析 App - Streamlit 主入口
双按钮主页：比赛预测 | 数据更新
"""
import streamlit as st
import httpx

st.set_page_config(
    page_title="足彩分析系统",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ===== 页面状态管理 =====
if "page" not in st.session_state:
    st.session_state.page = "home"


# ===== 主页 =====
def render_home():
    """主页：两个大按钮"""
    st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppHeader {display: none;}
        div[data-testid="stToolbar"] {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

    _, col_logo, _ = st.columns([1, 2, 1])
    with col_logo:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h1 style='text-align:center; font-size:4rem;'>⚽</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<h1 style='text-align:center;'>足彩分析系统</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center; color:gray;'>Poisson + Elo 预测模型 | 五大联赛</p>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            "<div style='text-align:center; padding:20px;'>"
            "<h3>📊 比赛预测</h3>"
            "<p style='color:gray;'>输入球队和赔率，获取 AI 预测</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("🎯 开始预测", use_container_width=True, type="primary"):
            st.session_state.page = "predict"
            st.rerun()

    with col2:
        st.markdown(
            "<div style='text-align:center; padding:20px;'>"
            "<h3>📥 数据更新</h3>"
            "<p style='color:gray;'>自动下载或手动上传比赛数据</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("📦 更新数据", use_container_width=True, type="primary"):
            st.session_state.page = "data_update"
            st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    # 系统状态
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        try:
            r = httpx.get("http://localhost:8000/api/health", timeout=3)
            if r.status_code == 200:
                st.success("✅ 系统就绪")
            else:
                st.error("❌ 后端异常")
        except:
            st.error("❌ 后端未连接")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center; color:gray; font-size:0.8rem;'>"
        "数据源: Football-Data.co.uk | 版本 1.1.0</div>",
        unsafe_allow_html=True,
    )


# ===== 页面路由 =====
if st.session_state.page == "home":
    render_home()
elif st.session_state.page == "predict":
    from frontend.pages.prediction import render
    render()
elif st.session_state.page == "data_update":
    from frontend.pages.data_update import render
    render()
