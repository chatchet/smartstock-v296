import streamlit as st
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_smartstock_v296_engine, run_eod_analyzer, calculate_rsi_wilder

st.set_page_config(page_title="SmartStock V2.9.6 Dashboard", layout="wide")

def draw_audit_charts(df, ticker):
    """复刻专业审计图表：三周期、B-XTRender、线义对齐 """
    # 强制设置中文字体环境
    plt.rcParams['axes.unicode_minus'] = False
    
    # 1. 样式定义：蜡烛图实体颜色对齐报告
    mc = mpf.make_marketcolors(up='#ef5350', down='#26a69a', edge='inherit', wick='inherit', volume='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', gridcolor='#eeeeee', facecolor='white')

    fig = plt.figure(figsize=(14, 25), facecolor='white')
    
    # 周期参数配置：(HI_P一年高, LO_P支撑, MA_P均线, RSI_P, EMA_P) 
    configs = [
        ('DAILY', '6M', 252, 20, 200, 5, 3),   # Daily: 252D/20D/200D
        ('WEEKLY', '2Y', 52, 10, 50, 10, 5),   # Weekly: 52W/10W/50W
        ('MONTHLY', '8Y', 12, 6, 20, 20, 10)   # Monthly: 12M/6M/20M
    ]

    for i, (p_name, p_range, h_p, l_p, ma_p, rsi_p, ema_p) in enumerate(configs, 1):
        if p_name == 'DAILY':
            work_df = df.copy()
        elif p_name == 'WEEKLY':
            work_df = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        else:
            work_df = df.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        
        # 指标计算 
        work_df['HI'] = work_df['High'].rolling(h_p).max().shift(1) # 紫虚线
        work_df['LO'] = work_df['Low'].rolling(l_p).min().shift(1)  # 橙点线
        work_df['MA'] = work_df['Close'].rolling(ma_p).mean()      # 蓝实线
        
        # B-XTRender 动能 
        rsi_diff = calculate_rsi_wilder(work_df['Close'], rsi_p) - 50
        work_df['hist'] = rsi_diff.ewm(span=ema_p, adjust=False).mean()
        work_df['signal'] = work_df['hist'].ewm(span=ema_p*2, adjust=False).mean()
        
        plot_df = work_df.last(p_range)
        
        # 布局：主图与动能图
        ax_main = plt.subplot(6, 1, (i*2-1))
        ax_hist = plt.subplot(6, 1, (i*2))
        
        # 添加指标线
        apds = [
            mpf.make_addplot(plot_df['HI'], ax=ax_main, color='#9c27b0', linestyle='--', width=1.0), # Purple Dash
            mpf.make_addplot(plot_df['LO'], ax=ax_main, color='#ff9800', linestyle=':', width=1.5),  # Orange Dot
            mpf.make_addplot(plot_df['MA'], ax=ax_main, color='#2196f3', linestyle='-', width=1.2),  # Blue Solid
        ]
        
        # 动能柱颜色逻辑
        colors = ['#26a69a' if val > 0 else '#ef5350' for val in plot_df['hist']]
        apds.append(mpf.make_addplot(plot_df['hist'], ax=ax_hist, type='bar', color=colors, width=0.8))
        apds.append(mpf.make_addplot(plot_df['signal'], ax=ax_hist, color='#1a237e', width=1.5)) # Signal Line
        
        mpf.plot(plot_df, type='candle', ax=ax_main, addplot=apds, style=s, datetime_format='%y-%m')
        ax_main.set_title(f"{p_name} | {ticker} | V2.9.6", fontsize=14, fontweight='bold', loc='left')
        ax_hist.axhline(0, color='black', linewidth=0.5, alpha=0.3)
        ax_hist.set_ylabel("B-XTRender", fontsize=8)

    plt.tight_layout()
    return fig

# UI 核心
st.sidebar.title("SmartStock V2.9.6")
ticker = st.sidebar.text_input("Ticker Symbol", value="D05.SI")

t1, t2 = st.tabs(["【 AUDIT SUMMARY 】", "【 BACKTEST AUDIT 】"])

with t1:
    if st.button("RUN EOD ANALYSIS"):
        res = run_eod_analyzer(ticker)
        if res:
            st.info(f"### ACTION: {res['Action']}")
            st.write(f"**REASON:** {res['Reason']}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fuel (Vol Ratio)", res["Fuel"])
            c2.metric("Push (Close Pos)", res["Push"])
            c3.metric("Gap (Dist High)", res["Gap"])
            c4.metric("Stop (20D-LOW)", res["Stop"])
            
            st.divider()
            st.subheader("CHART AUDIT (MULTI-PERIOD SYNC)")
            fig = draw_audit_charts(res["Full_Data"], ticker)
            st.pyplot(fig)
            
            # CHART LEGEND 对齐报告 
            st.markdown("""
            **CHART LEGEND / 图表线义解释:**
            - 🟦 **BLUE SOLID**: 200D/50W/20M MA (大周期成本分界线) 
            - 🟪 **PURPLE DASH**: 1-YEAR HIGH (阻力位，高位缩量严禁追高) 
            - 🟧 **ORANGE DOT**: L20 SUPPORT (审计硬止损线) 
            - 🟢🔴 **B-XTRender**: 底部动能柱（柱状代表动能，蓝线代表趋势基准） 
            """)
