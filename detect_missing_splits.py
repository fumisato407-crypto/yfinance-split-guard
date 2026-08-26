"""Detect broken split adjustments in yfinance price data.

Scans daily close-to-close ratios for discontinuities that real trading
almost never produces, then classifies each one:

  * GLITCH        -- a few bars served at the wrong scale, then the series
                     snaps back (bad vendor bars, not a split)
  * NOT_APPLIED   -- a split exists in ticker.splits but the adjusted
                     prices still contain the jump
  * UNRECORDED    -- a persistent scale change with no matching entry in
                     ticker.splits (a split yfinance doesn't know about)

Only dependency: yfinance (pandas comes with it).

    pip install yfinance
    python detect_missing_splits.py 1306.T 8227.T AAPL
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

# Daily ratios outside this band are treated as suspicious. Real one-day
# moves of -45% / +80% are extremely rare for large tickers (and impossible
# on exchanges with daily price limits, like Tokyo). Widen the band if you
# scan micro-caps or crypto.
RATIO_LO, RATIO_HI = 0.55, 1.8

# Candidate split factors to snap a jump to (2:1, 3:1, 1:10, ...).
FACTORS = (2, 3, 4, 5, 6, 8, 10, 15, 20)

# A discontinuity counts as a "glitch" if the series returns to the prior
# scale within this many bars.
GLITCH_MAX_LEN = 3

# Allow the recorded split date and the actual jump in the data to differ
# by a few days (off-by-one ex-dates are common for non-US tickers).
DATE_TOLERANCE_DAYS = 5


@dataclass
class Finding:
    date: str
    ratio: float
    factor: float      # snapped split factor (price divided by this going forward)
    kind: str          # GLITCH | NOT_APPLIED | UNRECORDED


def _snap_factor(raw: float) -> float:
    """Snap an observed jump (e.g. 2.97 or 0.34) to the nearest clean factor."""
    f = raw if raw >= 1 else 1.0 / raw
    return float(min(FACTORS, key=lambda k: abs(k - f)))


def _glitch_end(close: pd.Series, i: int) -> int | None:
    """If the scale change at index i reverts within GLITCH_MAX_LEN bars,
    return the index of the recovery bar; otherwise None."""
    before = float(close.iloc[i - 1])
    for j in range(i + 1, min(i + 1 + GLITCH_MAX_LEN, len(close))):
        back = float(close.iloc[j]) / before
        if 1 / RATIO_HI < back < RATIO_HI:   # back on the prior scale
            return j
    return None


def scan(symbol: str, period: str = "2y") -> list[Finding]:
    t = yf.Ticker(symbol)
    df = t.history(period=period, auto_adjust=True)
    if df.empty:
        print(f"{symbol}: no data returned")
        return []

    close = df["Close"].astype(float)
    ratio = close / close.shift(1)
    recorded = t.splits  # Series indexed by date; empty if none recorded

    findings: list[Finding] = []
    skip_until = -1  # bars consumed by an already-reported glitch
    for i, (date, r) in enumerate(ratio.items()):
        if i <= skip_until or pd.isna(r) or RATIO_LO < r < RATIO_HI:
            continue

        recovery = _glitch_end(close, i)
        if recovery is not None:
            kind = "GLITCH"
            skip_until = recovery  # don't re-flag the recovery jump
        else:
            near = [
                d for d in recorded.index
                if abs((d.date() - date.date()).days) <= DATE_TOLERANCE_DAYS
            ] if len(recorded) else []
            kind = "NOT_APPLIED" if near else "UNRECORDED"

        findings.append(Finding(
            date=str(date.date()),
            ratio=round(float(r), 4),
            factor=_snap_factor(float(r)),
            kind=kind,
        ))
    return findings


def main(symbols: list[str]) -> None:
    for sym in symbols:
        findings = scan(sym)
        if not findings:
            print(f"{sym}: OK - no suspicious discontinuities")
            continue
        print(f"{sym}: {len(findings)} suspicious discontinuit"
              f"{'y' if len(findings) == 1 else 'ies'}")
        for f in findings:
            print(f"  {f.date}  ratio={f.ratio:<8} factor~{f.factor:g}  -> {f.kind}")
        print("  GLITCH: multiply the bad bars back to the prior scale (OHLC * factor).")
        print("  NOT_APPLIED / UNRECORDED: divide prices BEFORE the jump by the factor")
        print("  (and multiply volume), or add the split to a manual correction table.")


if __name__ == "__main__":
    main(sys.argv[1:] or ["1306.T", "8227.T"])
