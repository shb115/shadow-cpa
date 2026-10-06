# -*- coding: utf-8 -*-
"""
Unprotected Shadow-32 at three clock phases: the Round-1 attack and its trace count at a
clock phase chosen without the criterion of Section 4.1 (the sentence of Section 4.1 on the
phase chosen without the criterion).

Data (data/shadow32_fixedkey/, 2,048 traces of 12,500 samples each, the same firmware image
shadow32_nop at -O0 with the round keys 0D 3B 60 33 ..., the same plaintext sequence):
  s32_ref_12500.npz                       the set of the paper; phase selected by the criterion
                                          of Section 4.1 (`phase` = 'seekclip')
  s32_shadow32_O0_fixedphase_12500.npz    the clock phase found at power-on, no selection
                                          (`phase` = 'fixed (no phase selection)'); it happened
                                          to be a phase at which samples reach the largest
                                          ADC value
  s32_shadow32_O0_noclipphase_12500.npz   a phase at which no sample reaches the largest ADC
                                          value (`phase` = 'noclip (|trace|<=0.47) @try1')

For each set the script reports:
  1. the amplitude: largest and smallest value, fraction of samples at the positive rail of
     the ADC (v >= 0.4959) over all samples and within Rounds 1 to 4, whether the negative
     rail is reached, and the number of traces at the rail at the four Round-1 peak samples;
  2. the round structure found without the key (round_structure.py);
  3. Algorithm 1 on all 2,048 traces (cpa_shadow32_12500.recover_fullkey): the recovered
     RK1..RK4 against the stored round keys and, for the Round-1 CPAs h0, h1, h2 and h3,
     |rho| of the correct candidate at its peak sample, its rank among the 256 values and
     the best wrong representative; the decision on D;
  4. the success rate against the number of traces restricted to Round 1, with the
     evaluation of Section 4.6 (success_rate.py): disjoint contiguous subsets of the set,
     min(2048/N, 20) per point; each Round-1 CPA with the true values of the earlier stages,
     ranked among the 256 values with alpha = +1; the decision on D from the subset's own h0
     CPA; the joint event is that the decision returns the true RK1_0 with alpha = +1 and
     the four CPAs rank the correct candidate first; the first N from which the joint rate
     stays at 1.0.  The ranking rule of cpa_shadow32_12500.py (alpha-signed peak) is
     evaluated on the same subsets as a check;
  5. the signal-to-noise ratio of the h0 leakage: the variance of the class means over the
     mean within-class variance of the traces grouped by HW(s0), s0 = h0 xor RK1_0,
     maximum over Round 1, for the classes with more than five traces (and for all nine);
and the ratios of the SNR between the phases.  The plaintext and round-key arrays are
checked to be identical across the three sets.

Usage :  python phase_compare.py          (about three minutes)
Output:  results/RESULTS_phase_compare.md, results/_phase_compare.json
"""
import os, sys, json, time
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from round_structure import round_structure, round_interval
from cpa_shadow32_12500 import recover_fullkey, rank_of, F8, hx
from success_rate import corr, events_of, r1_ranks, decide

DATA = os.path.join(HERE, "..", "data", "shadow32_fixedkey")
OUT = os.path.join(HERE, "..", "results")
SETS = [("selected", "selected phase (the paper's set)", "s32_ref_12500.npz"),
        ("fixed", "phase at power-on, not selected", "s32_shadow32_O0_fixedphase_12500.npz"),
        ("noclip", "phase at which no sample reaches the largest value", "s32_shadow32_O0_noclipphase_12500.npz")]
CLIP = 0.4959                     # positive rail, as in trace_stats.py
NEG = -0.5                        # smallest code of the ADC
NLIST = [16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 2048]
MAXREP = 20
_PC = np.array([bin(i).count("1") for i in range(256)], np.float64)
R1 = [("R1k0", "h0", 0), ("R1k1", "h1", 1), ("R1k2", "h2", 2), ("R1k3", "h3", 3)]


