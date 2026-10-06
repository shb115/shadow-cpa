# -*- coding: utf-8 -*-
"""
Shadow-32 success rate, guessing entropy and sign decision against the number of traces
(Fig. 13 and Section 4.6 of the paper), for the 13 CPAs of Algorithm 1.

Events evaluated on every subset of traces (each CPA with the true values of the earlier
stages, ranked in its own candidate set):
  Round 1, 128 representatives each, the 256 values they score ranked with alpha = +1:
      h0 -> RK1_0,  h1 -> RK1_1,  h2 (built with the true RK1_0) -> RK1_2,
      h3 (built with the true RK1_1) -> RK1_3
  the decision on D: the pair from the subset's own h0 CPA, h2 built with its positive-peak
      member p and h2* with p ^ 0xFF; correct when it returns the true RK1_0 with alpha = +1
  eight 4-bit CPAs, 16 candidates each:
      RK2_0 upper nibble (lower = upper nibble of RK1_3), RK2_2 lower nibble (HW of the lower
      nibble only, upper nibble unmodeled), RK2_2 upper nibble (lower nibble fixed, full-byte
      HW), RK2_3 lower nibble (upper = lower nibble of RK1_3), RK3_2, RK3_3, RK4_2 and RK4_3
      lower nibbles (upper nibbles from the key schedule)
Joint event 'all 16 bytes' = the decision on D is correct and the other twelve CPAs rank the
correct candidate first on the same subset.  Since every stage is evaluated with the true
earlier values, this is exactly the event that the chain of Algorithm 1 returns all 16 bytes.

Point of interest (PoI)
  key-independent : a Round-r CPA runs over the samples of Round r, [b0 + (r-1)P, b0 + rP),
                    with the period P and the boundary b0 taken from each set's mean trace
                    alone (round_structure.py).  This is the attack.
  key-dependent   : the rule of the previous version, kept only for comparison.  The PoI is
                    the argmax |rho| of the correct hypothesis column over all 2,048 traces,
                    and an interval of 80 samples around it is used.

Scoring: score(candidate) = max over the PoI samples of alpha * rho(t) (alpha = +1, the true
sign); rank = position of the correct candidate in the descending order.  Both PoI rules are
evaluated on exactly the same disjoint contiguous subsets: for a trace count N every key set
contributes min(2048/N, 20) subsets, so ten key sets give 200 attacks per point up to N = 96.

Usage :  python success_rate.py          (about ten minutes)
Output:  results/RESULTS_success_rate.md, results/_success_rate.npz
         figures/shadow32_10keys/fig13a_success_rate.pdf/.png
         figures/shadow32_10keys/fig13b_guessing_entropy.pdf/.png
         figures/shadow32_10keys/fig13c_sign_decision.pdf/.png
"""
import os, sys, glob, time
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from round_structure import round_structure, round_interval
from shadow32_ks import nx8

DATA = os.path.join(HERE, "..", "data", "shadow32_10keys")
OUT  = os.path.join(HERE, "..", "results")
FIG  = os.path.join(HERE, "..", "figures", "shadow32_10keys")
os.makedirs(OUT, exist_ok=True); os.makedirs(FIG, exist_ok=True)

HALF   = 40                 # key-dependent rule: +-40 samples around the correct-key argmax
NLIST  = [8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 48, 64, 96, 128, 192, 256, 512, 1024, 2048]
MAXREP = 20
RULES  = ["independent", "dependent"]

EV = ["RK1_0 (h0)", "RK1_1 (h1)", "RK1_2 (h2)", "RK1_3 (h3)",
      "RK2_0 upper", "RK2_2 lower (nibble HW)", "RK2_2 upper given lower", "RK2_3 lower",
      "RK3_2 lower", "RK3_3 lower", "RK4_2 lower", "RK4_3 lower"]
NEV = len(EV)

_PC  = np.array([bin(i).count('1') for i in range(256)], np.float64)
G128 = np.arange(128, dtype=np.int64)
G16  = np.arange(16, dtype=np.int64)

def rol(v, r): return ((v << r) ^ (v >> (8 - r))) & 0xFF
def F(x):      return (rol(x, 1) & rol(x, 7)) ^ rol(x, 2)


