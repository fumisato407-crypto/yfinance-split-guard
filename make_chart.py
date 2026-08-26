# Renders chart.png: 1306.T as served by yfinance vs. the repaired series.
# Top panel: daily close with the two bars served at 1/10 scale (2026-03-30/31).
# Bottom panel: 200-day SMA of both series, zoomed to show the dent.
#
# Dependencies: yfinance, matplotlib  (pip install yfinance matplotlib)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import yfinance as yf

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"    # repaired series
ORANGE = "#eb6834"  # as served by yfinance

df = yf.Ticker("1306.T").history(period="2y", auto_adjust=True)
close_raw = df["Close"].astype(float).copy()
close_raw.index = close_raw.index.tz_localize(None)

# Repair: the 2026-03-30/31 bars are served at 1/10 scale; multiply them back.
close_fix = close_raw.copy()
glitch = (close_fix.index >= "2026-03-30") & (close_fix.index <= "2026-03-31")
close_fix[glitch] = close_fix[glitch] * 10.0

ma_raw = close_raw.rolling(200).mean()
ma_fix = close_fix.rolling(200).mean()

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(9.6, 6.4), dpi=150, sharex=True,
    gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.12},
)
fig.patch.set_facecolor(SURFACE)

for ax in (ax1, ax2):
    ax.set_facecolor(SURFACE)
    ax.grid(True, axis="y", color=GRID, linewidth=0.8)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)

# --- Top: daily close ---
ax1.plot(close_raw.index, close_raw.values, color=ORANGE, linewidth=1.6,
         label="As served by yfinance", zorder=3)
ax1.plot(close_fix.index, close_fix.values, color=BLUE, linewidth=1.6,
         linestyle=(0, (4, 2)), label="Repaired (glitch bars ×10)", zorder=4)

gd = close_raw[glitch]
ax1.scatter(gd.index, gd.values, s=28, color=ORANGE, edgecolor=SURFACE,
            linewidth=1.2, zorder=5)
ax1.annotate("2026-03-30/31 served at 1/10 scale\n(split still absent from t.splits)",
             xy=(gd.index[0], gd.values[0]), xytext=(pd.Timestamp("2025-04-20"), 130),
             fontsize=9, color=INK,
             arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))

ax1.set_ylabel("Close (JPY)", color=MUTED, fontsize=9)
ax1.set_title("1306.T (TOPIX ETF) — yfinance data vs. repaired series, as of 2026-08-26",
              color=INK, fontsize=11.5, loc="left", pad=12)
ax1.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)

# --- Bottom: MA200 zoom ---
ax2.plot(ma_raw.index, ma_raw.values, color=ORANGE, linewidth=1.6, zorder=3)
ax2.plot(ma_fix.index, ma_fix.values, color=BLUE, linewidth=1.6,
         linestyle=(0, (4, 2)), zorder=4)
ax2.set_ylabel("200-day SMA (JPY)", color=MUTED, fontsize=9)

lo = pd.Timestamp("2026-01-01")
sub = pd.concat([ma_raw[ma_raw.index >= lo], ma_fix[ma_fix.index >= lo]]).dropna()
ax2.set_ylim(sub.min() * 0.985, sub.max() * 1.01)

i = ma_raw.index.get_indexer([pd.Timestamp("2026-05-15")], method="nearest")[0]
d = ma_raw.index[i]
gap_pct = (ma_raw.loc[d] / ma_fix.loc[d] - 1) * 100
ax2.annotate(f"two bad bars dent the MA200 by ~{abs(gap_pct):.1f}%\nfor the next 200 trading days",
             xy=(d, ma_raw.loc[d]), xytext=(pd.Timestamp("2025-01-10"), sub.min() * 1.002),
             fontsize=9, color=INK,
             arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))

ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

fig.savefig("chart.png", facecolor=SURFACE, bbox_inches="tight")
print(f"saved chart.png (MA200 dent at {d.date()}: {gap_pct:+.2f}%)")
