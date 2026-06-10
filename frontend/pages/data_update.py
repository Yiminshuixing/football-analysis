"""数据更新页面 — 自动下载 + 手动上传 CSV（移动端适配）"""
import streamlit as st
from frontend.utils import api_get, api_post
from frontend.team_names import CN_NAME_MAP


def render():
    # ===== 页面级 CSS =====
    st.markdown("""
    <style>
        /* 返回按钮行 */
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

        /* 联赛卡片 ★ 移动端水平滚动 */
        .league-scroll {
            display: flex;
            gap: 12px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            scroll-snap-type: x mandatory;
            padding: 4px 0 12px 0;
            margin: 0 -4px;
        }
        .league-scroll::-webkit-scrollbar { height: 4px; }
        .league-scroll::-webkit-scrollbar-thumb {
            background: rgba(128,128,128,0.3);
            border-radius: 2px;
        }
        .league-card {
            flex: 0 0 auto;
            min-width: 140px;
            scroll-snap-align: start;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(128,128,128,0.15);
            border-radius: 14px;
            padding: 14px 18px;
            text-align: center;
            backdrop-filter: blur(2px);
        }
        .league-card .league-emoji { font-size: 1.5rem; }
        .league-card .league-name { font-size: 0.85rem; font-weight: 600; }
        .league-card .league-round { font-size: 0.9rem; color: #888; margin: 4px 0; }
        .league-card .league-count { font-size: 1.2rem; font-weight: 700; }

        /* 导入明细条目 */
        .import-detail {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(128,128,128,0.12);
            border-radius: 12px;
            padding: 12px 14px;
            margin: 4px 0;
        }
        .import-detail .id-title { font-weight: 600; font-size: 0.95rem; }
        .import-detail .id-stat { font-size: 0.88rem; color: #ccc; margin: 2px 0; }
        .import-detail .id-stat strong { color: #fff; }

        /* 文件上传器 */
        section[data-testid="stFileUploader"] {
            border-radius: 12px;
            padding: 8px;
        }

        /* 移动端适配 */
        @media (max-width: 480px) {
            .league-card { min-width: 120px; padding: 10px 12px; }
            .league-card .league-count { font-size: 1rem; }
            .import-detail { padding: 10px 12px; }
        }
    </style>
    """, unsafe_allow_html=True)

    # ===== 返回按钮 =====
    st.markdown('<div class="back-row">', unsafe_allow_html=True)
    if st.button("← 返回", key="data_back"):
        st.session_state.page = "home"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.title("📥 数据更新")
    st.caption("从 Football-Data.co.uk 自动下载或手动上传 CSV 文件")

    # ===== 当前数据状态（可横向滚动卡片） =====
    with st.container(border=True):
        st.markdown("##### 📊 当前数据概况")
        matchdays = api_get("/matches/matchdays")
        if matchdays:
            emojis = {"英超": "🏴", "德甲": "🇩🇪", "西甲": "🇪🇸", "意甲": "🇮🇹", "法甲": "🇫🇷"}
            # 横向滚动容器
            cards_html = '<div class="league-scroll">'
            for league, info in matchdays.items():
                cards_html += f"""
                    <div class="league-card">
                        <div class="league-emoji">{emojis.get(league, '⚽')}</div>
                        <div class="league-name">{league}</div>
                        <div class="league-round">第 {info['matchday']} 轮</div>
                        <div class="league-count">{info['total_matches']} 场</div>
                    </div>
                """
            cards_html += '</div>'
            st.markdown(cards_html, unsafe_allow_html=True)
        else:
            st.info("暂无比赛数据，请先更新")

    st.divider()

    # ===== 自动更新 =====
    st.markdown("##### 🤖 自动更新")
    st.caption("从 football-data.co.uk 自动下载最新 CSV 并导入")

    if st.button("📥 从 football-data.co.uk 自动更新", type="primary", use_container_width=True):
        with st.status("⏳ 正在下载并导入数据...", expanded=True) as status:
            status.write("📡 连接 football-data.co.uk...")
            result = api_post("/matches/refresh", {"source": "csv"})

            if result:
                total = result.get("total_synced", 0)
                import_details = result.get("import_details", {})
                leagues = result.get("leagues", {})
                emojis = {"英超": "🏴", "德甲": "🇩🇪", "西甲": "🇪🇸",
                          "意甲": "🇮🇹", "法甲": "🇫🇷"}

                status.update(label=f"✅ 完成！共导入 {total} 场新比赛", state="complete")
                st.success(f"📊 共导入 **{total}** 场新比赛")

                # ===== 导入明细 =====
                if import_details:
                    st.markdown("##### 📋 导入明细")
                    # 用卡片列表
                    detail_html = ""
                    for lname, info in import_details.items():
                        new_n = info.get("new", 0)
                        skipped = info.get("skipped", 0)
                        total_in_csv = info.get("total_in_csv", 0)
                        detail_html += f"""
                        <div class="import-detail">
                            <div class="id-title">{emojis.get(lname, '')} {lname}</div>
                            <div class="id-stat">🆕 新增 <strong>{new_n}</strong> 场</div>
                            <div class="id-stat">⏭️ 跳过 <strong>{skipped}</strong> 场（已存在）</div>
                            <div class="id-stat">📄 CSV 共 <strong>{total_in_csv}</strong> 行</div>
                        </div>
                        """
                    st.markdown(detail_html, unsafe_allow_html=True)
                    st.info("💡 跳过检查: 通过球队名+日期+联赛去重，不重复导入")

                # ===== 当前数据概况（横向滚动） =====
                if leagues:
                    st.markdown("##### 📊 更新后数据概况")
                    cards_html = '<div class="league-scroll">'
                    for lname, linfo in leagues.items():
                        cards_html += f"""
                            <div class="league-card">
                                <div class="league-emoji">{emojis.get(lname, '⚽')}</div>
                                <div class="league-name">{lname}</div>
                                <div class="league-round">第 {linfo.get('matchday', '?')} 轮</div>
                                <div class="league-count">{linfo.get('total_matches', 0)} 场</div>
                            </div>
                        """
                    cards_html += '</div>'
                    st.markdown(cards_html, unsafe_allow_html=True)

                if not total and not import_details:
                    st.info("所有联赛已是最新数据，无需更新")
            else:
                status.update(label="❌ 更新失败", state="error")
                st.error("自动更新失败，请稍后重试或使用手动上传")

    st.divider()

    # ===== 手动上传 =====
    st.markdown("##### 📂 手动上传 CSV")
    st.caption("从 football-data.co.uk 下载 CSV 文件后手动上传")

    # CSV 格式说明
    with st.expander("📖 如何获取 CSV 文件？"):
        st.markdown("""
        1. 打开 [Football-Data.co.uk](https://www.football-data.co.uk/data.php)
        2. 找到对应联赛和赛季的 CSV 链接
        3. 右键 → 另存为下载 .csv 文件
        4. 回到本页面上传

        **联赛 CSV 代码对照：**
        | 联赛 | 代码 |
        |------|:----:|
        | 🏴 英超 | E0 |
        | 🇩🇪 德甲 | D1 |
        | 🇪🇸 西甲 | SP1 |
        | 🇮🇹 意甲 | I1 |
        | 🇫🇷 法甲 | F1 |

        **文件名示例：** `E0.csv`（英超）、`D1.csv`（德甲）
        """)

    # 输入行 - 移动端自动竖排
    col1, col2 = st.columns(2)
    with col1:
        league_code = st.selectbox(
            "选择联赛",
            options=[("E0", "🏴 英超"), ("D1", "🇩🇪 德甲"),
                     ("SP1", "🇪🇸 西甲"), ("I1", "🇮🇹 意甲"),
                     ("F1", "🇫🇷 法甲")],
            format_func=lambda x: x[1],
        )[0]

    with col2:
        from datetime import datetime
        now = datetime.now()
        season_default = f"{now.year - 1}-{str(now.year)[2:]}" \
            if now.month < 8 else f"{now.year}-{str(now.year + 1)[2:]}"
        season_input = st.text_input("赛季", value=season_default, placeholder="如 2025-26")

    # 文件上传器
    uploaded_file = st.file_uploader(
        "选择 CSV 文件",
        type=["csv"],
        help="从 football-data.co.uk 下载的 CSV 文件",
    )

    # 上传并导入
    if uploaded_file is not None and st.button("📤 上传并导入", type="primary", use_container_width=True):
        with st.status("⏳ 正在导入...", expanded=True) as status:
            csv_text = uploaded_file.read().decode("utf-8-sig", errors="replace")
            status.write(f"📄 读取文件: {uploaded_file.name} ({len(csv_text)} 字符)")

            result = api_post("/matches/upload/csv", json_body={
                "league_code": league_code,
                "csv_text": csv_text,
                "season": season_input,
            })

            if result:
                count = result.get("matches_imported", 0)
                skipped = result.get("skipped", 0)
                total_csv = result.get("total_in_csv", 0)
                lname = result.get("league_name", league_code)
                season = result.get("season", season_input)
                emojis = {"英超": "🏴", "德甲": "🇩🇪", "西甲": "🇪🇸",
                          "意甲": "🇮🇹", "法甲": "🇫🇷"}

                status.update(
                    label=f"✅ 导入完成！{lname} {season} 新增 {count} 场",
                    state="complete",
                )

                st.success(f"📊 {lname} {season}: 导入结果")
                detail_c1, detail_c2, detail_c3 = st.columns(3)
                with detail_c1:
                    st.metric("🆕 新增", f"{count} 场")
                with detail_c2:
                    st.metric("⏭️ 跳过（已有）", f"{skipped} 场")
                with detail_c3:
                    st.metric("📄 CSV 总行数", f"{total_csv} 行")

                if count > 0 or skipped > 0:
                    # 刷新 matchday 显示（横向滚动）
                    new_md = api_get("/matches/matchdays")
                    if new_md:
                        st.markdown("##### 📊 更新后数据概况")
                        cards_html = '<div class="league-scroll">'
                        for l, info in new_md.items():
                            cards_html += f"""
                                <div class="league-card">
                                    <div class="league-emoji">{emojis.get(l, '⚽')}</div>
                                    <div class="league-name">{l}</div>
                                    <div class="league-round">第 {info['matchday']} 轮</div>
                                    <div class="league-count">{info['total_matches']} 场</div>
                                </div>
                            """
                        cards_html += '</div>'
                        st.markdown(cards_html, unsafe_allow_html=True)
                else:
                    st.info("ℹ️ 该联赛赛季数据已完整，无新增比赛")
            else:
                status.update(label="❌ 导入失败", state="error")
                st.error("CSV 导入失败，请检查文件格式是否正确")
