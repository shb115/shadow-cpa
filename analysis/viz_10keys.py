# -*- coding: utf-8 -*-
# NOTE (artifact): DATA / FIGDIR repointed to the deposit layout. Nothing else changed.
import os, sys, glob
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE  = os.path.dirname(os.path.abspath(__file__))
DATA   = os.path.join(_HERE, "..", "data", "shadow32_10keys")
FIGDIR = os.path.join(_HERE, "..", "figures", "shadow32_10keys")
os.makedirs(FIGDIR, exist_ok=True)

# NOTE (artifact): FONT 8 -> 7 and bbox='tight' -> constrained_layout, so that the two
# panels keep their 3.46 in width and match the font size of the other paper figures.
FONT = 7
W_HALF, H_HALF = 3.46, 2.70
DPI  = 600
plt.rcParams.update({
    "font.size": FONT, "axes.labelsize": FONT, "axes.titlesize": FONT,
    "xtick.labelsize": FONT - 1, "ytick.labelsize": FONT - 1,
    "legend.fontsize": FONT - 1, "lines.linewidth": 1.1,
    "lines.markersize": 3.0, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "grid.linewidth": 0.4, "legend.frameon": True, "legend.framealpha": 0.9,
    "figure.constrained_layout.use": True,
    "figure.constrained_layout.h_pad": 0.01,
    "figure.constrained_layout.w_pad": 0.01,
})

HALF_SR = 40
MAXREP  = 20
NLIST   = [8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 48, 64, 96, 128, 192, 256, 512, 1024, 2048]
SHOW    = [0, 1, 2, 3]
LBL     = [r"$RK^1_0$", r"$RK^1_1$", r"$RK^1_2$", r"$RK^1_3$"]
COL     = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

def rol(v, r): return ((v << r) ^ (v >> (8 - r))) & 0xFF
def F(x):      return (rol(x, 1) & rol(x, 7)) ^ rol(x, 2)
_PC = np.array([bin(i).count('1') for i in range(256)], np.float64)
G   = np.arange(256)


def intermediates(pt, rk):
    l0, l1, r0, r1 = (pt[:, i].astype(np.int64) for i in range(4))
    out = []
    for rnd in range(4):
        k0, k1, k2, k3 = rk[4*rnd:4*rnd+4]
        s0 = F(l0) ^ l1 ^ k0
        s1 = F(r0) ^ r1 ^ k1
        out += [(F(l0) ^ l1, k0), (F(r0) ^ r1, k1), (F(s0) ^ l0, k2), (F(s1) ^ r0, k3)]
        nl1 = F(s0) ^ l0 ^ k2; nr1 = F(s1) ^ r0 ^ k3
        l0, l1, r0, r1 = s1, nl1, s0, nr1
    return out


def analyse(npz):
    d  = np.load(npz)
    tr = d["traces"].astype(np.float64)
    pt = d["pt"]; rk = [int(x) for x in d["rk"][:16]]
    inter = intermediates(pt, rk)

    rank_list = [[None]*16 for _ in NLIST]
    Tn_full = tr - tr.mean(0); Tss_full = (Tn_full**2).sum(0)
    nfull = np.zeros(16, int)

    for si, (base, ktrue) in enumerate(inter):
        h = _PC[(base ^ ktrue).astype(np.uint8)]; hn = h - h.mean()
        cc = (hn @ Tn_full) / np.sqrt((hn**2).sum() * np.maximum(Tss_full, 1e-30))
        pos = int(np.argmax(np.abs(cc)))

        H = _PC[(base[:, None] ^ G[None, :]) & 0xFF]
        aS, bS = max(0, pos-HALF_SR), min(tr.shape[1], pos+HALF_SR)
        Ws_ = tr[:, aS:bS]
        for ni, n in enumerate(NLIST):
            reps = min(len(tr) // n, MAXREP)
            rr = []
            for t in range(reps):
                sl = slice(t*n, (t+1)*n)
                Wn = Ws_[sl] - Ws_[sl].mean(0); Wq = (Wn**2).sum(0)
                Hn = H[sl] - H[sl].mean(0)
                c  = (Hn.T @ Wn) / np.sqrt(np.outer((Hn**2).sum(0), np.maximum(Wq, 1e-30)))
                pk = c.max(axis=1)
                rr.append(int(np.where(np.argsort(-pk) == ktrue)[0][0]) + 1)
            rank_list[ni][si] = rr
        nfull[si] = 1 if rank_list[-1][si][0] == 1 else 0
    return dict(rank_list=rank_list, nfull=nfull)


files = sorted(glob.glob(os.path.join(DATA, "*.npz")))
print("데이터 %d개" % len(files))
R = []
for f in files:
    r = analyse(f); R.append(r)
    print("  %s  전체트레이스 복구 %2d/16" % (os.path.basename(f), r["nfull"].sum()))

SR      = np.zeros((len(NLIST), 16))
GE      = np.zeros((len(NLIST), 16))
SR_full = np.zeros(len(NLIST))
NTRIAL  = np.zeros(len(NLIST), int)
for ni in range(len(NLIST)):
    allr = []
    for r in R:
        per = [r["rank_list"][ni][si] for si in range(16)]
        for t in range(len(per[0])):
            allr.append([per[si][t] for si in range(16)])
    A_ = np.array(allr)
    SR[ni]      = (A_ == 1).mean(axis=0)
    GE[ni]      = A_.mean(axis=0)
    SR_full[ni] = (A_ == 1).all(axis=1).mean()
    NTRIAL[ni]  = len(A_)

plt.figure(figsize=(W_HALF, H_HALF))
for j, si in enumerate(SHOW):
    plt.plot(NLIST, SR[:, si], marker='o', color=COL[j], label=LBL[j])
plt.plot(NLIST, SR_full, marker='s', color='k', ls='--', label='full 64-bit key')
plt.xscale('log'); plt.ylim([-0.03, 1.03]); plt.grid(True, alpha=0.4)
plt.xlabel('Number of traces'); plt.ylabel('Success rate')
plt.legend(loc='lower right', handlelength=1.5, borderpad=0.3, labelspacing=0.25)
plt.savefig(FIGDIR + "/viz1_success_rate.png", dpi=DPI); plt.close()

plt.figure(figsize=(W_HALF, H_HALF))
for j, si in enumerate(SHOW):
    plt.plot(NLIST, GE[:, si], marker='o', color=COL[j], label=LBL[j])
plt.xscale('log'); plt.yscale('log'); plt.grid(True, alpha=0.4, which='both')
plt.xlabel('Number of traces'); plt.ylabel('Guessing entropy')
plt.legend(loc='upper right', handlelength=1.5, borderpad=0.3, labelspacing=0.25)
plt.savefig(FIGDIR + "/viz2_guessing_entropy.png", dpi=DPI); plt.close()

print()
print(" 트레이스 | 시행 | SR RK1_0  RK1_1  RK1_2  RK1_3 | SR(full) | GE RK1_0")
for ni, n in enumerate(NLIST):
    print("   %5d  | %4d |   %.2f   %.2f   %.2f   %.2f  |   %.2f   |  %6.2f"
          % (n, NTRIAL[ni], SR[ni,0], SR[ni,1], SR[ni,2], SR[ni,3], SR_full[ni], GE[ni,0]))
first = [NLIST[ni] for ni in range(len(NLIST)) if SR_full[ni] == 1.0]
print("\nRK1~RK4 16서브키 전체 SR=1.0 최초 도달 : %s 트레이스" % (first[0] if first else "N/A"))
print("그림 2개 -> %s" % FIGDIR)
