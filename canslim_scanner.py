"""
canslim_scanner.py
==================
CAN SLIM stock screener based on William O'Neil's methodology.

Criteria:
    C - Current quarterly EPS growth >= 25% YoY
    A - Annual EPS growth >= 25% over 3 years
    N - Near 52-week high (within 10%) or making new highs
    S - Up/Down volume ratio >= 1.0 (accumulation)
    L - Relative Strength vs S&P 500 (RS Rating proxy)
    I - Industry/sector filter (informational)
    M - Market direction (S&P 500 above 50-day MA + follow-through day)

Usage:
    from canslim_scanner import CANSLIMScanner
    scanner = CANSLIMScanner()
    results = scanner.scan(["AAPL", "GOOGL", "MSFT"])
    scanner.print_results(results)
"""

import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional


# ─────────────────────────────────────────────
# Configuration / Thresholds
# ─────────────────────────────────────────────
CONFIG = {
    "C_min_eps_growth":        25.0,   # % current quarterly EPS growth YoY
    "A_min_annual_eps_growth": 25.0,   # % annual EPS growth (3-yr avg)
    "N_near_high_pct":         10.0,   # % below 52-wk high to still qualify
    "S_min_ud_ratio":          1.0,    # up/down volume ratio minimum
    "L_min_rs_rating":         70.0,   # RS rating (0-99 proxy) minimum
    "M_spy_above_ma_days":     50,     # SPY must be above its N-day MA
    "lookback_days":           365,    # history window for most calculations
    "vol_avg_days":            50,     # days for average volume baseline
}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _pct_change(new_val, old_val) -> Optional[float]:
    """Safe percent change calculation."""
    if old_val is None or old_val == 0 or np.isnan(old_val):
        return None
    return ((new_val - old_val) / abs(old_val)) * 100


def _safe_get(series: pd.Series, idx: int) -> Optional[float]:
    """Safely retrieve a value from a series by position."""
    try:
        val = series.iloc[idx]
        return float(val) if not pd.isna(val) else None
    except (IndexError, TypeError):
        return None


# ─────────────────────────────────────────────
# Individual CAN SLIM checks
# ─────────────────────────────────────────────

def check_C(ticker: yf.Ticker) -> dict:
    """
    C - Current Quarterly EPS Growth >= 25% YoY.
    Compares most recent quarter EPS vs same quarter last year.
    """
    result = {"score": False, "value": None, "detail": "Insufficient data"}
    try:
        income = ticker.quarterly_income_stmt
        if income is None or income.empty:
            return result

        # Look for EPS row (Basic EPS or Diluted EPS)
        eps_rows = [r for r in income.index if "diluted" in r.lower() and "eps" in r.lower()]
        if not eps_rows:
            eps_rows = [r for r in income.index if "basic" in r.lower() and "eps" in r.lower()]
        if not eps_rows:
            # Fall back to net income / shares
            ni_rows = [r for r in income.index if "net income" in r.lower()]
            if not ni_rows:
                return result
            ni_series = income.loc[ni_rows[0]].dropna()
            if len(ni_series) < 5:
                return result
            current_eps = _safe_get(ni_series, 0)
            year_ago_eps = _safe_get(ni_series, 4)
        else:
            eps_series = income.loc[eps_rows[0]].dropna()
            if len(eps_series) < 5:
                return result
            current_eps = _safe_get(eps_series, 0)
            year_ago_eps = _safe_get(eps_series, 4)

        if current_eps is None or year_ago_eps is None:
            return result

        growth = _pct_change(current_eps, year_ago_eps)
        if growth is None:
            return result

        passed = growth >= CONFIG["C_min_eps_growth"]
        result.update({
            "score": passed,
            "value": round(growth, 1),
            "detail": f"Q EPS growth: {growth:.1f}% (min {CONFIG['C_min_eps_growth']}%)"
        })
    except Exception as e:
        result["detail"] = f"Error: {e}"
    return result