def corr(H, W):
    """Pearson correlation of every column of H (hypotheses, N x K) with every column of W
    (samples, N x S), as a (K, S) array.  Both variance terms are guarded so that a constant
    column gives 0 rather than nan."""
    Wn = W - W.mean(0); Wq = (Wn ** 2).sum(0)
    Hn = H - H.mean(0)
    return (Hn.T @ Wn) / np.sqrt(np.outer(np.maximum((Hn ** 2).sum(0), 1e-30),
                                          np.maximum(Wq, 1e-30)))


def hyp_byte(h, cands):
    """Full-byte Hamming weight of h ^ cand, (N, K)."""
    return _PC[(h[:, None] ^ np.asarray(cands, dtype=np.int64)[None, :]) & 0xFF]


def hyp_lo_nibble(h):
    """HW of the lower nibble only of h ^ lo, lo = 0..15 (upper nibble unmodeled), (N, 16)."""
    return _PC[(h[:, None] ^ G16[None, :]) & 0x0F]


def rank_of(score, idx):
    """1-based position of candidate idx in the descending order of score (stable)."""
    order = np.argsort(-score, kind="stable")
    return int(np.where(order == idx)[0][0]) + 1


def rstate(l0, l1, r0, r1, k):
    s0 = F(l0) ^ l1 ^ k[0]; s1 = F(r0) ^ r1 ^ k[1]
    return s1, F(s0) ^ l0 ^ k[2], s0, F(s1) ^ r0 ^ k[3]


def check_schedule(rk):
    """The key-schedule relations Algorithm 1 relies on, on the reference rk[:16]."""
    nxo3 = nx8(((rk[0] & 0xF) << 4) | (rk[1] & 0xF))
    nxo4 = nx8(((rk[4] & 0xF) << 4) | (rk[5] & 0xF))
    return all([rk[5] == rk[2], (rk[4] & 0xF) == (rk[3] >> 4), (rk[7] >> 4) == (rk[3] & 0xF),
                (rk[8] >> 4) == (nxo3 >> 4), (rk[8] & 0xF) == (rk[7] >> 4), rk[9] == rk[6],
                (rk[10] >> 4) == (nxo3 & 0xF), (rk[11] >> 4) == (rk[7] & 0xF),
                (rk[12] >> 4) == (nxo4 >> 4), (rk[12] & 0xF) == (rk[11] >> 4), rk[13] == rk[10],
                (rk[14] >> 4) == (nxo4 & 0xF), (rk[15] >> 4) == (rk[11] & 0xF)])


def events_of(pt, rk):
    """Hypothesis matrix H (N x K), index `ok` of the correct candidate, round and kind of
    each of the 12 ranking events, from the true keys."""
    L0, L1, R0, R1 = (pt[:, i].astype(np.int64) for i in range(4))
    h0 = F(L0) ^ L1; h1 = F(R0) ^ R1
    ev = [dict(H=hyp_byte(h0, G128), ok=rk[0], rnd=1, r1=True),
          dict(H=hyp_byte(h1, G128), ok=rk[1], rnd=1, r1=True),
          dict(H=hyp_byte(F(h0 ^ rk[0]) ^ L0, G128), ok=rk[2], rnd=1, r1=True),
          dict(H=hyp_byte(F(h1 ^ rk[1]) ^ R0, G128), ok=rk[3], rnd=1, r1=True)]
    l0, l1, r0, r1 = rstate(L0, L1, R0, R1, rk[0:4])
    h20 = F(l0) ^ l1
    ev.append(dict(H=hyp_byte(h20, [(hi << 4) | (rk[3] >> 4) for hi in range(16)]), ok=rk[4] >> 4, rnd=2, r1=False))
    s0 = h20 ^ rk[4]; s1 = F(r0) ^ r1 ^ rk[5]
    h22 = F(s0) ^ l0; h23 = F(s1) ^ r0
    ev.append(dict(H=hyp_lo_nibble(h22), ok=rk[6] & 0xF, rnd=2, r1=False))
    ev.append(dict(H=hyp_byte(h22, [(hi << 4) | (rk[6] & 0xF) for hi in range(16)]), ok=rk[6] >> 4, rnd=2, r1=False))
    ev.append(dict(H=hyp_byte(h23, [((rk[3] & 0xF) << 4) | lo for lo in range(16)]), ok=rk[7] & 0xF, rnd=2, r1=False))
    st = (l0, l1, r0, r1)
    for rnd in (3, 4):
        st = rstate(*st, rk[4 * (rnd - 2):4 * (rnd - 2) + 4])
        l0, l1, r0, r1 = st
        base = 4 * (rnd - 1)
        s0 = F(l0) ^ l1 ^ rk[base]; s1 = F(r0) ^ r1 ^ rk[base + 1]
        ev.append(dict(H=hyp_byte(F(s0) ^ l0, [((rk[base + 2] >> 4) << 4) | lo for lo in range(16)]),
                       ok=rk[base + 2] & 0xF, rnd=rnd, r1=False))
        ev.append(dict(H=hyp_byte(F(s1) ^ r0, [((rk[base + 3] >> 4) << 4) | lo for lo in range(16)]),
                       ok=rk[base + 3] & 0xF, rnd=rnd, r1=False))
    assert len(ev) == NEV
    return ev, h0, L0


