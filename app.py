import streamlit as st
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_smartstock_v296_engine, run_eod_analyzer, calculate_rsi_wilder

st.set_page_config(page_title="SmartStock V2.9.6 Dashboard", layout="wide")

def draw_audit_charts(df, ticker):
    """绘制 Daily/Weekly/Monthly 三周期联动，包含 B-XTRender 系统"""
    # 样式配置：对齐专业报告 K 线颜色
    mc = mpf.make_marketcolors(up='#ef5350', down='#26a69a', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', gridcolor='#eeeeee', facecolor='white')
    
    fig = plt.figure(figsize=(14, 25), facecolor='white')
    
    # 周期配置 (HI一年高, LO支撑, MA成本线, RSI周期, EMA平滑)
    configs = [
        ('DAILY', '6M', 252, 20, 200, 5, 3),   # DAILY: 蓝(200D MA) 
        ('WEEKLY', '2Y', 52, 10, 50, 10, 5),   # WEEKLY: 蓝(50W MA) 
        ('MONTHLY', '8Y', 12, 6, 20, 20, 10)   # MONTHLY: 蓝(20M MA) 
    ]

    for i, (p_name, p_range, h_p, l_p, ma_p, rsi_p, ema_p) in enumerate(configs, 1):
        if p_name == 'DAILY':
            work_df = df.copy()
        elif p_name == 'WEEKLY':
            work_df = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        else:
            work_df = df.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        
        # 计算线义解释中的指标 
        work_df['HI'] = work_df['High'].rolling(h_p).max().shift(1) # 紫虚线
        work_df['LO'] = work_df['Low'].rolling(l_p).min().shift(1)  # 橙点线
        work_df['MA'] = work_df['Close'].rolling(ma_p).mean()      # 蓝实线
        
        # B-XTRender 系统核心计算
        rsi_raw = calculate_rsi_wilder(work_df['Close'], rsi_p) - 50
        work_df['hist'] = rsi_raw.ewm(span=ema_p, adjust=False).mean()
        work_df['signal'] = work_df['hist'].ewm(span=ema_p*2, adjust=False).mean()
        
        plot_df = work_df.last(p_range)
        
        # 布局：主图与动能图
        ax_main = plt.subplot(6, 1, (i*2-1))
        ax_hist = plt.subplot(6, 1, (i*2))
        
        # 添加主图指标线
        apds = [
            mpf.make_addplot(plot_df['HI'], ax=ax_main, color='#9c27b0', linestyle='--', width=1.0),
            mpf.make_addplot(plot_df['LO'], ax=ax_main, color='#ff9800', linestyle=':', width=1.5),
            mpf.make_addplot(plot_df['MA'], ax=ax_main, color='#2196f3', linestyle='-', width=1.2),
        ]
        
        # 添加 B-XTRender 动能柱与蓝线
        colors = ['#26a69a' if val > 0 else '#ef5350' for val in plot_df['hist']]
        apds.append(mpf.make_addplot(plot_df['hist'], ax=ax_hist, type='bar', color=colors, width=0.7))
        apds.append(mpf.make_addplot(plot_df['signal'], ax=ax_hist, color='#1a237e', width=1.5))
        
        # 绘制 K 线并叠加指标
        mpf.plot(plot_df, type='candle', ax=ax_main, addplot=apds, style=s, datetime_format='%y-%m')
        ax_main.set_title(f"{p_name} | {ticker} | V2.9.6", fontsize=14, fontweight='bold', loc='left')
        ax_hist.axhline(0, color='gray', linewidth=0.5, alpha=0.5)

    plt.tight_layout()
    return fig

# UI 交互层
st.sidebar.title("SmartStock V2.9.6")
ticker = st.sidebar.text_input("Ticker Symbol", value="D05.SI")

t1, t2 = st.tabs(["【 AUDIT SUMMARY 】", "【 BACKTEST AUDIT 】"])

with t1:
    if st.button("RUN EOD ANALYSIS"):
        res = run_eod_analyzer(ticker)
        if res:
            # 对齐审计摘要 UI 
            st.info(f"### ACTION: {res['Action']}")
            st.write(f"**REASON:** {res['Reason']}")
            
            # 物理记录对齐
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fuel (Vol Ratio)", res["Fuel"])
            c2.metric("Push (Close Pos)", res["Push"])
            c3.metric("Gap (Dist High)", res["Gap"])
            c4.metric("Stop (20D-LOW)", res["Stop"])
            
            st.divider()
            st.subheader("CHART AUDIT (MULTI-PERIOD SYNC)")
            fig = draw_audit_charts(res["Full_Data"], ticker)
            st.pyplot(fig)
            
            # CHART LEGEND 对齐
            st.markdown("""
            **CHART LEGEND / 图表线义解释:**
            - 🟦 **BLUE SOLID**: 200D/50W/20M MA (大周期成本分界线)
            - 🟪 **PURPLE DASH**: 1-YEAR HIGH (阻力位，高位缩量严禁追高)
            - 🟧 **ORANGE DOT**: L20 SUPPORT (审计硬止损线)
            - 🟢🔴 **B-XTRender**: 底部动能柱与趋势蓝线
            """)
