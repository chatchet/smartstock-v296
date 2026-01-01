import streamlit as st
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_smartstock_v296_engine, run_eod_analyzer, calculate_rsi_wilder

st.set_page_config(page_title="SmartStock V2.9.6 Dashboard", layout="wide")

def draw_audit_charts(df, ticker):
    """三周期联动绘图，严格对齐 CHART LEGEND """
    fig = plt.figure(figsize=(12, 20), facecolor='white')
    
    # 定义周期配置
    configs = [
        ('DAILY', '6M', 252, 20, 200, 5, 3),   # 252日高, 20日低, 200日均线
        ('WEEKLY', '2Y', 52, 10, 50, 10, 5),   # 52周高, 10周低, 50周均线
        ('MONTHLY', '8Y', 12, 6, 20, 20, 10)   # 12月高, 6月低, 20月均线
    ]

    for i, (p_name, p_range, h_p, l_p, ma_p, rsi_p, ema_p) in enumerate(configs, 1):
        # 1. 数据重采样
        if p_name == 'DAILY':
            work_df = df.copy()
        elif p_name == 'WEEKLY':
            work_df = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        else:
            work_df = df.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        
        # 2. 计算 Legend 指标 
        work_df['HI'] = work_df['High'].rolling(h_p).max().shift(1)
        work_df['LO'] = work_df['Low'].rolling(l_p).min().shift(1)
        work_df['MA'] = work_df['Close'].rolling(ma_p).mean()
        
        # 3. 计算 B-XTRender (底部动能柱) 
        rsi = calculate_rsi_wilder(work_df['Close'], rsi_p) - 50
        work_df['hist'] = rsi.ewm(span=ema_p, adjust=False).mean()
        work_df['signal'] = work_df['hist'].ewm(span=ema_p*2, adjust=False).mean()
        
        # 截取显示范围
        plot_df = work_df.last(p_range)
        
        # 4. 绘图
        ax_main = plt.subplot(6, 1, (i*2-1)) # 主图占位
        ax_hist = plt.subplot(6, 1, (i*2))   # 动能图占位
        
        # 主图线条配置
        apds = [
            mpf.make_addplot(plot_df['HI'], ax=ax_main, color='purple', linestyle='--', width=1), # 紫虚线: 1-YEAR HIGH
            mpf.make_addplot(plot_df['LO'], ax=ax_main, color='orange', linestyle=':', width=1.5), # 橙点线: L20 SUPPORT
            mpf.make_addplot(plot_df['MA'], ax=ax_main, color='blue', linestyle='-', width=1.2),  # 蓝实线: 大周期成本线
        ]
        
        # 动能柱配置 (B-XTRender)
        colors = ['#26a69a' if val > 0 else '#ef5350' for val in plot_df['hist']]
        apds.append(mpf.make_addplot(plot_df['hist'], ax=ax_hist, type='bar', color=colors, width=0.7))
        apds.append(mpf.make_addplot(plot_df['signal'], ax=ax_hist, color='blue', width=1)) # 底部蓝线
        
        mpf.plot(plot_df, type='candle', ax=ax_main, addplot=apds, style='charles', datetime_format='%y-%m')
        ax_main.set_title(f"{p_name} | {ticker} | V2.9.6", fontsize=12, fontweight='bold', loc='left')
        ax_hist.set_ylim(work_df['hist'].min()*1.2, work_df['hist'].max()*1.2)
        ax_hist.axhline(0, color='gray', linestyle='-', alpha=0.3)

    plt.tight_layout()
    return fig

# UI 布局
st.sidebar.title("SmartStock V2.9.6")
ticker = st.sidebar.text_input("Ticker Symbol", value="D05.SI")

t1, t2 = st.tabs(["【 AUDIT SUMMARY 】", "【 BACKTEST AUDIT 】"])

with t1:
    if st.button("RUN EOD ANALYSIS"):
        res = run_eod_analyzer(ticker)
        if res:
            st.info(f"### ACTION: {res['Action']}")
            st.write(f"**REASON:** {res['Reason']}")
            
            # Physics Log
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fuel (Vol Ratio)", res["Fuel"])
            c2.metric("Push (Close Pos)", res["Push"])
            c3.metric("Gap (Dist High)", res["Gap"])
            c4.metric("Macro Check", res["Macro"])
            
            # 绘图显示
            st.divider()
            st.subheader("CHART AUDIT (MULTI-PERIOD SYNC)")
            fig = draw_audit_charts(res["Full_Data"], ticker)
            st.pyplot(fig)
            
            # 线义说明
            st.caption("Legend: 🟦 200D MA | 🟪 252D High (Dash) | 🟧 20D Low (Dot) | 🟢🔴 B-XTRender Hist")
