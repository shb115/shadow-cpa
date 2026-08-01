# -*- coding: utf-8 -*-
"""
Shadow-64 전력 파형 그림 (논문 Fig. shadow64-power-trace)
============================================================================
대상 : data/shadow64/s64_ref_25000.npz  (4096 x 25000)
규격 : 노트북(cwnano-shadow32-cpa.ipynb) 의 trace 그림과 동일한 rcParams

실행 :  python fig_shadow64_trace.py
출력 :  figures/shadow64/trace.png        전체 25000 샘플
        figures/shadow64/trace_zoom.png   1라운드 부근 확대
"""
import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
NPZ  = os.path.join(HERE, "..", "data", "shadow64", "s64_ref_25000.npz")
FIG  = os.path.join(HERE, "..", "figures", "shadow64")
os.makedirs(FIG, exist_ok=True)

FONT = 7
W_FULL, H_TRACE = 7.09, 1.60
DPI = 600
plt.rcParams.update({
    "font.size": FONT, "axes.labelsize": FONT, "axes.titlesize": FONT,
    "xtick.labelsize": FONT - 1, "ytick.labelsize": FONT - 1,
    "legend.fontsize": FONT - 1, "axes.linewidth": 0.5,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.major.size": 2.0, "ytick.major.size": 2.0,
    "xtick.major.pad": 1.5, "ytick.major.pad": 1.5,
    "axes.labelpad": 1.5, "grid.linewidth": 0.35,
    "axes.unicode_minus": False,
    # 노트북과 동일 : figsize 를 그대로 유지 (bbox='tight' 로 자르지 않는다)
    "figure.constrained_layout.use": True,
    "figure.constrained_layout.h_pad": 0.01,
    "figure.constrained_layout.w_pad": 0.01,
})

d  = np.load(NPZ)
tr = d["traces"]
t  = np.asarray(tr[0], np.float64)
print("traces %s | clkout %.1f MHz | phase %s"
      % (tr.shape, float(d["clkout"]) / 1e6, str(d["phase"])))

# ------------------------------------------------------------------ 라운드 주기
# 자기상관의 최대 lag 로 라운드 주기를 재고, 32 라운드가 놓인 구간을 확인한다.
x  = t - t.mean()
ac = np.correlate(x, x, "full")[len(x) - 1:]
per = 400 + int(np.argmax(ac[400:1200]))
print("라운드 주기 %d 샘플 -> 32 라운드 = %d 샘플 (전체 %d)"
      % (per, per * 32, len(t)))

# ------------------------------------------------------------------ 전체 파형
# 라운드 경계마다 하강 스파이크가 나타나므로 32 라운드가 원파형에서 그대로 보인다.
plt.figure(figsize=(W_FULL, H_TRACE))
plt.plot(t, lw=0.3, rasterized=True)
plt.grid(True, alpha=0.35)
plt.xlabel("Sample index"); plt.ylabel("Power consumption")
plt.xlim([0, len(t)])
plt.savefig(os.path.join(FIG, "trace.png"), format="png", dpi=DPI)
plt.close()

# ------------------------------------------------------------------ 앞 4라운드 확대
n4 = per * 4
plt.figure(figsize=(W_FULL, H_TRACE))
plt.plot(t[:n4], lw=0.35, rasterized=True)
for r in range(1, 4):
    plt.axvline(r * per, color="#d62728", ls=":", lw=0.5)
plt.grid(True, alpha=0.35)
plt.xlabel("Sample index"); plt.ylabel("Power consumption")
plt.xlim([0, n4])
plt.savefig(os.path.join(FIG, "trace_zoom.png"), format="png", dpi=DPI)
plt.close()

print("그림 -> figures/shadow64/trace.png (논문용), trace_zoom.png (참고)")
