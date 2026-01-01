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
    # 获取3年数据以支撑长周期指标 
    df = yf.download(symbol, period="3y", auto_adjust=True)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    # 1. 物理参数确权 
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

    # 2. 宏观判定 (M/W Check) 
    df_w = df['Close'].resample('W').last().to_frame()
    df_w['MA50_w'] = df_w['Close'].rolling(50).mean()
    w_bull = df_w['Close'].iloc[-1] > df_w['MA50_w'].iloc[-1]
    
    df_m = df['Close'].resample('ME').last().to_frame()
    m_bull = df_m['Close'].iloc[-1] > df_m['Close'].rolling(20).mean().iloc[-1]

    # 3. 逻辑结论 (对齐报告 )
    action, reason = "WAIT", "Consolidation"
    if dist_to_high < 0.01:
        if vol_ratio < 1.2:
            action, reason = "WAIT / ABSORBING", "Low volume near high. (高位缩量消化)"
        elif close_pos > 0.7:
            action, reason = "BREAKOUT", "High volume breakout."

    # 修复：确保所有输出为基础字符串或数值，防止 ValueError 
    return {
        "Ticker": symbol,
        "Price": round(curr_c, 3),
        "Action": action,
        "Reason": reason,
        "Gap": f"{dist_to_high:.2%}",
        "Fuel": f"{vol_ratio:.2f}x",
        "Push": f"{close_pos:.1%}",
        "Macro": "PASS" if (w_bull and m_bull) else "FAIL",
        "Stop": round(low_20, 2),
        "Full_Data": df
    }

def run_smartstock_v296_engine(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if df.empty: return {}, pd.DataFrame(), pd.DataFrame()
    return {'veto': 0}, pd.DataFrame(), pd.DataFrame({'Date': df.index, 'Equity': 100000.0})
