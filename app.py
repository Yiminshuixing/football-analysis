"""
足彩分析 App - Streamlit 主入口
双按钮主页：比赛预测 | 数据更新
移动端适配: 响应式 CSS + 自适应布局
"""
import streamlit as st
import httpx

st.set_page_config(
    page_title="足彩分析系统",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ===== 全局移动端适配 CSS =====
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    /* ===== 基础重置 ===== */
    * { box-sizing: border-box; }
    .main { padding: 0.5rem !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }

    /* ===== Streamlit 列布局适配 ===== */
    div[data-testid="column"] {
        min-width: 0;
    }

    /* ===== 按钮 - 大触摸区域 ===== */
    .stButton button {
        min-height: 48px;
        font-size: 1.05rem !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        transition: transform 0.15s ease;
    }
    .stButton button:active {
        transform: scale(0.97);
    }

    /* ===== 输入框 - 防止 iOS 缩放 ===== */
    .stTextInput input, .stNumberInput input {
        font-size: 16px !important;  /* iOS 不会自动缩放 */
        min-height: 44px;
        border-radius: 10px !important;
    }
    .stSelectbox div[data-baseweb="select"] {
        min-height: 44px;
    }

    /* ===== 指标卡片 ===== */
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.05);
        padding: 12px 16px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.15);
        backdrop-filter: blur(2px);
    }
    div[data-testid="stMetric"] label {
        font-size: 0.85rem !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }

    /* ===== 状态容器 ===== */
    div[data-testid="stStatusWidget"] {
        border-radius: 12px;
    }

    /* ===== 文件上传器 ===== */
    section[data-testid="stFileUploader"] {
        border-radius: 12px;
    }

    /* ===== 分割线间距 ===== */
    hr {
        margin: 1.5rem 0 !important;
    }

    /* ===== 移动端专用: ≤768px ===== */
    @media (max-width: 768px) {
        .main { padding: 0.3rem !important; }
        .block-container {
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            max-width: 100% !important;
        }

        /* 标题缩小 */
        h1 { font-size: 1.6rem !important; }
        h2 { font-size: 1.3rem !important; }
        h3 { font-size: 1.1rem !important; }

        /* 所有列在移动端自动堆叠为 2 列网格 */
        div[data-testid="column"] {
            min-width: calc(50% - 8px) !important;
            flex: 1 1 calc(50% - 8px) !important;
        }

        /* 按钮更易触 */
        .stButton button {
            min-height: 52px;
            font-size: 1.1rem !important;
        }

        /* 指标卡片紧凑 */
        div[data-testid="stMetric"] {
            padding: 8px 12px;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
        }

        /* 隐藏低价值信息 */
        .stCaption {
            font-size: 0.75rem !important;
        }
    }

    /* ===== 小屏手机: ≤480px ===== */
    @media (max-width: 480px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }

        /* 所有列在手机端全部竖排 */
        div[data-testid="column"] {
            min-width: 100% !important;
            flex: 0 0 100% !important;
            padding: 4px 0 !important;
        }

        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.15rem !important; }

        .stButton button {
            min-height: 48px;
            font-size: 1rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ===== 页面状态管理 =====
if "page" not in st.session_state:
    st.session_state.page = "home"


# ===== 主页 =====
def render_home():
    """主页：两个大按钮（移动端竖排）"""
    with st.container():
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<h1 style='text-align:center; font-size:3rem; margin-bottom:0;'>⚽</h1>"
            "<h1 style='text-align:center; margin-top:0;'>足彩分析</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center; color:gray; font-size:0.9rem;'>"
            "Poisson + Elo 预测模型 ｜ 五大联赛</p>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 双按钮 - 移动端自动竖排 (CSS 控制)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            "<div style='text-align:center; padding:10px;'>"
            "<div style='font-size:2.5rem;'>🔮</div>"
            "<h3 style='margin:8px 0;'>比赛预测</h3>"
            "<p style='color:gray; font-size:0.85rem; margin:0;'>输入球队和赔率</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("🎯 开始预测", use_container_width=True, type="primary", key="home_predict"):
            st.session_state.page = "predict"
            st.rerun()

    with col2:
        st.markdown(
            "<div style='text-align:center; padding:10px;'>"
            "<div style='font-size:2.5rem;'>📥</div>"
            "<h3 style='margin:8px 0;'>数据更新</h3>"
            "<p style='color:gray; font-size:0.85rem; margin:0;'>下载或上传数据</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("📦 更新数据", use_container_width=True, type="primary", key="home_data"):
            st.session_state.page = "data_update"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 系统状态
    with st.container():
        st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
        try:
            r = httpx.get("http://localhost:8000/api/health", timeout=3)
            if r.status_code == 200:
                st.success("✅ 系统就绪")
            else:
                st.error("❌ 后端异常")
        except:
            st.error("❌ 后端未连接")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center; color:gray; font-size:0.75rem;'>"
        "数据源: Football-Data.co.uk ｜ v1.1.0</div>",
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
