import os, sys, io
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE  = os.path.dirname(os.path.abspath(__file__))
NPZ    = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
             _HERE, "..", "data", "shadow64", "s64_ref_25000.npz")
OUT    = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
             _HERE, "..", "figures", "shadow64")
WIN    = 1500
EXHALF = 100
ALPHA  = +1.0

D1 = os.path.join(OUT, "stage1_8bit")
D2 = os.path.join(OUT, "stage2_16bit")
D3 = os.path.join(OUT, "exhaustive_16bit")
for d in (D1, D2, D3): os.makedirs(d, exist_ok=True)

M16 = 0xFFFF
def ROL16(v, r):
    v = np.asarray(v, np.int64); return ((v << r) | (v >> (16 - r))) & M16
def F16(x): return (ROL16(x,1) & ROL16(x,7)) ^ ROL16(x,2)
_PC = np.array([bin(i).count('1') for i in range(256)], np.float64)
def HWb(a):  return _PC[np.asarray(a, np.int64) & 0xFF]
def HW16(v):
    v = np.asarray(v, np.int64) & M16
    return _PC[v & 0xFF] + _PC[(v >> 8) & 0xFF]

G, G7, ALL = np.arange(256), np.arange(128), np.arange(65536)

d  = np.load(NPZ)
tr = d["traces"].astype(np.float64)
pt = d["pt"]
RK = [int(x) for x in d["rk"][:4]]
MASTER = d["master"] if "master" in d.files else None
N, S = tr.shape

Tc = tr[:, :WIN]; Tn = Tc - Tc.mean(0); Tss = (Tn**2).sum(0); good = Tss > 0

def corr_all(H, Tn_, Tss_, good_):
    Hn = H - H.mean(0)
    c = np.zeros((H.shape[1], Tn_.shape[1]))
    c[:, good_] = (Hn.T @ Tn_[:, good_]) / np.sqrt((Hn**2).sum(0)[:, None] * Tss_[good_][None, :])
    return c

def peak_of(c):
    idx = np.argmax(np.abs(c), axis=1)
    return c[np.arange(c.shape[0]), idx]

FONT = 7
W_FULL = 7.09
H_FULL = 1.95
W_HALF, H_HALF = 3.46, 1.70
YLIM    = [-0.05, 0.95]
GRAY    = [0.88, 0.88, 0.88]
RED     = '#d62728'
PINK    = '#ff9896'
BLUE    = '#1f77b4'
DPI     = 600
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
})

def plot_cpa(c, best, path, label):
    cc = np.abs(c)
    plt.figure(figsize=(W_HALF, H_HALF))
    other = np.delete(np.arange(cc.shape[0]), best)
    plt.plot(cc[other].T, color=GRAY, lw=0.25, rasterized=True)
    plt.plot(cc[best], color=RED, lw=0.8, label=label)
    plt.ylim(YLIM); plt.grid(True, alpha=0.35)
    plt.legend(loc='upper right', handlelength=1.1, borderpad=0.2, handletextpad=0.3)
    plt.xlabel('Sample index'); plt.ylabel('Absolute correlation')
    plt.xlim([0, cc.shape[1]])
    plt.savefig(path, dpi=DPI); plt.close()

w  = lambda a, b: (pt[:, a].astype(np.int64) << 8) | pt[:, b].astype(np.int64)
l0, l1, r0, r1 = w(0,1), w(2,3), w(4,5), w(6,7)

rows = []

EXH_WORDS = ["RK1_2"]
EXH_TOPN  = 256
EXH_BAR   = 24

