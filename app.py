import streamlit as st
import mplfinance as mpf
import matplotlib.pyplot as plt
import pandas as pd

from engine import run_eod_analyzer, get_rsi_ema, run_smartstock_v296_engine


st.set_page_config(page_title="SmartStock V2.9.6 Audit", layout="wide")


# ====== Bilingual UI strings ======
UI = {
    "title": "SmartStock V2.9.6 审计系统 / Audit System",
    "ticker": "股票代码 / Ticker Symbol",
    "start": "回测开始日期 / Backtest Start",
    "run_eod": "运行收盘审计 / RUN EOD ANALYSIS",
    "run_bt": "运行回测审计 / RUN BACKTEST",
    "tab1": "【 审计摘要 / AUDIT SUMMARY 】",
    "tab2": "【 回测审计 / BACKTEST AUDIT 】",
    "action": "动作 / ACTION",
    "reason": "原因 / REASON",
    "fuel": "燃料(量能) / Fuel",
    "push": "推动(收盘位置) / Push",
    "gap": "距高点 / Gap",
    "stop": "止损线 / Stop (20D-LOW)",
    "macro": "宏观过滤 / Macro",
    "chart": "多周期图表审计 / Multi-Period Chart Audit",
    "perf": "策略表现 / Strategy Performance",
    "total_return": "总回报 / Total Return",
    "trades": "交易次数 / Total Trades",
    "final_equity": "最终净值 / Final Equity",
    "veto": "宏观否决 / Macro Vetoes",
    "breakout": "突破次数 / Breakout",
    "reversal": "反转次数 / Reversal",
    "no_data": "数据不足或下载失败 / Not enough data or download failed",
}


def draw_v296_charts(data_dict, ticker: str):
    """
    目标：尽可能对齐你 Colab 的 V2.9.6 图
    - Up: green, Down: red
    - show_n / datetime_format 对齐
    - HI/LO shift(1)
    - MA 不 shift
    - BX: Daily(5,3) bar + Weekly/Monthly(20,10) line
    """
    # --- Candle colors aligned with your Colab image ---
    mc = mpf.make_marketcolors(
        up="#26a69a", down="#ef5350", edge="inherit", wick="inherit", volume="inherit"
    )
    style = mpf.make_mpf_style(
        marketcolors=mc, gridstyle="--", gridcolor="#eeeeee", facecolor="white"
    )

    fig = plt.figure(figsize=(14, 22), facecolor="white")

    configs = [
        # df_key, show_n, HI, LO, MA, name, datetime_format
        ("D_Data", 150, 252, 20, 200, "DAILY", "%b %d"),
        ("W_Data", 120, 52, 10, 50, "WEEKLY", "%Y-%m"),
        ("M_Data", 120, 12, 6, 20, "MONTHLY", "%Y-%m"),
    ]

    for i, (key, show_n, h_p, l_p, ma_p, name, dt_fmt) in enumerate(configs):
        df_raw = data_dict.get(key)
        if df_raw is None or df_raw.empty:
            continue

        df = df_raw.copy()

        # --- Core overlays (aligned with V2.9.6) ---
        df["HI"] = df["High"].rolling(h_p).max().shift(1)
        df["LO"] = df["Low"].rolling(l_p).min().shift(1)
        df["MA"] = df["Close"].rolling(ma_p).mean()   # no shift

        # --- BX parameters by timeframe ---
        if name == "DAILY":
            df["bx_s"] = get_rsi_ema(df["Close"], 5, 3)      # bar
            df["bx_l"] = get_rsi_ema(df["Close"], 20, 10)    # line (still ok to display)
        else:
            # weekly/monthly: line uses (20,10); bar uses (5,3) but you can still display bar for consistency
            df["bx_s"] = get_rsi_ema(df["Close"], 5, 3)
            df["bx_l"] = get_rsi_ema(df["Close"], 20, 10)

        p_df = df.tail(show_n)

        ax_p = plt.subplot2grid((9, 1), (i * 3, 0), rowspan=2)
        ax_b = plt.subplot2grid((9, 1), (i * 3 + 2, 0), rowspan=1)

        bx_colors = ["#26a69a" if v > 0 else "#ef5350" for v in p_df["bx_s"]]

        apds = [
            mpf.make_addplot(p_df["HI"], ax=ax_p, color="#9c27b0", linestyle="--", width=1.0),
            mpf.make_addplot(p_df["LO"], ax=ax_p, color="#ff9800", linestyle=":", width=1.5),
            mpf.make_addplot(p_df["MA"], ax=ax_p, color="#2196f3", linestyle="-", width=1.2),

            mpf.make_addplot(p_df["bx_s"], ax=ax_b, type="bar", color=bx_colors, width=0.7),
            mpf.make_addplot(p_df["bx_l"], ax=ax_b, color="#1a237e", width=1.5),  # ✅ 修复：width，不是 linewidth
        ]

        mpf.plot(
            p_df,
            type="candle",
            ax=ax_p,
            addplot=apds,
            style=style,
            datetime_format=dt_fmt,
            xrotation=15,
            axtitle="",
            volume=False,
            warn_too_much_data=999999,
        )

        ax_p.set_title(f"{name} | {ticker} | V2.9.6", fontsize=12, fontweight="bold", loc="left")
        ax_b.axhline(0, color="gray", alpha=0.3)
        ax_b.set_ylabel("BX", fontsize=8)

    plt.tight_layout()
    return fig


# ====== UI ======
st.title(UI["title"])
ticker = st.sidebar.text_input(UI["ticker"], value="D05.SI")
start_date = st.sidebar.date_input(UI["start"], value=pd.to_datetime("2020-01-01"))

t1, t2 = st.tabs([UI["tab1"], UI["tab2"]])

with t1:
    if st.sidebar.button(UI["run_eod"]):
        res = run_eod_analyzer(ticker)
        if not res:
            st.error(UI["no_data"])
        else:
            st.info(f"### {UI['action']}: {res['Action']}")
            st.write(f"**{UI['reason']}:** {res['Reason']}")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric(UI["fuel"], res["Fuel"])
            c2.metric(UI["push"], res["Push"])
            c3.metric(UI["gap"], res["Gap"])
            c4.metric(UI["stop"], res["Stop"])
            c5.metric(UI["macro"], res["Macro"])

            st.subheader(UI["chart"])
            st.pyplot(draw_v296_charts(res, ticker))

with t2:
    if st.sidebar.button(UI["run_bt"]):
        stats, trades, equity = run_smartstock_v296_engine(ticker, start_date, pd.to_datetime("today"))
        if equity is None or equity.empty:
            st.error(UI["no_data"])
        else:
            st.subheader(f"{UI['perf']}: {ticker}")

            c1, c2, c3 = st.columns(3)
            c1.metric(UI["total_return"], stats.get("Total Return", "n/a"))
            c2.metric(UI["trades"], stats.get("Trades", 0))
            c3.metric(UI["final_equity"], stats.get("Final Value", "n/a"))

            c4, c5, c6 = st.columns(3)
            c4.metric(UI["veto"], stats.get("Macro Vetoes", 0))
            c5.metric(UI["breakout"], stats.get("Breakout", 0))
            c6.metric(UI["reversal"], stats.get("Reversal", 0))

            st.line_chart(equity.set_index("Date")["Equity"])
            st.dataframe(trades)


