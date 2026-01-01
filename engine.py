import pandas as pd
import numpy as np
import yfinance as yf

def get_rsi_ema(series, period, ema_span):
    if len(series) < period: return pd.Series(0.0, index=series.index)
    delta = series.diff()
    alpha = 1 / period
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = -delta.where(delta < 0, 0).ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return (rsi - 50).ewm(span=ema_span, adjust=False).mean()

def run_eod_analyzer(symbol):
    try:
        d_raw = yf.download(symbol, period="2y", interval="1d", auto_adjust=True)
        w_raw = yf.download(symbol, period="5y", interval="1wk", auto_adjust=True)
        m_raw = yf.download(symbol, period="10y", interval="1mo", auto_adjust=True)
        
        if d_raw.empty or w_raw.empty: return None
        for df in [d_raw, w_raw, m_raw]:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        c_d = d_raw['Close'].iloc[-1]
        h_ref_d = d_raw['High'].rolling(252).max().shift(1).iloc[-1]
        s_ref_d = d_raw['Low'].rolling(20).min().shift(1).iloc[-1]
        ma_mid_d = d_raw['Close'].rolling(50).mean().iloc[-1]
        vol_avg20 = d_raw['Volume'].rolling(20).mean().iloc[-1]
        
        bx_s = get_rsi_ema(d_raw['Close'], 5, 3)
        bx_l_w = get_rsi_ema(w_raw['Close'], 20, 10).iloc[-1]
        
        w_bullish = (w_raw['Close'].iloc[-1] > w_raw['Close'].rolling(50).mean().iloc[-1]) and (bx_l_w > -5)
        m_pass = m_raw['Close'].iloc[-1] > m_raw['Close'].rolling(20).mean().iloc[-1]
        
        dist_pct = (h_ref_d - c_d) / h_ref_d
        fuel = d_raw['Volume'].iloc[-1] / vol_avg20
        push = (c_d - d_raw['Low'].iloc[-1]) / (d_raw['High'].iloc[-1] - d_raw['Low'].iloc[-1]) if d_raw['High'].iloc[-1] != d_raw['Low'].iloc[-1] else 0.5
        
        action, reason = "WAIT / 等待", "Normal Consolidation"
        if c_d < s_ref_d:
            action, reason = "SELL / 卖出", "Break 20D Support"
        elif not (w_bullish and m_pass):
            action, reason = "WAIT / MACRO_VETO", "Macro (W/M) trend failed"
        else:
            if c_d > h_ref_d:
                action, reason = ("BUY / 突破买入", "Strong Breakout") if fuel > 1.2 else ("WAIT / 弱突破", "Low energy")
            elif dist_pct < 0.01 and fuel < 1.0:
                action, reason = "WAIT / ABSORBING", "Low volume near high"
            elif bx_s.iloc[-2] <= 0 and bx_s.iloc[-1] > 0 and c_d > ma_mid_d:
                action, reason = "BUY / 反转买入", "BX_S Golden Cross"

        return {
            "Action": action, "Reason": reason,
            "Fuel": f"{fuel:.2f}x", "Push": f"{push:.1%}", "Gap": f"{dist_pct:.2%}", "Stop": round(s_ref_d, 2),
            "D_Data": d_raw, "W_Data": w_raw, "M_Data": m_raw
        }
    except: return None

def run_smartstock_v296_engine(symbol, start, end):
    """回测 Tab 依赖的核心回测引擎"""
    try:
        df = yf.download(symbol, start=start, end=end, auto_adjust=True)
        if df.empty: return {}, pd.DataFrame(), pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 简单模拟回测逻辑（示例：买入并持有）
        df['Equity'] = (df['Close'] / df['Close'].iloc[0]) * 100000
        stats = {"Total Return": f"{((df['Equity'].iloc[-1]/100000)-1):.2%}", "Veto": 0}
        equity_df = df[['Equity']].reset_index()
        return stats, pd.DataFrame(), equity_df
    except:
        return {}, pd.DataFrame(), pd.DataFrame()
