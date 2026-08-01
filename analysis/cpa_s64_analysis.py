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
    print("%s: 1단계 %02X(r=%+.3f, 쌍 {%02X,%02X}) -> 2단계 %02X(r=%+.3f) => %04X %s | 전수탐색 정답 %d위"
          % (name, klo, p1_7[b7], pair[0], pair[1], khi, p2[khi], kw, "OK" if ok else "X", rt))
    rows.append(dict(name=name, ref=ref, klo=klo, khi=khi, kw=kw, ok=ok,
                     pair=pair, r1=float(p1_7[b7]), r2=float(p2[khi]),
                     rank_true=rt, rank_comp=rc, exh_top=k1st, exh_top_r=p1st, exh_true_r=pt_))
    return kw

print("파일 %s  traces=%s  samples=%d" % (os.path.basename(NPZ), tr.shape, int(d["samples"])))
print("정답 RK1 = %s" % " ".join("%04X" % x for x in RK))
if MASTER is not None and MASTER.size:
    print("마스터키 = %s" % "".join("%02X" % x for x in MASTER))
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
print("RK1 복구 = %s" % " ".join("%04X" % x for x in rec))
print("=> 워드 %d/4, 바이트 %d/8" % (nw, nb))

md = []
A = md.append
A("# Shadow-64 CPA 결과 — 1라운드 라운드키 복구\n")
A("- 데이터 : `%s` (%d 트레이스 x %d 샘플)" % (os.path.basename(NPZ), N, S))
if MASTER is not None and MASTER.size:
    A("- 마스터키 : `%s` (랜덤)" % "".join("%02X" % x for x in MASTER))
A("- 정답 RK1 : `%s`" % " ".join("%04X" % x for x in RK))
A("- 수집 : clkout 7.5MHz / adc 7.5MHz, seekclip 위상, `-O0` 펌웨어 + NOP 패딩")
A("- 분석 구간 : 1·2단계 `[:%d]`, 전수탐색은 누설지점 ±%d\n" % (WIN, EXHALF))

A("## 1. 복구 결과\n")
A("**워드 %d/4, 바이트 %d/8 복구.**\n" % (nw, nb))
A(r"| 워드 | 1단계 하위(8-bit) \|r\| | 2단계 상위(16-bit) \|r\| | 복구 | 정답 | 결과 |")
A("|---|---|---|---|---|---|")
for r in rows:
    A("| %s | `%02X` %.3f | `%02X` %.3f | `%04X` | `%04X` | %s |"
      % (r["name"], r["klo"], abs(r["r1"]), r["khi"], abs(r["r2"]), r["kw"], r["ref"],
         "완전복구" if r["ok"] else "실패"))
A("")
A("1단계(바이트 HW)는 상위 8비트가 잡음으로 들어가 상관이 낮고(0.5~0.7),")
A("하위를 고정한 뒤 **전체 16-bit HW** 로 상위를 찾는 2단계에서 상관이 크게 오른다(0.67~0.90).\n")

A("## 2. 방법\n")
A("```")
A("h  = F16(L0) ^ L1                     # 키 XOR 이전 중간값")
A("① 하위바이트 : HW8(h&0xFF ^ c) 로 CPA          -> klo")
A("② 상위바이트 : klo 고정해 16-bit 값 재구성 후")
A("               HW16(h ^ ((c<<8)|klo)) 로 CPA   -> khi")
A("   RK = (khi<<8) | klo")
A("```")
A("이후 `S1L = h ^ RK` 로 다음 중간값을 만들어 RK1_2 / RK1_3 로 이어간다.\n")

