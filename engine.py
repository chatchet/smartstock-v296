import pandas as pd
import numpy as np
import yfinance as yf


# ========== RSI Wilder (RMA) ==========
def calculate_rsi_wilder(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    alpha = 1 / period
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def get_rsi_ema(series: pd.Series, rsi_period: int, ema_span: int) -> pd.Series:
    rsi = calculate_rsi_wilder(series, rsi_period)
    return (rsi - 50).ewm(span=ema_span, adjust=False).mean()


# ========== Download helpers ==========
def _fix_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _download(symbol: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False)
    return _fix_cols(df)


# ========== EOD Analyzer (对齐 Colab V2.9.6 口径) ==========
def run_eod_analyzer(symbol: str):
    """
    输出 dict:
    - Action / Reason / Fuel / Push / Gap / Stop / Macro
    - D_Data / W_Data / M_Data
    """
    try:
        d = _download(symbol, period="2y", interval="1d")
        w = _download(symbol, period="5y", interval="1wk")
        m = _download(symbol, period="10y", interval="1mo")
        if d is None or d.empty or w is None or w.empty or m is None or m.empty:
            return None

        # --- Daily refs (shift(1) for territory lines) ---
        c_d = float(d["Close"].iloc[-1])
        h_ref = float(d["High"].rolling(252).max().shift(1).iloc[-1])
        s_ref = float(d["Low"].rolling(20).min().shift(1).iloc[-1])
        ma_long = float(d["Close"].rolling(200).mean().iloc[-1])  # 注意：不 shift，与 Colab 一致
        ma_mid  = float(d["Close"].rolling(50).mean().iloc[-1])   # 不 shift
        vol_avg20 = float(d["Volume"].rolling(20).mean().iloc[-1])  # 不 shift

        # --- Physics metrics ---
        dist_pct = (h_ref - c_d) / max(h_ref, 1e-12)
        fuel = float(d["Volume"].iloc[-1]) / max(vol_avg20, 1e-12)

        d_raw_h = float(d["High"].iloc[-1])
        d_raw_l = float(d["Low"].iloc[-1])
        push = (c_d - d_raw_l) / max(d_raw_h - d_raw_l, 1e-12)

        # --- Macro: weekly + monthly ---
        bx_l_w = float(get_rsi_ema(w["Close"], 20, 10).iloc[-1])
        w_bullish = (float(w["Close"].iloc[-1]) > float(w["Close"].rolling(50).mean().iloc[-1])) and (bx_l_w > -5)

        m_pass = float(m["Close"].iloc[-1]) > float(m["Close"].rolling(20).mean().iloc[-1])

        # --- Daily momentum bx_s for reversal check (use last two CLOSED daily bars) ---
        bx_s_d = get_rsi_ema(d["Close"], 5, 3)

        # --- Signal Tree (严格对齐你审计文件描述) ---
        action, reason = "WAIT / 等待", "Normal Consolidation / 正常整理"

        if c_d < s_ref:
            action, reason = "SELL / 卖出", "Break 20D Support (止损离场)"
        elif not (w_bullish and m_pass):
            action, reason = "WAIT / 等待 (MACRO_VETO / 宏观否决)", f"Macro Fail (W:{'PASS' if w_bullish else 'FAIL'}, M:{'PASS' if m_pass else 'FAIL'})"
        else:
            if c_d > h_ref:
                if fuel >= 1.2 and push >= 0.7:
                    action, reason = "BUY / 买入 (ENTRY_PLAN / 突破)", "High-quality breakout confirmed. (高质量突破确认)"
                else:
                    action, reason = "WAIT / 等待 (WEAK_BREAK / 弱突破)", "Price broke high but quality low. (虚假或弱突破)"
            elif 0 <= dist_pct < 0.01:
                if fuel < 1.0:
                    action, reason = "WAIT / 等待 (ABSORBING / 消化压力)", "Low volume near high. (高位缩量消化)"
            else:
                # Reversal: bx_s crosses above 0 and price above MA_MID
                if bx_s_d.iloc[-2] <= 0 and bx_s_d.iloc[-1] > 0 and c_d > ma_mid:
                    action, reason = "BUY / 买入 (ENTRY_PLAN / 反转)", "Momentum reversal in trend. (上升趋势动能反转)"

        return {
            "Action": action,
            "Reason": reason,
            "Fuel": f"{fuel:.2f}x",
            "Push": f"{push:.1%}",
            "Gap": f"{dist_pct:.2%}",
            "Stop": round(s_ref, 2),
            "Macro": "PASS" if (w_bullish and m_pass) else "FAIL",
            "D_Data": d,
            "W_Data": w,
            "M_Data": m,
        }
    except Exception:
        return None


# ========== True Sync Backtest (对齐你最后那版逻辑) ==========
def run_smartstock_v296_engine(symbol: str, start, end):
    """
    返回:
      stats(dict), trades(df), equity(df with columns ['Date','Equity'])
    """
    try:
        df = yf.download(symbol, start=start, end=end, interval="1d", auto_adjust=True, progress=False)
        df = _fix_cols(df)
        if df is None or df.empty or len(df) < 260:
            return {}, pd.DataFrame(), pd.DataFrame()

        # --- Build weekly/monthly synced series from daily (True Sync 口径) ---
        df_w = df["Close"].resample("W").last().to_frame()
        df_w["MA50_w"] = df_w["Close"].rolling(50).mean()
        df_w["bx_l"] = get_rsi_ema(df_w["Close"], 20, 10)
        df_w["w_bullish"] = (df_w["Close"] > df_w["MA50_w"]) & (df_w["bx_l"] > -5)
        df_w_sync = df_w.reindex(df.index, method="ffill")

        df_m = df["Close"].resample("ME").last().to_frame()
        df_m["MA20_m"] = df_m["Close"].rolling(20).mean()
        df_m["m_bullish"] = df_m["Close"] > df_m["MA20_m"]
        df_m_sync = df_m.reindex(df.index, method="ffill")

        # --- Daily refs (shifted) ---
        df["h_ref"] = df["High"].rolling(252).max().shift(1)
        df["s_ref"] = df["Low"].rolling(20).min().shift(1)

        # Daily MA & VolMA (不 shift；与你 True Sync 版一致)
        df["ma_mid"] = df["Close"].rolling(50).mean()
        df["vol_ma20"] = df["Volume"].rolling(20).mean()

        # bx_s daily
        df["bx_s"] = get_rsi_ema(df["Close"], 5, 3)

        # --- Trading params ---
        init_cash = 100000.0
        cash = init_cash
        pos = 0
        COMM = 0.001
        SLIP = 0.0005
        MAX_POS = 0.7

        PLAN_TTL = 15
        COOLDOWN = 10

        pending_buy = {"active": False, "type": None}
        pending_sell = False
        plan = {"active": False, "age": 0}
        cooldown_timer = 0

        stats = {"issued": 0, "veto": 0, "triggered": 0, "ch_break": 0, "ch_rev": 0}
        trades = []
        equity_curve = []

        entry_p = None
        entry_type = None
        shares = 0

        # --- Loop ---
        for i in range(252, len(df)):
            o_t = float(df["Open"].iloc[i])
            h_t = float(df["High"].iloc[i])
            l_t = float(df["Low"].iloc[i])
            c_t = float(df["Close"].iloc[i])
            v_t = float(df["Volume"].iloc[i])

            # A) Execution at next open
            if pending_sell and pos > 0:
                p_sell = o_t * (1 - SLIP)
                cash += shares * p_sell * (1 - COMM)
                trades.append(
                    {"Date": df.index[i], "Type": "SELL", "EntryType": entry_type, "Price": p_sell, "Ret": (p_sell / entry_p) - 1}
                )
                pos = 0
                shares = 0
                pending_sell = False
                cooldown_timer = COOLDOWN
                plan["active"] = False

            if pending_buy["active"] and pos == 0:
                p_buy = o_t * (1 + SLIP)
                shares = int((cash * MAX_POS) / (p_buy * (1 + COMM)))
                if shares > 0:
                    cash -= shares * p_buy * (1 + COMM)
                    pos = 1
                    entry_p = p_buy
                    entry_type = pending_buy["type"]
                    trades.append({"Date": df.index[i], "Type": "BUY", "EntryType": entry_type, "Price": p_buy, "Ret": np.nan})
                    stats["triggered"] += 1
                pending_buy["active"] = False

            # Equity mark-to-market at close
            mkt_val = shares * c_t
            equity = cash + mkt_val
            equity_curve.append(equity)

            if cooldown_timer > 0:
                cooldown_timer -= 1

            # B) Decision at close -> execute next open
            upper = float(df["h_ref"].iloc[i])
            stop_line = float(df["s_ref"].iloc[i])

            # Sell rule
            if pos > 0 and (not pending_sell) and (c_t < stop_line):
                pending_sell = True

            # Buy scan
            if pos == 0 and (not pending_buy["active"]) and cooldown_timer == 0:
                m_bull = bool(df_m_sync["m_bullish"].iloc[i])
                w_bull = bool(df_w_sync["w_bullish"].iloc[i])
                macro_pass = m_bull and w_bull

                # Channel 1: Breakout Plan activation near high
                if (not plan["active"]) and (c_t > upper * 0.97):
                    plan["active"] = True
                    plan["age"] = 0
                    stats["issued"] += 1

                if plan["active"]:
                    plan["age"] += 1
                    close_pos = (c_t - l_t) / max(h_t - l_t, 1e-12)
                    vol_ratio = v_t / max(float(df["vol_ma20"].iloc[i]), 1e-12)

                    if (c_t > upper) and (close_pos > 0.7) and (vol_ratio > 1.2):
                        if macro_pass:
                            pending_buy = {"active": True, "type": "BREAKOUT"}
                            stats["ch_break"] += 1
                        else:
                            stats["veto"] += 1
                        plan["active"] = False
                    elif (plan["age"] > PLAN_TTL) or (c_t < float(df["ma_mid"].iloc[i])):
                        plan["active"] = False

                # Channel 2: Reversal
                bx_now = float(df["bx_s"].iloc[i])
                bx_prev = float(df["bx_s"].iloc[i - 1])
                if (not pending_buy["active"]) and macro_pass and (c_t > float(df["ma_mid"].iloc[i])):
                    if bx_prev <= 0 and bx_now > 0:
                        pending_buy = {"active": True, "type": "REVERSAL"}
                        stats["ch_rev"] += 1

        equity_df = pd.DataFrame({"Date": df.index[252:], "Equity": equity_curve})
        trades_df = pd.DataFrame(trades)

        stats_out = {
            "Total Return": f"{(equity_df['Equity'].iloc[-1] / init_cash) - 1:.2%}",
            "Trades": int(len(trades_df[trades_df["Type"].isin(["BUY", "SELL"])])) if not trades_df.empty else 0,
            "Final Value": f"${equity_df['Equity'].iloc[-1]:,.0f}",
            "Macro Vetoes": int(stats["veto"]),
            "Breakout": int(stats["ch_break"]),
            "Reversal": int(stats["ch_rev"]),
        }
        return stats_out, trades_df, equity_df

    except Exception:
        return {}, pd.DataFrame(), pd.DataFrame()


