# -*- coding: utf-8 -*-
"""
Routines shared by the scripts that read the masked trace sets
(masked_eval.py, full_encryption.py, fig_tvla.py).

The masked files hold float16 arrays of 16,384 x 10,000 or 16,384 x 46,000 samples, up to
1.5 GB once decompressed.  Every statistic below is computed in column chunks that are
converted to float64 one chunk at a time, so that no script needs more than about 3 GB of
memory.  The `traces` array of a file is read exactly once; indexing the NpzFile key again
would decompress the whole array again.

Conventions, as in Section 4.7 of the paper:

  Welch t       t = mean(fixed group) - mean(random group), ddof = 1; threshold |t| > 4.5.
  second order  each group is centered by its own per-sample mean and squared, then the same
                Welch t is computed on the squares.
  ADC rail      a sample is at the positive rail when v >= 0.4959 (the largest code of the
                ADC is 127/256 = 0.4961; the code step is 1/256).
  round end     the sample at which the idle NOP loop that follows the masked round begins.
                With m the mean trace over all traces of the set and
                r[t] = mean over u = t .. t+13 of |m[u] - m[u+14]| (14 cycles is the period of
                the NOP loop), the round end is the last t with r[t] > 0.02, plus 14; from
                there to the end of the trace m repeats with period 14.
  table builds  (table-recomputation implementation) the 256-entry table is built at 41
                cycles per entry, so the mean trace is 41-periodic during a build.  With
                r41[t] = mean over u = t .. t+40 of |m[u] - m[u+41]|, a build is a run of at
                least 5,000 consecutive t with r41[t] < 0.05; a run over [i, j) of r41 is
                reported as the build [i, j+41).  Every exceeding sample of the t-test is
                located by the number of builds completed before it and its distance from
                the end of the last of them.
  CPA           7-bit CPA over the 128 representatives k = 0..127 with the hypothesis
                HW(h xor k), Pearson correlation at every sample; the second-order CPA uses
                the centered squared samples, centered again.  The rank of the correct
                candidate is its position among the 128 representatives ordered by the
                maximum of |rho| over the round.
"""
import os
import numpy as np

TH = 4.5                     # t-test threshold
CLIP = 0.4959                # ADC positive rail, as in capture_exp.save() and trace_stats.py
CODE = 1.0 / 256.0           # ADC code step
NOP_PERIOD = 14              # cycles per iteration of the idle loop after the round
TABLE_PERIOD = 41            # cycles per entry of the table build
RK_TRUE = [0x0D, 0x3B, 0x60, 0x33]     # Round-1 key of every masked set

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "masked")
OUT = os.path.join(HERE, "..", "results")

SETS = {                      # tag -> (file, implementation, one-round capture?)
    "ISW_seed1":    ("masking_ISW_v2_seed1_16384x10000.npz", "ISW", True),
    "ISW_seed2":    ("masking_ISW_v2_seed2_16384x10000.npz", "ISW", True),
    "ISWLUT_seed1": ("masking_ISWLUT_v2_seed1_16384x46000.npz", "ISWLUT", True),
    "ISWLUT_seed2": ("masking_ISWLUT_v2_seed2_16384x46000.npz", "ISWLUT", True),
    "ISW_full":     ("masking_ISW_v2_full_seed1_16384x46000.npz", "ISW", False),
    "ISWLUT_full":  ("masking_ISWLUT_v2_full_seed1_16384x46000.npz", "ISWLUT", False),
}
IMPL_NAME = {"ISW": "ISW", "ISWLUT": "table recomputation"}


# ----------------------------------------------------------------------------- loading
def load_set(tag):
    """Return (traces float16 (N, S), pt, group, meta dict).  `traces` is read once."""
    d = np.load(os.path.join(DATA, SETS[tag][0]))
    meta = {k: (d[k].tolist() if d[k].ndim else d[k].item())
            for k in d.files if k not in ("traces", "pt", "group", "rk")}
    tr = d["traces"]
    pt = d["pt"]
    g = d["group"]
    assert tr.dtype == np.float16, tr.dtype
    assert [int(x) for x in d["key"]] == RK_TRUE
    d.close()
    return tr, pt, g, meta


# ----------------------------------------------------------------------------- Welch t, chunked
def welch(a, b):
    """Welch t per column of a (na, c) and b (nb, c), float64."""
    d = np.sqrt(a.var(0, ddof=1) / a.shape[0] + b.var(0, ddof=1) / b.shape[0])
    d[d == 0] = np.inf
    return (a.mean(0) - b.mean(0)) / d


