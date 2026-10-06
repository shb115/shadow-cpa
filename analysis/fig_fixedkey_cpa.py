# -*- coding: utf-8 -*-
"""
Correlation figures of the fixed-key Shadow-32 set (Figs 5-10 of the paper, Sections 4.2-4.4)
and the sign decision D of Section 4.3.

The figures are the CPAs of Algorithm 1 on this set, plus the complement-pair figures of
Section 4.2 that exhibit the duals:
  Fig. 5   one acquired trace
  Fig. 6   signed correlation of h0 over the candidates 0..127 and 128..255
  Fig. 7   |rho| of h1 over 0..127
  Fig. 8   |rho| of h2 and h2* (RK1_2), and of h3 and h3* (RK1_3), over 0..127
  Fig. 9   the four 4-bit CPAs of Round 2: upper nibble of RK2_0; lower nibble of RK2_2 with
           the upper nibble unmodeled (labeled 0x?n); upper nibble of RK2_2 with the lower
           nibble fixed; lower nibble of RK2_3
  Fig. 10  the four 4-bit CPAs of Rounds 3 and 4
Every CPA runs over the samples of the round its subkey belongs to, [b0 + (r-1)P, b0 + rP),
with the period P and the boundary b0 taken from the mean trace alone (round_structure.py).
The x axis is the absolute sample index.  The 7-bit CPA on RK2_1, a byte the key schedule
already fixes, is printed as a check only and has no figure.

Usage :  python fig_fixedkey_cpa.py
Output:  figures/shadow32_fixedkey/shadow-power-trace.pdf / .png   (Fig. 5)
         figures/shadow32_fixedkey/shadow-cpa-*.pdf / .png
         results/RESULTS_fixedkey_cpa.md
"""
import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from round_structure import round_structure, round_interval
from cpa_shadow32_12500 import F8 as F, nx8, cpa_on_target, signed_peak_per_key

