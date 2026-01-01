import streamlit as st
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_smartstock_v296_engine, run_eod_analyzer, calculate_rsi_wilder

st.set_page_config(page_title="SmartStock V2.9.6 Dashboard", layout="wide")

def draw_audit_charts(df, ticker):
    """绘制三周期联动图表，包含 B-XTRender 动能系统 """
    fig = plt.figure(figsize=(14, 22), facecolor='white')
    
    # 指标配置：日/周/月
    configs = [
        ('DAILY', '6M', 252, 20, 200, 5, 3),   # HI, LO, MA, RSI_P, EMA_P
        ('WEEKLY', '2Y', 52, 10, 50, 10, 5),
        ('MONTHLY', '8Y', 12, 6, 20, 20, 10)
    ]

    for i, (p_name, p_range, h_p, l_p, ma_p, rsi_p, ema_p) in enumerate(configs, 1):
        # 数据重采样
        if p_name == 'DAILY':
            work_df = df.copy()
        elif p_name == 'WEEKLY':
            work_df = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        else:
            work_df = df.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        
        # 计算 Chart Legend 指标 
        work_df['HI'] = work_df['High'].rolling(h_p).max().shift(1) # 紫虚线
        work_df['LO'] = work_df['Low'].rolling(l_p).min().shift(1)  # 橙点线
        work_df['MA'] = work_df['Close'].rolling(ma_p).mean()      # 蓝实线
        
        # 计算 B-XTRender 动能
        rsi = calculate_rsi_wilder(work_df['Close'], rsi_p) - 50
        work_df['hist'] = rsi.ewm(span=ema_p, adjust=False).mean()
        work_df['signal'] = work_df['hist'].ewm(span=ema_p*2, adjust=False).mean()
        
        plot_df = work_df.last(p_range)
        
        # 布局：上部主图，下部动能图
        ax_main = plt.subplot(6, 1, (i*2-1))
        ax_hist = plt.subplot(6, 1, (i*2))
        
        # 配置主图叠加层 
        apds = [
            mpf.make_addplot(plot_df['HI'], ax=ax_main, color='purple', linestyle='--', width=0.8),
            mpf.make_addplot(plot_df['LO'], ax=ax_main, color='orange', linestyle=':', width=1.2),
            mpf.make_addplot(plot_df['MA'], ax=ax_main, color='blue', linestyle='-', width=1.0),
        ]
        
        # 配置 B-XTRender 动能柱 
        colors = ['#26a69a' if val > 0 else '#ef5350' for val in plot_df['hist']]
        apds.append(mpf.make_addplot(plot_df['hist'], ax=ax_hist, type='bar', color=colors, width=0.7))
        apds.append(mpf.make_addplot(plot_df['signal'], ax=ax_hist, color='navy', width=1.2))
        
        mpf.plot(plot_df, type='candle', ax=ax_main, addplot=apds, style='charles', datetime_format='%Y-%m')
        ax_main.set_title(f"{p_name} | {ticker} | V2.9.6", fontsize=14, fontweight='bold', loc='left')
        ax_hist.axhline(0, color='gray', linewidth=0.5, alpha=0.5)

    plt.tight_layout()
    return fig

# UI
st.sidebar.title("SmartStock V2.9.6")
ticker = st.sidebar.text_input("Ticker Symbol", value="D05.SI")

t1, t2 = st.tabs(["【 AUDIT SUMMARY 】", "【 BACKTEST AUDIT 】"])

with t1:
    if st.button("RUN EOD ANALYSIS"):
        res = run_eod_analyzer(ticker)
        if res:
            st.info(f"### ACTION: {res['Action']}")
            st.write(f"**REASON:** {res['Reason']}")
            
            # Physics Log 仪表盘 
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fuel (Vol Ratio)", res["Fuel"])
            c2.metric("Push (Close Pos)", res["Push"])
            c3.metric("Gap (Dist High)", res["Gap"])
            c4.metric("Macro Check", res["Macro"])
            
            st.divider()
            st.subheader("CHART AUDIT (MULTI-PERIOD SYNC)")
            fig = draw_audit_charts(res["Full_Data"], ticker)
            st.pyplot(fig)
            
            # 对齐 Legend 解释 
            st.markdown("""
            **CHART LEGEND:**
            - 🟦 **BLUE SOLID**: 200D/50W/20M MA (大周期成本线)
            - 🟪 **PURPLE DASH**: 1-YEAR HIGH (阻力参考)
            - 🟧 **ORANGE DOT**: L20 SUPPORT (审计止损线)
            - 🟢🔴 **B-XTRender**: 动能共振系统
            """)