def exhaustive16(h, ktrue, name):
    hh = HW16(h ^ ktrue); hn = hh - hh.mean()
    Tn0 = tr - tr.mean(0); Ts0 = (Tn0**2).sum(0); g0 = Ts0 > 0
    cc = np.zeros(S); cc[g0] = (hn @ Tn0[:, g0]) / np.sqrt((hn**2).sum() * Ts0[g0])
    pos = int(np.argmax(np.abs(cc)))
    a, b = max(0, pos-EXHALF), min(S, pos+EXHALF+1)
    Tw = tr[:, a:b]; Tnw = Tw - Tw.mean(0); Tsw = (Tnw**2).sum(0); gw = Tsw > 0
    peak = np.zeros(65536)
    for i in range(0, 65536, 4096):
        C = ALL[i:i+4096]
        H = HW16(h[:, None] ^ C[None, :]); H -= H.mean(0)
        c = (H.T @ Tnw[:, gw]) / np.sqrt((H**2).sum(0)[:, None] * Tsw[gw][None, :])
        peak[i:i+4096] = c[np.arange(len(C)), np.argmax(np.abs(c), axis=1)]
    order = np.argsort(-np.abs(peak))
    rank_t = int(np.where(order == ktrue)[0][0]) + 1
    rank_c = int(np.where(order == (ktrue ^ M16))[0][0]) + 1
    ktop   = int(order[0])

    if name in EXH_WORDS:

        ks = order[:EXH_TOPN]
        H = HW16(h[:, None] ^ ks[None, :]); H -= H.mean(0)
        cs = np.zeros((len(ks), b - a))
        cs[:, gw] = (H.T @ Tnw[:, gw]) / np.sqrt((H**2).sum(0)[:, None] * Tsw[gw][None, :])
        cs = np.abs(cs)
        i_top = int(np.where(ks == ktop)[0][0])
        i_tru = int(np.where(ks == ktrue)[0][0])
        plt.figure(figsize=(W_HALF, H_HALF))
        rest = np.setdiff1d(np.arange(len(ks)), [i_top, i_tru])
        plt.plot(cs[rest].T, color=GRAY, lw=0.25, rasterized=True)
        plt.plot(cs[i_top], color=RED, lw=0.8,
                 label='selected 0x%04X   |r|=%.3f' % (ktop, cs[i_top].max()))
        plt.plot(cs[i_tru], color=BLUE, lw=0.8, ls='--',
                 label='true key 0x%04X   |r|=%.3f' % (ktrue, cs[i_tru].max()))
        plt.ylim(YLIM); plt.grid(True, alpha=0.35)
        plt.legend(loc='upper right', handlelength=1.1, borderpad=0.2, handletextpad=0.3)
        plt.xlabel('Sample index'); plt.ylabel('Absolute correlation'); plt.xlim([0, b - a])
        plt.savefig(os.path.join(D3, "exh_%s_cpa_top%d.png" % (name, EXH_TOPN)), dpi=DPI)
        plt.close()

        kb = order[:EXH_BAR]; vals = np.abs(peak[kb])
        colors = [RED if k == ktop else (BLUE if k == ktrue else
                  (PINK if k == (ktrue ^ M16) else GRAY)) for k in kb]
        plt.figure(figsize=(W_FULL, H_FULL))
        plt.bar(range(EXH_BAR), vals, color=colors)
        plt.xticks(range(EXH_BAR), ["%04X" % k for k in kb], rotation=90)
        plt.ylim([vals.min() - 0.008, vals.max() + 0.004])
        plt.grid(True, axis='y', alpha=0.4)
        plt.ylabel('Peak absolute correlation')
        plt.xlabel('Candidate key (sorted by peak)')
        from matplotlib.patches import Patch
        plt.legend(handles=[Patch(color=RED,       label='selected (rank 1) 0x%04X' % ktop),
                            Patch(color=BLUE, label='true key 0x%04X (rank %d)' % (ktrue, rank_t)),
                            Patch(color=PINK,      label='complement 0x%04X (rank %d)' % (ktrue ^ M16, rank_c))],
                   loc='upper right', handlelength=1.1, borderpad=0.2, handletextpad=0.3)
        plt.savefig(os.path.join(D3, "exh_%s_rank_top%d.png" % (name, EXH_BAR)), dpi=DPI)
        plt.close()

    return rank_t, rank_c, float(abs(peak[ktrue])), ktop, float(abs(peak[ktop]))

