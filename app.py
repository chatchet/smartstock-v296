import streamlit as st
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_smartstock_v296_engine, run_eod_analyzer, calculate_rsi_wilder

st.set_page_config(page_title="SmartStock V2.9.6 Dashboard", layout="wide")

def draw_unified_charts(df, ticker):
    """
    完全对齐 Colab 风格：
    1. 价格与 BX 动能系统合并在一个 Figure 中
    2. 严格对齐 Daily/Weekly/Monthly 三段式布局
    """
    # 样式定义
    mc = mpf.make_marketcolors(up='#ef5350', down='#26a69a', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', gridcolor='#eeeeee', facecolor='white')
    
    # 创建一个大的画布，分为 3 个主区域 (Daily/Weekly/Monthly)
    fig = plt.figure(figsize=(12, 22), facecolor='white')
    
    # 周期配置 (显示根数, HI周期, LO周期, MA周期, RSI周期, EMA平滑)
    configs = [
        ('DAILY', 80, 252, 20, 200, 5, 3),   # 对齐 Colab show_n=80
        ('WEEKLY', 52, 52, 10, 50, 10, 5),   # 1年周线
        ('MONTHLY', 40, 12, 6, 20, 20, 10)   # 约3年月线
    ]

    for i, (p_name, show_n, h_p, l_p, ma_p, rsi_p, ema_p) in enumerate(configs):
        # 1. 数据采样
        if p_name == 'DAILY':
            work_df = df.copy()
        elif p_name == 'WEEKLY':
            work_df = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        else:
            work_df = df.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        
        # 2. 计算指标 
        work_df['HI'] = work_df['High'].rolling(h_p).max().shift(1) # 紫虚线
        work_df['LO'] = work_df['Low'].rolling(l_p).min().shift(1)  # 橙点线
        work_df['MA'] = work_df['Close'].rolling(ma_p).mean()      # 蓝实线
        
        # B-XTRender 计算
        rsi_raw = calculate_rsi_wilder(work_df['Close'], rsi_p) - 50
        work_df['hist'] = rsi_raw.ewm(span=ema_p, adjust=False).mean()
        work_df['signal'] = work_df['hist'].ewm(span=ema_p*2, adjust=False).mean()
        
        plot_df = work_df.tail(show_n) # 统一 show_n
        
        # 3. 分配子图：每个周期占用 2 个 subplot 行 (价格 3 : 动能 1)
        ax_price = plt.subplot2grid((9, 1), (i*3, 0), rowspan=2)
        ax_bx = plt.subplot2grid((9, 1), (i*3 + 2, 0), rowspan=1)
        
        # 配置叠加层
        apds = [
            mpf.make_addplot(plot_df['HI'], ax=ax_price, color='#9c27b0', linestyle='--', width=1.0),
            mpf.make_addplot(plot_df['LO'], ax=ax_price, color='#ff9800', linestyle=':', width=1.5),
            mpf.make_addplot(plot_df['MA'], ax=ax_price, color='#2196f3', linestyle='-', width=1.2),
        ]
        
        # BX 动能柱
        colors = ['#26a69a' if v > 0 else '#ef5350' for v in plot_df['hist']]
        apds.append(mpf.make_addplot(plot_df['hist'], ax=ax_bx, type='bar', color=colors, width=0.7))
        apds.append(mpf.make_addplot(plot_df['signal'], ax=ax_bx, color='#1a237e', width=1.2))
        
        # 绘图
        mpf.plot(plot_df, type='candle', ax=ax_price, addplot=apds, style=s, datetime_format='%y-%m')
        ax_price.set_title(f"{p_name} | {ticker} | V2.9.6", fontsize=12, fontweight='bold', loc='left')
        ax_bx.axhline(0, color='gray', linewidth=0.5, alpha=0.5)
        ax_bx.set_ylabel("BX-Render", fontsize=8)

    plt.tight_layout()
    return fig

# --- Streamlit UI 部分 ---
st.sidebar.title("SmartStock V2.9.6")
ticker = st.sidebar.text_input("Ticker Symbol", value="D05.SI")

t1, t2 = st.tabs(["【 AUDIT SUMMARY 】", "【 BACKTEST AUDIT 】"])

with t1:
    if st.button("RUN EOD ANALYSIS"):
        res = run_eod_analyzer(ticker)
        if res:
            # 1. 顶部摘要对齐审计文件 [cite: 1]
            st.info(f"### ACTION: {res['Action']}")
            st.write(f"**REASON:** {res['Reason']}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fuel (Vol Ratio)", res["Fuel"])
            c2.metric("Push (Close Pos)", res["Push"])
            c3.metric("Gap (Dist High)", res["Gap"])
            c4.metric("Stop (20D-LOW)", res["Stop"])
            
            st.divider()
            # 2. 呈现统一长图
            st.subheader("CHART AUDIT (UNIFIED MULTI-PERIOD)")
            fig = draw_unified_charts(res["Full_Data"], ticker)
            st.pyplot(fig)
            
            # 3. Legend 确权 
            st.markdown("""
            **CHART LEGEND:**
            - 🟦 **BLUE SOLID**: 200D/50W/20M MA
            - 🟪 **PURPLE DASH**: 1-YEAR HIGH (Ref Line)
            - 🟧 **ORANGE DOT**: L20 SUPPORT (Audit Stop)
            - 🟢🔴 **B-XTRender**: Momentum Oscillator
            """)
