# 在 engine.py 中确保有这个函数
def run_eod_analyzer(symbol):
    df = yf.download(symbol, period="2y", auto_adjust=True)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    # 1. 计算指标 (与回测口径严格一致)
    # 周线逻辑
    df_w = df['Close'].resample('W').last().to_frame()
    df_w['MA50_w'] = df_w['Close'].rolling(50).mean()
    rsi_20_w = calculate_rsi_wilder(df_w['Close'], 20)
    df_w['bx_l'] = (rsi_20_w - 50).ewm(span=10, adjust=False).mean()
    w_bull = (df_w['Close'].iloc[-1] > df_w['MA50_w'].iloc[-1]) and (df_w['bx_l'].iloc[-1] > -5)
    
    # 月线逻辑
    df_m = df['Close'].resample('ME').last().to_frame()
    m_bull = df_m['Close'].iloc[-1] > df_m['Close'].rolling(20).mean().iloc[-1]

    # 日线逻辑
    curr_c = df['Close'].iloc[-1]
    curr_h = df['High'].iloc[-1]
    curr_l = df['Low'].iloc[-1]
    curr_v = df['Volume'].iloc[-1]
    upper_ref = df['High'].rolling(252).max().shift(1).iloc[-1]
    ma50 = df['Close'].rolling(50).mean().iloc[-1]
    vol_ma20 = df['Volume'].rolling(20).mean().iloc[-1]
    
    bx_s_series = (calculate_rsi_wilder(df['Close'], 5) - 50).ewm(span=3, adjust=False).mean()
    bx_s_now = bx_s_series.iloc[-1]
    bx_s_prev = bx_s_series.iloc[-2]

    # 2. 信号判定
    macro_pass = w_bull and m_bull
    signal = "WAIT"
    
    # 逻辑优先级：Breakout > Reversal > Entry_Plan
    if curr_c > upper_ref and (curr_c - curr_l)/(curr_h - curr_l) > 0.7 and curr_v > vol_ma20 * 1.2:
        signal = "BREAKOUT" if macro_pass else "VETOED_BREAKOUT"
    elif bx_s_prev <= 0 and bx_s_now > 0 and curr_c > ma50:
        signal = "REVERSAL" if macro_pass else "VETOED_REVERSAL"
    elif curr_c > upper_ref * 0.97:
        signal = "ENTRY_PLAN"

    return {
        "Ticker": symbol,
        "Price": round(curr_c, 3),
        "Signal": signal,
        "Weekly_Bull": "YES" if w_bull else "NO",
        "Monthly_Bull": "YES" if m_bull else "NO",
        "bx_s": round(bx_s_now, 2),
        "bx_l": round(df_w['bx_l'].iloc[-1], 2),
        "Vol_Ratio": round(curr_v / vol_ma20, 2) if vol_ma20 > 0 else 0
    }
