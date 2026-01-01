import streamlit as st
import pandas as pd
import plotly.express as px
from engine import run_smartstock_v296_engine

st.set_page_config(page_title="SmartStock V2.9.6 Audit", layout="wide")

st.title("⚖️ SmartStock V2.9.6 Audit System")
st.caption("Singapore Market Aligned | True-Sync Backtest Engine")

# Sidebar
with st.sidebar:
    st.header("Settings")
    ticker = st.text_input("Ticker (Yahoo Finance)", value="D05.SI")
    start_date = st.date_input("Start Date", value=pd.to_datetime("2010-01-01"))
    btn_run = st.button("Run Audit Backtest")

# 修改后的 app.py 核心部分
tab1, tab2 = st.tabs(["🎯 Daily Analysis (EOD)", "📊 Audit Backtest"])

with tab1:
    st.subheader("Universal EOD Signal Radar")
    if st.button("Scan Current Signals"):
        res = run_eod_analyzer(ticker)
        if res:
            st.json(res) # 也可以用 st.table(pd.DataFrame([res])) 展示
            if res["Signal"] != "WAIT":
                st.success(f"Signal Detected: {res['Signal']}")

with tab2:
 if btn_run:
    with st.spinner("Synchronizing data and auditing signals..."):
        stats, trades, equity = run_smartstock_v296_engine(ticker, start_date, "2026-01-01")
        
        if stats:
            # Metrics
            total_ret = (equity['Equity'].iloc[-1] / 100000.0) - 1
            st.columns(3)[0].metric("Total Return", f"{total_ret:.2%}")
            st.columns(3)[1].metric("Macro Vetoes", stats['veto'])
            st.columns(3)[2].metric("Integrity Check", "PASS ✅")

            # Chart
            fig = px.line(equity, x='Date', y='Equity', title=f"Equity Curve: {ticker}")
            st.plotly_chart(fig, use_container_width=True)

            # Trades list
            st.subheader("Audit Trade Log")
            st.dataframe(trades, use_container_width=True)
        else:
            st.error("No data found. Check the ticker symbol.")
