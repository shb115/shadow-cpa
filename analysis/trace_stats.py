# -*- coding: utf-8 -*-
"""
Trace statistics of the unprotected sets quoted in the paper, computed from the deposited
traces alone (Section 4.1).

For every unprotected set (Shadow-32 fixed key, the ten key sets, Shadow-64, and the two
fixed-key sets at the other clock phases):
  - the fraction of samples at the ADC rail, |v| >= 0.4959 (the threshold capture_exp.save()
    printed at capture time; the largest code is 127/256 = 0.4961), over all samples and
    within Rounds 1 to 4; whether the negative rail is ever reached;
  - the round period and boundary from the mean trace (round_structure.py);
  - fixed-key set only: whether any of the samples at which the 13 CPAs of Algorithm 1 peak
    (results/_peaks_12500.json, or recomputed if the cache is missing) is saturated in any
    trace.
The statistics of the masked sets (rail fraction, round end from the idle loop, table builds)
are reported by masked_eval.py and full_encryption.py.

Usage :  python trace_stats.py
Output:  console, and the same text in results/RESULTS_trace_stats.md
"""
import os, sys, json
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from round_structure import round_structure, round_interval

DATA = os.path.join(HERE, "..", "data")
OUT  = os.path.join(HERE, "..", "results")
FIXED  = os.path.join(DATA, "shadow32_fixedkey", "s32_ref_12500.npz")
PHASES = [("fixedphase", os.path.join(DATA, "shadow32_fixedkey", "s32_shadow32_O0_fixedphase_12500.npz")),
          ("noclip", os.path.join(DATA, "shadow32_fixedkey", "s32_shadow32_O0_noclipphase_12500.npz"))]
KEYSET = [os.path.join(DATA, "shadow32_10keys", "s32_key%02d_12500.npz" % i) for i in range(1, 11)]
S64    = os.path.join(DATA, "shadow64", "s64_ref_25000.npz")
CLIP = 0.4959               # capture_exp.save(): (np.abs(f) >= 0.4959).mean()

L = []
def say(s=""):
    print(s, flush=True); L.append(s)


def clip_stats(name, path, nrounds):
    d = np.load(path)
    raw = d["traces"]                                   # float16, exact ADC codes
    N, S = raw.shape
    a = np.abs(raw.astype(np.float32))
    clip = a >= CLIP
    P, b0 = round_structure(raw.astype(np.float64), nrounds=nrounds)
    r1a, _ = round_interval(1, P, b0, S); _, r4b = round_interval(4, P, b0, S)
    neg = float((raw.astype(np.float32) <= -CLIP).mean())
    phase = str(d["phase"]) if "phase" in d.files else "-"
    say("%-10s %d x %-6d phase %-32s P = %d, b0 = %d, Rounds 1-4 = [%d, %d);  at the positive rail: %.2f%% of all samples, "
        "%.2f%% within Rounds 1-4, %.1f%% of the traces have at least one;  negative rail: %s  (min %.4f, max %.4f)"
        % (name, N, S, phase, P, b0, r1a, r4b, 100 * clip.mean(), 100 * clip[:, r1a:r4b].mean(),
           100 * clip.any(1).mean(), "never reached" if neg == 0 else "%.4f%%" % (100 * neg),
           float(raw.min()), float(raw.max())))
    return clip, P, b0


def fixedkey_peaks():
    """Peak samples of the 13 CPAs of Algorithm 1 on the fixed-key set, from the cache written
    by cpa_shadow32_12500.py, or recomputed."""
    cache = os.path.join(OUT, "_peaks_12500.json")
    if os.path.exists(cache):
        for row in json.load(open(cache, encoding="utf-8")):
            if row["name"] == "fixed" and "ps" in row:
                return row["ps"], "results/_peaks_12500.json"
    from cpa_shadow32_12500 import recover_fullkey
    d = np.load(FIXED)
    ps = recover_fullkey(d["traces"].astype(np.float64), d["pt"])[3]
    return ps, "recomputed"


def main():
    say("# Trace statistics of the unprotected sets\n")
    say("ADC rail: |v| >= %.4f (the threshold used by capture_exp.save(); the largest code is 0.4961).\n" % CLIP)
    say("```")
    clip_fx, P, b0 = clip_stats("fixedkey", FIXED, 16)
    for i, p in enumerate(KEYSET, 1):
        clip_stats("key%02d" % i, p, 16)
    clip_stats("shadow64", S64, 32)
    for name, p in PHASES:
        if os.path.exists(p):
            clip_stats(name, p, 16)
    say("```")
    say("\nThe two sets at the other clock phases (`fixedphase`: the phase at power-on, not selected; `noclip`: a "
        "phase at which no sample reaches the largest value) are analyzed in results/RESULTS_phase_compare.md.")
    ps, src = fixedkey_peaks()
    say("\nFixed-key set, samples at which the CPAs of Algorithm 1 peak (%s):\n" % src)
    say("| CPA | peak sample | traces at the rail there |")
    say("|---|---:|---:|")
    n_sat = 0
    for tag, s in ps.items():
        n = int(clip_fx[:, s].sum()); n_sat += n
        say("| %s | %d | %d |" % (tag, s, n))
    say("\n- %s of the %d peak samples is saturated in any trace.\n"
        % ("None" if n_sat == 0 else "At least one", len(ps)))
    open(os.path.join(OUT, "RESULTS_trace_stats.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
