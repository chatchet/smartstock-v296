import pandas as pd
import numpy as np
import yfinance as yf

# --- 指标算法对齐 ---
def get_rsi_ema(series, period, ema_span):
    if len(series) < period: return pd.Series(0.0, index=series.index)
    delta = series.diff()
    alpha = 1 / period
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = -delta.where(delta < 0, 0).ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return (rsi - 50).ewm(span=ema_span, adjust=False).mean()

# --- EOD 审计分析引擎 (V2.9.6 完整版) ---
def run_eod_analyzer(symbol):
    try:
        # 1. 独立数据池
        d = yf.download(symbol, period="2y", interval="1d", auto_adjust=True)
        w = yf.download(symbol, period="5y", interval="1wk", auto_adjust=True)
        m = yf.download(symbol, period="10y", interval="1mo", auto_adjust=True)
        if d.empty or w.empty: return None
        for df in [d, w, m]:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 2. 关键指标口径确权
        c_d = d['Close'].iloc[-1]
        # Shift(1) 逻辑用于突破和止损
        h_ref = d['High'].rolling(252).max().shift(1).iloc[-1]
        s_ref = d['Low'].rolling(20).min().shift(1).iloc[-1]
        ma_long = d['Close'].rolling(200).mean().iloc[-1]
        ma_mid = d['Close'].rolling(50).mean().iloc[-1]
        vol_avg20 = d['Volume'].rolling(20).mean().iloc[-1]
        
        # 动能对齐：bx_s(5,3) 柱, bx_l(20,10) 线
        bx_s = get_rsi_ema(d['Close'], 5, 3)
        bx_l_w = get_rsi_ema(w['Close'], 20, 10).iloc[-1]
        bx_l_m = get_rsi_ema(m['Close'], 20, 10).iloc[-1]
        
        # 3. 宏观 Veto 逻辑
        w_bullish = (w['Close'].iloc[-1] > w['Close'].rolling(50).mean().iloc[-1]) and (bx_l_w > -5)
        m_pass = m['Close'].iloc[-1] > m['Close'].rolling(20).mean().iloc[-1]
        
        # 4. 物理记录
        dist_pct = (h_ref - c_d) / h_ref
        fuel = d['Volume'].iloc[-1] / vol_avg20
        push = (c_d - d['Low'].iloc[-1]) / (d_raw_h - d_raw_l) if (d_raw_h := d['High'].iloc[-1]) != (d_raw_l := d['Low'].iloc[-1]) else 0.5
        
        # 5. 信号树 (V2.9.6 对齐)
        action, reason = "WAIT / 等待", "Normal Consolidation"
        if c_d < s_ref:
            action, reason = "SELL / 卖出", "Break 20D Support (止损离场)"
        elif not (w_bullish and m_pass):
            action, reason = "WAIT / MACRO_VETO", f"Macro Fail (W:{'PASS' if w_bullish else 'FAIL'}, M:{'PASS' if m_pass else 'FAIL'})"
        else:
            if c_d > h_ref:
                action, reason = ("BUY / 突破买入", "Strong Breakout (高位放量突破)") if fuel > 1.2 and push > 0.7 else ("WAIT / 弱突破", "Price above High but no fuel")
            elif dist_pct < 0.01:
                if fuel < 1.0: action, reason = "WAIT / ABSORBING", "Near high with low volume (缩量消化)"
            elif bx_s.iloc[-2] <= 0 and bx_s.iloc[-1] > 0 and c_d > ma_mid:
                action, reason = "BUY / 反转买入", "Momentum Reversal (BX_S Golden Cross)"

        return {
            "Action": action, "Reason": reason, "Fuel": f"{fuel:.2f}x", "Push": f"{push:.1%}", 
            "Gap": f"{dist_pct:.2%}", "Stop": round(s_ref, 2), "D_Data": d, "W_Data": w, "M_Data": m,
            "Macro": "PASS" if (w_bullish and m_pass) else "FAIL"
        }
    except: return None

# --- 真实同步回测引擎 (V2.9.6 True Sync) ---
def run_smartstock_v296_engine(symbol, start, end):
    try:
        df = yf.download(symbol, start=start, end=end, interval="1d", auto_adjust=True)
        if df.empty: return {}, pd.DataFrame(), pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 计算回测所需指标
        df['h_ref'] = df['High'].rolling(252).max().shift(1)
        df['s_ref'] = df['Low'].rolling(20).min().shift(1)
        df['ma_mid'] = df['Close'].rolling(50).mean()
        df['bx_s'] = get_rsi_ema(df['Close'], 5, 3)
        
        # 模拟 V2.9.6 逻辑
        pos = 0; equity = 100000; trades = []
        df['Equity'] = 100000.0
        
        for i in range(252, len(df)):
            price = df['Open'].iloc[i] # 次日开盘执行
            prev_c = df['Close'].iloc[i-1]
            
            if pos == 0:
                # 简化版突破/反转模拟
                if prev_c > df['h_ref'].iloc[i-1] or (df['bx_s'].iloc[-2] < 0 and df['bx_s'].iloc[-1] > 0):
                    pos = equity / price
                    trades.append({'Date': df.index[i], 'Type': 'BUY', 'Price': price})
            elif pos > 0:
                if prev_c < df['s_ref'].iloc[i-1]:
                    equity = pos * price * 0.999 # 含 0.1% 滑点
                    pos = 0
                    trades.append({'Date': df.index[i], 'Type': 'SELL', 'Price': price})
            
            df.iloc[i, df.columns.get_loc('Equity')] = pos * df['Close'].iloc[i] if pos > 0 else equity

        stats = {
            "Total Return": f"{((df['Equity'].iloc[-1]/100000)-1):.2%}",
            "Trades": len(trades),
            "Final Value": f"${df['Equity'].iloc[-1]:,.0f}"
        }
        return stats, pd.DataFrame(trades), df[['Equity']].reset_index()
    except: return {}, pd.DataFrame(), pd.DataFrame()
