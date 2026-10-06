# -*- coding: utf-8 -*-
"""
Fixed-versus-random t-test on the full 16-round masked encryption (Section 4.7, the test on
the full encryption).

Data: data/masked/masking_ISW_v2_full_seed1_16384x46000.npz and
      data/masked/masking_ISWLUT_v2_full_seed1_16384x46000.npz
  The first 46,000 cycles of a 16-round encryption of the two masked implementations
  (builds with EXTRA_OPTS=SHADOW32_FULL), 8,192 fixed-plaintext and 8,192 random-plaintext
  traces in random order, every mask, refresh byte and key mask uniformly random in both
  groups (196 random bytes per encryption, supplied by the acquisition script).

For each set the script reports (conventions in masked_tools.py):
  1. the first- and second-order Welch t-test over all 46,000 samples: max|t| with its sample
     and sign, the number of samples with |t| > 4.5, the first and last of them, and their
     positions when there are few;
  2. the round period of the full-encryption firmware, from the lag of the largest peak of
     the mean-trace autocorrelation (searched near the one-round length: lags 3,600 to 4,200
     for the ISW implementation, 43,000 to 45,500 for the table-recomputation one), the
     number of rounds the 46,000 samples cover, and the exceeding samples per round;
  3. for the table-recomputation implementation, the 41-cycle table builds and the position
     of every exceeding sample relative to them, next to the positions found in the
     one-round sets (results/_masked_eval.json, when masked_eval.py has been run);
  4. the noise standard deviation of the random group and the fraction of samples at the
     ADC rail.

Usage :  python full_encryption.py          (both sets, one to two minutes, under 3 GB)
Output:  results/RESULTS_full_encryption.md, results/_full_encryption.json
"""
import os, sys, json, time
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from masked_tools import (SETS, IMPL_NAME, TH, CLIP, CODE, TABLE_PERIOD, OUT, load_set, ttest_pass,
                          tstats, periodic_runs, locate, jsonable)

FULL = [t for t, v in SETS.items() if not v[2]]
AC_WINDOW = {"ISW": (3600, 4200), "ISWLUT": (43000, 45500)}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def round_period(m, lo, hi):
    x = m - m.mean()
    ac = np.array([np.dot(x[:-L], x[L:]) / np.dot(x, x) for L in range(lo, hi)])
    L = int(np.argmax(ac)) + lo
    return L, float(ac.max())


