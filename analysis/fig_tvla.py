# -*- coding: utf-8 -*-
"""
Fig. 14 of the paper: fixed-versus-random t-test, first order, of the two masked Shadow-32
implementations (Section 4.7).

(a) ISW implementation, seed 1, all 10,000 samples; (b) table recomputation with register
overwriting, seed 1, all 46,000 samples; 8,192 traces per group; red dotted lines at the
+-4.5 threshold; y range +-25 for (a) and +-8 for (b); the panel titles carry max|t|.

The t curves are read from results/_masked_ttest.npz, written by masked_eval.py; when that
cache is absent they are recomputed from data/masked/ (masked_tools.ttest_pass, about two
minutes).  With --mark-round-end a dashed line marks the start of the idle loop that
follows the round.

Usage :  python fig_tvla.py [--mark-round-end]
Output:  figures/shadow-tvla.pdf (+ .png)
"""
import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from masked_tools import TH, load_set, ttest_pass, tail_period, round_end, OUT

FIG = os.path.join(HERE, "..", "figures")
os.makedirs(FIG, exist_ok=True)
CACHE = os.path.join(OUT, "_masked_ttest.npz")
PANELS = [("ISW_seed1", "(a) ISW", (-25, 25), [-20, -10, 0, 10, 20]),
          ("ISWLUT_seed1", "(b) table recomputation with register overwriting", (-8, 8), [-8, -4, 0, 4, 8])]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 10,
                     "axes.labelsize": 10, "xtick.labelsize": 10, "ytick.labelsize": 10})


def curve(tag):
    """First-order t curve and round end of one set, from the cache or from the traces."""
    if os.path.exists(CACHE):
        c = np.load(CACHE)
        if "t1_" + tag in c.files:
            return c["t1_" + tag].astype(np.float64), int(c["round_end_" + tag])
    print("computing the t-test of %s from the traces" % tag, flush=True)
    tr, pt, g, meta = load_set(tag)
    cv = ttest_pass(tr, g)
    del tr
    p, _ = tail_period(cv["mean"])
    return cv["t1"], round_end(cv["mean"], p)


def main():
    mark = "--mark-round-end" in sys.argv
    fig, axes = plt.subplots(2, 1, figsize=(9, 5))
    for ax, (tag, label, ylim, yticks) in zip(axes, PANELS):
        t, end = curve(tag)
        S = len(t)
        mx = float(np.abs(t).max())
        ax.plot(np.arange(S), t, lw=0.5, color="tab:blue")
        ax.axhline(TH, color="red", ls=":", lw=1.2, zorder=3)
        ax.axhline(-TH, color="red", ls=":", lw=1.2, zorder=3)
        if mark:
            ax.axvline(end, color="0.4", ls="--", lw=0.8)
        ax.set_title("%s   (max$|t|$ = %.2f)" % (label, mx))
        ax.set_ylabel("$t$-statistic")
        ax.set_ylim(*ylim)
        ax.set_yticks(yticks)
        ax.set_xlim(-0.02 * S, 1.02 * S)
        ax.grid(True, lw=0.4, alpha=0.6)
        print("%-13s %d samples, max|t| = %.2f at %d, %d samples over %.1f, round end %d"
              % (tag, S, mx, int(np.abs(t).argmax()), int((np.abs(t) > TH).sum()), TH, end))
    axes[-1].set_xlabel("Sample")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "shadow-tvla.pdf"))
    fig.savefig(os.path.join(FIG, "shadow-tvla.png"), dpi=150)
    plt.close(fig)
    print("Figure : figures/shadow-tvla.pdf")


if __name__ == "__main__":
    main()
