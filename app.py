import streamlit as st
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_eod_analyzer, get_rsi_ema

st.set_page_config(page_title="SmartStock V2.9.6", layout="wide")

def draw_v296_charts(data_dict, ticker):
    fig = plt.figure(figsize=(14, 22), facecolor='white')
    
    # 配置对齐：(数据源, 显示根数, HI周期, LO周期, MA周期)
    plot_configs = [
        (data_dict['D_Data'], 80, 252, 20, 200, "DAILY"),
        (data_dict['W_Data'], 52, 52, 10, 50, "WEEKLY"),
        (data_dict['M_Data'], 40, 12, 6, 20, "MONTHLY")
    ]

    for i, (df_raw, show_n, h_p, l_p, ma_p, name) in enumerate(plot_configs):
        # 1. 指标计算 (严格按照线义)
        df = df_raw.copy()
        df['HI'] = df['High'].rolling(h_p).max().shift(1)
        df['LO'] = df['Low'].rolling(l_p).min().shift(1)
        df['MA'] = df['Close'].rolling(ma_p).mean()
        
        # BX 系统：柱=bx_s (RSI 5), 线=bx_l (RSI 20)
        df['bx_s'] = get_rsi_ema(df['Close'], 5, 3)
        df['bx_l'] = get_rsi_ema(df['Close'], 20, 10)
        
        p_df = df.tail(show_n)
        
        # 2. 布局：3:1 比例
        ax_p = plt.subplot2grid((9, 1), (i*3, 0), rowspan=2)
        ax_b = plt.subplot2grid((9, 1), (i*3 + 2, 0), rowspan=1)
        
        # 3. 叠加层
        # 价格层：紫虚、橙点、蓝实
        apds = [
            mpf.make_addplot(p_df['HI'], ax=ax_p, color='#9c27b0', linestyle='--', width=1),
            mpf.make_addplot(p_df['LO'], ax=ax_p, color='#ff9800', linestyle=':', width=1.5),
            mpf.make_addplot(p_df['MA'], ax=ax_p, color='#2196f3', linestyle='-', width=1.2),
        ]
        # BX 层：变色柱 bx_s + 深蓝线 bx_l
        colors = ['#26a69a' if v > 0 else '#ef5350' for v in p_df['bx_s']]
        apds.append(mpf.make_addplot(p_df['bx_s'], ax=ax_b, type='bar', color=colors, width=0.7))
        apds.append(mpf.make_addplot(p_df['bx_l'], ax=ax_b, color='#1a237e', width=1.5))
        
        # 4. 渲染
        mc = mpf.make_marketcolors(up='#ef5350', down='#26a69a', edge='inherit')
        style = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', gridcolor='#eeeeee')
        mpf.plot(p_df, type='candle', ax=ax_p, addplot=apds, style=style, datetime_format='%y-%m')
        
        ax_p.set_title(f"{name} | {ticker} | V2.9.6", fontsize=12, fontweight='bold', loc='left')
        ax_b.axhline(0, color='gray', alpha=0.3)
        ax_b.set_ylabel("Momentum", fontsize=8)

    plt.tight_layout()
    return fig

# UI 展示略（保持摘要 Card 显示逻辑）
