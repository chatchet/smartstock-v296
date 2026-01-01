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
        # 1. 独立数据池：拒绝 resample，对齐交易周/月
        d = yf.download(symbol, period="2y", interval="1d", auto_adjust=True)
        w = yf.download(symbol, period="5y", interval="1wk", auto_adjust=True)
        m = yf.download(symbol, period="10y", interval="1mo", auto_adjust=True)
        for df in [d, w, m]:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 2. 关键指标计算
        c_d = d['Close'].iloc[-1]
        h_ref = d['High'].rolling(252).max().shift(1).iloc[-1]
        s_ref = d['Low'].rolling(20).min().shift(1).iloc[-1]
        ma_long_d = d['Close'].rolling(200).mean().iloc[-1]
        ma_mid_d = d['Close'].rolling(50).mean().iloc[-1]
        vol_avg20 = d['Volume'].rolling(20).mean().iloc[-1]
        
        # BX 双动能：bx_s(5,3) 柱, bx_l(20,10) 线
        bx_s = get_rsi_ema(d['Close'], 5, 3)
        bx_l_w = get_rsi_ema(w['Close'], 20, 10).iloc[-1]
        
        # 3. 宏观过滤 (V2.9.6 原厂标准)
        w_bullish = (w['Close'].iloc[-1] > w['Close'].rolling(50).mean().iloc[-1]) and (bx_l_w > -5)
        m_pass = m['Close'].iloc[-1] > m['Close'].rolling(20).mean().iloc[-1]
        
        # 4. 辅助参数
        dist_pct = (h_ref - c_d) / h_ref
        fuel = d['Volume'].iloc[-1] / vol_avg20
        push = (c_d - d['Low'].iloc[-1]) / (d['High'].iloc[-1] - d['Low'].iloc[-1]) if d['High'].iloc[-1] != d['Low'].iloc[-1] else 0.5
        
        # 5. 信号树 (全分支对齐)
        action, reason = "WAIT / 等待", "Normal Consolidation"
        if c_d < s_ref:
            action, reason = "SELL / 卖出", "Break Support Line (止损确权)"
        elif not (w_bullish and m_pass):
            action, reason = "WAIT / MACRO_VETO", "Macro Check Fail (W/M Trend Mismatch)"
        else:
            if c_d > h_ref:
                if fuel > 1.2 and push > 0.7: action, reason = "BUY / 突破买入", "Strong Breakout with Fuel (放量突破)"
                else: action, reason = "WAIT / 弱突破", "Price above High but Low Fuel"
            elif dist_pct < 0.01 and fuel < 1.0:
                action, reason = "WAIT / ABSORBING", "Low volume near high (缩量消化)"
            elif bx_s.iloc[-2] <= 0 and bx_s.iloc[-1] > 0 and c_d > ma_mid_d:
                action, reason = "BUY / 反转买入", "Momentum Reversal (BX_S Golden Cross)"
            elif c_d > ma_mid_d:
                action, reason = "HOLD / 持有", "Steady trend above MA50"

        return {
            "Action": action, "Reason": reason, "Fuel": f"{fuel:.2f}x", "Push": f"{push:.1%}", 
            "Gap": f"{dist_pct:.2%}", "Stop": round(s_ref, 2), "D_Data": d, "W_Data": w, "M_Data": m,
            "Macro": "PASS" if (w_bullish and m_pass) else "FAIL"
        }
    except: return None

# --- True Sync 回测引擎 ---
def run_smartstock_v296_engine(symbol, start, end):
    try:
        df = yf.download(symbol, start=start, end=end, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 指标预算
        df['h_ref'] = df['High'].rolling(252).max().shift(1)
        df['s_ref'] = df['Low'].rolling(20).min().shift(1)
        df['bx_s'] = get_rsi_ema(df['Close'], 5, 3)
        df['ma_mid'] = df['Close'].rolling(50).mean()
        
        # 状态机初始化
        equity = 100000.0; pos = 0.0; trades = []; df['Equity'] = 100000.0
        max_cap = 0.7  # 0.7 仓位限制

        for i in range(252, len(df)):
            curr_c = df['Close'].iloc[i-1]
            bx_now = df['bx_s'].iloc[i-1]
            bx_prev = df['bx_s'].iloc[i-2]
            
            # 买入执行 (次日开盘)
            if pos == 0:
                is_break = curr_c > df['h_ref'].iloc[i-1]
                is_rev = (bx_prev < 0 and bx_now > 0 and curr_c > df['ma_mid'].iloc[i-1])
                if is_break or is_rev:
                    buy_price = df['Open'].iloc[i] * 1.001 # 含滑点
                    pos = (equity * max_cap) / buy_price
                    equity -= (pos * buy_price)
                    trades.append({'Date': df.index[i], 'Type': 'BUY', 'Price': buy_price, 'Reason': 'Breakout' if is_break else 'Reversal'})
            # 卖出执行
            elif pos > 0:
                if curr_c < df['s_ref'].iloc[i-1]:
                    sell_price = df['Open'].iloc[i] * 0.999 # 含滑点
                    equity += (pos * sell_price)
                    pos = 0
                    trades.append({'Date': df.index[i], 'Type': 'SELL', 'Price': sell_price})
            
            df.iloc[i, df.columns.get_loc('Equity')] = equity + (pos * df['Close'].iloc[i])

        stats = {
            "Total Return": f"{((df['Equity'].iloc[-1]/100000)-1):.2%}",
            "Trades": len(trades),
            "Final Value": f"${df['Equity'].iloc[-1]:,.0f}"
        }
        return stats, pd.DataFrame(trades), df[['Equity']].reset_index()
    except: return {}, pd.DataFrame(), pd.DataFrame()