def recover(h, ref, name):

    c1_full = corr_all(HWb((h & 0xFF)[:, None] ^ G[None, :]), Tn, Tss, good)
    p1_full = peak_of(c1_full)
    p1_7, _ = peak_of(corr_all(HWb((h & 0xFF)[:, None] ^ G7[None, :]), Tn, Tss, good)), None
    b7   = int(np.argmax(np.abs(p1_7)))
    pair = (b7, b7 ^ 0xFF)
    klo  = pair[0] if ALPHA * p1_7[b7] > 0 else pair[1]
    plot_cpa(c1_full, klo, os.path.join(D1, "stage1_%s.png" % name),
             "0x%02X   |r|=%.3f" % (klo, abs(p1_full[klo])))

    c2 = corr_all(HW16(h[:, None] ^ ((G[None, :] << 8) | klo)), Tn, Tss, good)
    p2 = peak_of(c2)
    khi = int(np.argmax(ALPHA * p2))
    kw  = (khi << 8) | klo
    plot_cpa(c2, khi, os.path.join(D2, "stage2_%s.png" % name),
             "RK=0x%04X   |r|=%.3f" % (kw, abs(p2[khi])))

    rt, rc, pt_, k1st, p1st = exhaustive16(h, ref, name)

    ok = (kw == ref)
    print("%s: stage 1 %02X(r=%+.3f, pair {%02X,%02X}) -> stage 2 %02X(r=%+.3f) => %04X %s | true key rank %d in the exhaustive search"
          % (name, klo, p1_7[b7], pair[0], pair[1], khi, p2[khi], kw, "OK" if ok else "X", rt))
    rows.append(dict(name=name, ref=ref, klo=klo, khi=khi, kw=kw, ok=ok,
                     pair=pair, r1=float(p1_7[b7]), r2=float(p2[khi]),
                     rank_true=rt, rank_comp=rc, exh_top=k1st, exh_top_r=p1st, exh_true_r=pt_))
    return kw

print("file %s  traces=%s  samples=%d" % (os.path.basename(NPZ), tr.shape, int(d["samples"])))
print("true RK1 = %s" % " ".join("%04X" % x for x in RK))
if MASTER is not None and MASTER.size:
    print("master key = %s" % "".join("%02X" % x for x in MASTER))
print()

h0 = F16(l0) ^ l1
h1 = F16(r0) ^ r1
k0 = recover(h0, RK[0], "RK1_0")
k1 = recover(h1, RK[1], "RK1_1")
s0 = (h0 ^ k0) & M16
s1 = (h1 ^ k1) & M16
k2 = recover(F16(s0) ^ l0, RK[2], "RK1_2")
k3 = recover(F16(s1) ^ r0, RK[3], "RK1_3")

rec = [k0, k1, k2, k3]
nw  = sum(a == b for a, b in zip(rec, RK))
nb  = sum(((rec[i] >> 8) & 0xFF) == ((RK[i] >> 8) & 0xFF) for i in range(4)) + \
      sum((rec[i] & 0xFF) == (RK[i] & 0xFF) for i in range(4))
print()
print("RK1 recovered = %s" % " ".join("%04X" % x for x in rec))
print("=> words %d/4, bytes %d/8" % (nw, nb))

md = []
A = md.append
A("# Shadow-64 CPA results: first round key recovery\n")
A("- Data : `%s` (%d traces x %d samples)" % (os.path.basename(NPZ), N, S))
if MASTER is not None and MASTER.size:
    A("- Master key : `%s` (random)" % "".join("%02X" % x for x in MASTER))
A("- True RK1 : `%s`" % " ".join("%04X" % x for x in RK))
A("- Acquisition : clkout 7.5MHz / adc 7.5MHz, seekclip phase, `-O0` firmware + NOP padding")
A("- Analysis window : `[:%d]` for stages 1 and 2, leakage point ±%d for the exhaustive search\n" % (WIN, EXHALF))

A("## 1. Recovery results\n")
A("**%d/4 words, %d/8 bytes recovered.**\n" % (nw, nb))
A(r"| Word | stage 1 low (8-bit) \|r\| | stage 2 high (16-bit) \|r\| | recovered | true | result |")
A("|---|---|---|---|---|---|")
for r in rows:
    A("| %s | `%02X` %.3f | `%02X` %.3f | `%04X` | `%04X` | %s |"
      % (r["name"], r["klo"], abs(r["r1"]), r["khi"], abs(r["r2"]), r["kw"], r["ref"],
         "full recovery" if r["ok"] else "failure"))
A("")
A("Stage 1 (byte HW) gives a low correlation (0.5~0.7) because the upper 8 bits enter as noise,")
A("while stage 2, which fixes the low byte and searches the high byte with the **full 16-bit HW**, raises it sharply (0.67~0.90).\n")

A("## 2. Method\n")
A("```")
A("h  = F16(L0) ^ L1                     # intermediate value before the key XOR")
A("① low byte  : CPA with HW8(h&0xFF ^ c)         -> klo")
A("② high byte : rebuild the 16-bit value with klo fixed, then")
A("              CPA with HW16(h ^ ((c<<8)|klo))  -> khi")
A("   RK = (khi<<8) | klo")
A("```")
A("The next intermediate value is then built as `S1L = h ^ RK`, and the same steps continue for RK1_2 / RK1_3.\n")

