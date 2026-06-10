"""数据更新页面 — 自动下载 + 手动上传 CSV"""
import streamlit as st
from frontend.utils import api_get, api_post
from frontend.team_names import CN_NAME_MAP


def render():
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← 返回"):
            st.session_state.page = "home"
            st.rerun()

    st.title("📥 数据更新")
    st.caption("从 Football-Data.co.uk 自动下载或手动上传 CSV 文件")

    # ===== 当前数据状态 =====
    with st.container(border=True):
        st.markdown("##### 📊 当前数据概况")
        matchdays = api_get("/matches/matchdays")
        if matchdays:
            cols = st.columns(5)
            emojis = {"英超": "🏴", "德甲": "🇩🇪", "西甲": "🇪🇸", "意甲": "🇮🇹", "法甲": "🇫🇷"}
            for i, (league, info) in enumerate(matchdays.items()):
                with cols[i]:
                    st.metric(
                        f"{emojis.get(league, '')} {league}",
                        f"第 {info['matchday']} 轮",
                        f"{info['total_matches']} 场",
                    )

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

                st.success(f"📊 共导入 {total} 场新比赛")

                # ===== 导入详情（每联赛新增 vs 跳过） =====
                if import_details:
                    st.markdown("##### 📋 导入明细（各联赛）")
                    detail_cols = st.columns(min(len(import_details), 5))
                    for i, (lname, info) in enumerate(import_details.items()):
                        new_n = info.get("new", 0)
                        skipped = info.get("skipped", 0)
                        total_in_csv = info.get("total_in_csv", 0)
                        with detail_cols[i % 5]:
                            st.markdown(f"**{emojis.get(lname, '')} {lname}**")
                            st.markdown(f"- 🆕 新增 **{new_n}** 场")
                            st.markdown(f"- ⏭️ 跳过 **{skipped}** 场（已存在）")
                            st.markdown(f"- 📄 CSV 共 **{total_in_csv}** 行")
                            st.caption("")
                    st.info("💡 跳过的比赛已通过\"球队名+日期+联赛\"去重检查，不与库中已有数据冲突")

                # ===== 当前数据概况 =====
                if leagues:
                    st.markdown("##### 📊 当前数据概况")
                    league_cols = st.columns(min(len(leagues), 5))
                    for i, (lname, linfo) in enumerate(leagues.items()):
                        with league_cols[i % 5]:
                            st.metric(
                                f"{emojis.get(lname, '')} {lname}",
                                f"第 {linfo.get('matchday', '?')} 轮",
                                f"{linfo.get('total_matches', 0)} 场",
                            )

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
        season_input = st.text_input("赛季", value=season_default)

    uploaded_file = st.file_uploader(
        "选择 CSV 文件",
        type=["csv"],
        help="从 football-data.co.uk 下载的 CSV 文件",
    )

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
                    # 刷新 matchday 显示
                    new_md = api_get("/matches/matchdays")
                    if new_md:
                        st.markdown("##### 📊 更新后数据概况")
                        md_cols = st.columns(5)
                        emojis = {"英超": "🏴", "德甲": "🇩🇪", "西甲": "🇪🇸",
                                  "意甲": "🇮🇹", "法甲": "🇫🇷"}
                        for i, (l, info) in enumerate(new_md.items()):
                            with md_cols[i % 5]:
                                st.metric(
                                    f"{emojis.get(l, '')} {l}",
                                    f"第 {info['matchday']} 轮",
                                    f"{info['total_matches']} 场",
                                )
                else:
                    st.info("ℹ️ 该联赛赛季数据已完整，无新增比赛（跳过已存在数据）")
            else:
                status.update(label="❌ 导入失败", state="error")
                st.error("CSV 导入失败，请检查文件格式是否正确")
