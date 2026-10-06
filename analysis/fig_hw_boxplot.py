# -*- coding: utf-8 -*-
"""
Fig. 1 of the paper: measured power grouped by the Hamming weight of the register value
(Section 2.1), and the statistics behind it.

Data: data/hwchar/fig1_lock_tbl1_1000.npz, 9,000 traces of 600 samples, acquired with
  firmware/hwchar/hwchar_tbl.c (method 1) and capture/capture_fig1_tbl.py.  Each byte value
  v is loaded from an identity table in RAM (T[i] = i, aligned to 256 bytes, so the low byte
  of the address equals v as well) into the register r0, cleared to zero beforehand, by
  `ldrb r0, [r1, r2]`; the Hamming distance of the transition is therefore HW(v).  The
  instruction sequence between trigger_high and trigger_low is fixed in inline assembly:
  r0 = r1 = r2 = 0, r1 = &T; 100 NOPs; ldrb r2,[p] (0 -> v); 100 NOPs; ldrb r0,[r1,r2]
  (0 -> T[v] = v, the measured load); 100 NOPs; r0 = r1 = r2 = 0; 20 NOPs.  1,000 traces per
  Hamming weight 0..8, the values of one weight almost equally often, in random order; the
  clock phase is locked to the template data/hwchar/phase_template.npz, the phase of
  Section 4.1 at which a probe trace reaches 98 % of the ADC full scale.

The script checks the metadata (hw = HW(value), index = value, 1,000 traces per weight),
computes rho(HW, power) at every sample and locates the measured load as the sample of the
largest |rho| (255; the two other events, ldrb r2 at 152 and the clearing of r0 at 358,
are reported as well), and at that sample reports the median, mean and standard deviation
per weight, the slope and R^2 of a line through the per-weight means, rho and R^2 over all
traces, the number of traces at the largest ADC value, and the whisker extents of the box
plot.  The figure uses gray boxes, a red median line, whiskers at 1.5 IQR and no fliers.

Usage :  python fig_hw_boxplot.py
Output:  figures/hw_boxplot.pdf (+ .png), results/RESULTS_hwchar.md, results/_hwchar.json
"""
import os, sys, json
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
NPZ = os.path.join(HERE, "..", "data", "hwchar", "fig1_lock_tbl1_1000.npz")
FIG = os.path.join(HERE, "..", "figures")
OUT = os.path.join(HERE, "..", "results")
os.makedirs(FIG, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
ADC_MAX = 127.0 / 256.0          # largest code of the ADC
HW = np.array([bin(v).count("1") for v in range(256)])


def main():
    d = np.load(NPZ)
    tr = d["traces"]                                  # float16 (9000, 600)
    value = d["value"].astype(int)
    hw = d["hw"].astype(int)
    index = d["index"].astype(int)
    N, S = tr.shape
    meta = {k: (d[k].tolist() if d[k].ndim else d[k].item()) for k in d.files if k not in ("traces", "value", "hw", "index", "rand")}
    R = dict(file=os.path.basename(NPZ), n_traces=int(N), n_samples=int(S), dtype=str(tr.dtype), meta=meta,
             hw_field_equals_HW_of_value=bool(np.array_equal(HW[value], hw)),
             index_equals_value=bool(np.array_equal(index, value)),
             traces_per_hw=np.bincount(hw, minlength=9).tolist())
    cv = np.bincount(value, minlength=256)
    R["traces_per_value_by_hw"] = {k: dict(values=int((HW == k).sum()), min=int(cv[HW == k].min()), max=int(cv[HW == k].max())) for k in range(9)}

    # rho(HW, power) at every sample
    x = hw.astype(np.float64)
    xc = x - x.mean()
    sxx = float((xc ** 2).sum())
    rho = np.zeros(S)
    for lo in range(0, S, 100):
        T = tr[:, lo:lo + 100].astype(np.float64)
        Tc = T - T.mean(0)
        den = np.sqrt((Tc ** 2).sum(0) * sxx)
        den[den == 0] = np.inf                        # constant columns (every trace at the rail)
        rho[lo:lo + 100] = (Tc * xc[:, None]).sum(0) / den
    s0 = int(np.argmax(np.abs(rho)))

    def near(c, w=15):
        lo, hi = max(0, c - w), min(S, c + w + 1)
        return int(lo + np.argmax(np.abs(rho[lo:hi])))
    ev = dict(ldrb_r2=near(152), ldrb_r0_measured=near(255), movs_r0_clear=near(358))
    R["rho"] = dict(sample_of_max_abs_rho=s0, rho_at_max=float(rho[s0]),
                    events={k: dict(sample=v, rho=float(rho[v])) for k, v in ev.items()},
                    samples_with_abs_rho_over_0p5=[[int(i), round(float(rho[i]), 4)] for i in np.where(np.abs(rho) > 0.5)[0]])

    # statistics at the measured sample
    y = tr[:, s0].astype(np.float64)
    data = [y[hw == k] for k in range(9)]
    med = [float(np.median(v)) for v in data]
    mean = [float(v.mean()) for v in data]
    sd = [float(v.std(ddof=1)) for v in data]
    b, a = np.polyfit(np.arange(9), mean, 1)
    r2_means = float(np.corrcoef(np.arange(9), mean)[0, 1] ** 2)
    rho_all = float(np.corrcoef(x, y)[0, 1])
    col_at_max = (tr.astype(np.float32) >= ADC_MAX - 1e-6).sum(0)
    whisk = []
    for v in data:
        v = np.sort(v)
        q1, q3 = np.percentile(v, [25, 75])
        lo_w = v[v >= q1 - 1.5 * (q3 - q1)].min()
        hi_w = v[v <= q3 + 1.5 * (q3 - q1)].max()
        whisk.append(dict(lo=float(lo_w), hi=float(hi_w), q1=float(q1), q3=float(q3), hidden_fliers=int(((v < lo_w) | (v > hi_w)).sum())))
    R["at_sample"] = dict(sample=s0, median=med, mean=mean, sd=sd,
                          median_strictly_increasing=bool(np.all(np.diff(med) > 0)),
                          mean_strictly_increasing=bool(np.all(np.diff(mean) > 0)),
                          slope_of_means_per_hw=float(b), intercept=float(a), r2_of_means=r2_means,
                          rho_all_traces=rho_all, r2_all_traces=rho_all ** 2,
                          traces_at_adc_max=int(col_at_max[s0]), max_value=float(y.max()),
                          whiskers_1p5_iqr=whisk)
    R["adc"] = dict(adc_max=ADC_MAX, trace_max=float(tr.max()), trace_min=float(tr.min()),
                    samples_at_adc_max_in_every_trace=[int(i) for i in np.where(col_at_max == N)[0]],
                    samples_at_adc_max_in_some_traces={int(i): int(col_at_max[i]) for i in np.where((col_at_max > 0) & (col_at_max < N))[0]},
                    traces_at_adc_max_at_sample_before=int(col_at_max[s0 - 1]))

    # the figure
    plt.rcdefaults()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.boxplot(data, positions=range(9), widths=0.5, patch_artist=True, showfliers=False,
               medianprops=dict(color="red", linewidth=1.5),
               boxprops=dict(facecolor="#e0e0e0", edgecolor="black", linewidth=1.0),
               whiskerprops=dict(color="black", linewidth=1.0),
               capprops=dict(color="black", linewidth=1.0))
    ax.set_xticks(range(9))
    ax.set_xticklabels([str(k) for k in range(9)])
    ax.set_xlabel("Hamming weight")
    ax.set_ylabel("Power consumption")
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hw_boxplot.pdf"))
    fig.savefig(os.path.join(FIG, "hw_boxplot.png"), dpi=150)
    plt.close(fig)

    json.dump(R, open(os.path.join(OUT, "_hwchar.json"), "w", encoding="utf-8"), indent=1)
    A = R["at_sample"]
    L = ["# Fig. 1: measured power against the Hamming weight of the register value (Section 2.1)\n",
         "Traces: `data/hwchar/fig1_lock_tbl1_1000.npz`, %d x %d, firmware `firmware/hwchar/hwchar_tbl.c` (identity table "
         "in RAM, `ldrb r0,[r1,r2]` into r0 cleared to zero), phase `%s`.\n" % (N, S, meta.get("phase")),
         "- metadata: hw = HW(value) %s, index = value %s, traces per Hamming weight %s" % (
             R["hw_field_equals_HW_of_value"], R["index_equals_value"], R["traces_per_hw"]),
         "- traces per value within a weight (min, max): %s" % ", ".join(
             "HW %d: %d values, %d to %d" % (k, v["values"], v["min"], v["max"]) for k, v in R["traces_per_value_by_hw"].items()),
         "- rho(HW, power) is largest at sample %d, rho = %+.4f (the measured load); the other events: ldrb r2 at %d (%+.3f), "
         "clearing of r0 at %d (%+.3f)" % (s0, rho[s0], ev["ldrb_r2"], rho[ev["ldrb_r2"]], ev["movs_r0_clear"], rho[ev["movs_r0_clear"]]),
         "- samples with |rho| > 0.5: %s" % ", ".join("%d (%+.3f)" % (i, v) for i, v in R["rho"]["samples_with_abs_rho_over_0p5"]),
         "", "## Sample %d\n" % s0,
         "| HW | traces | median | mean | sd | whisker low | Q1 | Q3 | whisker high | hidden fliers |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k in range(9):
        w = whisk[k]
        L.append("| %d | %d | %.4f | %.4f | %.4f | %.4f | %.4f | %.4f | %.4f | %d |" % (
            k, R["traces_per_hw"][k], med[k], mean[k], sd[k], w["lo"], w["q1"], w["q3"], w["hi"], w["hidden_fliers"]))
    L += ["", "- medians strictly increasing with the Hamming weight: %s; means: %s" % (A["median_strictly_increasing"], A["mean_strictly_increasing"]),
          "- line through the per-weight means: slope %+.5f per unit of Hamming weight, R^2 = %.4f" % (b, r2_means),
          "- over all %d traces: rho = %+.4f, R^2 = %.3f; the sign of the slope is %s, so alpha is positive on this device" % (
              N, rho_all, rho_all ** 2, "positive" if b > 0 else "negative"),
          "- traces at the largest ADC value (%.4f) at sample %d: %d (largest value there %.4f)" % (ADC_MAX, s0, A["traces_at_adc_max"], A["max_value"]),
          "- samples at the largest ADC value in every trace: %s; in some traces: %s" % (
              R["adc"]["samples_at_adc_max_in_every_trace"],
              ", ".join("%d (%d)" % (i, n) for i, n in R["adc"]["samples_at_adc_max_in_some_traces"].items())),
          "- box plot: 1.5 IQR whiskers, fliers hidden; figures/hw_boxplot.pdf", ""]
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "RESULTS_hwchar.md"), "w", encoding="utf-8").write(txt)
    print(txt)
    print("Figure : figures/hw_boxplot.pdf\nResult : results/RESULTS_hwchar.md\nNumbers: results/_hwchar.json")


if __name__ == "__main__":
    main()