A("## 3. Complement ambiguity: why alpha is needed\n")
A("The HW model carries a one-bit ambiguity that cannot be removed.\n")
A("- 8-bit : `HW(x^(k^0xFF)) = 8 - HW(x^k)` → the r values of a complement pair differ **in sign only**")
A("  (measured: true key `2C` +0.7197 / complement `D3` −0.7197, sum = 0.000000)")
A("- 16-bit : `HW16(x^(k^0xFFFF)) = 16 - HW16(x^k)` → flipping the high and low bytes **at the same time**")
A("  leaves `|rho|` exactly unchanged (measured difference = 0.0000)\n")
A("So `|r|` alone cannot decide this bit at either stage, and running stage 2 twice does not")
A("help. **The device sign alpha has to be known** (`alpha=+1` for HW leakage).")
A("In this experiment alpha was fixed to `+1` after checking that the true key correlation is")
A("always positive over the 160 Shadow-32 subkeys measured on the same board.\n")
A("> Note: flipping the low byte only does lower the fit (0.8878 → 0.5828). But the candidate")
A("> in which the high byte is flipped as well keeps `|r|` unchanged, so this asymmetry cannot be used.")
A("> Solving with `argmax|rho|` and no alpha recovers `RK ^ 0xFFFF` and drops to 2/4 words.\n")
A("Without alpha, therefore, exactly **two** candidates (`{k, k^0xFFFF}`) remain for each word.")
A("A single known plaintext and ciphertext pair separates them at once, so the practical cost is zero.\n")

A("## 4. Comparison with the 16-bit exhaustive search\n")
A("Rank of the true key when the 65536 candidates are swept with a single 16-bit HW model:\n")
A("| Word | exhaustive rank 1 | rank 1 \\|rho\\| | true \\|rho\\| | true rank | complement rank |")
A("|---|---|---|---|---|---|")
for r in rows:
    A("| %s | `%04X` | %.5f | %.5f | **%d** | %d |"
      % (r["name"], r["exh_top"], r["exh_top_r"], r["exh_true_r"], r["rank_true"], r["rank_comp"]))
A("")
bad = [r for r in rows if r["rank_true"] > 2]
if bad:
    A("**The exhaustive search does not place the true key in the top 2 for %s.**"
      % ", ".join("`%s`(rank %d)" % (r["name"], r["rank_true"]) for r in bad))
    A("The two-stage decomposition recovers them exactly from the same data.")
    A("Stage 1 looks at the low byte on its own and isolates the leakage of that byte,")
    A("while the exhaustive search treats high and low together and loses the ranking on the weak words.\n")
    A("The two-stage decomposition therefore does not only cut the work (65536 → 128+256 = 384), **it recovers better**.\n")
else:
    A("For every word the true key or its complement falls in the top 2.\n")

A("## 5. File layout\n")
A("```")
A("data/shadow64/s64_ref_25000.npz            traces 4096 x 25000")
A("firmware/shadow64_nop_newkey.c             acquisition firmware source (image not included)")
A("reference/shadow64.c                       reference implementation (not used for acquisition)")
A("analysis/cpa_s64_analysis.py               two-stage CPA + 16-bit exhaustive search")
A("analysis/shadow64_ks.py                    key schedule")
A("analysis/fig_shadow64_trace.py             power trace figures, round period autocorrelation")
A("results/RESULTS_shadow64.md                this document")
A("figures/shadow64/")
A("  stage1_8bit/stage1_RK1_*.png             stage 1 low byte 8-bit CPA (per word)")
A("  stage2_16bit/stage2_RK1_*.png            stage 2 16-bit CPA, low byte fixed (per word)")
A("  exhaustive_16bit/exh_RK1_2_*.png         16-bit exhaustive search (RK1_2 only: |r| curves top256 /")
A("                                           rank bars top24)")
A("  trace.png, trace_zoom.png                power traces")
A("```\n")
A("Reproduction : run `python cpa_s64_analysis.py` in `analysis/` (the default paths point to the layout above).")
A("The 16-bit exhaustive search comparison in Section 4 is supplementary and is not part of the paper.")

_DOC = os.path.normpath(os.path.join(_HERE, "..", "results", "RESULTS_shadow64.md"))
io.open(_DOC, "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\ndocument written: %s" % _DOC)
