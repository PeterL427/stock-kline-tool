"""
图表绘制引擎 —— 基于 Plotly 的多股票 K 线同图

主图：全部股票 K 线蜡烛叠加（涨跌幅 % 归一化）
副图：全部股票成交量柱叠加
"""

from typing import Dict

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 每只股票独立深色系：涨=实心填充，跌=空心边框
STOCK_COLORS = [
    "#B71C1C",  # 深红  → 主股票（最醒目）
    "#0D47A1",  # 深蓝
    "#1B5E20",  # 深绿
    "#E65100",  # 深橙
    "#4A148C",  # 深紫
    "#004D40",  # 深青绿
    "#BF360C",  # 深橙红
    "#283593",  # 靛蓝
    "#AD1457",  # 深粉
    "#263238",  # 深灰蓝
]




def _pct_col(series: pd.Series, base: float) -> pd.Series:
    """价格 → 涨跌幅 %"""
    return (series / base - 1) * 100


def plot_multi_stock_kline(
    stock_data_dict: Dict[str, pd.DataFrame],
    primary_code: str,
    stock_names: Dict[str, str],
    time_range_days: int = 60,
) -> go.Figure:
    """
    绘制多股票 K 线同图

    - 主图：所有股票 K 线蜡烛叠加（涨跌幅 % 归一化，带透明度）
    - 副图：所有股票成交量柱叠加
    - 主股票 MA 均线
    """
    primary_df = stock_data_dict.get(primary_code)
    if primary_df is None or primary_df.empty:
        raise ValueError(f"Primary stock {primary_code} has no data")

    primary_df = primary_df.tail(time_range_days).copy()
    primary_df = primary_df.sort_values("date").reset_index(drop=True)
    primary_name = stock_names.get(primary_code, primary_code)

    # 主股票基准价（第一天收盘）
    base_price = primary_df.iloc[0]["close"]

    # ---- 预处理：计算每只股票的涨跌幅 % ----
    prepared = {}  # code -> {date, open%, high%, low%, close%, volume, base}
    for code, df in stock_data_dict.items():
        if df is None or df.empty:
            continue
        d = df.tail(time_range_days).copy()
        d = d.sort_values("date").reset_index(drop=True)
        base = d.iloc[0]["close"]
        prepared[code] = {
            "date": d["date"],
            "open": _pct_col(d["open"], base),
            "high": _pct_col(d["high"], base),
            "low": _pct_col(d["low"], base),
            "close": _pct_col(d["close"], base),
            "volume": d["volume"],
            "df": d,
            "base": base,
        }

    p_primary = prepared[primary_code]

    # ========== 创建子图布局 ==========
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.6, 0.4],   # 主图60% + 成交量40%
    )

    # ========== 主图：所有股票 K 线蜡烛叠加 ==========
    codes_in_order = [primary_code] + [c for c in stock_data_dict if c != primary_code]

    for idx, code in enumerate(codes_in_order):
        if code not in prepared:
            continue
        p = prepared[code]
        name = stock_names.get(code, code)
        color = STOCK_COLORS[idx % len(STOCK_COLORS)]

        # 主股票用宽线醒目，对比股略细
        line_width = 0.8 if idx == 0 else 0.5

        fig.add_trace(
            go.Candlestick(
                x=p["date"],
                open=p["open"],
                high=p["high"],
                low=p["low"],
                close=p["close"],
                name=name,
                showlegend=True,
                increasing_line_color=color,
                increasing_fillcolor=color,
                decreasing_line_color=color,
                decreasing_fillcolor=color,  # 跌=实心（同色）
                line=dict(width=line_width),
            ),
            row=1, col=1,
        )

    # ========== 每只股票：5MA 均线（同色虚线）==========
    for idx, code in enumerate(codes_in_order):
        if code not in prepared:
            continue
        p = prepared[code]
        name = stock_names.get(code, code)
        color = STOCK_COLORS[idx % len(STOCK_COLORS)]
        if len(p["close"]) >= 5:
            ma5 = p["close"].rolling(window=5, min_periods=5).mean()
            fig.add_trace(
                go.Scatter(
                    x=p["date"],
                    y=ma5,
                    mode="lines",
                    name=f"{name} 5MA",
                    line=dict(color=color, width=1.0, dash="dash"),
                    showlegend=True,
                ),
                row=1, col=1,
            )

    # ========== 副图：所有股票成交量柱叠加 ==========
    for idx, code in enumerate(codes_in_order):
        if code not in prepared:
            continue
        p = prepared[code]
        name = stock_names.get(code, code)
        color = STOCK_COLORS[idx % len(STOCK_COLORS)]

        # 实心同色柱 + 透明度分层（主股最实 → 对比股逐层透明）
        vol_opacity = 0.9 if idx == 0 else max(0.5 - idx * 0.12, 0.15)

        fig.add_trace(
            go.Bar(
                x=p["date"],
                y=p["volume"],
                name=f"{name} 成交量",
                marker=dict(
                    color=color,
                    line=dict(color=color, width=0),
                ),
                opacity=vol_opacity,
                showlegend=True,
            ),
            row=2, col=1,
        )

    # ========== 计算涨跌幅 Y 轴范围 ==========
    all_pct = []
    for p in prepared.values():
        all_pct.extend(p["low"].values)
        all_pct.extend(p["high"].values)
    all_pct = pd.Series(all_pct)
    pct_min = all_pct.min()
    pct_max = all_pct.max()
    pct_pad = max((pct_max - pct_min) * 0.18, 1.0)

    # 成交量 Y 轴上限（最高柱 + 30% 头空间）
    all_vol = []
    for p in prepared.values():
        all_vol.extend(p["volume"].values)
    vol_max = max(all_vol) if all_vol else 1
    vol_upper = vol_max * 1.3

    # ========== 布局 ==========
    fig.update_layout(
        title=dict(
            text=f"📊 涨跌幅对比&nbsp;&nbsp;|&nbsp;&nbsp;<b>{primary_name}</b> ({primary_code})"
                 f"&nbsp;&nbsp;基准 → 0%",
            x=0.5, xanchor="center", font=dict(size=16),
        ),
        template="plotly_white",
        # 不设统一 hover（避免副图悬停时带出主图 K 线数据）
        # hovermode="x unified",
        height=1400,
        margin=dict(l=70, r=60, t=90, b=60),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.0,
            xanchor="right", x=1, font=dict(size=10),
        ),
        yaxis=dict(
            title="涨跌幅 %",
            side="left",
            range=[pct_min - pct_pad, pct_max + pct_pad],
            tickformat="+.1f",
            ticksuffix="%",
            zeroline=True,
            zerolinecolor="#ccc",
            zerolinewidth=1,
        ),
        yaxis2=dict(
            title="成交量",
            side="left",
            showgrid=True,
            gridcolor="#eee",
            rangemode="nonnegative",
            range=[0, vol_upper],
        ),
        dragmode="zoom",
        barmode="overlay",  # 成交量柱叠加
    )

    fig.update_xaxes(
        title="日期",
        rangeslider=dict(visible=False),
        type="category",
        row=2, col=1,
    )
    fig.update_xaxes(
        matches="x",
        type="category",
        row=1, col=1,
    )

    return fig