def welch2(a, b):
    """Second-order Welch t: each group centered by its own mean and squared."""
    return welch((a - a.mean(0)) ** 2, (b - b.mean(0)) ** 2)


def ttest_pass(tr, g, nsub=None, chunk=2000):
    """One pass over the columns of tr (float16 (N, S)) with group labels g (0 fixed, 1 random).
    Returns a dict of per-sample curves: t1, t2 (all traces), t1_sub, t2_sub (first `nsub`
    traces of each group in file order, if nsub is given), mean_fixed, mean_random, mean
    (all traces), sd_random (ddof = 1), clip_frac (fraction of traces at the rail)."""
    N, S = tr.shape
    ia = np.where(g == 0)[0]
    ib = np.where(g == 1)[0]
    keys = ["t1", "t2", "mean_fixed", "mean_random", "sd_random", "clip_frac"]
    if nsub:
        keys += ["t1_sub", "t2_sub"]
    out = {k: np.zeros(S, np.float64) for k in keys}
    for c0 in range(0, S, chunk):
        sl = slice(c0, min(S, c0 + chunk))
        a = tr[ia, sl].astype(np.float64)
        b = tr[ib, sl].astype(np.float64)
        out["t1"][sl] = welch(a, b)
        out["t2"][sl] = welch2(a, b)
        out["mean_fixed"][sl] = a.mean(0)
        out["mean_random"][sl] = b.mean(0)
        out["sd_random"][sl] = b.std(0, ddof=1)
        out["clip_frac"][sl] = ((a >= CLIP).sum(0) + (b >= CLIP).sum(0)) / float(N)
        if nsub:
            out["t1_sub"][sl] = welch(a[:nsub], b[:nsub])
            out["t2_sub"][sl] = welch2(a[:nsub], b[:nsub])
        del a, b
    out["mean"] = (out["mean_fixed"] * len(ia) + out["mean_random"] * len(ib)) / N
    out["n_fixed"] = len(ia)
    out["n_random"] = len(ib)
    return out


def tstats(t, lo, hi, clip_frac=None, listmax=20):
    """Summary of a t curve over [lo, hi): max|t| with sample and sign, number of samples
    over the threshold, first and last of them, and their positions when at most `listmax`."""
    a = np.abs(t[lo:hi])
    idx = np.where(a > TH)[0] + lo
    r = dict(window=[int(lo), int(hi)], max_abs_t=float(a.max()), at=int(a.argmax()) + lo,
             t_at_max=float(t[a.argmax() + lo]), n_over=int(len(idx)),
             first_over=int(idx[0]) if len(idx) else None, last_over=int(idx[-1]) if len(idx) else None)
    if len(idx) <= listmax:
        r["over_samples"] = [int(i) for i in idx]
        r["over_t"] = [round(float(t[i]), 2) for i in idx]
    if clip_frac is not None:
        r["clip_frac_at_max"] = float(clip_frac[r["at"]])
        if len(idx) <= listmax:
            r["clip_frac_at_over"] = [float(clip_frac[i]) for i in idx]
        r["max_clip_frac_at_over"] = float(clip_frac[idx].max()) if len(idx) else 0.0
    return r


# ----------------------------------------------------------------------------- round structure
def box_residual(m, p):
    """r[t] = mean over u = t .. t+p-1 of |m[u] - m[u+p]|; ~0 where m is p-periodic."""
    d = np.abs(m[:-p] - m[p:])
    return np.convolve(d, np.ones(p) / p, "valid")


def tail_period(m, tail=600, pmax=100):
    """Period of the pattern that dominates the last `tail` samples (autocorrelation)."""
    x = m[-tail:] - m[-tail:].mean()
    ac = np.array([np.dot(x[:-p], x[p:]) / np.dot(x, x) for p in range(2, pmax + 1)])
    return int(np.argmax(ac)) + 2, float(ac.max())


def round_end(m, p=NOP_PERIOD, thr=0.02):
    """Start of the idle NOP loop: last t with box_residual(m, p)[t] > thr, plus p."""
    r = box_residual(m, p)
    above = np.where(r > thr)[0]
    return int(above.max()) + p if len(above) else None


def periodic_runs(m, p=TABLE_PERIOD, thr=0.05, min_len=5000):
    """Runs [i, j+p) over which the mean trace is p-periodic (the table builds)."""
    ok = box_residual(m, p) < thr
    runs, i = [], 0
    while i < len(ok):
        if ok[i]:
            j = i
            while j < len(ok) and ok[j]:
                j += 1
            if j - i >= min_len:
                runs.append((int(i), int(j + p)))
            i = j
        else:
            i += 1
    return runs