def dependent_poi(tr, col):
    """Previous rule, for comparison only: argmax |rho| of the correct hypothesis column over
    all traces and all samples."""
    c = corr(col[:, None], tr)[0]
    return int(np.argmax(np.abs(c)))


def r1_ranks(C, ok):
    """Rank of the value ok among the 256 alpha-signed scores of the 128 representative
    curves (alpha = +1), and rank of its representative among the 128 by |peak|.  The curve
    of g ^ 0xFF is minus the curve of g, so value 255 - g scores max(-C_g)."""
    s256 = np.concatenate([C.max(1), (-C).max(1)[::-1]])
    g = ok if ok < 128 else ok ^ 0xFF
    return rank_of(s256, ok), rank_of(np.abs(C).max(1), g)


def decide(C0, h0, L0, W2, sl):
    """The decision on D on one subset.  C0: h0 CPA of the subset (128 x S); h2 and h2* are
    correlated over W2, the samples used for the h2 CPA under the current PoI rule.
    Returns (representative of the pair, chosen RK1_0, estimated sign of alpha, D)."""
    absmax = np.abs(C0).max(1)
    g = int(np.argmax(absmax))
    sp = C0[g, int(np.argmax(np.abs(C0[g])))]
    p = g if sp > 0 else (g ^ 0xFF)
    P2 = float(np.abs(corr(hyp_byte(F(h0[sl] ^ p) ^ L0[sl], G128), W2)).max())
    P2s = float(np.abs(corr(hyp_byte(F(h0[sl] ^ p ^ 0xFF) ^ L0[sl], G128), W2)).max())
    D = P2 - P2s
    return g, (p if D >= 0 else (p ^ 0xFF)), (1 if D >= 0 else -1), D


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def first_n(cond):
    """First N of NLIST from which cond (bool per N) stays True to the end, else None."""
    for j in range(len(NLIST)):
        if cond[j:].all():
            return NLIST[j]
    return None


