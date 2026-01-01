import pandas as pd
import numpy as np
import yfinance as yf

def calculate_rsi_wilder(series, period):
    delta = series.diff()
    alpha = 1 / period
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = -delta.where(delta < 0, 0).ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def run_eod_analyzer(symbol):
    df = yf.download(symbol, period="2y", auto_adjust=True)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    # 1. 指标计算 (对齐报告 Physics Log)
    curr_c = df['Close'].iloc[-1]
    curr_h = df['High'].iloc[-1]
    curr_l = df['Low'].iloc[-1]
    curr_v = df['Volume'].iloc[-1]
    
    upper_252 = df['High'].rolling(252).max().shift(1).iloc[-1]
    low_20 = df['Low'].rolling(20).min().shift(1).iloc[-1]
    vol_avg20 = df['Volume'].rolling(20).mean().shift(1).iloc[-1]
    
    dist_to_high = (upper_252 - curr_c) / upper_252
    vol_ratio = curr_v / vol_avg20 if vol_avg20 > 0 else 0
    close_pos = (curr_c - curr_l) / (curr_h - curr_l) if curr_h != curr_l else 0

    # 2. 宏观判定
    df_w = df['Close'].resample('W').last().to_frame()
    df_w['MA50_w'] = df_w['Close'].rolling(50).mean()
    w_bull = df_w['Close'].iloc[-1] > df_w['MA50_w'].iloc[-1]
    
    df_m = df['Close'].resample('ME').last().to_frame()
    m_bull = df_m['Close'].iloc[-1] > df_m['Close'].rolling(20).mean().iloc[-1]

    # 3. 逻辑判定 (对齐 Action/Reason)
    action, reason = "WAIT", "Normal Consolidation"
    if dist_to_high < 0.01:
        if vol_ratio < 1.2:
            action, reason = "WAIT / ABSORBING", "Low volume near high. (高位缩量消化)"
        elif close_pos > 0.7:
            action, reason = "BREAKOUT", "Strong volume breakout."

    # 修正：将 Vol_Ratio 格式化为字符串，避免 ValueError
    return {
        "Ticker": symbol,
        "Price": round(curr_c, 2),
        "Action": action,
        "Reason": reason,
        "Gap": f"{dist_to_high:.2%}",
        "Fuel": f"{vol_ratio:.2f}x",
        "Push": f"{close_pos:.1%}",
        "Macro": "PASS" if (w_bull and m_bull) else "FAIL",
        "Stop": round(low_20, 2),
        "Full_Data": df # 传递给绘图使用
    }

def run_smartstock_v296_engine(symbol, start, end):
    # 保持原有审计回测结构
    df = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if df.empty: return {}, pd.DataFrame(), pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    cash, pos = 100000.0, 0
    equity_curve = []
    for i in range(len(df)):
        equity_curve.append({'Date': df.index[i], 'Equity': cash + pos * df['Close'].iloc[i]})
    return {'veto': 0}, pd.DataFrame(), pd.DataFrame(equity_curve)