def locate(sample, runs):
    """Position of a sample relative to the table builds `runs`."""
    ends = [b for _, b in runs]
    k = int(np.searchsorted(ends, sample))            # builds completed before the sample
    inside = any(a <= sample < b for a, b in runs)
    return dict(builds_completed=k, inside_build=bool(inside),
                cycles_after_build_end=(int(sample - ends[k - 1]) if k else None))


# ----------------------------------------------------------------------------- CPA primitives
_PC = np.array([bin(i).count("1") for i in range(256)], np.float64)
K128 = np.arange(128, dtype=np.int64)


def rol8(x, r):
    x = np.asarray(x, dtype=np.int64)
    return ((x << r) | (x >> (8 - r))) & 0xFF


def F8(x):
    """Shadow F: ((x <<< 1) & (x <<< 7)) ^ (x <<< 2)."""
    return (rol8(x, 1) & rol8(x, 7)) ^ rol8(x, 2)


def hyp128(h):
    """HW(h ^ k) for the 128 representatives k = 0..127, shape (N, 128)."""
    return _PC[(np.asarray(h, np.int64)[:, None] ^ K128[None, :]) & 0xFF]


def corr12(tr, rows, H, chunk=3000, s_lo=0, s_hi=None):
    """Pearson correlation of every column of H (N, K) with every sample of tr[rows, s_lo:s_hi],
    first order (r1) and second order on the centered squared samples (r2), both (S, K) float32.
    tr is float16 (Nall, S); rows selects the traces (None = all)."""
    S = tr.shape[1] if s_hi is None else s_hi
    Hz = np.asarray(H, np.float64)
    Hz = Hz - Hz.mean(0)
    sd = Hz.std(0)
    sd[sd == 0] = np.inf
    Hz = Hz / sd
    N = Hz.shape[0]
    r1 = np.zeros((S - s_lo, H.shape[1]), np.float32)
    r2 = np.zeros_like(r1)
    for c0 in range(s_lo, S, chunk):
        c1 = min(c0 + chunk, S)
        X = (tr[:, c0:c1] if rows is None else tr[rows, c0:c1]).astype(np.float64)
        X -= X.mean(0)
        s = X.std(0)
        s[s == 0] = np.inf
        r1[c0 - s_lo:c1 - s_lo] = (X.T @ Hz) / N / s[:, None]
        X **= 2
        X -= X.mean(0)
        s = X.std(0)
        s[s == 0] = np.inf
        r2[c0 - s_lo:c1 - s_lo] = (X.T @ Hz) / N / s[:, None]
        del X
    return r1, r2


def signed_peak(c):
    """Signed rho of every candidate at the sample where its |rho| peaks; c is (S, K)."""
    idx = np.argmax(np.abs(c), axis=0)
    return c[idx, np.arange(c.shape[1])]


def s256(sp, alpha):
    """Scores of the 256 values from the 128 signed peaks: representative g scores alpha*sp[g],
    its complement g ^ 0xFF scores -alpha*sp[g] (HW(v ^ 0xFF) = 8 - HW(v))."""
    return np.concatenate([alpha * sp, (-alpha * sp)[::-1]])


def rank_of(score, idx):
    """1-based position of candidate idx in the descending order of score (stable)."""
    order = np.argsort(-np.asarray(score, np.float64), kind="stable")
    return int(np.where(order == idx)[0][0]) + 1


def rep(v):
    """Representative of a byte value: the member of {v, v ^ 0xFF} below 128."""
    return v if v < 128 else v ^ 0xFF


def noise_max(n, W, K=128):
    """Expected maximum of |rho| of pure noise over K candidates and W samples at n traces."""
    return float(np.sqrt(2.0 * np.log(K * W)) / np.sqrt(n))


def cpa_summary(c, W, correct, alpha=None, off=0):
    """Rank among the 128 representatives by max|rho| over [0, W), |rho| of the correct
    representative and its sample, best wrong representative, and, with alpha, the rank of
    the correct value among the 256 alpha-signed scores."""
    cw = c[:W]
    a = np.abs(cw).max(0)
    out = dict(rank=rank_of(a, correct), rho_correct=float(a[correct]),
               at=int(np.abs(cw[:, correct]).argmax()) + off,
               rho_best_wrong=float(np.delete(a, correct).max()), best=int(np.argmax(a)))
    if alpha is not None:
        out["rank256_alpha_signed"] = rank_of(s256(signed_peak(cw), alpha), correct)
    if c.shape[0] > W:
        out["max_abs_rho_in_padding"] = float(np.abs(c[W:]).max())
    return out


# ----------------------------------------------------------------------------- misc
def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    return o
