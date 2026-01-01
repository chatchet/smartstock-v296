import streamlit as st
import mplfinance as mpf
import matplotlib.pyplot as plt
import pandas as pd
from engine import run_eod_analyzer, get_rsi_ema, run_smartstock_v296_engine

st.set_page_config(page_title="SmartStock V2.9.6 | True Sync", layout="wide")

def draw_v296_unified_charts(data_dict, ticker):
    # 建立大图，三周期垂直对齐
    fig = plt.figure(figsize=(14, 24), facecolor='white')
    # 周期配置 (数据源, 窗口根数, HI周期, LO周期, MA周期, 标题)
    configs = [
        (data_dict['D_Data'], 80, 252, 20, 200, "DAILY"),
        (data_dict['W_Data'], 52, 52, 10, 50, "WEEKLY"),
        (data_dict['M_Data'], 40, 12, 6, 20, "MONTHLY")
    ]

    for i, (df_raw, show_n, h_p, l_p, ma_p, name) in enumerate(configs):
        df = df_raw.copy()
        # 1. 核心指标 (HI/LO 用 shift(1), MA/Volume 不 shift)
        df['HI'] = df['High'].rolling(h_p).max().shift(1)
        df['LO'] = df['Low'].rolling(l_p).min().shift(1)
        df['MA'] = df['Close'].rolling(ma_p).mean()
        
        # 2. BX 系统参数对齐：柱(bx_s:5,3), 线(bx_l:20,10)
        df['bx_s'] = get_rsi_ema(df['Close'], 5, 3)
        df['bx_l'] = get_rsi_ema(df['Close'], 20, 10)
        
        p_df = df.tail(show_n)
        
        # 3. 布局：价格轴与动能轴
        ax_p = plt.subplot2grid((9, 1), (i*3, 0), rowspan=2)
        ax_b = plt.subplot2grid((9, 1), (i*3 + 2, 0), rowspan=1)
        
        # 4. 叠加层定义
        apds = [
            mpf.make_addplot(p_df['HI'], ax=ax_p, color='#9c27b0', linestyle='--', width=1.0),
            mpf.make_addplot(p_df['LO'], ax=ax_p, color='#ff9800', linestyle=':', width=1.5),
            mpf.make_addplot(p_df['MA'], ax=ax_p, color='#2196f3', linestyle='-', width=1.2),
            mpf.make_addplot(p_df['bx_s'], ax=ax_b, type='bar', color=['#26a69a' if v > 0 else '#ef5350' for v in p_df['bx_s']], width=0.7),
            mpf.make_addplot(p_df['bx_l'], ax=ax_b, color='#1a237e', width=1.5),
        ]
        
        # 5. 执行绘制
        mpf.plot(p_df, type='candle', ax=ax_p, addplot=apds, style='charles', datetime_format='%y-%m')
        ax_p.set_title(f"{name} | {ticker} | V2.9.6", fontsize=12, fontweight='bold', loc='left')
        ax_b.axhline(0, color='gray', alpha=0.3)

    plt.tight_layout()
    return fig

# --- 网页 UI 层 ---
st.title("SmartStock V2.9.6 线上审计系统")
ticker = st.sidebar.text_input("Ticker Symbol", value="D05.SI")
start_date = st.sidebar.date_input("回测开始日期", value=pd.to_datetime("2020-01-01"))

t1, t2 = st.tabs(["【 EOD 审计摘要 】", "【 回测深度审计 】"])

with t1:
    if st.sidebar.button("执行 EOD 分析"):
        res = run_eod_analyzer(ticker)
        if res:
            st.info(f"### 建议动作: {res['Action']}")
            st.write(f"**逻辑原因:** {res['Reason']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fuel (Vol Ratio)", res['Fuel'])
            c2.metric("Push (Close Pos)", res['Push'])
            c3.metric("Gap (Dist High)", res['Gap'])
            c4.metric("Stop (20D Low)", res['Stop'])
            
            st.divider()
            st.pyplot(draw_v296_unified_charts(res, ticker))
        else:
            st.error("数据抓取失败，请检查 Ticker 格式。")

with t2:
    if st.sidebar.button("执行全量回测"):
        stats, trades, equity = run_smartstock_v296_engine(ticker, start_date, pd.to_datetime("today"))
        if not equity.empty:
            st.subheader("策略表现与资产曲线")
            c1, c2, c3 = st.columns(3)
            c1.metric("总收益率", stats["Total Return"])
            c2.metric("交易笔数", stats["Trades"])
            c3.metric("终值净值", stats["Final Value"])
            
            st.line_chart(equity.set_index('Date')['Equity'])
            st.write("### 交易流水细目")
            st.dataframe(trades)