def main():
    t0 = time.time()
    files = sorted(glob.glob(os.path.join(DATA, "*.npz")))
    assert files, "no traces under " + DATA
    R    = {r: [[] for _ in NLIST] for r in RULES}     # ranks (subsets x NEV) per set
    R128 = {r: [[] for _ in NLIST] for r in RULES}     # Round-1 ranks among the 128 representatives
    DEC  = {r: [[] for _ in NLIST] for r in RULES}     # pair ok, chosen ok, alpha ok, |D|
    info = []
    for f in files:
        d = np.load(f); tr = d["traces"].astype(np.float64); pt = d["pt"]
        rk = [int(x) for x in d["rk"][:16]]
        assert check_schedule(rk), "key-schedule relation fails on " + f
        P, b0 = round_structure(tr)
        info.append((os.path.basename(f), P, b0))
        ev, h0, L0 = events_of(pt, rk)
        win = {}
        for i, e in enumerate(ev):
            win[("independent", i)] = round_interval(e["rnd"], P, b0, tr.shape[1])
            col = e["H"][:, e["ok"] if not e["r1"] else (e["ok"] if e["ok"] < 128 else e["ok"] ^ 0xFF)]
            p = dependent_poi(tr, col)
            win[("dependent", i)] = (max(0, p - HALF), min(tr.shape[1], p + HALF))
        for rule in RULES:
            for ni, n in enumerate(NLIST):
                nsub = min(tr.shape[0] // n, MAXREP)
                rk_arr = np.zeros((nsub, NEV), int); r128 = np.zeros((nsub, 4), int); dec = np.zeros((nsub, 4))
                for t in range(nsub):
                    sl = slice(t * n, (t + 1) * n)
                    for i, e in enumerate(ev):
                        a, b = win[(rule, i)]
                        C = corr(e["H"][sl], tr[sl, a:b])
                        if e["r1"]:
                            rk_arr[t, i], r128[t, i] = r1_ranks(C, e["ok"])
                            if i == 0:
                                C0 = C
                        else:
                            rk_arr[t, i] = rank_of(C.max(1), e["ok"])
                    a2, b2 = win[(rule, 2)]
                    g, chosen, alpha_est, D = decide(C0, h0, L0, tr[sl, a2:b2], sl)
                    dec[t] = (int(rk[0] in (g, g ^ 0xFF)), int(chosen == rk[0]), int(alpha_est == 1), abs(D))
                R[rule][ni].append(rk_arr); R128[rule][ni].append(r128); DEC[rule][ni].append(dec)
        print("  %s  P=%d b0=%d  (%.0f s)" % (os.path.basename(f), P, b0, time.time() - t0), flush=True)

    # ---------------------------------------------------------------- aggregate
    agg = {}
    for rule in RULES:
        A = [np.vstack(R[rule][ni]) for ni in range(len(NLIST))]
        A128 = [np.vstack(R128[rule][ni]) for ni in range(len(NLIST))]
        Dd = [np.vstack(DEC[rule][ni]) for ni in range(len(NLIST))]
        ok = [((x == 1).all(1) & (d[:, 1] == 1) & (d[:, 2] == 1)) for x, d in zip(A, Dd)]
        agg[rule] = dict(NTRIAL=np.array([len(x) for x in A]),
                         SR=np.array([(x == 1).mean(0) for x in A]),
                         GE=np.array([x.mean(0) for x in A]),
                         GE128=np.array([x.mean(0) for x in A128]),
                         pair=np.array([d[:, 0].mean() for d in Dd]),
                         chosen=np.array([d[:, 1].mean() for d in Dd]),
                         dec_ok=np.array([(d[:, 1] * d[:, 2]).mean() for d in Dd]),
                         meanD=np.array([d[:, 3].mean() for d in Dd]),
                         SRfull=np.array([o.mean() for o in ok]),
                         CI=np.array([wilson(int(o.sum()), len(o)) for o in ok]))
    gi, gd = agg["independent"], agg["dependent"]
    pair, sign, mD = gi["pair"], gi["chosen"], gi["meanD"]
    np.savez_compressed(os.path.join(OUT, "_success_rate.npz"), NLIST=np.array(NLIST), EV=np.array(EV),
                        pair=pair, sign=sign, meanD=mD,
                        **{"%s_%s" % (r, k): v for r in RULES for k, v in agg[r].items()})

    def fmt(v):
        return "none" if v is None else str(v)

    L = ["# Shadow-32 success rate, guessing entropy and sign decision: the 13 CPAs of Algorithm 1\n",
         "Traces: `data/shadow32_10keys/`, ten key sets of 2,048 traces. Attacks per point: %s.\n"
         % ", ".join("%d@%d" % (t, n) for n, t in zip(NLIST, gi["NTRIAL"])),
         "Round structure per set (period, boundary): %s\n"
         % ", ".join("%s %d/%d" % (nm[4:9], P, b0) for nm, P, b0 in info),
         "Scoring: score(candidate) = max over the PoI samples of alpha * rho(t), alpha = +1 (the true sign); "
         "rank = position of the correct candidate in the descending order. Round-1 CPAs enumerate the 128 "
         "representatives; the rank is among the 256 values their curves score (GE_256) and, in addition, among "
         "the 128 representatives by |peak| (GE_128). Nibble CPAs rank 16 candidates. Every CPA is evaluated with "
         "the true values of the earlier stages. The decision on D takes the pair from the subset's own h0 CPA, "
         "builds h2 with the positive-peak member p and h2* with p xor 0xFF, and is correct when it returns the "
         "true RK1_0 with alpha = +1. The joint event 'all 16 bytes' is that the decision is correct and the other "
         "twelve CPAs rank the correct candidate first on the same subset.\n",
         "Trace counts below are the first N of NLIST from which the quantity stays at the stated level for every "
         "larger N.\n",
         "## Trace counts\n", "| claim | key-independent PoI | key-dependent PoI |", "|---|---:|---:|"]
    rows = [("each Round-1 subkey reaches SR 1.0", lambda g: first_n((g["SR"][:, :4] == 1.0).all(1)))]
    for i in range(4):
        rows.append(("  %s reaches SR 1.0" % EV[i], lambda g, i=i: first_n(g["SR"][:, i] == 1.0)))
    rows.append(("each of the eight 4-bit CPAs reaches SR 1.0", lambda g: first_n((g["SR"][:, 4:12] == 1.0).all(1))))
    for i in range(4, 12):
        rows.append(("  %s reaches SR 1.0" % EV[i], lambda g, i=i: first_n(g["SR"][:, i] == 1.0)))
    rows += [("all 16 bytes (the 13 CPAs of Algorithm 1) reach SR 1.0", lambda g: first_n(g["SRfull"] == 1.0)),
             ("decision on D correct with alpha = +1 on every attack", lambda g: first_n(g["dec_ok"] == 1.0)),
             ("guessing entropy (256-value) of the Round-1 subkeys below 1.1", lambda g: first_n(g["GE"][:, :4].max(1) < 1.1)),
             ("guessing entropy (256-value) of the Round-1 subkeys equal to 1", lambda g: first_n(g["GE"][:, :4].max(1) == 1.0)),
             ("guessing entropy (128-representative) of the Round-1 subkeys below 1.1", lambda g: first_n(g["GE128"].max(1) < 1.1)),
             ("guessing entropy (128-representative) of the Round-1 subkeys equal to 1", lambda g: first_n(g["GE128"].max(1) == 1.0))]
    for lbl, fn in rows:
        L.append("| %s | %s | %s |" % (lbl, fmt(fn(gi)), fmt(fn(gd))))
    for rule, g in (("key-independent", gi), ("key-dependent", gd)):
        L += ["", "## Success rate per CPA, %s PoI\n" % rule,
              "| traces | attacks | " + " | ".join(EV) + " | decision on D | all 16 bytes | Wilson 95% |",
              "|---:|---:|" + "---:|" * NEV + "---:|---:|---|"]
        for j, n in enumerate(NLIST):
            L.append("| %d | %d | %s | %.3f | %.3f | [%.3f, %.3f] |" % (
                n, g["NTRIAL"][j], " | ".join("%.3f" % v for v in g["SR"][j]), g["dec_ok"][j],
                g["SRfull"][j], g["CI"][j][0], g["CI"][j][1]))
    L += ["", "## Guessing entropy of the Round-1 subkeys\n",
          "| traces | attacks | " + " | ".join("%s GE_256 indep" % EV[i] for i in range(4)) + " | " +
          " | ".join("%s GE_128 indep" % EV[i] for i in range(4)) + " | " +
          " | ".join("%s GE_256 dep" % EV[i] for i in range(4)) + " |",
          "|---:|---:|" + "---:|" * 12]
    for j, n in enumerate(NLIST):
        L.append("| %d | %d | %s | %s | %s |" % (
            n, gi["NTRIAL"][j], " | ".join("%.3f" % v for v in gi["GE"][j, :4]),
            " | ".join("%.3f" % v for v in gi["GE128"][j]), " | ".join("%.3f" % v for v in gd["GE"][j, :4])))
    L += ["", "## Guessing entropy of the eight 4-bit CPAs (mean rank among 16), key-independent PoI\n",
          "| traces | " + " | ".join(EV[4:12]) + " |", "|---:|" + "---:|" * 8]
    for j, n in enumerate(NLIST):
        L.append("| %d | %s |" % (n, " | ".join("%.3f" % v for v in gi["GE"][j, 4:12])))
    L += ["", "## Sign decision (Section 4.3), over the Round-1 samples\n",
          "| traces | attacks | pair correct | decision correct | mean \\|D\\| |", "|---:|---:|---:|---:|---:|"]
    for j, n in enumerate(NLIST):
        L.append("| %d | %d | %.3f | %.3f | %.4f |" % (n, gi["NTRIAL"][j], pair[j], sign[j], mD[j]))
    L.append("\n- decision correct on every attack from **%s** traces upward" % fmt(first_n(sign == 1.0)))
    L.append("- at 2,048 traces: correct on %d/%d sets, mean |D| = %.4f" % (
        int(round(sign[-1] * gi["NTRIAL"][-1])), gi["NTRIAL"][-1], mD[-1]))
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "RESULTS_success_rate.md"), "w", encoding="utf-8").write(txt)
    print(txt)
    figures(agg, pair, sign, mD)
    print("done, %.0f s" % (time.time() - t0))


