import streamlit as st
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from engine import run_eod_analyzer, run_smartstock_v296_engine

# 页面设置
st.set_page_config(page_title="SmartStock V2.9.6 Audit / 智能股票审计", layout="wide")

# --- 绘图函数：使用与 Colab 完全一致的指标 ---
def draw_v296_charts(data_dict, ticker):
    fig = plt.figure(figsize=(14, 22), facecolor='white')
    configs = [
        (data_dict['D_Data'], 80, 252, 20, 200, "DAILY 日线"),
        (data_dict['W_Data'], 52, 52, 10, 50, "WEEKLY 周线"),
        (data_dict['M_Data'], 40, 12, 6, 20, "MONTHLY 月线")
    ]
    for i, (df_raw, show_n, h_p, l_p, ma_p, name) in enumerate(configs):
        df = df_raw.copy()
        df['HI'] = df['High'].rolling(h_p).max().shift(1)
        df['LO'] = df['Low'].rolling(l_p).min().shift(1)
        df['MA'] = df['Close'].rolling(ma_p).mean()
        # BX 指标：短柱、长线
        df['bx_s'] = ( (df['Close'].diff().where(df['Close'].diff()>0,0)).ewm(alpha=1/5, adjust=False).mean() /
                       (df['Close'].diff().where(df['Close'].diff()<0,0).abs().ewm(alpha=1/5, adjust=False).mean()+1e-9) )
        df['bx_s'] = (100 - 100/(1+df['bx_s']) - 50).ewm(span=3, adjust=False).mean()
        rsi20 = ((df['Close'].diff().where(df['Close'].diff()>0,0)).ewm(alpha=1/20, adjust=False).mean() /
                 (df['Close'].diff().where(df['Close'].diff()<0,0).abs().ewm(alpha=1/20, adjust=False).mean()+1e-9))
        rsi20 = 100 - 100/(1+rsi20)
        df['bx_l'] = (rsi20 - 50).ewm(span=10, adjust=False).mean()

        p_df = df.tail(show_n)
        # 价格图
        ax_p = plt.subplot2grid((9,1), (i*3,0), rowspan=2)
        # 动能图
        ax_b = plt.subplot2grid((9,1), (i*3+2,0), rowspan=1)
        # 附加指标
        add_plots = [
            mpf.make_addplot(p_df['HI'], ax=ax_p, color='#9c27b0', linestyle='--'),
            mpf.make_addplot(p_df['LO'], ax=ax_p, color='#ff9800', linestyle=':'),
            mpf.make_addplot(p_df['MA'], ax=ax_p, color='#2196f3'),
            mpf.make_addplot(p_df['bx_s'], ax=ax_b, type='bar',
                             color=['#26a69a' if v > 0 else '#ef5350' for v in p_df['bx_s']], width=0.7),
            mpf.make_addplot(p_df['bx_l'], ax=ax_b, color='#1a237e', linewidth=1.5)
        ]
        mpf.plot(p_df, type='candle', ax=ax_p, addplot=add_plots, style='charles', datetime_format='%y-%m')
        ax_p.set_title(f"{name}  {ticker}  V2.9.6", fontsize=12, fontweight='bold', loc='left')
        ax_b.axhline(0, color='gray', linewidth=0.5, alpha=0.5)
        ax_b.set_ylabel("BX 动能", fontsize=8)
    plt.tight_layout()
    return fig

# --- 页面布局 ---
st.sidebar.title("SmartStock V2.9.6 审计系统 / Audit System")
ticker = st.sidebar.text_input("Ticker Symbol / 股票代码", "D05.SI")
start_date = st.sidebar.date_input("Backtest Start / 回测开始日期", value=pd.to_datetime("2020-01-01"))

tab_summary, tab_backtest = st.tabs(["【EOD 审计摘要 / Summary】", "【回测深度审计 / Backtest Audit】"])

with tab_summary:
    if st.sidebar.button("执行EOD分析 / Run EOD Analysis"):
        res = run_eod_analyzer(ticker)
        if res:
            st.markdown(f"**Action 动作:** {res['Action_EN']} / {res['Action_CN']}")
            st.markdown(f"**Reason 原因:** {res['Reason_EN']} / {res['Reason_CN']}")
            cols = st.columns(4)
            cols[0].metric("Fuel 燃料", res["Fuel"])
            cols[1].metric("Push 推力", res["Push"])
            cols[2].metric("Gap 距离高点", res["Gap"])
            cols[3].metric("Stop 止损位", res["Stop"])
            fig = draw_v296_charts(res, ticker)
            st.pyplot(fig)
            st.markdown("*注：所有指标已与 Colab V2.9.6 策略对齐。*")

with tab_backtest:
    if st.sidebar.button("执行全量回测 / Run Full Backtest"):
        stats, trades_df, equity_df = run_smartstock_v296_engine(ticker, str(start_date), str(pd.to_datetime('today').date()))
        if equity_df.empty:
            st.error("无有效数据 / No valid data.")
        else:
            st.markdown(f"**Total Return 总收益率:** {stats['TotalReturn_EN']} / {stats['TotalReturn_CN']}")
            st.markdown(f"**Max Drawdown 最大回撤:** {stats['MaxDrawdown_EN']} / {stats['MaxDrawdown_CN']}")
            st.markdown(f"**Trades 交易笔数:** {stats['Trades']} （Breakouts: {stats['BreakoutTrades']}，Reversals: {stats['ReversalTrades']}）")
            if stats['BreakoutWinRate'] is not None:
                st.markdown(f"**Breakout Win Rate 突破胜率:** {stats['BreakoutWinRate']:.1%}")
            if stats['ReversalWinRate'] is not None:
                st.markdown(f"**Reversal Win Rate 反转胜率:** {stats['ReversalWinRate']:.1%}")
            st.markdown(f"**Final Equity 期末净值:** {stats['FinalEquity']}")
            st.line_chart(equity_df.set_index('Date')['Equity'])
            st.dataframe(trades_df)