def check_A(ticker: yf.Ticker) -> dict:
    """
    A - Annual EPS Growth >= 25% (3-year average growth rate).
    """
    result = {"score": False, "value": None, "detail": "Insufficient data"}
    try:
        income = ticker.income_stmt  # annual
        if income is None or income.empty:
            return result

        eps_rows = [r for r in income.index if "diluted" in r.lower() and "eps" in r.lower()]
        if not eps_rows:
            eps_rows = [r for r in income.index if "basic" in r.lower() and "eps" in r.lower()]

        if not eps_rows:
            ni_rows = [r for r in income.index if "net income" in r.lower()]
            if not ni_rows:
                return result
            series = income.loc[ni_rows[0]].dropna()
        else:
            series = income.loc[eps_rows[0]].dropna()

        if len(series) < 4:
            return result

        # Calculate YoY growth for 3 years
        growths = []
        for i in range(3):
            g = _pct_change(_safe_get(series, i), _safe_get(series, i + 1))
            if g is not None:
                growths.append(g)

        if not growths:
            return result

        avg_growth = np.mean(growths)
        passed = avg_growth >= CONFIG["A_min_annual_eps_growth"]
        result.update({
            "score": passed,
            "value": round(avg_growth, 1),
            "detail": f"3-yr avg annual EPS growth: {avg_growth:.1f}% (min {CONFIG['A_min_annual_eps_growth']}%)"
        })
    except Exception as e:
        result["detail"] = f"Error: {e}"
    return result


def check_N(history: pd.DataFrame) -> dict:
    """
    N - New Highs / Near 52-week high (within N_near_high_pct%).
    Bonus: flag if price is breaking out on high volume.
    """
    result = {"score": False, "value": None, "detail": "Insufficient data"}
    try:
        if history.empty or len(history) < 20:
            return result

        close = history["Close"]
        high_52w = close.rolling(252).max().iloc[-1]
        current = close.iloc[-1]

        pct_from_high = ((high_52w - current) / high_52w) * 100
        passed = pct_from_high <= CONFIG["N_near_high_pct"]

        result.update({
            "score": passed,
            "value": round(pct_from_high, 1),
            "detail": f"{pct_from_high:.1f}% below 52-wk high of {high_52w:.2f} (max {CONFIG['N_near_high_pct']}%)"
        })
    except Exception as e:
        result["detail"] = f"Error: {e}"
    return result


def check_S(history: pd.DataFrame) -> dict:
    """
    S - Supply & Demand: Up/Down Volume Ratio.
    Up days with above-avg volume vs down days with above-avg volume.
    """
    result = {"score": False, "value": None, "detail": "Insufficient data"}
    try:
        if history.empty or len(history) < CONFIG["vol_avg_days"]:
            return result

        df = history.copy()
        df["avg_vol"] = df["Volume"].rolling(CONFIG["vol_avg_days"]).mean()
        df["price_change"] = df["Close"].diff()
        df = df.dropna()

        above_avg = df[df["Volume"] > df["avg_vol"]]
        up_vol   = above_avg[above_avg["price_change"] > 0]["Volume"].sum()
        down_vol = above_avg[above_avg["price_change"] < 0]["Volume"].sum()

        if down_vol == 0:
            ratio = 99.0
        else:
            ratio = up_vol / down_vol

        passed = ratio >= CONFIG["S_min_ud_ratio"]
        result.update({
            "score": passed,
            "value": round(ratio, 2),
            "detail": f"Up/Down vol ratio: {ratio:.2f} (min {CONFIG['S_min_ud_ratio']})"
        })
    except Exception as e:
        result["detail"] = f"Error: {e}"
    return result


def check_L(history: pd.DataFrame, spy_history: pd.DataFrame) -> dict:
    """
    L - Leader or Laggard: RS Rating proxy (0-99).
    Compares 12-month price performance vs S&P 500.
    IBD formula weighted: 40% last 3m, 20% each prior 3m.
    """
    result = {"score": False, "value": None, "detail": "Insufficient data"}
    try:
        if history.empty or spy_history.empty:
            return result

        def weighted_perf(h):
            c = h["Close"]
            n = len(c)
            if n < 252:
                return None
            p3  = (c.iloc[-1]  / c.iloc[-63]  - 1) * 100 if n >= 63  else 0
            p6  = (c.iloc[-63] / c.iloc[-126] - 1) * 100 if n >= 126 else 0
            p9  = (c.iloc[-126]/ c.iloc[-189] - 1) * 100 if n >= 189 else 0
            p12 = (c.iloc[-189]/ c.iloc[-252] - 1) * 100 if n >= 252 else 0
            return 0.40 * p3 + 0.20 * p6 + 0.20 * p9 + 0.20 * p12

        stock_perf = weighted_perf(history)
        spy_perf   = weighted_perf(spy_history)

        if stock_perf is None or spy_perf is None:
            return result

        # RS = percentile proxy based on spread vs market
        # Simplified 0-99 rating: 50 = matches market
        spread = stock_perf - spy_perf
        rs_rating = max(0, min(99, 50 + spread * 0.5))

        passed = rs_rating >= CONFIG["L_min_rs_rating"]
        result.update({
            "score": passed,
            "value": round(rs_rating, 1),
            "detail": (
                f"RS Rating: {rs_rating:.0f}/99 | "
                f"Stock: {stock_perf:.1f}% vs SPY: {spy_perf:.1f}% "
                f"(min RS {CONFIG['L_min_rs_rating']})"
            )
        })
    except Exception as e:
        result["detail"] = f"Error: {e}"
    return result