def first_n(flags):
    for j in range(len(NLIST)):
        if all(flags[j:]):
            return NLIST[j]
    return None


def signed_peak_rank1(C, ok):
    """cpa_shadow32_12500 rule: alpha-signed peak of every representative (alpha = +1),
    the 256 values scored, rank 1 of the value ok?"""
    idx = np.argmax(np.abs(C), axis=1)
    sp = C[np.arange(C.shape[0]), idx]
    s = np.concatenate([sp, (-sp)[::-1]])
    return bool(np.argmax(s) == ok)


def analyze(key, label, fn):
    t0 = time.time()
    d = np.load(os.path.join(DATA, fn))
    raw = d["traces"]
    pt = d["pt"]
    rk = [int(x) for x in d["rk"]]
    N, S = raw.shape
    res = dict(label=label, file=fn, N=int(N), samples=int(S),
               phase=str(d["phase"]) if "phase" in d.files else None,
               firmware=str(d["firmware"]) if "firmware" in d.files else None,
               version=str(d["version"]) if "version" in d.files else None,
               rk_round1=hx(rk[:4]))
    tr = raw.astype(np.float64)
    at_max = raw.astype(np.float32) >= CLIP
    P, b0 = round_structure(tr)
    a1, b1 = round_interval(1, P, b0, S)
    a4, b4 = b0, min(S, b0 + 4 * P)
    res["round_structure"] = dict(period=int(P), boundary=int(b0), round1=[int(a1), int(b1)], rounds1to4=[int(a4), int(b4)])
    res["amplitude"] = dict(max=float(raw.max()), min=float(raw.min()),
                            frac_at_rail_all=float(at_max.mean()), frac_at_rail_rounds1to4=float(at_max[:, a4:b4].mean()),
                            frac_at_rail_round1=float(at_max[:, a1:b1].mean()),
                            traces_with_a_rail_sample=int(at_max.any(1).sum()),
                            negative_rail_reached=bool((raw.astype(np.float32) <= NEG).any()))
    print("  [%s] %d x %d, P = %d, b0 = %d, max %.4f, min %.4f, at the rail %.4f of all samples (%.4f in Rounds 1-4)"
          % (key, N, S, P, b0, res["amplitude"]["max"], res["amplitude"]["min"],
             res["amplitude"]["frac_at_rail_all"], res["amplitude"]["frac_at_rail_rounds1to4"]), flush=True)

    # Algorithm 1 on all traces
    rec, alpha, pk, ps, rs, cpas = recover_fullkey(tr, pt)
    by = {cp["tag"]: cp for cp in cpas}
    dec = cpas[0]["decision"]
    att = dict(recovered=hx(rec), reference=hx(rk[:16]), matching_bytes=int(sum(a == b for a, b in zip(rec, rk[:16]))),
               success=bool(rec == rk[:16]), alpha=float(alpha), noise_level=4.5 / np.sqrt(N),
               decision=dict(pair=[int(dec["pair"][0]), int(dec["pair"][1])], p=int(dec["p"]), P2=float(dec["P2"]),
                             P2s=float(dec["P2s"]), D=float(dec["D"])),
               round1={})
    for tag, h, i in R1:
        score = by[tag]["score"]
        ok = rk[i]
        others = [abs(score[v]) for v in range(256) if v not in (ok, ok ^ 0xFF)]
        att["round1"][h] = dict(rho_correct=float(abs(score[ok])), sample=int(ps[tag]) if rec[i] == ok else None,
                                rank256=rank_of(score, ok), best_wrong=float(max(others)),
                                traces_at_rail_at_peak=int(at_max[:, ps[tag]].sum()) if rec[i] == ok else None)
    att["h2star_max_rho"] = float(pk["R1k2s"])
    res["algorithm1"] = att
    print("      recovered %s (%s), D %+.3f; Round 1: %s" % (
        att["recovered"], "16/16" if att["success"] else "FAIL", att["decision"]["D"],
        ", ".join("%s %.3f @%s" % (h, att["round1"][h]["rho_correct"], att["round1"][h]["sample"]) for _, h, _ in R1)), flush=True)

    # SNR of the h0 leakage over Round 1
    L0, L1 = pt[:, 0].astype(np.int64), pt[:, 1].astype(np.int64)
    s0 = (F8(L0) ^ L1 ^ rk[0]) & 0xFF
    hw = _PC[s0].astype(int)
    counts = [int((hw == c).sum()) for c in range(9)]
    W = tr[:, a1:b1]
    snr = {}
    for name, cls in (("classes_with_more_than_5_traces", [c for c in range(9) if counts[c] > 5]),
                      ("all_classes", [c for c in range(9) if counts[c] > 1])):
        means = np.array([W[hw == c].mean(0) for c in cls])
        vars_ = np.array([W[hw == c].var(0) for c in cls])
        v = means.var(0) / np.maximum(vars_.mean(0), 1e-30)
        snr[name] = dict(classes=cls, max=float(v.max()), at=int(a1 + v.argmax()))
    res["snr_h0"] = dict(class_counts=counts, **snr)
    print("      SNR(h0) %.2f @%d (classes > 5 traces), %.2f @%d (all classes)" % (
        snr["classes_with_more_than_5_traces"]["max"], snr["classes_with_more_than_5_traces"]["at"],
        snr["all_classes"]["max"], snr["all_classes"]["at"]), flush=True)

    # success rate restricted to Round 1, evaluation of Section 4.6
    ev, h0, L0 = events_of(pt, rk)
    ev = ev[:4]
    sr = []
    for n in NLIST:
        nsub = min(N // n, MAXREP)
        cnt = np.zeros(4, int); cnt_sp = np.zeros(4, int); dec_ok = 0; pair_ok = 0; joint = 0; joint_sp = 0
        for t in range(nsub):
            sl = slice(t * n, (t + 1) * n)
            ranks = []; sp_ok = []
            for i, e in enumerate(ev):
                C = corr(e["H"][sl], W[sl])
                ranks.append(r1_ranks(C, e["ok"])[0] == 1)
                sp_ok.append(signed_peak_rank1(C, e["ok"]))
                if i == 0:
                    C0 = C
            g, chosen, alpha_est, D = decide(C0, h0, L0, W[sl], sl)
            d_ok = (chosen == rk[0] and alpha_est == 1)
            cnt += np.array(ranks, int); cnt_sp += np.array(sp_ok, int)
            dec_ok += int(d_ok); pair_ok += int(rk[0] in (g, g ^ 0xFF))
            joint += int(all(ranks) and d_ok); joint_sp += int(all(sp_ok) and d_ok)
        sr.append(dict(N=n, subsets=nsub, RK1_0=int(cnt[0]), RK1_1=int(cnt[1]), RK1_2=int(cnt[2]), RK1_3=int(cnt[3]),
                       pair=pair_ok, decision=dec_ok, joint=joint, joint_signed_peak_rule=joint_sp,
                       per_subkey_signed_peak_rule=[int(x) for x in cnt_sp]))
        print("      N = %4d, %2d subsets: RK1_0..3 %s, decision %d, joint %d (signed-peak rule %d)" % (
            n, nsub, cnt.tolist(), dec_ok, joint, joint_sp), flush=True)
    res["success_rate_round1"] = sr
    res["first_N"] = dict(joint=first_n([e["joint"] == e["subsets"] for e in sr]),
                          joint_signed_peak_rule=first_n([e["joint_signed_peak_rule"] == e["subsets"] for e in sr]),
                          decision=first_n([e["decision"] == e["subsets"] for e in sr]),
                          **{k: first_n([e[k] == e["subsets"] for e in sr]) for k in ("RK1_0", "RK1_1", "RK1_2", "RK1_3")})
    print("      joint rate 1.0 from N = %s (signed-peak rule %s), decision from %s, %.0f s" % (
        res["first_N"]["joint"], res["first_N"]["joint_signed_peak_rule"], res["first_N"]["decision"], time.time() - t0), flush=True)
    return res, pt, np.asarray(d["rk"])


def write_md(R):
    keys = [k for k, _, _ in SETS]
    S = R["sets"]
    L = ["# Unprotected Shadow-32 at three clock phases: the Round-1 attack (Section 4.1)\n",
         "Traces: `data/shadow32_fixedkey/`, 2,048 traces of 12,500 samples per set, the same firmware image "
         "(`shadow32_nop`, -O0) and the same plaintext sequence; round key `0D 3B 60 33`. Plaintext and round-key "
         "arrays identical across the sets: %s. ADC rail = v >= %.4f (largest code 0.4961); 1 sample = 1 cycle.\n"
         % ("yes" if R["pt_and_rk_identical"] else "NO", CLIP),
         "## 1. Sets, amplitude and round structure\n",
         "| Set | File | `phase` field | max | min | At the rail, all samples | At the rail, Rounds 1-4 | Negative rail | Period, boundary | Round-1 window |",
         "|---|---|---|---:|---:|---:|---:|---|---|---|"]
    for k in keys:
        r = S[k]; a = r["amplitude"]; rs = r["round_structure"]
        L.append("| %s | `%s` | `%s` | %.4f | %.4f | %.4f | %.4f | %s | %d, %d | [%d, %d) |" % (
            r["label"], r["file"], r["phase"], a["max"], a["min"], a["frac_at_rail_all"], a["frac_at_rail_rounds1to4"],
            "reached" if a["negative_rail_reached"] else "never reached", rs["period"], rs["boundary"], rs["round1"][0], rs["round1"][1]))
    L += ["", "## 2. Algorithm 1 on all 2,048 traces\n",
          "Round-1 CPAs: |rho| of the correct candidate at its peak sample, its rank among the 256 values "
          "(alpha-signed score), the best wrong representative; noise level 4.5/sqrt(2048) = %.4f.\n" % (4.5 / np.sqrt(2048)),
          "| Set | Recovered RK1..RK4 | h0 | h1 | h2 | h3 | Best wrong (h0, h1, h2, h3) | Decision: pair, p, max\\|rho\\| h2, h2*, D | Traces at the rail at the four peaks |",
          "|---|---|---|---|---|---|---|---|---:|"]
    for k in keys:
        r = S[k]; a = r["algorithm1"]; d = a["decision"]
        cells = ["%.3f @ %s [rank %d]" % (a["round1"][h]["rho_correct"], a["round1"][h]["sample"], a["round1"][h]["rank256"]) for _, h, _ in R1]
        L.append("| %s | `%s` (%s) | %s | %s | {%02X, %02X}, %02X, %.3f, %.3f, %+.3f | %d |" % (
            r["label"], a["recovered"], "16/16" if a["success"] else "%d/16" % a["matching_bytes"], " | ".join(cells),
            ", ".join("%.2f" % a["round1"][h]["best_wrong"] for _, h, _ in R1),
            d["pair"][0], d["pair"][1], d["p"], d["P2"], d["P2s"], d["D"],
            sum(a["round1"][h]["traces_at_rail_at_peak"] or 0 for _, h, _ in R1)))
    L += ["", "## 3. Success rate restricted to Round 1 (evaluation of Section 4.6)\n",
          "Disjoint contiguous subsets, min(2048/N, 20) per point. Joint = the decision on D returns the true RK1_0 "
          "with alpha = +1 and the four Round-1 CPAs, each with the true earlier values, rank the correct candidate "
          "first among the 256 values (rule of success_rate.py: maximum over the samples of alpha rho(t)). The last "
          "column applies the ranking rule of cpa_shadow32_12500.py (alpha-signed peak) on the same subsets.\n",
          "| Set | N | Subsets | RK1_0 | RK1_1 | RK1_2 | RK1_3 | Pair | Decision | Joint | Joint, signed-peak rule |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k in keys:
        for e in S[k]["success_rate_round1"]:
            L.append("| %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d |" % (
                S[k]["label"], e["N"], e["subsets"], e["RK1_0"], e["RK1_1"], e["RK1_2"], e["RK1_3"], e["pair"], e["decision"],
                e["joint"], e["joint_signed_peak_rule"]))
    L += ["", "First N from which the rate stays at 1.0 for every larger N:\n",
          "| Set | Joint | Joint, signed-peak rule | Decision | RK1_0 | RK1_1 | RK1_2 | RK1_3 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in keys:
        f = S[k]["first_N"]
        L.append("| %s | **%s** | %s | %s | %s | %s | %s | %s |" % (S[k]["label"], f["joint"], f["joint_signed_peak_rule"], f["decision"],
                                                                 f["RK1_0"], f["RK1_1"], f["RK1_2"], f["RK1_3"]))
    L += ["", "## 4. Signal-to-noise ratio of the h0 leakage over Round 1\n",
          "Variance of the class means over the mean within-class variance, traces grouped by HW(s0), "
          "s0 = h0 xor RK1_0; class counts %s.\n" % S[keys[0]]["snr_h0"]["class_counts"],
          "| Set | SNR, classes with more than 5 traces (at sample) | SNR, all nine classes (at sample) |", "|---|---|---|"]
    for k in keys:
        s = S[k]["snr_h0"]
        L.append("| %s | %.2f (%d) | %.2f (%d) |" % (S[k]["label"], s["classes_with_more_than_5_traces"]["max"], s["classes_with_more_than_5_traces"]["at"],
                                                   s["all_classes"]["max"], s["all_classes"]["at"]))
    rr = R["snr_ratio"]
    L += ["", "- SNR ratio, classes with more than 5 traces: selected / non-clipping = %.2f, power-on / non-clipping = %.2f "
          "(all nine classes: %.2f, %.2f)" % (rr["selected_over_noclip"], rr["fixed_over_noclip"], rr["selected_over_noclip_all"], rr["fixed_over_noclip_all"]),
          "- Correct-candidate |rho| of the four Round-1 CPAs: %s" % "; ".join(
              "%s %.2f to %.2f" % (S[k]["label"], min(S[k]["algorithm1"]["round1"][h]["rho_correct"] for _, h, _ in R1),
                                   max(S[k]["algorithm1"]["round1"][h]["rho_correct"] for _, h, _ in R1)) for k in keys),
          "- Joint Round-1 success rate 1.0 from: %s" % "; ".join("%s %s traces" % (S[k]["label"], S[k]["first_N"]["joint"]) for k in keys), ""]
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "RESULTS_phase_compare.md"), "w", encoding="utf-8").write(txt)
    return txt


def main():
    R = dict(sets={}, nlist=NLIST, maxrep=MAXREP, clip=CLIP)
    pts, rks = [], []
    for key, label, fn in SETS:
        r, pt, rk = analyze(key, label, fn)
        R["sets"][key] = r; pts.append(pt); rks.append(rk)
    R["pt_and_rk_identical"] = bool(all(np.array_equal(pts[0], p) for p in pts) and all(np.array_equal(rks[0], k) for k in rks))
    s = {k: R["sets"][k]["snr_h0"] for k in R["sets"]}
    R["snr_ratio"] = dict(
        selected_over_noclip=s["selected"]["classes_with_more_than_5_traces"]["max"] / s["noclip"]["classes_with_more_than_5_traces"]["max"],
        fixed_over_noclip=s["fixed"]["classes_with_more_than_5_traces"]["max"] / s["noclip"]["classes_with_more_than_5_traces"]["max"],
        selected_over_noclip_all=s["selected"]["all_classes"]["max"] / s["noclip"]["all_classes"]["max"],
        fixed_over_noclip_all=s["fixed"]["all_classes"]["max"] / s["noclip"]["all_classes"]["max"])
    json.dump(R, open(os.path.join(OUT, "_phase_compare.json"), "w", encoding="utf-8"), indent=1)
    print(write_md(R))
    print("Result : results/RESULTS_phase_compare.md\nNumbers: results/_phase_compare.json")


if __name__ == "__main__":
    main()
