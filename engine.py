import pandas as pd
import numpy as np
import yfinance as yf

# 核心算法：Wilder's RSI 对齐
def get_rsi_ema(series, period, ema_span):
    delta = series.diff()
    alpha = 1 / period
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = -delta.where(delta < 0, 0).ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return (rsi - 50).ewm(span=ema_span, adjust=False).mean()

def run_eod_analyzer(symbol):
    # 1. 三周期独立下载 (对齐 Colab 逻辑)
    d_raw = yf.download(symbol, period="2y", interval="1d", auto_adjust=True)
    w_raw = yf.download(symbol, period="5y", interval="1wk", auto_adjust=True)
    m_raw = yf.download(symbol, period="10y", interval="1mo", auto_adjust=True)
    
    if d_raw.empty or w_raw.empty: return None
    for df in [d_raw, w_raw, m_raw]:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    # 2. 关键指标计算 (口径对齐)
    # 日线
    c_d = d_raw['Close'].iloc[-1]
    h_ref_d = d_raw['High'].rolling(252).max().shift(1).iloc[-1]
    s_ref_d = d_raw['Low'].rolling(20).min().shift(1).iloc[-1]
    ma_200_d = d_raw['Close'].rolling(200).mean().iloc[-1]
    ma_50_d = d_raw['Close'].rolling(50).mean().iloc[-1]
    vol_avg20_d = d_raw['Volume'].rolling(20).mean().iloc[-1]
    bx_s_d = get_rsi_ema(d_raw['Close'], 5, 3).iloc[-1]
    bx_s_prev = get_rsi_ema(d_raw['Close'], 5, 3).iloc[-2]
    
    # 周线
    w_bullish = (w_raw['Close'].iloc[-1] > w_raw['Close'].rolling(50).mean().iloc[-1]) and \
                (get_rsi_ema(w_raw['Close'], 20, 10).iloc[-1] > -5)
    
    # 月线
    m_pass = m_raw['Close'].iloc[-1] > m_raw['Close'].rolling(20).mean().iloc[-1]

    # 3. V2.9.6 信号树引擎
    dist_pct = (h_ref_d - c_d) / h_ref_d
    fuel = d_raw['Volume'].iloc[-1] / vol_avg20_d
    push = (c_d - d_raw['Low'].iloc[-1]) / (d_raw['High'].iloc[-1] - d_raw['Low'].iloc[-1]) if d_raw['High'].iloc[-1] != d_raw['Low'].iloc[-1] else 0.5
    
    action, reason = "WAIT / 等待", "Normal Consolidation"
    
    # 逻辑分支
    if c_d < s_ref_d:
        action, reason = "SELL / 卖出", "Break Support Line (止损确权)"
    elif not (w_bullish and m_pass):
        action, reason = "WAIT / MACRO_VETO", "Macro trend not aligned (周月趋势不合规)"
    else:
        # 进攻分支
        if c_d > h_ref_d:
            if fuel > 1.2 and push > 0.7: action, reason = "BUY / 突破买入", "Strong Breakout with Fuel"
            else: action, reason = "WAIT / 弱突破", "High price but low energy"
        elif dist_pct < 0.01:
            if fuel < 1.0: action, reason = "WAIT / ABSORBING", "Near high with low volume (高位缩量消化)"
        elif bx_s_prev <= 0 and bx_s_d > 0 and c_d > ma_50_d:
            action, reason = "BUY / 反转买入", "Momentum Reversal (BX_S Golden Cross)"

    return {
        "Action": action, "Reason": reason,
        "Fuel": f"{fuel:.2f}x", "Push": f"{push:.1%}", "Gap": f"{dist_pct:.2%}", "Stop": round(s_ref_d, 2),
        "D_Data": d_raw, "W_Data": w_raw, "M_Data": m_raw
    }