def analyze(tag):
    t0 = time.time()
    fn, impl, _ = SETS[tag]
    log("==", tag, fn)
    tr, pt, g, meta = load_set(tag)
    N, S = tr.shape
    res = dict(file=fn, implementation=IMPL_NAME[impl], N=int(N), samples=int(S), meta=meta, pt_bytes=int(pt.shape[1]))
    cv = ttest_pass(tr, g)
    del tr
    res["n_fixed"], res["n_random"] = cv["n_fixed"], cv["n_random"]
    m = cv["mean"]
    L, acp = round_period(m, *AC_WINDOW[impl])
    res["round"] = dict(period=L, autocorr=acp, rounds_covered=S / L, complete_rounds=S // L,
                        samples_of_partial_round=S - (S // L) * L)
    log("   %d x %d, round period %d (autocorrelation %.3f): %.2f rounds in %d samples" % (N, S, L, acp, S / L, S))
    runs = periodic_runs(m) if impl == "ISWLUT" else []
    if runs:
        res["table_builds"] = [dict(start=a, end=b, length=b - a, entries=round((b - a) / TABLE_PERIOD, 1)) for a, b in runs]
        log("   41-cycle table builds: %s" % ", ".join("[%d, %d) %d" % (a, b, b - a) for a, b in runs))
    res["ttest"] = {}
    for key, o in (("t1", 1), ("t2", 2)):
        t = cv[key]
        r = tstats(t, 0, S, cv["clip_frac"], listmax=20)
        idx = np.where(np.abs(t) > TH)[0]
        r["per_round"] = np.bincount(idx // L, minlength=int(np.ceil(S / L))).tolist()
        if runs:
            r["location"] = {int(i): locate(int(i), runs) for i in idx} if len(idx) <= 20 else {}
        res["ttest"]["order%d" % o] = r
        log("   order %d: max|t| %.2f @%d (%s), over 4.5: %d (first %s, last %s), per round %s" % (
            o, r["max_abs_t"], r["at"], "+" if r["t_at_max"] > 0 else "-", r["n_over"], r["first_over"], r["last_over"], r["per_round"]))
        if "over_samples" in r:
            log("   order %d exceedances: %s" % (o, ", ".join("%d (%+.2f)" % (i, v) for i, v in zip(r["over_samples"], r["over_t"]))))
    sd = float(cv["sd_random"].mean())
    res["noise"] = dict(sd_random=sd, sd_codes=sd / CODE,
                        detectable_8192=dict(in_sd=TH * np.sqrt(2.0 / 8192), in_codes=TH * np.sqrt(2.0 / 8192) * sd / CODE))
    res["clip"] = dict(frac_overall=float(cv["clip_frac"].mean()),
                       n_samples_clipped_in_every_trace=int((cv["clip_frac"] == 1.0).sum()))
    log("   rail %.2f%% of samples, noise sd %.5f (%.2f codes), %.0f s" % (100 * res["clip"]["frac_overall"], sd, sd / CODE, time.time() - t0))
    return res


def one_round_locations():
    """Exceeding samples of the one-round table-recomputation sets and their position relative
    to the table builds, from masked_eval.py's output."""
    p = os.path.join(OUT, "_masked_eval.json")
    if not os.path.exists(p):
        return {}
    R = json.load(open(p, encoding="utf-8"))["sets"]
    out = {}
    for tag in ("ISWLUT_seed1", "ISWLUT_seed2"):
        if tag in R:
            out[tag] = dict(table_builds=R[tag].get("table_builds", []),
                            order1=R[tag]["ttest"]["t1"]["round"].get("location", {}),
                            order2=R[tag]["ttest"]["t2"]["round"].get("location", {}))
    return out


def write_md(R):
    L = ["# Masked Shadow-32, full 16-round encryption: fixed-versus-random t-test (Section 4.7)\n",
         "Traces: `data/masked/masking_*_v2_full_seed1_16384x46000.npz`, the first 46,000 cycles of a 16-round masked "
         "encryption, 8,192 fixed-plaintext and 8,192 random-plaintext traces per set. Welch t = mean(fixed) - "
         "mean(random), threshold |t| > 4.5; second order on the centered squared samples; 1 sample = 1 cycle.\n",
         "## 1. Rounds covered\n",
         "| Set | Traces x samples | Round period (cycles) | Autocorrelation | Rounds in 46,000 samples | Complete rounds | Table builds [start, end) |",
         "|---|---|---:|---:|---:|---:|---|"]
    for t in FULL:
        r = R["sets"][t]
        tb = ", ".join("[%d, %d)" % (b["start"], b["end"]) for b in r.get("table_builds", [])) or "-"
        L.append("| %s | %d x %d | %d | %.3f | %.2f | %d | %s |" % (
            t, r["N"], r["samples"], r["round"]["period"], r["round"]["autocorr"], r["round"]["rounds_covered"], r["round"]["complete_rounds"], tb))
    L += ["", "## 2. t-test over all 46,000 samples, 8,192 traces per group\n",
          "| Set | Order | max\\|t\\| | at sample (sign) | Samples over 4.5 | First, last | Per round | Positions (t) |",
          "|---|---|---:|---|---:|---|---|---|"]
    for t in FULL:
        r = R["sets"][t]
        for o in (1, 2):
            rr = r["ttest"]["order%d" % o]
            pos = ", ".join("%d (%+.2f)" % (i, v) for i, v in zip(rr["over_samples"], rr["over_t"])) if "over_samples" in rr else "-"
            L.append("| %s | %d | %.2f | %d (%s) | %d | %s, %s | %s | %s |" % (
                t, o, rr["max_abs_t"], rr["at"], "+" if rr["t_at_max"] > 0 else "-", rr["n_over"], rr["first_over"], rr["last_over"],
                " ".join(str(x) for x in rr["per_round"]), pos))
    L += ["", "## 3. Position of the exceeding samples of the table-recomputation implementation\n",
          "Builds completed before the sample and its distance from the end of the last of them (cycles); the "
          "one-round columns give the same for the exceeding samples of the one-round acquisitions.\n",
          "| Capture | Order | Sample | t | Builds completed | Cycles after the end of the last build |",
          "|---|---|---:|---:|---:|---:|"]
    r = R["sets"].get("ISWLUT_full")
    if r:
        for o in (1, 2):
            rr = r["ttest"]["order%d" % o]
            for i, v in zip(rr.get("over_samples", []), rr.get("over_t", [])):
                lc = rr["location"].get(str(i), rr["location"].get(i))
                L.append("| full encryption | %d | %d | %+.2f | %d | %s |" % (o, i, v, lc["builds_completed"], lc["cycles_after_build_end"]))
    for tag, v in R.get("one_round", {}).items():
        for o in (1, 2):
            for i, lc in v["order%d" % o].items():
                L.append("| %s (one round) | %d | %s | | %d | %s |" % (tag, o, i, lc["builds_completed"], lc["cycles_after_build_end"]))
    L += ["", "## 4. Noise and samples at the ADC rail\n",
          "| Set | Noise sd of the random group (ADC units, codes) | Detectable difference at n = 8,192 (sd, codes) | Fraction of samples at the rail | Samples at the rail in every trace |",
          "|---|---|---|---:|---:|"]
    for t in FULL:
        r = R["sets"][t]
        L.append("| %s | %.5f, %.2f | %.4f sd, %.2f codes | %.4f | %d |" % (
            t, r["noise"]["sd_random"], r["noise"]["sd_codes"], r["noise"]["detectable_8192"]["in_sd"], r["noise"]["detectable_8192"]["in_codes"],
            r["clip"]["frac_overall"], r["clip"]["n_samples_clipped_in_every_trace"]))
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "RESULTS_full_encryption.md"), "w", encoding="utf-8").write(txt)
    return txt


def main():
    args = sys.argv[1:]
    tags = FULL if not args else [t for t in FULL if t in args or t.split("_")[0] in args]
    jpath = os.path.join(OUT, "_full_encryption.json")
    R = json.load(open(jpath, encoding="utf-8")) if os.path.exists(jpath) else {}
    R.setdefault("sets", {})
    for t in tags:
        R["sets"][t] = analyze(t)
        json.dump(jsonable(R), open(jpath, "w", encoding="utf-8"), indent=1)
    R["one_round"] = one_round_locations()
    json.dump(jsonable(R), open(jpath, "w", encoding="utf-8"), indent=1)
    print(write_md(R))
    print("Result : results/RESULTS_full_encryption.md\nNumbers: results/_full_encryption.json")


if __name__ == "__main__":
    main()
