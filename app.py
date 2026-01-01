import streamlit as st
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_smartstock_v296_engine, run_eod_analyzer

st.set_page_config(page_title="SmartStock V2.9.6", layout="wide")

def draw_triple_charts(df):
    """绘制三周期联动图表 (对齐上传图片效果)"""
    fig = plt.figure(figsize=(12, 18))
    
    periods = [('Daily', '6M'), ('Weekly', '2Y'), ('Monthly', '8Y')]
    for i, (p_name, p_range) in enumerate(periods, 1):
        ax = fig.add_subplot(3, 1, i)
        
        # 数据重采样
        if p_name == 'Daily':
            plot_df = df.last(p_range)
        elif p_name == 'Weekly':
            plot_df = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).last(p_range)
        else:
            plot_df = df.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).last(p_range)
            
        mpf.plot(plot_df, type='candle', ax=ax, style='charles', datetime_format='%Y-%m')
        ax.set_title(f"{p_name} | {ticker} | V2.9.6", fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    return fig

st.sidebar.title("SmartStock V2.9.6")
ticker = st.sidebar.text_input("Ticker Symbol", value="D05.SI")

tab1, tab2 = st.tabs(["【 AUDIT SUMMARY 】", "【 BACKTEST AUDIT 】"])

with tab1:
    if st.button("RUN EOD ANALYSIS"):
        with st.spinner("Analyzing Physics..."):
            res = run_eod_analyzer(ticker)
            if res:
                # 1. 顶部摘要
                st.info(f"### ACTION: {res['Action']}")
                st.write(f"**REASON:** {res['Reason']}")
                
                # 2. Physics Log 对齐
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Fuel (Vol Ratio)", res["Fuel"])
                c2.metric("Push (Close Pos)", res["Push"])
                c3.metric("Gap (Dist High)", res["Gap"])
                c4.metric("Macro Check", res["Macro"])
                
                # 3. 绘图区域 (三周期联动)
                st.divider()
                st.subheader("MULTI-TIMEFRAME VISUALIZATION")
                fig = draw_triple_charts(res["Full_Data"])
                st.pyplot(fig)
            else:
                st.error("Data error.")

with tab2:
    if st.button("EXECUTE BACKTEST"):
        stats, trades, equity = run_smartstock_v296_engine(ticker, "2010-01-01", "2026-01-01")
        if not equity.empty:
            st.line_chart(equity.set_index('Date'))
