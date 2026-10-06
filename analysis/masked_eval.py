# -*- coding: utf-8 -*-
"""
Leakage assessment and attack on the two masked Shadow-32 implementations
(Section 4.7 of the paper; Fig. 14 is drawn by fig_tvla.py from the cache written here).

Data: data/masked/masking_ISW_v2_seed{1,2}_16384x10000.npz and
      data/masked/masking_ISWLUT_v2_seed{1,2}_16384x46000.npz
  One masked round per trace, 8,192 fixed-plaintext traces (group 0, plaintext 0x11223344)
  and 8,192 random-plaintext traces (group 1) in random order, round key 0D 3B 60 33; the
  masks, the refresh bytes and the key masks are uniformly random in both groups.  Seed 2 is
  an independent acquisition under the same conditions.

For every set the script reports (conventions in masked_tools.py):
  1. the round end, i.e. the start of the idle NOP loop that follows the round (3,880 cycles
     for the ISW implementation, 44,176 for the table-recomputation one), and, for the
     table-recomputation implementation, the four 41-cycle table builds;
  2. the fixed-versus-random Welch t-test over the round, first order and second order
     (centered squared samples): max|t| with its sample and sign, the number of samples with
     |t| > 4.5 and their positions when there are few; the same on the first 4,096 traces
     of each group, the trace count of the previous version;
  3. the independent repetition: samples over the threshold in both acquisitions with the
     same sign, and the Pearson correlation of the two t curves over the round;
  4. the attacker-model CPA of the Round-1 stage of Algorithm 1 on the random group, 8,192
     traces, with the leakage model and the round samples of the unprotected attack: the
     7-bit CPAs on h0 and h1, the decision on D (the pair of RK1_0, p, max|rho| of h2 and
     h2*, D, alpha), then h2 and h3 built with the recovered values; for each CPA the rank
     of the correct candidate among the 128 representatives, |rho| of the correct candidate
     and its sample, and the best wrong candidate; the diagnostic h2 and h3 built with the
     true RK1_0 and RK1_1 (the true value of the earlier stage, which the attacker does not
     have; no mask is used anywhere); at first order and at second order; the noise level 4.5/sqrt(N),
     the expected maximum of noise over 128 candidates and the round, and the empirical
     maximum of |rho| over the NOP padding;
  5. the success rate against the number of traces, on disjoint contiguous subsets of the
     random group, min(8192/N, 20) subsets per point, for every CPA whose correct candidate
     ranks first on the full set;
  6. the effect size: the noise standard deviation of the random group over the round, in
     ADC codes, and the smallest mean difference the test detects at |t| = 4.5 with 4,096
     and with 8,192 traces per group;
  7. the fraction of samples at the ADC rail, overall and at every reported sample.

Usage :  python masked_eval.py                 (the four sets, about ten minutes, under 3 GB)
         python masked_eval.py ISW             (one implementation, both seeds)
         python masked_eval.py ISWLUT_seed1    (one set)
Output:  results/RESULTS_masked_eval.md, results/_masked_eval.json (every number),
         results/_masked_ttest.npz (t curves, mean traces and round ends; read by fig_tvla.py)
"""
import os, sys, json, time
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from masked_tools import (SETS, IMPL_NAME, TH, CLIP, CODE, NOP_PERIOD, TABLE_PERIOD, RK_TRUE, OUT,
                          load_set, ttest_pass, tstats, tail_period, round_end, periodic_runs,
                          locate, F8, hyp128, corr12, signed_peak, s256, rank_of, rep, noise_max,
                          cpa_summary, jsonable)

