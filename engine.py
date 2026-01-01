# engine.py
import pandas as pd
import numpy as np
import yfinance as yf

# ----------------------------
# Core Indicators (Colab-aligned)
# ----------------------------
def calculate_rsi_wilder(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    alpha = 1 / period
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = -delta.where(delta < 0, 0).ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    return 100 - (100 / (1 + rs))

def get_rsi_ema(series: pd.Series, rsi_period: int, ema_span: int) -> pd.Series:
    """Return (RSI_wilder - 50) smoothed by EMA(span=ema_span)."""
    rsi = calculate_rsi_wilder(series, rsi_period)
    return (rsi - 50).ewm(span=ema_span, adjust=False).mean()

def _download_daily(symbol: str, start: str | None = None, end: str | None = None, period: str | None = None) -> pd.DataFrame:
    if period:
        df = yf.download(symbol, period=period, interval="1d", auto_adjust=True)
    else:
        df = yf.download(symbol, start=start, end=end, interval="1d", auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Open","High","Low","Close","Volume"], how="any")
    return df

def _resample_ohlcv(df_d: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Colab-aligned resample from DAILY to WEEKLY/MONTHLY OHLCV."""
    out = df_d.resample(rule).agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    })
    return out.dropna(subset=["Open","High","Low","Close"], how="any")

# ----------------------------
# EOD Analyzer (Aligned with your V2.9.6 decision tree)
# Uses a single DAILY pool, and resamples for W/M.
# ----------------------------
def run_eod_analyzer(symbol: str) -> dict | None:
    try:
        # Use enough bars to compute 252H/200MA etc.
        d = _download_daily(symbol, period="10y")
        if d.empty or len(d) < 260:
            return None

        w = _resample_ohlcv(d, "W")   # weekly from daily
        m = _resample_ohlcv(d, "ME")  # month-end from daily

        # ---- refs (same spirit as your Colab/EOD audit)
        c_d = float(d["Close"].iloc[-1])
        h_d = float(d["High"].iloc[-1])
        l_d = float(d["Low"].iloc[-1])
        v_d = float(d["Volume"].iloc[-1])

        h_ref = float(d["High"].rolling(252).max().shift(1).iloc[-1])
        s_ref = float(d["Low"].rolling(20).min().shift(1).iloc[-1])

        ma_long = float(d["Close"].rolling(200).mean().iloc[-1])
        ma_mid  = float(d["Close"].rolling(50).mean().iloc[-1])
        vol_ma20 = float(d["Volume"].rolling(20).mean().iloc[-1])

        dist_pct = (h_ref - c_d) / h_ref if h_ref > 0 else np.nan
        fuel = v_d / vol_ma20 if vol_ma20 > 0 else 0.0
        push = (c_d - l_d) / (h_d - l_d) if h_d != l_d else 0.5

        # ---- Macro (Colab-style: weekly needs bx_l>-5)
        bx_l_w = float(get_rsi_ema(w["Close"], 20, 10).iloc[-1]) if len(w) > 25 else -999
        w_bullish = (w["Close"].iloc[-1] > w["Close"].rolling(50).mean().iloc[-1]) and (bx_l_w > -5)

        m_bullish = (m["Close"].iloc[-1] > m["Close"].rolling(20).mean().iloc[-1]) if len(m) > 25 else False
        macro_pass = bool(w_bullish and m_bullish)

        # ---- bx_s reversal check (daily)
        bx_s = get_rsi_ema(d["Close"], 5, 3)
        bx_s_prev = float(bx_s.iloc[-2]) if len(bx_s) >= 2 else 0.0
        bx_s_now  = float(bx_s.iloc[-1]) if len(bx_s) >= 1 else 0.0

        # ---- Decision Tree (match your described V2.9.6)
        action, reason = "WAIT / 等待", "Normal Consolidation / 正常整理"

        if c_d < s_ref:
            action, reason = "SELL / 卖出", "Break 20D Support / 跌破20日支撑"
        elif not macro_pass:
            action, reason = "WAIT / MACRO_VETO", f"Macro Fail / 宏观否决 (W:{'PASS' if w_bullish else 'FAIL'}, M:{'PASS' if m_bullish else 'FAIL'})"
        else:
            if c_d > h_ref:
                if fuel > 1.2 and push > 0.7:
                    action, reason = "BUY / 突破买入", "Strong Breakout / 高位放量强势突破"
                else:
                    action, reason = "WAIT / 弱突破", "Above High but no fuel/push / 站上高点但动能不足"
            elif dist_pct < 0.01:
                if fuel < 1.0:
                    action, reason = "WAIT / 等待(ABSORBING/消化压力)", "Near high with low volume / 高位缩量消化"
            elif (bx_s_prev <= 0 and bx_s_now > 0 and c_d > ma_mid):
                action, reason = "BUY / 反转买入", "Momentum Reversal / 动能由弱转强"

        return {
            "symbol": symbol,
            "Action": action,
            "Reason": reason,
            "Fuel": f"{fuel:.2f}x",
            "Push": f"{push:.1%}",
            "Gap": f"{dist_pct:.2%}",
            "Stop": round(s_ref, 2),
            "Macro": "PASS" if macro_pass else "FAIL",

            # return the pools for plotting
            "D_Data": d,
            "W_Data": w,
            "M_Data": m,

            # for debugging if needed
            "ma_long": ma_long,
            "ma_mid": ma_mid,
            "h_ref": h_ref,
            "s_ref": s_ref,
        }
    except Exception:
        return None

# ----------------------------
# True Sync Backtest Engine (Colab run_smartstock_v296_true_sync)
# ----------------------------
def run_smartstock_v296_engine(symbol: str, start: str, end: str):
    """
    Returns: stats(dict), trades_df, equity_df(Date, Equity)
    Strictly aligned with your Colab `run_smartstock_v296_true_sync`.
    """
    try:
        df = _download_daily(symbol, start=start, end=end)
        if df.empty or len(df) < 260:
            return {}, pd.DataFrame(), pd.DataFrame()

        # ---- build weekly/monthly sync pools from daily (Colab)
        df_w = df["Close"].resample("W").last().to_frame()
        df_w["MA50_w"] = df_w["Close"].rolling(50).mean()
        rsi_20_w = calculate_rsi_wilder(df_w["Close"], 20)
        df_w["bx_l"] = (rsi_20_w - 50).ewm(span=10, adjust=False).mean()
        df_w["w_bullish"] = (df_w["Close"] > df_w["MA50_w"]) & (df_w["bx_l"] > -5)
        df_w_sync = df_w.reindex(df.index, method="ffill")

        df_m = df["Close"].resample("ME").last().to_frame()
        df_m["m_bullish"] = df_m["Close"] > df_m["Close"].rolling(20).mean()
        df_m_sync = df_m.reindex(df.index, method="ffill")

        # ---- daily refs (Colab)
        df["Upper_ref"] = df["High"].rolling(252).max().shift(1)
        df["Lower_ref"] = df["Low"].rolling(20).min().shift(1)
        df["MA50"] = df["Close"].rolling(50).mean()
        df["Vol_MA20"] = df["Volume"].rolling(20).mean()
        df["bx_s"] = (calculate_rsi_wilder(df["Close"], 5) - 50).ewm(span=3, adjust=False).mean()

        # ---- state machine (Colab)
        cash = 100000.0
        init_cash = 100000.0
        pos = 0
        PLAN_TTL, COOLDOWN, MAX_POS = 15, 10, 0.7
        pending_buy = {"active": False, "type": None}
        pending_sell = False
        plan = {"active": False, "age": 0}
        cooldown_timer = 0

        stats = {"issued": 0, "veto": 0, "triggered": 0, "ch_break": 0, "ch_rev": 0}
        trades = []
        equity_curve = []

        entry_p = None
        entry_type = None

        for i in range(252, len(df)):
            dt = df.index[i]
            o_t = float(df["Open"].iloc[i])
            h_t = float(df["High"].iloc[i])
            l_t = float(df["Low"].iloc[i])
            c_t = float(df["Close"].iloc[i])
            v_t = float(df["Volume"].iloc[i])

            # A) execute at next-day open
            if pending_sell and pos > 0:
                p_sell = o_t * (1 - 0.0005)
                cash += pos * p_sell * (1 - 0.001)
                trades.append({
                    "Date": dt,
                    "Type": "SELL",
                    "EntryType": entry_type,
                    "Price": p_sell,
                    "Ret": (p_sell / entry_p) - 1 if entry_p else np.nan
                })
                pos = 0
                pending_sell = False
                cooldown_timer = COOLDOWN

            if pending_buy["active"] and pos == 0:
                p_buy = o_t * (1 + 0.0005)
                pos = int((cash * MAX_POS) / (p_buy * 1.001))
                cash -= pos * p_buy * 1.001
                entry_p = p_buy
                entry_type = pending_buy["type"]

                pending_buy["active"] = False
                stats["triggered"] += 1

                trades.append({
                    "Date": dt,
                    "Type": "BUY",
                    "EntryType": entry_type,
                    "Price": p_buy,
                    "Ret": np.nan
                })

            equity_curve.append(cash + pos * c_t)
            if cooldown_timer > 0:
                cooldown_timer -= 1

            # B) decision at close
            if pos > 0 and (not pending_sell) and c_t < float(df["Lower_ref"].iloc[i]):
                pending_sell = True

            if pos == 0 and (not pending_buy["active"]) and cooldown_timer == 0:
                m_bull = bool(df_m_sync["m_bullish"].iloc[i])
                w_bull = bool(df_w_sync["w_bullish"].iloc[i])
                macro_pass = m_bull and w_bull

                upper = float(df["Upper_ref"].iloc[i])

                # Channel 1: plan & breakout
                if (not plan["active"]) and (c_t > upper * 0.97):
                    plan["active"] = True
                    plan["age"] = 0
                    stats["issued"] += 1

                if plan["active"]:
                    plan["age"] += 1
                    close_pos = (c_t - l_t) / (h_t - l_t) if h_t != l_t else 0.0
                    vol_ma20 = float(df["Vol_MA20"].iloc[i])
                    vol_ratio = v_t / vol_ma20 if vol_ma20 > 0 else 0.0

                    if (c_t > upper) and (close_pos > 0.7) and (vol_ratio > 1.2):
                        if macro_pass:
                            pending_buy = {"active": True, "type": "BREAKOUT"}
                            stats["ch_break"] += 1
                            plan["active"] = False
                        else:
                            stats["veto"] += 1
                            plan["active"] = False
                    elif (plan["age"] > PLAN_TTL) or (c_t < float(df["MA50"].iloc[i])):
                        plan["active"] = False

                # Channel 2: reversal
                bx_s_now = float(df["bx_s"].iloc[i])
                bx_s_prev = float(df["bx_s"].iloc[i - 1])
                if (not pending_buy["active"]) and macro_pass and (c_t > float(df["MA50"].iloc[i])):
                    if bx_s_prev <= 0 and bx_s_now > 0:
                        pending_buy = {"active": True, "type": "REVERSAL"}
                        stats["ch_rev"] += 1

        eq = pd.Series(equity_curve, index=df.index[252:252 + len(equity_curve)], name="Equity")
        equity_df = eq.reset_index().rename(columns={"index": "Date"})

        # stats
        total_ret = (eq.iloc[-1] / init_cash) - 1 if len(eq) else 0.0
        dd = (eq / eq.cummax() - 1).min() if len(eq) else 0.0

        trades_df = pd.DataFrame(trades)

        out_stats = {
            "Total Return": f"{total_ret:.2%}",
            "Max Drawdown": f"{dd:.2%}",
            "Macro Vetoes": int(stats["veto"]),
            "Signals Issued": int(stats["issued"]),
            "Signals Triggered": int(stats["triggered"]),
            "Breakout Trades": int(stats["ch_break"]),
            "Reversal Trades": int(stats["ch_rev"]),
            "Final Equity": f"${eq.iloc[-1]:,.0f}" if len(eq) else "$100,000",
        }
        return out_stats, trades_df, equity_df

    except Exception:
        return {}, pd.DataFrame(), pd.DataFrame()



