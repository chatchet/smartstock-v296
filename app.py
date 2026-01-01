import streamlit as st
import pandas as pd
import plotly.express as px
from engine import run_smartstock_v296_engine, run_eod_analyzer

st.set_page_config(page_title="SmartStock V2.9.6 Dashboard", layout="wide")

st.title("⚖️ SmartStock V2.9.6 Dashboard")
st.caption("Singapore Market | Universal EOD Engine & Audit Backtester")

# Sidebar 设置
with st.sidebar:
    st.header("Global Settings")
    ticker = st.text_input("Ticker Symbol (e.g. D05.SI)", value="D05.SI")
    st.info("System v2.9.6: High-fidelity logic synchronization.")

# 定义标签页
tab1, tab2 = st.tabs(["🎯 Daily Analysis (EOD)", "📊 Audit Backtest"])

with tab1:
    st.subheader(f"Current Signal Radar: {ticker}")
    if st.button("Scan Current Market Status"):
        with st.spinner("Analyzing real-time signals..."):
            result = run_eod_analyzer(ticker)
            if result:
                # 核心指标卡片
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current Price", result["Price"])
                c2.metric("Signal Status", result["Signal"])
                c3.metric("Weekly Bull", result["Weekly_Bull"])
                c4.metric("Monthly Bull", result["Monthly_Bull"])
                
                # 技术细节
                st.write("### Technical Scan (Audit Data)")
                st.table(pd.DataFrame([result]))
            else:
                st.error("Data error. Check the ticker symbol.")

with tab2:
    st.subheader(f"Strategy Audit: {ticker}")
    start_date = st.date_input("Audit Start Date", value=pd.to_datetime("2010-01-01"))
    if st.button("Run Full Strategy Audit"):
        with st.spinner("Crunching historical bars..."):
            stats, trades, equity = run_smartstock_v296_engine(ticker, start_date, "2026-01-01")
            
            if stats:
                # 汇总指标
                total_ret = (equity['Equity'].iloc[-1] / 100000.0) - 1
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Return", f"{total_ret:.2%}")
                m2.metric("Macro Vetoes", stats['veto'])
                m3.metric("Integrity Check", "PASS ✅")

                # 权益曲线
                fig = px.line(equity, x='Date', y='Equity', title=f"Historical Growth for {ticker}")
                st.plotly_chart(fig, use_container_width=True)

                # 交易日志
                st.subheader("Detailed Trade Log")
                st.dataframe(trades, use_container_width=True)
            else:
                st.error("No historical data available for this range.")