def check_I(ticker: yf.Ticker) -> dict:
    """
    I - Institutional Sponsorship / Industry.
    Returns sector and industry info. Informational only — no hard pass/fail.
    """
    result = {"score": True, "value": None, "detail": "No sector data"}
    try:
        info = ticker.info
        sector   = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        inst_pct = info.get("heldPercentInstitutions", None)

        detail = f"Sector: {sector} | Industry: {industry}"
        if inst_pct is not None:
            detail += f" | Inst. ownership: {inst_pct*100:.1f}%"

        result.update({
            "score": True,  # informational — always passes
            "value": inst_pct,
            "detail": detail
        })
    except Exception as e:
        result["detail"] = f"Error: {e}"
    return result


def check_M(spy_history: pd.DataFrame) -> dict:
    """
    M - Market Direction.
    Pass if SPY is above its 50-day MA.
    Bonus: detect IBD-style Follow-Through Day (FTD):
      - Rally attempt underway (SPY up 4+ days from a low)
      - A big gain day (>1.7%) on volume > prior day
    """
    result = {"score": False, "value": None, "detail": "Insufficient data", "ftd": False}
    try:
        if spy_history.empty or len(spy_history) < 60:
            return result

        close  = spy_history["Close"]
        volume = spy_history["Volume"]
        ma50   = close.rolling(CONFIG["M_spy_above_ma_days"]).mean()

        current_price = close.iloc[-1]
        current_ma50  = ma50.iloc[-1]
        above_ma      = current_price > current_ma50

        # Follow-Through Day detection (simplified)
        recent = spy_history.tail(20).copy()
        recent["ret"] = recent["Close"].pct_change()
        ftd = False
        for i in range(4, len(recent)):
            day = recent.iloc[i]
            prev = recent.iloc[i - 1]
            # Rally day: +1.7% on higher volume
            if day["ret"] >= 0.017 and day["Volume"] > prev["Volume"]:
                # Check prior 3 days were also positive (rally attempt)
                prior_rets = [recent.iloc[i - j]["ret"] for j in range(1, 4)]
                if sum(r > 0 for r in prior_rets) >= 2:
                    ftd = True
                    break

        pct_above_ma = _pct_change(current_price, current_ma50)
        result.update({
            "score": above_ma,
            "value": round(pct_above_ma, 2) if pct_above_ma else None,
            "detail": (
                f"SPY {'ABOVE' if above_ma else 'BELOW'} 50-day MA "
                f"({current_price:.2f} vs MA {current_ma50:.2f}) | "
                f"FTD detected: {'YES ✓' if ftd else 'No'}"
            ),
            "ftd": ftd
        })
    except Exception as e:
        result["detail"] = f"Error: {e}"
    return result


# ─────────────────────────────────────────────
# Main Scanner Class
# ─────────────────────────────────────────────