NSUB = 4096                                       # trace count per group of the previous version
NLIST = [128, 256, 512, 1024, 2048, 4096, 8192]   # success-rate points
MAXREP = 20
ONE_ROUND = [t for t, v in SETS.items() if v[2]]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ----------------------------------------------------------------------------- CPA, attacker model
def attack(tr, rows, pt, W):
    """Round-1 stage of Algorithm 1 on the traces tr[rows] with plaintexts pt (rows of the
    random group), both orders; CPAs over the round [0, W).  Returns (summary, chain)."""
    L0, L1, R0, R1 = (pt[:, j].astype(np.int64) for j in range(4))
    h0 = F8(L0) ^ L1
    h1 = F8(R0) ^ R1
    h2d = F8(h0 ^ RK_TRUE[0]) ^ L0           # diagnostic: built with the true RK1_0
    h3d = F8(h1 ^ RK_TRUE[1]) ^ R0           # diagnostic: built with the true RK1_1
    hyps = dict(h0=h0, h1=h1, h2_diag=h2d, h3_diag=h3d)

    # pass A: h0, h1 and the two diagnostic CPAs, all samples, both orders
    HA = np.concatenate([hyp128(h0), hyp128(h1), hyp128(h2d), hyp128(h3d)], 1)
    r1, r2 = corr12(tr, rows, HA)
    C = {1: {}, 2: {}}
    for o, r in ((1, r1), (2, r2)):
        for i, key in enumerate(("h0", "h1", "h2_diag", "h3_diag")):
            C[o][key] = r[:, 128 * i:128 * (i + 1)]
    del r1, r2

    # stage 1: the complement pair of RK1_0 and its positive-peak member p
    chain = {}
    for o in (1, 2):
        sp0 = signed_peak(C[o]["h0"][:W])
        g0 = int(np.argmax(np.abs(sp0)))
        p = g0 if sp0[g0] > 0 else (g0 ^ 0xFF)
        chain[o] = dict(pair=[g0, g0 ^ 0xFF], p=int(p))
    # pass B: h2 built with p and h2* built with p ^ 0xFF, for the p of each order
    need = {}
    for o in (1, 2):
        p = chain[o]["p"]
        need[("h2", p)] = F8(h0 ^ p) ^ L0
        need[("h2s", p)] = F8(h0 ^ p ^ 0xFF) ^ L0
    keys = list(need)
    r1, r2 = corr12(tr, rows, np.concatenate([hyp128(need[k]) for k in keys], 1))
    for o, r in ((1, r1), (2, r2)):
        p = chain[o]["p"]
        i2, i2s = keys.index(("h2", p)), keys.index(("h2s", p))
        C[o]["h2"] = r[:, 128 * i2:128 * (i2 + 1)]
        C[o]["h2s"] = r[:, 128 * i2s:128 * (i2s + 1)]
    del r1, r2
    # stage 2: the decision on D, then RK1_0, RK1_1 and RK1_2
    for o in (1, 2):
        ch = chain[o]
        p = ch["p"]
        sp2 = signed_peak(C[o]["h2"][:W])
        sp2s = signed_peak(C[o]["h2s"][:W])
        P2, P2s = float(np.abs(sp2).max()), float(np.abs(sp2s).max())
        D = P2 - P2s
        alpha = 1.0 if D >= 0 else -1.0
        RK0 = p if D >= 0 else (p ^ 0xFF)
        sp1 = signed_peak(C[o]["h1"][:W])
        RK1 = int(np.argmax(s256(sp1, alpha)))
        spw = sp2 if D >= 0 else sp2s
        RK2 = int(np.argmax(s256(spw, alpha)))
        ch.update(P2=P2, P2s=P2s, D=float(D), alpha=alpha, RK0=int(RK0), RK1=RK1, RK2=RK2)
    # pass C: h3 built with the recovered RK1_1 (the diagnostic CPA when it is the true one)
    needC = {}
    for o in (1, 2):
        k1 = chain[o]["RK1"]
        if k1 != RK_TRUE[1]:
            needC[k1] = F8(h1 ^ k1) ^ R0
    if needC:
        kc = list(needC)
        r1, r2 = corr12(tr, rows, np.concatenate([hyp128(needC[k]) for k in kc], 1))
    for o in (1, 2):
        k1 = chain[o]["RK1"]
        if k1 == RK_TRUE[1]:
            C[o]["h3"] = C[o]["h3_diag"]
        else:
            i = kc.index(k1)
            C[o]["h3"] = (r1 if o == 1 else r2)[:, 128 * i:128 * (i + 1)]
    for o in (1, 2):
        ch = chain[o]
        sp3 = signed_peak(C[o]["h3"][:W])
        RK3 = int(np.argmax(s256(sp3, ch["alpha"])))
        rec = [ch["RK0"], ch["RK1"], ch["RK2"], RK3]
        ch.update(RK3=RK3, recovered=rec, recovered_hex=" ".join("%02X" % v for v in rec),
                  byte_correct=[rec[j] == RK_TRUE[j] for j in range(4)],
                  pair_correct=(RK_TRUE[0] in ch["pair"]),
                  decision_correct=(ch["RK0"] == RK_TRUE[0] and ch["alpha"] == 1.0))

    # summaries
    cpa = {1: {}, 2: {}}
    for o in (1, 2):
        ch = chain[o]
        al = ch["alpha"]
        cpa[o]["h0"] = cpa_summary(C[o]["h0"], W, RK_TRUE[0], al)
        cpa[o]["h1"] = cpa_summary(C[o]["h1"], W, RK_TRUE[1], al)
        s = cpa_summary(C[o]["h2"], W, RK_TRUE[2], al)
        s["built_with"] = ch["p"]
        s["correct_candidate_meaningful"] = (ch["p"] == RK_TRUE[0])
        cpa[o]["h2"] = s
        s = cpa_summary(C[o]["h2s"], W, RK_TRUE[2], al)
        s["built_with"] = ch["p"] ^ 0xFF
        s["correct_candidate_meaningful"] = ((ch["p"] ^ 0xFF) == RK_TRUE[0])
        cpa[o]["h2s"] = s
        s = cpa_summary(C[o]["h3"], W, RK_TRUE[3], al)
        s["built_with"] = ch["RK1"]
        s["correct_candidate_meaningful"] = (ch["RK1"] == RK_TRUE[1])
        cpa[o]["h3"] = s
        cpa[o]["h2_diag"] = cpa_summary(C[o]["h2_diag"], W, RK_TRUE[2], al)
        cpa[o]["h3_diag"] = cpa_summary(C[o]["h3_diag"], W, RK_TRUE[3], al)
    del C
    return cpa, chain, hyps


