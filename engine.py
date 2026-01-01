import pandas as pd
import numpy as np
import yfinance as yf

# 1. 严格对齐 Wilder's RSI (RMA)
def calculate_rsi_wilder(series, period):
    delta = series.diff()
    alpha = 1 / period
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = -delta.where(delta < 0, 0).ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# 2. 每日信号分析引擎 (EOD Engine)
def run_eod_analyzer(symbol):
    df = yf.download(symbol, period="2y", auto_adjust=True)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    # 指标计算 (与回测同步)
    df_w = df['Close'].resample('W').last().to_frame()
    df_w['MA50_w'] = df_w['Close'].rolling(50).mean()
    rsi_20_w = calculate_rsi_wilder(df_w['Close'], 20)
    df_w['bx_l'] = (rsi_20_w - 50).ewm(span=10, adjust=False).mean()
    w_bull = (df_w['Close'].iloc[-1] > df_w['MA50_w'].iloc[-1]) and (df_w['bx_l'].iloc[-1] > -5)
    
    df_m = df['Close'].resample('ME').last().to_frame()
    m_bull = df_m['Close'].iloc[-1] > df_m['Close'].rolling(20).mean().iloc[-1]

    curr_c, curr_h, curr_l, curr_v = df['Close'].iloc[-1], df['High'].iloc[-1], df['Low'].iloc[-1], df['Volume'].iloc[-1]
    upper_ref = df['High'].rolling(252).max().shift(1).iloc[-1]
    ma50 = df['Close'].rolling(50).mean().iloc[-1]
    vol_ma20 = df['Volume'].rolling(20).mean().iloc[-1]
    
    bx_s_series = (calculate_rsi_wilder(df['Close'], 5) - 50).ewm(span=3, adjust=False).mean()
    bx_s_now, bx_s_prev = bx_s_series.iloc[-1], bx_s_series.iloc[-2]

    # 信号逻辑判定
    macro_pass = w_bull and m_bull
    signal = "WAIT"
    
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

# 3. 历史审计回测引擎 (True-Sync Engine)
def run_smartstock_v296_engine(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if df.empty: return None, None, None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    # 多周期对齐
    df_w = df['Close'].resample('W').last().to_frame()
    df_w['MA50_w'] = df_w['Close'].rolling(50).mean()
    df_w['bx_l'] = (calculate_rsi_wilder(df_w['Close'], 20) - 50).ewm(span=10, adjust=False).mean()
    df_w['w_bullish'] = (df_w['Close'] > df_w['MA50_w']) & (df_w['bx_l'] > -5)
    df_w_sync = df_w.reindex(df.index, method='ffill')
    
    df_m = df['Close'].resample('ME').last().to_frame()
    df_m['m_bullish'] = df_m['Close'] > df_m['Close'].rolling(20).mean()
    df_m_sync = df_m.reindex(df.index, method='ffill')

    df['Upper_ref'] = df['High'].rolling(252).max().shift(1)
    df['Lower_ref'] = df['Low'].rolling(20).min().shift(1)
    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['bx_s'] = (calculate_rsi_wilder(df['Close'], 5) - 50).ewm(span=3, adjust=False).mean()

    # 初始化状态
    cash, pos = 100000.0, 0
    PLAN_TTL, COOLDOWN, MAX_POS = 15, 10, 0.7
    pending_buy = {"active": False, "type": None}
    pending_sell, plan = False, {"active": False, "age": 0}
    cooldown_timer, stats = 0, {'triggered': 0, 'veto': 0, 'ch_break': 0, 'ch_rev': 0}
    trades, equity_curve = [], []

    for i in range(252, len(df)):
        dt = df.index[i]
        o_t, h_t, l_t, c_t, v_t = df['Open'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['Close'].iloc[i], df['Volume'].iloc[i]
        
        if pending_sell and pos > 0:
            p_sell = o_t * 0.9995
            cash += pos * p_sell * 0.999
            trades.append({'Date': dt, 'Exit_Price': p_sell, 'Return': (p_sell/entry_p)-1, 'Type': entry_type})
            pos, pending_sell, cooldown_timer = 0, False, COOLDOWN
        
        if pending_buy["active"] and pos == 0:
            p_buy = o_t * 1.0005
            pos = int((cash * MAX_POS) / (p_buy * 1.001))
            cash -= (pos * p_buy * 1.001)
            entry_p, entry_type = p_buy, pending_buy["type"]
            pending_buy["active"], stats['triggered'] = False, stats['triggered'] + 1

        equity_curve.append({'Date': dt, 'Equity': cash + pos * c_t})
        if cooldown_timer > 0: cooldown_timer -= 1

        if pos > 0 and not pending_sell and c_t < df['Lower_ref'].iloc[i]:
            pending_sell = True

        if pos == 0 and not pending_buy["active"] and cooldown_timer == 0:
            macro_pass = df_m_sync['m_bullish'].iloc[i] and df_w_sync['w_bullish'].iloc[i]
            upper = df['Upper_ref'].iloc[i]
            if not plan['active'] and c_t > upper * 0.97:
                plan['active'], plan['age'] = True, 0
            
            if plan['active']:
                plan['age'] += 1
                close_pos = (c_t - l_t) / (h_t - l_t) if h_t != l_t else 0
                vol_ratio = v_t / df['Vol_MA20'].iloc[i] if df['Vol_MA20'].iloc[i] > 0 else 0
                if c_t > upper and close_pos > 0.7 and vol_ratio > 1.2:
                    if macro_pass:
                        pending_buy = {"active": True, "type": "BREAKOUT"}
                        stats['ch_break'] += 1
                        plan['active'] = False
                    else: stats['veto'] += 1; plan['active'] = False
                elif plan['age'] > PLAN_TTL or c_t < df['MA50'].iloc[i]:
                    plan['active'] = False

            bx_s_now, bx_s_prev = df['bx_s'].iloc[i], df['bx_s'].iloc[i-1]
            if not pending_buy["active"] and macro_pass and c_t > df['MA50'].iloc[i]:
                if bx_s_prev <= 0 and bx_s_now > 0:
                    pending_buy = {"active": True, "type": "REVERSAL"}
                    stats['ch_rev'] += 1

    return stats, pd.DataFrame(trades), pd.DataFrame(equity_curve)
