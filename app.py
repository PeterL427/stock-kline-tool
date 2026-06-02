"""
股票K线同图工具 —— Streamlit Web 界面

优化:
  1. 多信源并行（新浪日K + baostock）
  2. 历史记录（替代快速添加）
  3. 智能搜索（代码/名称/拼音）

启动： streamlit run app.py
"""

import streamlit as st
from data_fetcher import (
    fetch_stock_data,
    get_stock_name,
    clear_cache,
    normalise_code,
)
from chart_engine import plot_multi_stock_kline
from stock_list import search_stocks, get_name_by_code

# ======================== 页面配置 ========================
st.set_page_config(
    page_title="股票 K 线同图对比工具",
    page_icon="📈",
    layout="wide",
)

# ======================== Session State 初始化 ========================
_DEFAULTS = {
    "stock_codes": [],
    "stock_names": {},
    "primary_code": None,
    "time_range": 60,

    "use_custom_date": False,
    "custom_start": None,
    "custom_end": None,
    "search_key": "",  # 搜索框缓存，避免 rerun 清空
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ======================== 辅助函数 ========================
def _load_history():
    """从 URL 参数读取历史记录（跨会话持久化）"""
    import json
    try:
        # 用旧版 API 更可靠
        params = st.query_params
        raw = params.get("hist", "") if hasattr(params, "get") else ""
        if not raw and hasattr(params, "get_all"):
            raw = params.get_all("hist")
            raw = raw[0] if raw else ""
        if not raw:
            return []
        hist = json.loads(raw)
        return hist if isinstance(hist, list) else []
    except Exception:
        return []


def _save_history(hist: list):
    """写入历史到 URL 参数"""
    import json
    # 紧凑格式，避免 URL 空格变 + 导致 JSON 解析失败
    st.query_params["hist"] = json.dumps(hist[:20], ensure_ascii=False, separators=(",", ":"))


def add_stock(code: str) -> None:
    """添加股票到当前会话 + 保存历史"""
    code = normalise_code(code)
    if not code:
        st.toast("⚠️ 请输入6位股票代码")
        return
    if code in st.session_state.stock_codes:
        st.toast(f"ℹ️ {code} 已在列表中")
        return

    with st.spinner(f"正在获取 {code} 数据…"):
        name = get_stock_name(code)
        if name:
            st.session_state.stock_codes.append(code)
            st.session_state.stock_names[code] = name
            if st.session_state.primary_code is None:
                st.session_state.primary_code = code
            # 写入 URL 参数（跨会话持久化）
            hist = _load_history()
            if not any(h[0] == code for h in hist):
                hist.insert(0, [code, name])
                _save_history(hist)
            st.toast(f"✅ {code} {name} 已添加")
            st.rerun()
        else:
            st.toast(f"❌ 未找到股票 {code}，请检查代码", icon="🚨")


def remove_stock(code: str) -> None:
    """移除股票"""
    st.session_state.stock_codes.remove(code)
    st.session_state.stock_names.pop(code, None)
    if st.session_state.primary_code == code:
        st.session_state.primary_code = (
            st.session_state.stock_codes[0] if st.session_state.stock_codes else None
        )
    st.rerun()


@st.dialog("添加股票")
def show_search_dialog():
    """搜索对话框"""
    q = st.text_input("输入股票代码、名称或拼音首字母", key="dialog_search", placeholder="如 000001 / 平安 / PA")
    
    if q and len(q.strip()) >= 1:
        results = search_stocks(q.strip(), max_results=5)
        if results:
            for code, name, match_type in results:
                tag = {"code": "🔢", "name": "📝", "pinyin": "🔤"}.get(match_type, "")
                if st.button(f"{tag} {code} {name}", key=f"sr_{code}", width='stretch'):
                    add_stock(code)
                    st.rerun()
        else:
            # 也允许直接输入任意6位代码
            clean = normalise_code(q)
            if clean and len(clean) == 6:
                if st.button(f"➕ 直接添加 {clean}", key="sr_direct", width='stretch'):
                    add_stock(clean)
                    st.rerun()
            else:
                st.caption("未找到匹配的股票")

    # 底部：历史记录（来自 URL 参数）
    hist_local = _load_history()[:10]
    if hist_local:
        st.divider()
        st.caption("📜 最近使用")
        cols = st.columns(2)
        for i, (hcode, hname) in enumerate(hist_local):
            with cols[i % 2]:
                if st.button(f"{hname} ({hcode})", key=f"hist_{hcode}", width='stretch'):
                    add_stock(hcode)
                    st.rerun()


# ======================== 侧边栏：设置 ========================
with st.sidebar:
    st.markdown("## ⚙️ 设置")
    st.divider()

    # ======== 1. 搜索股票 ========
    st.markdown("### 🔍 搜索股票")
    if st.button("🔍 打开搜索", width='stretch', type="primary"):
        show_search_dialog()

    st.divider()

    # ======== 2. 历史记录 ========
    st.markdown("### 📜 历史记录")
    # 从 URL 参数读取（每个用户自己的历史）
    if "history_list" not in st.session_state:
        st.session_state.history_list = _load_history()
    history = st.session_state.history_list[:10]
    if history:
        hist_cols = st.columns(2)
        for i, (hcode, hname) in enumerate(history):
            with hist_cols[i % 2]:
                already = hcode in st.session_state.stock_codes
                label = f"✅ {hname}" if already else f"{hname}"
                if st.button(label, key=f"sidebar_hist_{hcode}", width='stretch',
                             disabled=already):
                    if not already:
                        add_stock(hcode)
    else:
        st.caption("添加股票后自动保存到此处（浏览器本地）")

    st.divider()

    # ======== 3. 时间范围 ========
    st.markdown("### 📅 时间范围")
    time_options = {
        "最近 7 日": 7,
        "最近 15 日": 15,
        "最近 30 日": 30,
        "最近 60 日": 60,
        "最近 120 日": 120,
        "自定义": -1,
    }
    selected_label = st.select_slider(
        "时间范围",
        options=list(time_options.keys()),
        value="最近 60 日",
        label_visibility="collapsed",
    )

    if selected_label == "自定义":
        st.session_state.use_custom_date = True
        col1, col2 = st.columns(2)
        with col1:
            start = st.date_input("起始", value=None)
        with col2:
            end = st.date_input("结束", value=None)
        if start and end:
            st.session_state.custom_start = start
            st.session_state.custom_end = end
            # 估算天数
            st.session_state.time_range = (end - start).days
        else:
            st.session_state.time_range = 60
    else:
        st.session_state.use_custom_date = False
        st.session_state.time_range = time_options[selected_label]

    st.divider()

    # ======== 4. 操作 ========
    st.markdown("### 🛠️ 操作")
    col_rf, col_cl = st.columns(2)
    with col_rf:
        if st.button("🔄 刷新数据", width='stretch'):
            clear_cache()
            st.toast("缓存已清除，下次请求重新拉取")
    with col_cl:
        if st.button("🗑️ 清空所有", width='stretch'):
            for k in _DEFAULTS:
                st.session_state[k] = _DEFAULTS[k]
            st.rerun()

    st.divider()

    # ======== 5. 使用说明 ========
    with st.expander("📖 使用说明"):
        st.markdown(
            """
            - **搜索**：点击「🔍 打开搜索」
            - **涨跌幅 %**：起始日 0% 归一化对比
            - **K 线**：主股点击标签可切换
            - **成交量**：彩色柱叠加
            - **5MA**：每只股票同色虚线
            - **时间**：预设 N 日或自定义
            - **多信源**：新浪+baostock 并行
            - **历史**：自动保存，下次直接点击
            """
        )


# ======================== 主区域：图表 & 股票列表 ========================
if not st.session_state.stock_codes:
    # ---- 空状态引导 ----
    st.markdown(
        """
        <div style="text-align:center; padding:80px 20px; color:#888;">
            <h1 style="font-size:64px; margin:0;">📈</h1>
            <h2>股票 K 线同图对比工具</h2>
            <p style="font-size:18px;">
                点击左侧 <b>🔍 打开搜索</b> 添加股票<br>
                涨跌幅 % 归一化对比 · 成交量折线
            </p>
            <p style="font-size:14px; color:#aaa;">
                再次打开时历史记录会自动显示
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    # ---- 顶部：已添加股票标签条 ----
    st.markdown("### 📌 已添加的股票")
    tag_cols = st.columns(len(st.session_state.stock_codes))
    for i, code in enumerate(st.session_state.stock_codes):
        name = st.session_state.stock_names.get(code, code)
        is_primary = code == st.session_state.primary_code
        with tag_cols[i]:
            col_tag, col_del = st.columns([4, 1])
            with col_tag:
                if st.button(
                    f"📊 {name}" if is_primary else f"📈 {name}",
                    key=f"primary_{code}",
                    width='stretch',
                    type="primary" if is_primary else "secondary",
                ):
                    st.session_state.primary_code = code
                    st.rerun()
            with col_del:
                if st.button("✕", key=f"del_{code}", width='stretch'):
                    remove_stock(code)

    st.divider()

    # ---- 数据加载 + 绘图 ----
    with st.spinner("⏳ 加载数据（多信源并行）…"):
        stock_data = {}
        failed_codes = []
        for code in st.session_state.stock_codes:
            df = fetch_stock_data(
                code,
                time_range_days=st.session_state.time_range,
            )
            if df is not None and not df.empty:
                stock_data[code] = df
            else:
                failed_codes.append(code)

        if not stock_data:
            st.error("所有股票数据加载失败，请检查网络或股票代码")
        else:
            # 如果 primary 在失败列表里，自动切换
            if (
                st.session_state.primary_code not in stock_data
                and stock_data
            ):
                st.session_state.primary_code = list(stock_data.keys())[0]

            # ---- 绘图 ----
            fig = plot_multi_stock_kline(
                stock_data_dict=stock_data,
                primary_code=st.session_state.primary_code,
                stock_names=st.session_state.stock_names,
                time_range_days=st.session_state.time_range,
            )
            st.plotly_chart(fig, width='stretch', config={
                "scrollZoom": True,
                "displayModeBar": True,
                "modeBarButtonsToAdd": ["drawline", "eraseshape"],
            })

            # ---- 失败提醒 ----
            if failed_codes:
                names = [
                    f"{c} {st.session_state.stock_names.get(c, '')}"
                    for c in failed_codes
                ]
                st.warning(f"以下股票获取失败，已跳过：{', '.join(names)}")