def success_rate(tr, ir, pt, W, cpa, hyps):
    """Success rate against N of every CPA (order, key) whose correct candidate ranks first on
    the full random group: disjoint contiguous subsets of the random group in file order."""
    correct = dict(h0=RK_TRUE[0], h1=RK_TRUE[1], h2_diag=RK_TRUE[2], h3_diag=RK_TRUE[3])
    qual = [(o, key) for o in (1, 2) for key in ("h0", "h1", "h2_diag", "h3_diag") if cpa[o][key]["rank"] == 1]
    out = dict(qualifying=["order %d %s" % (o, k) for o, k in qual], per_cpa={})
    if not qual:
        return out
    ukeys = sorted(set(k for _, k in qual))
    HS = np.concatenate([hyp128(hyps[k]) for k in ukeys], 1)
    Nr = len(ir)
    rates = {q: [] for q in qual}
    for n in NLIST:
        nsub = min(Nr // n, MAXREP)
        ok = {q: 0 for q in qual}
        t0 = time.time()
        for j in range(nsub):
            sl = slice(j * n, (j + 1) * n)
            r1, r2 = corr12(tr, ir[sl], HS[sl], s_hi=W)
            for o, key in qual:
                r = r1 if o == 1 else r2
                i = ukeys.index(key)
                a = np.abs(r[:, 128 * i:128 * (i + 1)]).max(0)
                ok[(o, key)] += int(np.argmax(a) == correct[key])
        for q in qual:
            rates[q].append(dict(N=n, subsets=nsub, successes=ok[q], rate=ok[q] / nsub))
        log("   success rate N=%5d (%2d subsets): %s  %.0fs" % (
            n, nsub, "  ".join("order %d %s %d/%d" % (q[0], q[1], ok[q], nsub) for q in qual), time.time() - t0))
    for q in qual:
        rr = rates[q]
        stable = next((x["N"] for i, x in enumerate(rr) if all(y["rate"] == 1.0 for y in rr[i:])), None)
        out["per_cpa"]["order %d %s" % q] = dict(rates=rr, smallest_N_with_rate_1_from_there_on=stable)
    return out


# ----------------------------------------------------------------------------- one set
def analyze(tag, curves):
    t0 = time.time()
    fn, impl, _ = SETS[tag]
    log("==", tag, fn)
    tr, pt, g, meta = load_set(tag)
    N, S = tr.shape
    res = dict(file=fn, implementation=IMPL_NAME[impl], N=int(N), samples=int(S), meta=meta)

    # 1. t-test pass, round end, table builds
    cv = ttest_pass(tr, g, nsub=NSUB)
    res["n_fixed"], res["n_random"] = cv["n_fixed"], cv["n_random"]
    m = cv["mean"]
    p, acp = tail_period(m)
    assert p == NOP_PERIOD, "NOP loop period %d, expected %d" % (p, NOP_PERIOD)
    end = round_end(m, p)
    res["nop_period"] = dict(period=p, autocorr=acp)
    res["round_end"] = end
    res["clip"] = dict(frac_overall=float(cv["clip_frac"].mean()),
                       frac_round=float(cv["clip_frac"][:end].mean()),
                       n_samples_clipped_in_every_trace=int((cv["clip_frac"] == 1.0).sum()))
    log("   %d x %d, round end %d (NOP period %d, autocorrelation %.3f), rail %.2f%% of samples"
        % (N, S, end, p, acp, 100 * res["clip"]["frac_overall"]))
    runs = periodic_runs(m) if impl == "ISWLUT" else []
    if runs:
        res["table_builds"] = [dict(start=a, end=b, length=b - a, entries=round((b - a) / TABLE_PERIOD, 1)) for a, b in runs]
        log("   41-cycle table builds: %s" % ", ".join("[%d, %d) %d" % (a, b, b - a) for a, b in runs))

    # 2. t-test statistics
    res["ttest"] = {}
    for key, nm, n in (("t1", "order 1, N = 8192", N // 2), ("t2", "order 2, N = 8192", N // 2),
                       ("t1_sub", "order 1, N = 4096", NSUB), ("t2_sub", "order 2, N = 4096", NSUB)):
        t = cv[key]
        r = dict(label=nm, n_per_group=n, round=tstats(t, 0, end, cv["clip_frac"]), whole=tstats(t, 0, S))
        if runs:
            r["round"]["location"] = {int(i): locate(int(i), runs) for i in np.where(np.abs(t[:end]) > TH)[0]}
        res["ttest"][key] = r
        rr = r["round"]
        log("   %-18s round: max|t| %6.2f @%-5d (%s)  over 4.5: %3d  %s | whole trace: max|t| %.2f, over %d"
            % (nm, rr["max_abs_t"], rr["at"], "+" if rr["t_at_max"] > 0 else "-", rr["n_over"],
               ("at " + ", ".join("%d (%+.2f)" % (i, v) for i, v in zip(rr["over_samples"], rr["over_t"])))
               if "over_samples" in rr else "[%d, %d]" % (rr["first_over"], rr["last_over"]),
               r["whole"]["max_abs_t"], r["whole"]["n_over"]))
    res["t_sd_in_padding"] = dict(t1=float(cv["t1"][end:].std()), t2=float(cv["t2"][end:].std()))

    # 6. effect size
    sd = float(cv["sd_random"][:end].mean())
    res["effect_size"] = dict(noise_sd_random_round=sd, noise_sd_codes=sd / CODE,
                              detectable={str(n): dict(in_sd=TH * np.sqrt(2.0 / n), in_codes=TH * np.sqrt(2.0 / n) * sd / CODE)
                                          for n in (NSUB, N // 2)})
    curves[tag] = dict(t1=cv["t1"], t2=cv["t2"], t1_sub=cv["t1_sub"], t2_sub=cv["t2_sub"],
                       mean=m, clip_frac=cv["clip_frac"], round_end=end)
    del cv

    # 4. CPA, random group
    ir = np.where(g == 1)[0]
    P = pt[ir]
    Nr = len(ir)
    res["cpa"] = dict(N=int(Nr), window=[0, end], noise_level=TH / np.sqrt(Nr), expected_noise_max=noise_max(Nr, end))
    log("   CPA on the random group, %d traces, window [0, %d), noise level %.4f, expected noise maximum %.4f"
        % (Nr, end, res["cpa"]["noise_level"], res["cpa"]["expected_noise_max"]))
    cpa, chain, hyps = attack(tr, ir, P, end)
    res["cpa"]["order1"], res["cpa"]["order2"] = cpa[1], cpa[2]
    res["cpa"]["chain_order1"], res["cpa"]["chain_order2"] = chain[1], chain[2]
    for o in (1, 2):
        for key in ("h0", "h1", "h2", "h2s", "h3", "h2_diag", "h3_diag"):
            s = cpa[o][key]
            log("   order %d %-8s rank %3d/128  |rho| correct %.4f @%-5d  best wrong %.4f  padding max %.4f%s"
                % (o, key, s["rank"], s["rho_correct"], s["at"], s["rho_best_wrong"], s.get("max_abs_rho_in_padding", -1),
                   ("  (built with %02X)" % s["built_with"]) if "built_with" in s else ""))
        ch = chain[o]
        log("   order %d chain: pair {%02X, %02X}, p = %02X, max|rho| h2 %.4f, h2* %.4f, D %+.4f, alpha %+d -> %s (true %s)"
            % (o, ch["pair"][0], ch["pair"][1], ch["p"], ch["P2"], ch["P2s"], ch["D"], int(ch["alpha"]),
               ch["recovered_hex"], " ".join("%02X" % v for v in RK_TRUE)))

    # 5. success rate of the rank-1 CPAs
    res["success_rate"] = success_rate(tr, ir, P, end, cpa, hyps)
    log("   done in %.0f s" % (time.time() - t0))       # wall-clock time: console only, not recorded
    del tr
    return res


def replication(curves, R):
    """Seed 1 against seed 2 over the common round window."""
    rep_ = {}
    for impl in ("ISW", "ISWLUT"):
        a, b = curves.get(impl + "_seed1"), curves.get(impl + "_seed2")
        if a is None or b is None:
            continue
        W = min(a["round_end"], b["round_end"])
        r = dict(round_window=[0, W])
        for key, nm in (("t1", "order 1, N = 8192"), ("t2", "order 2, N = 8192"),
                        ("t1_sub", "order 1, N = 4096"), ("t2_sub", "order 2, N = 4096")):
            x, y = a[key][:W], b[key][:W]
            ox, oy = np.abs(x) > TH, np.abs(y) > TH
            both = ox & oy & (np.sign(x) == np.sign(y))
            r[key] = dict(label=nm, seed1_over=int(ox.sum()), seed2_over=int(oy.sum()),
                          both_same_sign=int(both.sum()), pearson=float(np.corrcoef(x, y)[0, 1]))
            if both.sum() <= 20:
                r[key]["both_same_sign_samples"] = [int(i) for i in np.where(both)[0]]
        rep_[impl] = r
    R["replication"] = rep_


# ----------------------------------------------------------------------------- report
def fsign(v):
    return "+" if v > 0 else "-"


def write_md(R):
    tags = [t for t in ONE_ROUND if t in R["sets"]]
    L = ["# Masked Shadow-32: fixed-versus-random t-test and the CPA of Algorithm 1 (Section 4.7)\n",
         "Traces: `data/masked/`, one masked round per trace, 8,192 fixed-plaintext and 8,192 random-plaintext "
         "traces per set, round key `0D 3B 60 33`; seed 2 is an independent acquisition. Conventions: Welch t = "
         "mean(fixed) - mean(random), threshold |t| > 4.5; second order on the centered squared samples; the round "
         "window runs from the trigger to the start of the idle NOP loop (the round end below); CPA = 7-bit CPA over "
         "the 128 representatives with the hypothesis HW(h xor k), rank = position of the correct candidate among "
         "the 128 by max|rho| over the round; ADC rail = v >= %.4f; 1 sample = 1 clock cycle.\n" % CLIP]
    # 1 round end
    L += ["## 1. Round end and table builds\n",
          "| Set | Traces x samples | NOP period | Round end (cycles) | Table builds [start, end), length |",
          "|---|---|---:|---:|---|"]
    for t in tags:
        r = R["sets"][t]
        tb = ", ".join("[%d, %d) %d" % (b["start"], b["end"], b["length"]) for b in r.get("table_builds", [])) or "-"
        L.append("| %s | %d x %d | %d | %d | %s |" % (t, r["N"], r["samples"], r["nop_period"]["period"], r["round_end"], tb))
    L.append("")
    # 2 t-test
    for key, title in (("t1", "## 2. First-order t-test over the round, 8,192 traces per group\n"),
                       ("t2", "## 3. Second-order t-test (centered squared samples) over the round, 8,192 traces per group\n"),
                       ("t1_sub", "## 4. First-order t-test, first 4,096 traces per group\n"),
                       ("t2_sub", "## 5. Second-order t-test, first 4,096 traces per group\n")):
        L += [title, "| Set | max\\|t\\| | at sample (sign) | samples over 4.5 | positions (t) | rail fraction at the max\\|t\\| sample | largest rail fraction over the exceeding samples |",
              "|---|---:|---|---:|---|---:|---:|"]
        for t in tags:
            rr = R["sets"][t]["ttest"][key]["round"]
            pos = (", ".join("%d (%+.2f)" % (i, v) for i, v in zip(rr["over_samples"], rr["over_t"]))
                   if "over_samples" in rr else "first %d, last %d" % (rr["first_over"], rr["last_over"]))
            L.append("| %s | %.2f | %d (%s) | %d | %s | %.3f | %.3f |" % (
                t, rr["max_abs_t"], rr["at"], fsign(rr["t_at_max"]), rr["n_over"], pos, rr["clip_frac_at_max"], rr["max_clip_frac_at_over"]))
        L.append("")
    # location of exceedances
    L += ["## 6. Position of the exceeding samples relative to the table builds (table recomputation)\n",
          "| Set | Order | Sample | t | Builds completed before it | Cycles after the end of the last build | Inside a build |",
          "|---|---|---:|---:|---:|---:|---|"]
    for t in tags:
        r = R["sets"][t]
        if "table_builds" not in r:
            continue
        for key, o in (("t1", 1), ("t2", 2)):
            rr = r["ttest"][key]["round"]
            for i, v in zip(rr.get("over_samples", []), rr.get("over_t", [])):
                lc = rr["location"][str(i)] if str(i) in rr["location"] else rr["location"][i]
                L.append("| %s | %d | %d | %+.2f | %d | %s | %s |" % (
                    t, o, i, v, lc["builds_completed"], lc["cycles_after_build_end"], "yes" if lc["inside_build"] else "no"))
    L.append("")
    # replication
    L += ["## 7. Independent repetition: seed 1 against seed 2 over the round\n",
          "| Implementation | Statistic | Over 4.5 in seed 1 / seed 2 | Over in both with the same sign | Pearson correlation of the t curves |",
          "|---|---|---|---|---:|"]
    for impl, r in R.get("replication", {}).items():
        for key in ("t1", "t2", "t1_sub", "t2_sub"):
            x = r[key]
            same = "%d" % x["both_same_sign"] + (" (sample %s)" % ", ".join(str(s) for s in x["both_same_sign_samples"])
                                                  if x.get("both_same_sign_samples") else "")
            L.append("| %s | %s | %d / %d | %s | %.3f |" % (IMPL_NAME[impl], x["label"], x["seed1_over"], x["seed2_over"], same, x["pearson"]))
    L.append("")
    # CPA
    L += ["## 8. CPA of Algorithm 1, Round-1 stage, on the random group (8,192 traces)\n",
          "h0 and h1 are the CPAs of Section 4.2; h2 is built with the positive-peak member p of the RK1_0 pair and "
          "h2* with p xor 0xFF (the decision on D of Section 4.3); h3 is built with the recovered RK1_1. The "
          "diagnostic rows build h2 with the true RK1_0 and h3 with the true RK1_1, which is what the attack would "
          "run had the earlier stage succeeded; they use the true value of the earlier stage, which is not available "
          "to the attacker (no mask is used by any CPA). Rank: position of the correct candidate among the 128 representatives "
          "by max|rho| over the round (in brackets: among the 256 values by the alpha-signed score, Section 4.3). "
          "Noise level 4.5/sqrt(N) = %.4f.\n" % (TH / np.sqrt(8192))]
    for t in tags:
        r = R["sets"][t]["cpa"]
        L += ["### %s (window [0, %d), expected maximum of noise over 128 x %d = %.4f)\n" % (t, r["window"][1], r["window"][1], r["expected_noise_max"]),
              "| Order | CPA | Built with | Rank of correct (of 128) [of 256] | \\|rho\\| correct @ sample | Best wrong \\|rho\\| | max\\|rho\\| over the NOP padding |",
              "|---|---|---|---:|---|---:|---:|"]
        for o in (1, 2):
            c = r["order%d" % o]
            for key, lbl in (("h0", "h0 (RK1_0 = 0D)"), ("h1", "h1 (RK1_1 = 3B)"), ("h2", "h2 (RK1_2 = 60)"),
                             ("h2s", "h2* (rejected by D)"), ("h3", "h3 (RK1_3 = 33)"),
                             ("h2_diag", "h2 diagnostic, true RK1_0 (not available to the attacker)"),
                             ("h3_diag", "h3 diagnostic, true RK1_1 (not available to the attacker)")):
                s = c[key]
                bw = ("%02X" % s["built_with"]) if "built_with" in s else "-"
                note = "" if s.get("correct_candidate_meaningful", True) else " (no correct candidate)"
                L.append("| %d | %s | %s | %d [%d]%s | %.4f @ %d | %.4f | %.4f |" % (
                    o, lbl, bw, s["rank"], s["rank256_alpha_signed"], note, s["rho_correct"], s["at"], s["rho_best_wrong"],
                    s.get("max_abs_rho_in_padding", float("nan"))))
            ch = r["chain_order%d" % o]
            L.append("| %d | decision | | pair {%02X, %02X}, p = %02X: max\\|rho\\| h2 = %.4f, h2* = %.4f, D = %+.4f, alpha = %+d | recovered `%s` (true `%s`), bytes correct %s | | |" % (
                o, ch["pair"][0], ch["pair"][1], ch["p"], ch["P2"], ch["P2s"], ch["D"], int(ch["alpha"]),
                ch["recovered_hex"], " ".join("%02X" % v for v in RK_TRUE), "".join("1" if b else "0" for b in ch["byte_correct"])))
        L.append("")
    # success rate
    L += ["## 9. Success rate against the number of traces, CPAs that rank the correct candidate first at 8,192 traces\n",
          "Disjoint contiguous subsets of the random group, min(8192/N, 20) per point; success = the correct "
          "representative ranks first by max|rho| over the round. A diagnostic CPA (h2_diag, h3_diag) is built with "
          "the true value of the earlier stage, which is not available to the attacker.\n",
          "| Set | CPA | " + " | ".join("N = %d" % n for n in NLIST) + " | Smallest N with rate 1.0 from there on |",
          "|---|---|" + "---:|" * len(NLIST) + "---:|"]
    for t in tags:
        sr = R["sets"][t]["success_rate"]
        if not sr["per_cpa"]:
            L.append("| %s | none ranks first | %s | - |" % (t, " | ".join("" for _ in NLIST)))
        for nm, v in sr["per_cpa"].items():
            lbl = nm + (" (true earlier value, not available to the attacker)" if nm.endswith("_diag") else "")
            L.append("| %s | %s | %s | %s |" % (t, lbl, " | ".join("%d/%d" % (x["successes"], x["subsets"]) for x in v["rates"]),
                                                 v["smallest_N_with_rate_1_from_there_on"]))
    L.append("")
    # effect size
    L += ["## 10. Effect size and noise\n",
          "Noise = mean over the round of the per-sample standard deviation of the random group; one ADC code = 1/256. "
          "Smallest detectable difference between the group means at |t| = 4.5 with n traces per group: 4.5 sqrt(2/n) noise sd.\n",
          "| Set | Noise sd (ADC units) | Noise sd (codes) | Detectable at n = 4,096 (sd, codes) | Detectable at n = 8,192 (sd, codes) |",
          "|---|---:|---:|---|---|"]
    for t in tags:
        e = R["sets"][t]["effect_size"]
        d4, d8 = e["detectable"]["4096"], e["detectable"]["8192"]
        L.append("| %s | %.5f | %.2f | %.4f sd, %.2f codes | %.4f sd, %.2f codes |" % (
            t, e["noise_sd_random_round"], e["noise_sd_codes"], d4["in_sd"], d4["in_codes"], d8["in_sd"], d8["in_codes"]))
    L.append("")
    # clipping
    L += ["## 11. Samples at the ADC rail\n",
          "Fraction of the samples at the positive rail, over all samples and within the round; the number of samples "
          "at which every trace is at the rail (one sample of every NOP iteration); the fraction of traces at the "
          "rail at the four max|t| samples (orders 1 and 2, N = 8,192 and 4,096) and the largest such fraction over "
          "all exceeding samples of the four statistics.\n",
          "| Set | All samples | Within the round | Samples at the rail in every trace | At the max\\|t\\| samples | Largest over the exceeding samples |",
          "|---|---:|---:|---:|---|---:|"]
    for t in tags:
        r = R["sets"][t]
        atmax = ", ".join("%.3f" % r["ttest"][k]["round"]["clip_frac_at_max"] for k in ("t1", "t2", "t1_sub", "t2_sub"))
        mx = max(r["ttest"][k]["round"]["max_clip_frac_at_over"] for k in ("t1", "t2", "t1_sub", "t2_sub"))
        L.append("| %s | %.4f | %.4f | %d | %s | %.3f |" % (t, r["clip"]["frac_overall"], r["clip"]["frac_round"], r["clip"]["n_samples_clipped_in_every_trace"], atmax, mx))
    L.append("")
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "RESULTS_masked_eval.md"), "w", encoding="utf-8").write(txt)
    return txt


def main():
    args = sys.argv[1:]
    tags = ONE_ROUND if not args else [t for t in ONE_ROUND if t in args or t.split("_")[0] in args]
    jpath = os.path.join(OUT, "_masked_eval.json")
    npath = os.path.join(OUT, "_masked_ttest.npz")
    R = json.load(open(jpath, encoding="utf-8")) if os.path.exists(jpath) else {}
    R.setdefault("sets", {})
    R["conventions"] = ("Welch t = mean(fixed) - mean(random), ddof = 1, |t| > 4.5; second order = per-group centered "
                        "squares; round end = last t with box_14 |m[t] - m[t+14]| > 0.02 plus 14 on the mean of all "
                        "traces; table builds = runs of box_41 residual < 0.05 of at least 5000 samples, end = run end + 41; "
                        "CPA rank = among the 128 representatives by max|rho| over [0, round end); rail = v >= %.4f" % CLIP)
    curves = {}
    if os.path.exists(npath):
        c = np.load(npath)
        for t in ONE_ROUND:
            if "t1_" + t in c.files and t not in tags:
                curves[t] = {k: c[k + "_" + t] for k in ("t1", "t2", "t1_sub", "t2_sub", "mean", "clip_frac")}
                curves[t]["round_end"] = int(c["round_end_" + t])
    for t in tags:
        R["sets"][t] = analyze(t, curves)
        json.dump(jsonable(R), open(jpath, "w", encoding="utf-8"), indent=1)
        # the curves are cached in float64 so that a partial rerun reproduces the replication
        # statistics of a full run exactly
        np.savez_compressed(npath, **{"%s_%s" % (k, tg): (np.asarray(v, np.float64) if k != "round_end" else np.int64(v))
                                      for tg, cv in curves.items() for k, v in cv.items()})
    replication(curves, R)
    json.dump(jsonable(R), open(jpath, "w", encoding="utf-8"), indent=1)
    print(write_md(R))
    print("Result : results/RESULTS_masked_eval.md\nNumbers: results/_masked_eval.json\nCurves : results/_masked_ttest.npz")


if __name__ == "__main__":
    main()
