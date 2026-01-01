# app.py
import streamlit as st
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt

from engine import run_eod_analyzer, run_smartstock_v296_engine, get_rsi_ema

st.set_page_config(page_title="SmartStock V2.9.6 Audit System", layout="wide")

# ----------------------------
# Simple bilingual helper (UI only; chart text excluded by your requirement)
# ----------------------------
def ui(zh: str, en: str) -> str:
    return f"{zh} / {en}"

# ----------------------------
# Plotting (Colab-style long figure)
# IMPORTANT: Use data pools from run_eod_analyzer:
#   - D_Data is daily downloaded once
#   - W_Data/M_Data are resampled from daily inside engine (aligned)
# ----------------------------
def draw_v296_charts(data_dict: dict, ticker: str):
    fig = plt.figure(figsize=(14, 22), facecolor="white")

    configs = [
        (data_dict["D_Data"], 80, 252, 20, 200, "DAILY"),
        (data_dict["W_Data"], 52, 52, 10, 50, "WEEKLY"),
        (data_dict["M_Data"], 40, 12, 6, 20, "MONTHLY"),
    ]

    mc = mpf.make_marketcolors(up="#ef5350", down="#26a69a", edge="inherit", wick="inherit")
    style = mpf.make_mpf_style(marketcolors=mc, gridstyle="--", gridcolor="#eeeeee", facecolor="white")

    for i, (df_raw, show_n, h_p, l_p, ma_p, name) in enumerate(configs):
        df = df_raw.copy()

        # refs
        df["HI"] = df["High"].rolling(h_p).max().shift(1)
        df["LO"] = df["Low"].rolling(l_p).min().shift(1)
        df["MA"] = df["Close"].rolling(ma_p).mean()

        # BX: follow your chart preference (bar + line)
        # bx_s: (5,3) ; bx_l: (20,10)
        df["bx_s"] = get_rsi_ema(df["Close"], 5, 3)
        df["bx_l"] = get_rsi_ema(df["Close"], 20, 10)

        p_df = df.tail(show_n)

        ax_p = plt.subplot2grid((9, 1), (i * 3, 0), rowspan=2)
        ax_b = plt.subplot2grid((9, 1), (i * 3 + 2, 0), rowspan=1)

        bar_colors = ["#26a69a" if v > 0 else "#ef5350" for v in p_df["bx_s"]]

        apds = [
            mpf.make_addplot(p_df["HI"], ax=ax_p, color="#9c27b0", linestyle="--", width=1.0),
            mpf.make_addplot(p_df["LO"], ax=ax_p, color="#ff9800", linestyle=":", width=1.5),
            mpf.make_addplot(p_df["MA"], ax=ax_p, color="#2196f3", linestyle="-", width=1.2),

            mpf.make_addplot(p_df["bx_s"], ax=ax_b, type="bar", color=bar_colors, width=0.7),
            # FIX: mplfinance does NOT accept linewidth= ; use width=
            mpf.make_addplot(p_df["bx_l"], ax=ax_b, color="#1a237e", width=1.5),
        ]

        mpf.plot(
            p_df,
            type="candle",
            ax=ax_p,
            addplot=apds,
            style=style,
            datetime_format="%y-%m"
        )

        ax_p.set_title(f"{name} | {ticker} | V2.9.6", fontsize=12, fontweight="bold", loc="left")
        ax_b.axhline(0, color="gray", alpha=0.3)
        ax_b.set_ylabel("BX", fontsize=8)

    plt.tight_layout()
    return fig

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title(ui("SmartStock V2.9.6 审计系统", "SmartStock V2.9.6 Audit System"))
ticker = st.sidebar.text_input(ui("股票代码", "Ticker Symbol"), value="D05.SI")
start_date = st.sidebar.date_input(ui("回测开始日期", "Backtest Start"), value=pd.to_datetime("2020-01-01").date())
end_date = st.sidebar.date_input(ui("回测结束日期", "Backtest End"), value=pd.to_datetime("today").date())

st.title(ui("SmartStock V2.9.6 审计系统", "SmartStock V2.9.6 Audit System"))

tab1, tab2 = st.tabs([ui("审计摘要", "AUDIT SUMMARY"), ui("回测审计", "BACKTEST AUDIT")])

