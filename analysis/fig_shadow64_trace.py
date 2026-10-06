# -*- coding: utf-8 -*-
"""
Shadow-64 power-trace figure (Fig. 15 of the paper, fig/shadow64-power-trace.pdf) and the round
period measured by autocorrelation.

Data   : data/shadow64/s64_ref_25000.npz (4,096 traces x 25,000 samples); the first trace is drawn.
Method : the round period is the lag of the largest peak of the autocorrelation of the trace
         (searched between 400 and 1,200 samples), and 32 x period is compared with the trace
         length; the figure uses the rcParams of the other trace figures (fig_fixedkey_cpa.py).

Usage :  python fig_shadow64_trace.py
Output:  figures/shadow64/trace.pdf (+ .png)   the whole trace, 25,000 samples (Fig. 15)
         figures/shadow64/trace_zoom.png         the first four rounds, for reference
"""
import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
NPZ  = os.path.join(HERE, "..", "data", "shadow64", "s64_ref_25000.npz")
FIG  = os.path.join(HERE, "..", "figures", "shadow64")
os.makedirs(FIG, exist_ok=True)

FONT = 7
W_FULL, H_TRACE = 7.09, 1.60
DPI = 600
plt.rcParams.update({
    "font.size": FONT, "axes.labelsize": FONT, "axes.titlesize": FONT,
    "xtick.labelsize": FONT - 1, "ytick.labelsize": FONT - 1,
    "legend.fontsize": FONT - 1, "axes.linewidth": 0.5,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.major.size": 2.0, "ytick.major.size": 2.0,
    "xtick.major.pad": 1.5, "ytick.major.pad": 1.5,
    "axes.labelpad": 1.5, "grid.linewidth": 0.35,
    "axes.unicode_minus": False,
    # figsize is kept as is (no bbox='tight'), as in the other figures of the paper
    "figure.constrained_layout.use": True,
    "figure.constrained_layout.h_pad": 0.01,
    "figure.constrained_layout.w_pad": 0.01,
})

d  = np.load(NPZ)
tr = d["traces"]
t  = np.asarray(tr[0], np.float64)
print("traces %s | clkout %.1f MHz | phase %s"
      % (tr.shape, float(d["clkout"]) / 1e6, str(d["phase"])))

# ------------------------------------------------------------------ round period
# The lag of the largest autocorrelation peak gives the round period; 32 rounds should fit
# in the trace.
x  = t - t.mean()
ac = np.correlate(x, x, "full")[len(x) - 1:]
per = 400 + int(np.argmax(ac[400:1200]))
print("round period %d samples -> 32 rounds = %d samples (trace length %d)"
      % (per, per * 32, len(t)))

# ------------------------------------------------------------------ whole trace
# A downward spike marks every round boundary, so the 32 rounds are visible in the raw trace.
plt.figure(figsize=(W_FULL, H_TRACE))
plt.plot(t, lw=0.3, rasterized=True)
plt.grid(True, alpha=0.35)
plt.xlabel("Sample index"); plt.ylabel("Power consumption")
plt.xlim([0, len(t)])
plt.savefig(os.path.join(FIG, "trace.pdf"))
plt.savefig(os.path.join(FIG, "trace.png"), format="png", dpi=DPI)
plt.close()

# ------------------------------------------------------------------ first four rounds
n4 = per * 4
plt.figure(figsize=(W_FULL, H_TRACE))
plt.plot(t[:n4], lw=0.35, rasterized=True)
for r in range(1, 4):
    plt.axvline(r * per, color="#d62728", ls=":", lw=0.5)
plt.grid(True, alpha=0.35)
plt.xlabel("Sample index"); plt.ylabel("Power consumption")
plt.xlim([0, n4])
plt.savefig(os.path.join(FIG, "trace_zoom.png"), format="png", dpi=DPI)
plt.close()

print("figures -> figures/shadow64/trace.pdf, trace.png (Fig. 15), trace_zoom.png (reference)")