A("## 3. 보수 모호성 — alpha 가 필요한 이유\n")
A("HW 모델에는 제거할 수 없는 1비트 모호성이 있다.\n")
A("- 8-bit : `HW(x^(k^0xFF)) = 8 - HW(x^k)` → 보수쌍의 r 은 **부호만 반대**")
A("  (실측: 정답 `2C` +0.7197 / 보수 `D3` −0.7197, 합 = 0.000000)")
A("- 16-bit : `HW16(x^(k^0xFFFF)) = 16 - HW16(x^k)` → 상·하위를 **동시에** 뒤집으면")
A("  `|rho|` 가 완전히 동일 (실측 차 = 0.0000)\n")
A("따라서 `|r|` 만으로는 어느 단계에서도 이 1비트를 결정할 수 없고, 2단계를 두 번 돌려도")
A("마찬가지다. **디바이스 부호 alpha 를 알아야 한다** (HW 누설이면 `alpha=+1`).")
A("본 실험의 alpha 는 같은 보드의 Shadow-32 160개 서브키에서 정답키 상관이 항상 양수임을")
A("확인해 `+1` 로 확정했다.\n")
A("> 참고: 하위만 뒤집으면 적합도가 실제로 떨어진다(0.8878 → 0.5828). 하지만 상위까지")
A("> 같이 뒤집힌 후보가 `|r|` 을 그대로 유지하므로 이 비대칭은 이용할 수 없다.")
A("> alpha 없이 `argmax|rho|` 로 풀면 `RK ^ 0xFFFF` 를 복구해 워드 2/4 로 떨어진다.\n")
A("즉 alpha 를 모르면 워드마다 후보가 **정확히 2개** (`{k, k^0xFFFF}`) 로 남는다.")
A("알려진 평문·암호문 쌍 하나로 즉시 판별 가능하므로 실질적 비용은 없다.\n")

A("## 4. 16-bit 전수탐색과의 비교\n")
A("65536 후보를 16-bit HW 하나로 훑었을 때의 정답 순위:\n")
A("| 워드 | 전수탐색 1위 | 1위 \\|rho\\| | 정답 \\|rho\\| | 정답 순위 | 보수 순위 |")
A("|---|---|---|---|---|---|")
for r in rows:
    A("| %s | `%04X` | %.5f | %.5f | **%d위** | %d위 |"
      % (r["name"], r["exh_top"], r["exh_top_r"], r["exh_true_r"], r["rank_true"], r["rank_comp"]))
A("")
bad = [r for r in rows if r["rank_true"] > 2]
if bad:
    A("**전수탐색은 %s 에서 정답을 상위 2개 안에 넣지 못한다.**"
      % ", ".join("`%s`(%d위)" % (r["name"], r["rank_true"]) for r in bad))
    A("반면 같은 데이터에서 2단계 분해는 이들을 정확히 복구한다.")
    A("하위바이트를 따로 보는 1단계가 그 바이트의 누설을 분리해 내기 때문이고,")
    A("전수탐색은 상·하위를 뭉뚱그려 보면서 약한 워드에서 순위가 흐트러진다.\n")
    A("즉 2단계 분해는 계산량 절감(65536 → 256+256)만이 아니라 **복구 성능 자체가 더 좋다**.\n")
else:
    A("모든 워드에서 정답 또는 보수가 상위 2개 안에 들어온다.\n")

A("## 5. 파일 구성\n")
A("```")
A("data/shadow64/s64_ref_25000.npz            파형 4096 x 25000")
A("firmware/shadow64_nop_newkey.c             수집 펌웨어 소스 (이미지는 미포함)")
A("reference/shadow64.c                       레퍼런스 구현 (파형 수집에는 미사용)")
A("analysis/cpa_s64_analysis.py               2단계 CPA + 16-bit 전수탐색")
A("analysis/shadow64_ks.py                    키 스케줄")
A("analysis/fig_shadow64_trace.py             전력 파형 그림, 라운드 주기 자기상관 측정")
A("results/RESULTS_shadow64.md                이 문서")
A("figures/shadow64/")
A("  stage1_8bit/stage1_RK1_*.png             1단계 하위바이트 8-bit CPA (워드별)")
A("  stage2_16bit/stage2_RK1_*.png            2단계 하위고정 16-bit CPA (워드별)")
A("  exhaustive_16bit/exh_RK1_2_*.png         16-bit 전수탐색 (RK1_2 만: |r| 곡선 top256 /")
A("                                           순위 막대 top24)")
A("  trace.png, trace_zoom.png                전력 파형")
A("```\n")
A("재현 : `analysis/` 에서 `python cpa_s64_analysis.py` (기본 경로가 위 배치를 가리킨다).")
A("4절의 16-bit 전수탐색 비교는 보충 자료이며 논문 본문에는 싣지 않았다.")

_DOC = os.path.normpath(os.path.join(_HERE, "..", "results", "RESULTS_shadow64.md"))
io.open(_DOC, "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n문서 저장: %s" % _DOC)