# ----------------------------
# Tab 1: EOD
# ----------------------------
with tab1:
    run_eod = st.sidebar.button(ui("运行收盘审计", "RUN EOD ANALYSIS"))

    if run_eod:
        res = run_eod_analyzer(ticker)

        if not res:
            st.error(ui("无法获取数据或数据不足。请检查股票代码。", "Unable to fetch enough data. Please check ticker."))
        else:
            st.info(f"### {ui('动作', 'ACTION')}: {res['Action']}")
            st.write(f"**{ui('原因', 'REASON')}**: {res['Reason']}")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric(ui("燃料(量能倍数)", "Fuel (Vol Ratio)"), res["Fuel"])
            c2.metric(ui("推力(收盘位置)", "Push (Close Pos)"), res["Push"])
            c3.metric(ui("距离高点", "Gap to High"), res["Gap"])
            c4.metric(ui("止损线(20日低)", "Stop (20D Low)"), res["Stop"])
            c5.metric(ui("宏观过滤", "Macro Filter"), res["Macro"])

            st.subheader(ui("多周期图表审计", "Multi-Period Chart Audit"))
            fig = draw_v296_charts(res, ticker)
            st.pyplot(fig)

            st.markdown(
                ui(
                    """
**图例说明：**
- 🟦 蓝色实线：均线 MA（Daily=200D / Weekly=50W / Monthly=20M）
- 🟪 紫色虚线：高点参考线 HI（Daily=252 / Weekly=52 / Monthly=12）
- 🟧 橙色点线：支撑参考线 LO（Daily=20 / Weekly=10 / Monthly=6）
- 🟢🔴 BX 柱：短动能 (bx_s)
- 🟦 BX 线：长动能 (bx_l)
""",
                    """
**Legend:**
- 🟦 Blue solid: MA (Daily=200D / Weekly=50W / Monthly=20M)
- 🟪 Purple dash: HI reference (Daily=252 / Weekly=52 / Monthly=12)
- 🟧 Orange dot: LO support (Daily=20 / Weekly=10 / Monthly=6)
- 🟢🔴 BX bars: short momentum (bx_s)
- 🟦 BX line: long momentum (bx_l)
"""
                )
            )

# ----------------------------
# Tab 2: Backtest (True Sync)
# ----------------------------
with tab2:
    run_bt = st.sidebar.button(ui("运行回测审计", "RUN BACKTEST"))

    if run_bt:
        stats, trades, equity = run_smartstock_v296_engine(
            ticker,
            start=str(pd.Timestamp(start_date).date()),
            end=str(pd.Timestamp(end_date).date())
        )

        if equity is None or equity.empty:
            st.error(ui("回测失败：数据不足或股票代码无效。", "Backtest failed: not enough data or invalid ticker."))
        else:
            st.subheader(ui(f"策略表现：{ticker}", f"Strategy Performance: {ticker}"))

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(ui("总回报", "Total Return"), stats.get("Total Return", "-"))
            c2.metric(ui("最大回撤", "Max Drawdown"), stats.get("Max Drawdown", "-"))
            c3.metric(ui("宏观否决次数", "Macro Vetoes"), str(stats.get("Macro Vetoes", "-")))
            c4.metric(ui("最终权益", "Final Equity"), stats.get("Final Equity", "-"))

            c5, c6, c7, c8 = st.columns(4)
            c5.metric(ui("计划单次数", "Signals Issued"), str(stats.get("Signals Issued", "-")))
            c6.metric(ui("触发次数", "Signals Triggered"), str(stats.get("Signals Triggered", "-")))
            c7.metric(ui("突破次数", "Breakout Trades"), str(stats.get("Breakout Trades", "-")))
            c8.metric(ui("反转次数", "Reversal Trades"), str(stats.get("Reversal Trades", "-")))

            st.line_chart(equity.set_index("Date")["Equity"])

            st.subheader(ui("交易明细", "Trades"))
            st.dataframe(trades, use_container_width=True)
# 在侧边栏添加免责声明
st.sidebar.markdown("---")
st.sidebar.caption("📊 **Disclaimer / 免责声明**")
st.sidebar.caption("""
本系统仅供研究参考，不构成投资建议。风险自担。
For research only. Not financial advice. Use at your own risk.
""")

# 在主界面添加操作说明
with st.expander("📖 Usage Guide & Logic / 操作说明与逻辑逻辑"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **中文说明：**
        1. 输入代码（如 D05.SI）并执行分析。
        2. **BX系统**：柱状图代表短线爆发力，线条代表长线趋势。
        3. **信号逻辑**：包含宏观 Veto 过滤，确保不在下降趋势中盲目抄底。
        """)
    with col2:
        st.markdown("""
        **English Guide:**
        1. Enter ticker and run analysis.
        2. **BX System**: Histogram for short-term burst, Line for long-term trend.
        3. **Logic**: Includes Macro Veto to avoid catching falling knives in downtrends.
        """)