def figures(agg, pair, sign, mD):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FONT = 7
    plt.rcParams.update({
        "font.size": FONT, "axes.labelsize": FONT, "axes.titlesize": FONT,
        "xtick.labelsize": FONT - 1, "ytick.labelsize": FONT - 1,
        "legend.fontsize": FONT - 1, "lines.linewidth": 1.1, "lines.markersize": 3.0,
        "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "grid.linewidth": 0.4, "legend.frameon": True, "legend.framealpha": 0.9,
        "figure.constrained_layout.use": True,
        "figure.constrained_layout.h_pad": 0.01, "figure.constrained_layout.w_pad": 0.01,
        "pdf.fonttype": 42, "ps.fonttype": 42})
    WH = (3.46, 2.70)
    N = np.array(NLIST)
    LBL = [r"$RK^1_0$", r"$RK^1_1$", r"$RK^1_2$", r"$RK^1_3$"]
    COL = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    gi, gd = agg["independent"], agg["dependent"]

    def save(fig, name):
        fig.savefig(os.path.join(FIG, name + ".pdf"))
        fig.savefig(os.path.join(FIG, name + ".png"), dpi=600)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=WH)
    for j in range(4):
        ax.plot(N, gi["SR"][:, j], marker='o', color=COL[j], label=LBL[j])
    ax.plot(N, gi["SRfull"], marker='s', color='k', label='all 16 bytes')
    ax.plot(N, gd["SRfull"], marker='^', color='0.45', ls='--', label='all 16 bytes, key-dependent PoI')
    ax.fill_between(N, gi["CI"][:, 0], gi["CI"][:, 1], color='k', alpha=0.12, lw=0)
    ax.set_xscale('log'); ax.set_ylim([-0.03, 1.03]); ax.grid(True, alpha=0.4)
    ax.set_xlabel('Number of traces'); ax.set_ylabel('Success rate')
    ax.legend(loc='lower right', handlelength=1.5, borderpad=0.3, labelspacing=0.22)
    save(fig, "fig13a_success_rate")

    fig, ax = plt.subplots(figsize=WH)
    for j in range(4):
        ax.plot(N, gi["GE"][:, j], marker='o', color=COL[j], label=LBL[j])
        ax.plot(N, gd["GE"][:, j], color=COL[j], ls=':', lw=0.9)
    ax.plot([], [], color='0.3', ls='-', label='key-independent PoI')
    ax.plot([], [], color='0.3', ls=':', label='key-dependent PoI')
    ax.set_xscale('log'); ax.set_yscale('log'); ax.grid(True, alpha=0.4, which='both')
    ax.set_xlabel('Number of traces'); ax.set_ylabel('Guessing entropy')
    ax.legend(loc='upper right', handlelength=1.5, borderpad=0.3, labelspacing=0.22)
    save(fig, "fig13b_guessing_entropy")

    fig, ax = plt.subplots(figsize=WH)
    ax.plot(N, pair, marker='^', color='0.45', ls='--', label=r'$RK^1_0$ complement pair correct')
    ax.plot(N, sign, marker='o', color='#1f77b4', label='sign decision correct')
    ax.set_xscale('log'); ax.set_ylim([-0.03, 1.03]); ax.grid(True, alpha=0.4)
    ax.set_xlabel('Number of traces'); ax.set_ylabel('Success rate')
    ax2 = ax.twinx()
    ax2.plot(N, mD, marker='s', color='#d62728', ls='-.', ms=2.4, label=r'mean $|D|$')
    ax2.set_ylabel(r'mean $|D|$', color='#d62728'); ax2.tick_params(axis='y', colors='#d62728')
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc='lower right', handlelength=1.5, borderpad=0.3, labelspacing=0.22)
    save(fig, "fig13c_sign_decision")


if __name__ == "__main__":
    main()
