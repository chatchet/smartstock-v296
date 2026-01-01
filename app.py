import streamlit as st
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_eod_analyzer, get_rsi_ema, run_smartstock_v296_engine
import pandas as pd

st.set_page_config(page_title="SmartStock V2.9.6 Audit", layout="wide")

def draw_v296_charts(data_dict, ticker):
    fig = plt.figure(figsize=(14, 22), facecolor='white')
    # 周期配置 (数据源, 窗口, HI, LO, MA, 标题)
    configs = [
        (data_dict['D_Data'], 80, 252, 20, 200, "DAILY"),
        (data_dict['W_Data'], 52, 52, 10, 50, "WEEKLY"),
        (data_dict['M_Data'], 40, 12, 6, 20, "MONTHLY")
    ]
    for i, (df_raw, show_n, h_p, l_p, ma_p, name) in enumerate(configs):
        df = df_raw.copy()
        df['HI'] = df['High'].rolling(h_p).max().shift(1)
        df['LO'] = df['Low'].rolling(l_p).min().shift(1)
        df['MA'] = df['Close'].rolling(ma_p).mean()
        # 对齐所有周期的 BX 指标口径
        df['bx_s'] = get_rsi_ema(df['Close'], 5, 3) # 柱
        df['bx_l'] = get_rsi_ema(df['Close'], 20, 10) # 线
        
        p_df = df.tail(show_n)
        ax_p = plt.subplot2grid((9, 1), (i*3, 0), rowspan=2)
        ax_b = plt.subplot2grid((9, 1), (i*3 + 2, 0), rowspan=1)
        
        apds = [
            mpf.make_addplot(p_df['HI'], ax=ax_p, color='#9c27b0', linestyle='--', width=1),
            mpf.make_addplot(p_df['LO'], ax=ax_p, color='#ff9800', linestyle=':', width=1.5),
            mpf.make_addplot(p_df['MA'], ax=ax_p, color='#2196f3', linestyle='-', width=1.2),
            mpf.make_addplot(p_df['bx_s'], ax=ax_b, type='bar', color=['#26a69a' if v > 0 else '#ef5350' for v in p_df['bx_s']], width=0.7),
            mpf.make_addplot(p_df['bx_l'], ax=ax_b, color='#1a237e', width=1.5),
        ]
        mpf.plot(p_df, type='candle', ax=ax_p, addplot=apds, style='charles', datetime_format='%y-%m')
        ax_p.set_title(f"{name} | {ticker} | V2.9.6", fontsize=12, fontweight='bold', loc='left')
        ax_b.axhline(0, color='gray', alpha=0.3)
    plt.tight_layout()
    return fig

# --- UI 交互 ---
st.title("SmartStock V2.9.6 Audit System")
ticker = st.sidebar.text_input("Ticker Symbol", value="D05.SI")
start_date = st.sidebar.date_input("Backtest Start", value=pd.to_datetime("2020-01-01"))

t1, t2 = st.tabs(["【 AUDIT SUMMARY 】", "【 BACKTEST AUDIT 】"])

with t1:
    if st.sidebar.button("RUN EOD ANALYSIS"):
        res = run_eod_analyzer(ticker)
        if res:
            st.info(f"### ACTION: {res['Action']}")
            st.write(f"**REASON:** {res['Reason']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fuel", res['Fuel'])
            c2.metric("Push", res['Push'])
            c3.metric("Gap", res['Gap'])
            c4.metric("Stop", res['Stop'])
            st.pyplot(draw_v296_charts(res, ticker))

with t2:
    if st.sidebar.button("RUN BACKTEST"):
        stats, trades, equity = run_smartstock_v296_engine(ticker, start_date, pd.to_datetime("today"))
        if not equity.empty:
            st.subheader(f"Strategy Performance: {ticker}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Return", stats["Total Return"])
            c2.metric("Total Trades", stats["Trades"])
            c3.metric("Final Equity", stats["Final Value"])
            st.line_chart(equity.set_index('Date')['Equity'])
            st.dataframe(trades)