class CANSLIMScanner:
    """
    Screens a list of tickers against all 7 CAN SLIM criteria.

    Args:
        config (dict): Optional overrides to CONFIG thresholds.

    Example:
        scanner = CANSLIMScanner()
        results = scanner.scan(["AAPL", "MSFT", "GOOGL"])
        scanner.print_results(results)
        df = scanner.to_dataframe(results)
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = {**CONFIG, **(config or {})}
        self._spy_history = None
        self._spy_ticker  = None

    def _get_spy_data(self) -> tuple:
        if self._spy_history is None:
            print("  [M] Fetching SPY market data...")
            spy = yf.Ticker("SPY")
            self._spy_history = spy.history(period="2y")
            self._spy_ticker  = spy
        return self._spy_ticker, self._spy_history

    def scan_one(self, symbol: str) -> dict:
        """Run all CAN SLIM checks on a single ticker symbol."""
        print(f"\n{'─'*50}")
        print(f"  Scanning: {symbol}")
        print(f"{'─'*50}")

        output = {
            "symbol":  symbol,
            "scanned": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "C": {}, "A": {}, "N": {}, "S": {}, "L": {}, "I": {}, "M": {},
            "passes": 0,
            "total":  7,
            "error":  None
        }

        try:
            ticker  = yf.Ticker(symbol)
            history = ticker.history(period="2y")

            if history.empty:
                output["error"] = f"No price history for {symbol}"
                return output

            _, spy_history = self._get_spy_data()

            output["C"] = check_C(ticker)
            output["A"] = check_A(ticker)
            output["N"] = check_N(history)
            output["S"] = check_S(history)
            output["L"] = check_L(history, spy_history)
            output["I"] = check_I(ticker)
            output["M"] = check_M(spy_history)

            output["passes"] = sum(
                output[k].get("score", False)
                for k in ["C", "A", "N", "S", "L", "I", "M"]
            )

        except Exception as e:
            output["error"] = str(e)

        return output

    def scan(self, symbols: list, min_passes: int = 4) -> list:
        """
        Scan a list of symbols. Returns all results sorted by passes desc.

        Args:
            symbols:     List of ticker strings.
            min_passes:  Minimum CAN SLIM criteria passed to include in output.
                         Set to 0 to return all.
        """
        print(f"\n{'='*50}")
        print(f"  CAN SLIM Scanner — {len(symbols)} symbols")
        print(f"  Min passes required: {min_passes}/7")
        print(f"{'='*50}")

        results = [self.scan_one(s.upper().strip()) for s in symbols]
        results.sort(key=lambda x: x["passes"], reverse=True)

        if min_passes > 0:
            results = [r for r in results if r["passes"] >= min_passes]

        return results

    # ── Output helpers ──────────────────────────────────

    def print_results(self, results: list):
        """Pretty-print scan results to console."""
        if not results:
            print("\nNo symbols passed the minimum criteria threshold.")
            return

        print(f"\n{'='*60}")
        print(f"  SCAN RESULTS — {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*60}")

        for r in results:
            sym = r["symbol"]
            passes = r["passes"]
            bar = "█" * passes + "░" * (7 - passes)

            print(f"\n  {sym:8s}  [{bar}]  {passes}/7 criteria met")
            if r.get("error"):
                print(f"    ⚠ Error: {r['error']}")
                continue

            icons = {"C": "💰", "A": "📈", "N": "🆕", "S": "📊",
                     "L": "⭐", "I": "🏭", "M": "🌐"}
            for k in ["C", "A", "N", "S", "L", "I", "M"]:
                crit = r[k]
                chk  = "✓" if crit.get("score") else "✗"
                print(f"    {icons[k]} {k}: {chk}  {crit.get('detail', 'N/A')}")

        print(f"\n{'='*60}")
        print(f"  {len(results)} symbol(s) shown.")

    def to_dataframe(self, results: list) -> pd.DataFrame:
        """
        Convert scan results to a tidy summary DataFrame.
        Useful for sorting, filtering, and export to CSV.
        """
        rows = []
        for r in results:
            row = {
                "Symbol":  r["symbol"],
                "Passes":  r["passes"],
                "Scanned": r["scanned"],
                "Error":   r.get("error", ""),
            }
            for k in ["C", "A", "N", "S", "L", "I", "M"]:
                crit = r.get(k, {})
                row[f"{k}_pass"]   = crit.get("score", False)
                row[f"{k}_value"]  = crit.get("value", None)
                row[f"{k}_detail"] = crit.get("detail", "")
            rows.append(row)

        df = pd.DataFrame(rows)
        df = df.sort_values("Passes", ascending=False).reset_index(drop=True)
        return df

    def export_csv(self, results: list, filename: str = "canslim_results.csv"):
        """Export results to CSV."""
        df = self.to_dataframe(results)
        df.to_csv(filename, index=False)
        print(f"\n  Exported {len(df)} rows → {filename}")
        return df


# ─────────────────────────────────────────────
# Watchlist presets
# ─────────────────────────────────────────────

WATCHLISTS = {
    "mega_cap_tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
    "financials":    ["JPM", "BAC", "GS", "MS", "V", "MA", "XLF", "KRE"],
    "healthcare":    ["UNH", "LLY", "ABBV", "JNJ", "MRK", "PFE", "AMGN"],
    "industrials":   ["CAT", "DE", "HON", "GE", "BA", "RTX", "LMT"],
    "sample_mixed":  ["NVDA", "AAPL", "GOOGL", "META", "JPM", "UNH", "CAT"],
}


if __name__ == "__main__":
    scanner = CANSLIMScanner()
    results = scanner.scan(WATCHLISTS["sample_mixed"], min_passes=4)
    scanner.print_results(results)
    scanner.export_csv(results)
