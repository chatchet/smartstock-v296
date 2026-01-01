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
    # 抓取3年数据以支撑 200D MA 计算
    df = yf.download(symbol, period="3y", auto_adjust=True)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    # 1. 物理参数记录 [cite: 3]
    curr_c = df['Close'].iloc[-1]
    curr_h = df['High'].iloc[-1]
    curr_l = df['Low'].iloc[-1]
    curr_v = df['Volume'].iloc[-1]
    
    upper_252 = df['High'].rolling(252).max().shift(1).iloc[-1]
    low_20 = df['Low'].rolling(20).min().shift(1).iloc[-1] # STOP_D 逻辑 
    vol_avg20 = df['Volume'].rolling(20).mean().shift(1).iloc[-1]
    
    dist_to_high = (upper_252 - curr_c) / upper_252
    vol_ratio = curr_v / vol_avg20 if vol_avg20 > 0 else 0
    close_pos = (curr_c - curr_l) / (curr_h - curr_l) if curr_h != curr_l else 0

    # 2. 逻辑判定 (对齐审计摘要 )
    action, reason = "WAIT", "Normal Consolidation"
    if dist_to_high < 0.01: # Threshold: 1.0% [cite: 3]
        if vol_ratio < 1.2:
            action, reason = "WAIT / ABSORBING", "Low volume near high. (高位缩量消化)"
        elif close_pos > 0.7:
            action, reason = "BREAKOUT", "Strong volume breakout."

    return {
        "Ticker": symbol,
        "Price": round(curr_c, 3),
        "Action": action,
        "Reason": reason,
        "Gap": f"{dist_to_high:.2%}",
        "Fuel": f"{vol_ratio:.2f}x", # 修复之前的格式化错误
        "Push": f"{close_pos:.1%}",
        "Stop": round(low_20, 2),
        "Full_Data": df
    }

def run_smartstock_v296_engine(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if df.empty: return {}, pd.DataFrame(), pd.DataFrame()
    return {'veto': 0}, pd.DataFrame(), pd.DataFrame({'Date': df.index, 'Equity': 100000.0})