NPZ = os.path.join(HERE, "..", "data", "shadow32_fixedkey", "s32_ref_12500.npz")
FIG = os.path.join(HERE, "..", "figures", "shadow32_fixedkey")
OUT = os.path.join(HERE, "..", "results")
os.makedirs(FIG, exist_ok=True); os.makedirs(OUT, exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
FONT = 7
W_FULL, H_FULL = 7.09, 1.95
H_TRACE = 1.60
W_HALF, H_HALF = 3.46, 1.70
DPI = 600
plt.rcParams.update({
    "font.size": FONT, "axes.labelsize": FONT, "axes.titlesize": FONT,
    "xtick.labelsize": FONT - 1, "ytick.labelsize": FONT - 1,
    "legend.fontsize": FONT - 1, "axes.linewidth": 0.5,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.major.size": 2.0, "ytick.major.size": 2.0,
    "xtick.major.pad": 1.5, "ytick.major.pad": 1.5,
    "axes.labelpad": 1.5, "grid.linewidth": 0.35,
    "legend.frameon": True, "legend.framealpha": 0.9, "legend.borderaxespad": 0.3,
    "figure.constrained_layout.use": True,
    "figure.constrained_layout.h_pad": 0.01, "figure.constrained_layout.w_pad": 0.01,
    "pdf.fonttype": 42, "ps.fonttype": 42,
})
LEG = dict(handlelength=1.1, borderpad=0.2, handletextpad=0.3, labelspacing=0.2)
CPA_THRESH = 0.5            # a curve is highlighted only if it clearly stands out


def _save(name):
    plt.savefig(os.path.join(FIG, name + ".pdf"))
    plt.savefig(os.path.join(FIG, name + ".png"), dpi=DPI)
    plt.close()


def signed_show(c, x0, start, name, size=(W_HALF, H_HALF)):
    """Signed correlation of 128 candidates; highlight the global max and min curves."""
    xs = x0 + np.arange(c.shape[0])
    imax = int(np.unravel_index(np.argmax(c), c.shape)[1])
    imin = int(np.unravel_index(np.argmin(c), c.shape)[1])
    plt.figure(figsize=size)
    for i in range(c.shape[1]):
        if i not in (imax, imin):
            plt.plot(xs, c[:, i], color=[0.88, 0.88, 0.88], lw=0.25, rasterized=True)
    plt.plot(xs, c[:, imax], color='#d62728', lw=0.8, label="0x%02X" % (imax + start))
    plt.plot(xs, c[:, imin], color='#2ca02c', lw=0.8, label="0x%02X" % (imin + start))
    plt.ylim([-0.95, 0.95]); plt.xlim([xs[0], xs[-1] + 1]); plt.grid(True, alpha=0.35)
    plt.legend(**LEG); plt.xlabel('Sample index'); plt.ylabel('Correlation coefficient')
    _save(name)
    return imax + start, imin + start, float(c.max()), float(c.min())


def abs_show(c, x0, start, name, size=(W_HALF, H_HALF), labels=None, fmt="0x%02X"):
    """|correlation| of the candidates; highlight the best one if it clearly stands out.
    `labels` gives the value to print for each column (e.g. the full byte with the fixed
    nibble filled in), `fmt` its format (0x?%X for a nibble whose other half is unmodeled)."""
    xs = x0 + np.arange(c.shape[0])
    a = np.abs(c)
    best = int(np.argmax(a.max(axis=0)))
    hl = a.max() > CPA_THRESH
    plt.figure(figsize=size)
    for i in range(a.shape[1]):
        if not (hl and i == best):
            plt.plot(xs, a[:, i], color=[0.88, 0.88, 0.88], lw=0.25, rasterized=True)
    if hl:
        lab = labels[best] if labels is not None else best + start
        plt.plot(xs, a[:, best], color='#d62728', lw=0.8, label=fmt % lab)
        plt.legend(**LEG)
    plt.ylim([-0.05, 0.95]); plt.xlim([xs[0], xs[-1] + 1]); plt.grid(True, alpha=0.35)
    plt.xlabel('Sample index'); plt.ylabel('Absolute correlation')
    _save(name)
    return (labels[best] if labels is not None else best + start), float(a.max())


def main():
    d = np.load(NPZ)
    tr = d["traces"].astype(np.float64); pt = d["pt"]
    RK = [int(x) for x in d["rk"][:16]]
    P, b0 = round_structure(tr)
    IV = [round_interval(r, P, b0, tr.shape[1]) for r in (1, 2, 3, 4)]
    T = [tr[:, a:b] for a, b in IV]
    x0 = [a for a, _ in IV]
    L0, L1, R0, R1 = (pt[:, i].astype(np.int64) for i in range(4))
    G128 = range(128)

    # ---- one acquired trace (Fig. 5); no key involved
    t = tr[0]
    plt.figure(figsize=(W_FULL, H_TRACE))
    plt.plot(t, lw=0.4); plt.grid(True, alpha=0.35)
    plt.xlabel('Sample index'); plt.ylabel('Power consumption'); plt.xlim([0, len(t)])
    _save("shadow-power-trace")

    rep = ["# Fixed-key Shadow-32 set: correlation figures and the sign decision\n",
           "Round period %d, round boundary %d (from the mean trace).  Round intervals: %s\n"
           % (P, b0, ", ".join("[%d, %d)" % iv for iv in IV))]
    stages = []                                   # (stage, target, candidates, value, |rho|, figure)

    # ---- Round 1 : h0 over 0..127 and 128..255 (Fig. 6); the pair of RK1_0 and p
    h0 = F(L0) ^ L1
    c0 = cpa_on_target(G128, T[0], h0)
    k0a, k0a_min, mx_a, mn_a = signed_show(c0, x0[0], 0, "shadow-cpa-k0-128")
    k0b_max, k0b, mx_b, mn_b = signed_show(cpa_on_target(range(128, 256), T[0], h0), x0[0], 128, "shadow-cpa-k0-256")
    rep.append("- Fig. 6(a) 0..127: max 0x%02X (%+.3f), min 0x%02X (%+.3f)" % (k0a, mx_a, k0a_min, mn_a))
    rep.append("- Fig. 6(b) 128..255: max 0x%02X (%+.3f), min 0x%02X (%+.3f)" % (k0b_max, mx_b, k0b, mn_b))
    sp0 = signed_peak_per_key(c0)
    g0 = int(np.argmax(np.abs(sp0)))
    p = g0 if sp0[g0] > 0 else (g0 ^ 0xFF)        # the member of the pair with the positive peak
    rep.append("- RK1_0 pair {0x%02X, 0x%02X} (|rho| %.3f), positive-peak member p = 0x%02X" % (g0, g0 ^ 0xFF, abs(sp0[g0]), p))

    # ---- h1 over 0..127 (Fig. 7): the pair of RK1_1
    h1 = F(R0) ^ R1
    c1 = cpa_on_target(G128, T[0], h1)
    k1, pk1 = abs_show(c1, x0[0], 0, "shadow-cpa-k1", size=(W_FULL, H_FULL))
    rep.append("- Fig. 7 RK1_1 candidate pair {0x%02X, 0x%02X}, peak |rho| %.3f" % (k1, k1 ^ 0xFF, pk1))

    # ---- h2 built with p and h2* built with p ^ 0xFF, Fig. 8(a,b): the decision on D
    c2  = cpa_on_target(G128, T[0], F(h0 ^ p) ^ L0)
    c2b = cpa_on_target(G128, T[0], F(h0 ^ p ^ 0xFF) ^ L0)
    _, p2 = abs_show(c2, x0[0], 0, "shadow-cpa-k2")
    _, p2b = abs_show(c2b, x0[0], 0, "shadow-cpa-k2-bar")
    D = p2 - p2b
    alpha = 1.0 if D >= 0 else -1.0
    RK1 = [p if D >= 0 else p ^ 0xFF, None, None, None]
    rep.append("- Fig. 8(a,b) decision: max|rho| h2 (built with 0x%02X) = %.3f, h2* (built with 0x%02X) = %.3f, "
               "D = %+.3f -> RK1_0 = 0x%02X, alpha = %+d" % (p, p2, p ^ 0xFF, p2b, D, RK1[0], int(alpha)))

    # every complement pair is now resolved by the alpha-signed peak
    def pick(c):
        s = signed_peak_per_key(c); i = int(np.argmax(np.abs(s)))
        return i if alpha * s[i] > 0 else (i ^ 0xFF)
    RK1[1] = pick(c1)
    RK1[2] = pick(c2 if D >= 0 else c2b)

    # ---- h3 built with RK1_1 and h3* built with its complement, Fig. 8(c,d)
    c3  = cpa_on_target(G128, T[0], F(h1 ^ RK1[1]) ^ R0)
    c3b = cpa_on_target(G128, T[0], F(h1 ^ RK1[1] ^ 0xFF) ^ R0)
    _, p3 = abs_show(c3, x0[0], 0, "shadow-cpa-k3")
    _, p3b = abs_show(c3b, x0[0], 0, "shadow-cpa-k3-bar")
    RK1[3] = pick(c3)
    rep.append("- Fig. 8(c,d): max|rho| h3 (built with RK1_1 = 0x%02X) = %.3f, h3* = %.3f" % (RK1[1], p3, p3b))
    rep.append("- Round 1 recovered: RK1_0 0x%02X, RK1_1 0x%02X, RK1_2 0x%02X, RK1_3 0x%02X" % tuple(RK1))
    stages += [("RK1_0 (h0)", "byte, pair {0x%02X, 0x%02X} resolved by D" % (g0, g0 ^ 0xFF), 128, "0x%02X" % RK1[0], abs(sp0[g0]), "Fig. 6"),
               ("RK1_1 (h1)", "byte, pair {0x%02X, 0x%02X} resolved by the sign" % (k1, k1 ^ 0xFF), 128, "0x%02X" % RK1[1], pk1, "Fig. 7"),
               ("RK1_2 (h2, RK1_0 = 0x%02X assumed)" % p, "byte", 128,
                ("0x%02X" % RK1[2]) if D >= 0 else "rejected by D", p2, "Fig. 8(a)"),
               ("RK1_2 (h2*, RK1_0 = 0x%02X assumed)" % (p ^ 0xFF), "byte", 128,
                ("0x%02X" % RK1[2]) if D < 0 else "rejected by D", p2b, "Fig. 8(b)"),
               ("RK1_3 (h3, RK1_1 = 0x%02X)" % RK1[1], "byte", 128, "0x%02X" % RK1[3], p3, "Fig. 8(c)")]

    # ---- Round 2 (Fig. 9): the four 4-bit CPAs of Algorithm 1
    s0 = F(L0) ^ L1 ^ RK1[0]; s1 = F(R0) ^ R1 ^ RK1[1]
    l0, l1, r0, r1 = s1, F(s0) ^ L0 ^ RK1[2], s0, F(s1) ^ R0 ^ RK1[3]
    RK2 = [None, RK1[2], None, None]                                   # RK2_1 = RK1_2
    # (a) upper nibble of RK2_0, lower nibble = upper nibble of RK1_3
    lo = RK1[3] >> 4
    cands = [(hi << 4) | lo for hi in range(16)]
    RK2[0], q = abs_show(cpa_on_target(cands, T[1], F(l0) ^ l1), x0[1], 0, "shadow-cpa-r2-k0-hi", labels=cands)
    stages.append(("RK2_0", "upper nibble (lower = 0x%X from RK1_3)" % lo, 16, "0x%02X" % RK2[0], q, "Fig. 9(a)"))
    t0 = F(l0) ^ l1 ^ RK2[0]; t1 = F(r0) ^ r1 ^ RK2[1]
    h22 = F(t0) ^ l0
    # (b) lower nibble of RK2_2, upper nibble unmodeled: HW of the lower nibble only
    lo2, q = abs_show(cpa_on_target(range(16), T[1], h22, mask=0x0F), x0[1], 0, "shadow-cpa-r2-k2-lo", fmt="0x?%X")
    stages.append(("RK2_2", "lower nibble (upper unmodeled)", 16, "0x?%X" % lo2, q, "Fig. 9(b)"))
    # (c) upper nibble of RK2_2 with the lower nibble fixed, full-byte HW
    cands = [(hi << 4) | lo2 for hi in range(16)]
    RK2[2], q = abs_show(cpa_on_target(cands, T[1], h22), x0[1], 0, "shadow-cpa-r2-k2-hi", labels=cands)
    stages.append(("RK2_2", "upper nibble (lower = 0x%X from the previous CPA)" % lo2, 16, "0x%02X" % RK2[2], q, "Fig. 9(c)"))
    # (d) lower nibble of RK2_3, upper nibble = lower nibble of RK1_3
    hi = RK1[3] & 0xF
    cands = [(hi << 4) | lo_ for lo_ in range(16)]
    RK2[3], q = abs_show(cpa_on_target(cands, T[1], F(t1) ^ r0), x0[1], 0, "shadow-cpa-r2-k3-lo", labels=cands)
    stages.append(("RK2_3", "lower nibble (upper = 0x%X from RK1_3)" % hi, 16, "0x%02X" % RK2[3], q, "Fig. 9(d)"))
    # check only: 7-bit CPA on RK2_1, which the key schedule already fixes (no figure)
    cc = cpa_on_target(G128, T[1], F(r0) ^ r1)
    vchk = pick(cc); qchk = float(np.abs(cc).max())
    print("RK2_1 check (7-bit CPA, not part of the attack): 0x%02X, |rho| %.3f; key schedule gives 0x%02X"
          % (vchk, qchk, RK2[1]))
    rep.append("- Fig. 9: Round-2 4-bit CPAs give RK2_0 0x%02X, RK2_2 lower nibble 0x?%X then 0x%02X, RK2_3 0x%02X; "
               "RK2_1 = RK1_2 = 0x%02X from the key schedule" % (RK2[0], lo2, RK2[2], RK2[3], RK2[1]))
    rep.append("- RK2_1 check (7-bit CPA, not counted): 0x%02X, |rho| %.3f, %s the key-schedule value"
               % (vchk, qchk, "equals" if vchk == RK2[1] else "DIFFERS from"))

    # ---- Rounds 3 and 4 (Fig. 10): 4-bit CPAs, the other nibble from the key schedule
    l0, l1, r0, r1 = t1, F(t0) ^ l0 ^ RK2[2], t0, F(t1) ^ r0 ^ RK2[3]
    nxo = nx8(((RK1[0] & 0xF) << 4) | (RK1[1] & 0xF))
    RK3 = [(((nxo >> 4) & 0xF) << 4) | ((RK2[3] >> 4) & 0xF), RK2[2], None, None]
    u0 = F(l0) ^ l1 ^ RK3[0]; u1 = F(r0) ^ r1 ^ RK3[1]
    cands = [((nxo & 0xF) << 4) | lo_ for lo_ in range(16)]
    RK3[2], q = abs_show(cpa_on_target(cands, T[2], F(u0) ^ l0), x0[2], 0, "shadow-cpa-r3-k2", labels=cands)
    stages.append(("RK3_2", "lower nibble (upper = 0x%X from NX)" % (nxo & 0xF), 16, "0x%02X" % RK3[2], q, "Fig. 10(a)"))
    cands = [((RK2[3] & 0xF) << 4) | lo_ for lo_ in range(16)]
    RK3[3], q = abs_show(cpa_on_target(cands, T[2], F(u1) ^ r0), x0[2], 0, "shadow-cpa-r3-k3", labels=cands)
    stages.append(("RK3_3", "lower nibble (upper = 0x%X from RK2_3)" % (RK2[3] & 0xF), 16, "0x%02X" % RK3[3], q, "Fig. 10(b)"))
    l0, l1, r0, r1 = u1, F(u0) ^ l0 ^ RK3[2], u0, F(u1) ^ r0 ^ RK3[3]
    nxo4 = nx8(((RK2[0] & 0xF) << 4) | (RK2[1] & 0xF))
    RK4 = [(((nxo4 >> 4) & 0xF) << 4) | ((RK3[3] >> 4) & 0xF), RK3[2], None, None]
    v0 = F(l0) ^ l1 ^ RK4[0]; v1 = F(r0) ^ r1 ^ RK4[1]
    cands = [((nxo4 & 0xF) << 4) | lo_ for lo_ in range(16)]
    RK4[2], q = abs_show(cpa_on_target(cands, T[3], F(v0) ^ l0), x0[3], 0, "shadow-cpa-r4-k2", labels=cands)
    stages.append(("RK4_2", "lower nibble (upper = 0x%X from NX)" % (nxo4 & 0xF), 16, "0x%02X" % RK4[2], q, "Fig. 10(c)"))
    cands = [((RK3[3] & 0xF) << 4) | lo_ for lo_ in range(16)]
    RK4[3], q = abs_show(cpa_on_target(cands, T[3], F(v1) ^ r0), x0[3], 0, "shadow-cpa-r4-k3", labels=cands)
    stages.append(("RK4_3", "lower nibble (upper = 0x%X from RK3_3)" % (RK3[3] & 0xF), 16, "0x%02X" % RK4[3], q, "Fig. 10(d)"))

    rec = RK1 + RK2 + RK3 + RK4
    rep += ["", "## The 13 CPAs of Algorithm 1 on this set\n",
            "| CPA | Target | Candidates | Result | max \\|rho\\| | Figure |", "|---|---|---:|---|---:|---|"]
    for s in stages:
        rep.append("| %s | %s | %d | %s | %.3f | %s |" % s)
    rep += ["", "Derived from the key schedule: RK2_1 = RK1_2 = 0x%02X; RK3_0 = 0x%02X, RK3_1 = RK2_2 = 0x%02X; "
            "RK4_0 = 0x%02X, RK4_1 = RK3_2 = 0x%02X." % (RK2[1], RK3[0], RK3[1], RK4[0], RK4[1])]
    rep.append("\nRecovered RK1..RK4 : `%s`" % " ".join("%02X" % x for x in rec))
    rep.append("Reference RK1..RK4 : `%s`" % " ".join("%02X" % x for x in RK))
    rep.append("Match : **%d/16**" % sum(a == b for a, b in zip(rec, RK)))
    open(os.path.join(OUT, "RESULTS_fixedkey_cpa.md"), "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
