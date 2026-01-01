import pandas as pd
import numpy as np
import yfinance as yf

# --- 核心算法：Wilder RSI 计算 ---
def calculate_rsi_wilder(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    alpha = 1 / period
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = -delta.where(delta < 0, 0).ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

# --- EOD 分析器：依据日/周/月三周期和完整信号树生成建议 ---
def run_eod_analyzer(symbol: str):
    try:
        # 1. 下载三周期数据
        d = yf.download(symbol, period="2y", interval="1d", auto_adjust=True)
        w = yf.download(symbol, period="5y", interval="1wk", auto_adjust=True)
        m = yf.download(symbol, period="10y", interval="1mo", auto_adjust=True)
        if d.empty or w.empty or m.empty:
            return None

        # 抹平多重列索引
        for df in (d, w, m):
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        # 2. 计算日线关键指标（未来函数全部 shift(1)）
        close_d = d['Close'].iloc[-1]
        high_ref = d['High'].rolling(252).max().shift(1).iloc[-1]
        support_ref = d['Low'].rolling(20).min().shift(1).iloc[-1]
        ma_long = d['Close'].rolling(200).mean().iloc[-1]
        ma_mid = d['Close'].rolling(50).mean().iloc[-1]
        vol_avg20 = d['Volume'].rolling(20).mean().iloc[-1]
        # 动能短：BX_s
        bx_s = (calculate_rsi_wilder(d['Close'], 5) - 50).ewm(span=3, adjust=False).mean()

        # 3. 周/月动能与宏观过滤
        rsi20_w = calculate_rsi_wilder(w['Close'], 20)
        bx_l_w = (rsi20_w - 50).ewm(span=10, adjust=False).mean().iloc[-1]
        w_ma50 = w['Close'].rolling(50).mean().iloc[-1]
        w_bullish = (w['Close'].iloc[-1] > w_ma50) and (bx_l_w > -5)

        rsi20_m = calculate_rsi_wilder(m['Close'], 20)
        bx_l_m = (rsi20_m - 50).ewm(span=10, adjust=False).mean().iloc[-1]
        m_ma20 = m['Close'].rolling(20).mean().iloc[-1]
        m_bullish = (m['Close'].iloc[-1] > m_ma20)

        # 4. 物理记录
        dist_pct = (high_ref - close_d) / high_ref if high_ref else 0
        vol_ratio = d['Volume'].iloc[-1] / vol_avg20 if vol_avg20 else 0
        day_high, day_low = d['High'].iloc[-1], d['Low'].iloc[-1]
        push_ratio = (close_d - day_low) / (day_high - day_low) if day_high != day_low else 0.5

        # 5. 信号树对齐 V2.9.6
        action_en, action_cn = "WAIT", "等待"
        reason_en, reason_cn = "Normal consolidation", "常态整理"

        if close_d < support_ref:  # 止损
            action_en, action_cn = "SELL", "卖出"
            reason_en, reason_cn = "Break 20D support", "跌破20日支撑"
        elif not (w_bullish and m_bullish):  # 宏观否决
            action_en, action_cn = "WAIT", "等待"
            reason_en = f"Macro veto: W:{'PASS' if w_bullish else 'FAIL'}, M:{'PASS' if m_bullish else 'FAIL'}"
            reason_cn = f"宏观否决，周线{'通过' if w_bullish else '失败'}，月线{'通过' if m_bullish else '失败'}"
        else:
            # 突破与吸筹
            if close_d > high_ref:
                if vol_ratio > 1.2 and push_ratio > 0.7:
                    action_en, action_cn = "BUY", "买入"
                    reason_en, reason_cn = "Strong breakout confirmed", "高位放量强突破"
                else:
                    action_en, action_cn = "WAIT", "等待"
                    reason_en, reason_cn = "Weak breakout: no volume", "突破但无量"
            elif dist_pct < 0.01:  # 接近高点
                if vol_ratio < 1.0:
                    action_en, action_cn = "WAIT", "等待"
                    reason_en, reason_cn = "Near high: absorbing", "接近高位，缩量消化"
            # 动能反转
            elif bx_s.iloc[-2] <= 0 and bx_s.iloc[-1] > 0 and close_d > ma_mid:
                action_en, action_cn = "BUY", "买入"
                reason_en, reason_cn = "Momentum reversal", "动能反转买入"

        return {
            "Action_EN": action_en, "Action_CN": action_cn,
            "Reason_EN": reason_en, "Reason_CN": reason_cn,
            "Fuel": f"{vol_ratio:.2f}x", "Push": f"{push_ratio:.1%}",
            "Gap": f"{dist_pct:.2%}", "Stop": f"{support_ref:.2f}",
            "D_Data": d, "W_Data": w, "M_Data": m,
            "Macro": "PASS" if (w_bullish and m_bullish) else "FAIL"
        }
    except Exception:
        return None

# --- True Sync 回测引擎 ---
def run_smartstock_v296_engine(symbol: str, start: str, end: str):
    """
    对齐 V2.9.6 回测：包括计划窗口、突破/反转双通道、宏观 veto、冷却期、仓位限制和滑点/佣金。
    返回 statistics、trades DataFrame、equity DataFrame。
    """
    df = yf.download(symbol, start=start, end=end, interval="1d", auto_adjust=True)
    if df.empty or len(df) < 260:
        return {}, pd.DataFrame(), pd.DataFrame()

    # 清洗列索引
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 日线指标
    df["h_ref"] = df["High"].rolling(252).max().shift(1)
    df["s_ref"] = df["Low"].rolling(20).min().shift(1)
    df["ma_mid"] = df["Close"].rolling(50).mean()          # 不 shift
    df["ma_long"] = df["Close"].rolling(200).mean()        # 不 shift
    df["vol_ma20"] = df["Volume"].rolling(20).mean()
    df["bx_s"] = (calculate_rsi_wilder(df["Close"], 5) - 50).ewm(span=3, adjust=False).mean()

    # 周/月宏观指标预先对齐到日线索引
    # 周
    w = yf.download(symbol, start=start, end=end, interval="1wk", auto_adjust=True)
    if isinstance(w.columns, pd.MultiIndex):
        w.columns = w.columns.get_level_values(0)
    w['ma50'] = w['Close'].rolling(50).mean()
    w['bx_l'] = (calculate_rsi_wilder(w['Close'], 20) - 50).ewm(span=10, adjust=False).mean()
    w['w_bull'] = (w['Close'] > w['ma50']) & (w['bx_l'] > -5)
    w_sync = w['w_bull'].reindex(df.index, method='ffill')

    # 月
    m = yf.download(symbol, start=start, end=end, interval="1mo", auto_adjust=True)
    if isinstance(m.columns, pd.MultiIndex):
        m.columns = m.columns.get_level_values(0)
    m['ma20'] = m['Close'].rolling(20).mean()
    m['m_bull'] = (m['Close'] > m['ma20'])
    m_sync = m['m_bull'].reindex(df.index, method='ffill')

    # 回测状态机
    cash = init_cash = 100000.0
    pos = 0
    cooldown_timer = 0
    plan = {"active": False, "age": 0}
    pending_buy = {"active": False, "type": None}
    pending_sell = False
    trades = []
    equity_curve = []
    stats = {'issued': 0, 'veto': 0, 'triggered': 0, 'ch_break': 0, 'ch_rev': 0}

    for i in range(252, len(df)):
        dt = df.index[i]
        o = df["Open"].iloc[i]
        c = df["Close"].iloc[i]
        high_ref = df["h_ref"].iloc[i]
        support = df["s_ref"].iloc[i]
        ma_mid = df["ma_mid"].iloc[i]
        vol_avg = df["vol_ma20"].iloc[i]
        bx_s_now = df["bx_s"].iloc[i]
        bx_s_prev = df["bx_s"].iloc[i-1]

        macro_pass = bool(m_sync.iloc[i] and w_sync.iloc[i])

        # --- 执行层（次日开盘） ---
        if pending_sell and pos > 0:
            price_sell = o * (1 - 0.0005)
            cash += pos * price_sell * (1 - 0.001)
            trades.append({'Date': dt, 'Type': 'SELL', 'Price': price_sell,
                           'Reason': 'EXIT' if pos_type == 'BREAKOUT' else 'EXIT_REV'})
            pos = 0
            cooldown_timer = 10
            pending_sell = False
            plan['active'] = False

        if pending_buy["active"] and pos == 0:
            price_buy = o * (1 + 0.0005)
            qty = int((cash * 0.7) / (price_buy * 1.001))
            if qty > 0:
                pos = qty
                cash -= qty * price_buy * 1.001
                pos_type = pending_buy["type"]
                trades.append({'Date': dt, 'Type': 'BUY', 'Price': price_buy, 'Reason': pos_type})
            pending_buy["active"] = False
            stats['triggered'] += 1

        # 记录组合净值
        equity_curve.append(cash + pos * c)

        # 冷却倒计时
        if cooldown_timer > 0:
            cooldown_timer -= 1

        # --- 收盘判定决策层 ---
        # 1. 卖出：破支撑
        if pos > 0 and not pending_sell and c < support:
            pending_sell = True

        # 2. 无仓位时可能买入
        if pos == 0 and not pending_buy["active"] and cooldown_timer == 0:
            # 突破计划激活条件
            if not plan['active'] and c > high_ref * 0.97:
                plan['active'] = True
                plan['age'] = 0
                stats['issued'] += 1

            # 突破计划执行
            if plan['active']:
                plan['age'] += 1
                close_pos = (c - df['Low'].iloc[i]) / (df['High'].iloc[i] - df['Low'].iloc[i]) if df['High'].iloc[i] != df['Low'].iloc[i] else 0.5
                vol_ratio = df['Volume'].iloc[i] / vol_avg if vol_avg else 0
                if c > high_ref and close_pos > 0.7 and vol_ratio > 1.2:
                    if macro_pass:
                        pending_buy = {"active": True, "type": "BREAKOUT"}
                        stats['ch_break'] += 1
                    else:
                        stats['veto'] += 1
                    plan['active'] = False
                elif plan['age'] > 15 or c < ma_mid:
                    plan['active'] = False

            # 动能反转通道
            if not pending_buy["active"] and macro_pass and c > ma_mid:
                if bx_s_prev <= 0 and bx_s_now > 0:
                    pending_buy = {"active": True, "type": "REVERSAL"}
                    stats['ch_rev'] += 1

    # 计算结果
    final_equity = equity_curve[-1]
    total_return = final_equity / init_cash - 1
    mdd = (pd.Series(equity_curve) / pd.Series(equity_curve).cummax() - 1).min()
    # 分类胜率
    trades_df = pd.DataFrame(trades)
    breakout_winrate = None
    reversal_winrate = None
    if not trades_df.empty:
        breakout_trades = trades_df[trades_df['Reason']=='BREAKOUT']
        reversal_trades = trades_df[trades_df['Reason']=='REVERSAL']
        if not breakout_trades.empty:
            sells = breakout_trades[breakout_trades['Type']=='SELL']
            win_count = (sells['Price'] > breakout_trades['Price'].shift(1)).sum()
            breakout_winrate = win_count / len(sells)
        if not reversal_trades.empty:
            sells = reversal_trades[reversal_trades['Type']=='SELL']
            win_count = (sells['Price'] > reversal_trades['Price'].shift(1)).sum()
            reversal_winrate = win_count / len(sells)

    stats_out = {
        "TotalReturn_EN": f"{total_return:.2%}", "TotalReturn_CN": f"{total_return*100:.2f}%",
        "MaxDrawdown_EN": f"{mdd:.2%}", "MaxDrawdown_CN": f"{mdd*100:.2f}%",
        "Trades": len(trades_df), "MacroVeto": stats['veto'],
        "BreakoutTrades": stats['ch_break'], "ReversalTrades": stats['ch_rev'],
        "BreakoutWinRate": breakout_winrate, "ReversalWinRate": reversal_winrate,
        "FinalEquity": f"${final_equity:,.2f}"
    }
    equity_df = pd.DataFrame({"Date": df.index[252:252+len(equity_curve)], "Equity": equity_curve})
    return stats_out, trades_df, equity_df

