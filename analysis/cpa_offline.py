"""저장된 데이터셋으로 CPA 수행 (하드웨어 불필요).

corr(A, B) 는 표준 피어슨 상관을 열 단위로 계산한다. B 에 256개 가설을
한 번에 넣어도 키마다 루프 돌린 것과 결과가 같다.
"""
import os
import sys

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
         "..", "data", "masked", "masking_ISW_traces.npz")
TRUE_K0 = 0x0D


# ---------- 상관 계산 ----------
def hypohw(pt):
    return np.array([bin(p).count('1') for p in pt])


def corr(A, B):
    if len(A) != len(B):
        raise ValueError("operands could not be broadcast together")

    def matlab_like_corr(A, B):
        np.seterr(divide='ignore', invalid='ignore')
        DA = A - np.mean(A, axis=0)
        DB = B - np.mean(B, axis=0)
        CV = np.dot(DA.T, DB) / np.double(len(A))
        VA = np.mean(np.square(DA), axis=0)[:, np.newaxis]
        VB = np.mean(np.square(DB), axis=0)[np.newaxis, :]
        return (CV / np.sqrt(np.dot(VA, VB)))

    a = np.array(A, dtype=np.float64)
    b = np.array(B, dtype=np.float64)
    ret = matlab_like_corr(a, b)
    ret[np.isnan(ret)] = 0
    return ret


def ROL8(val, rot):
    return ((val << rot) | ((val >> (8 - rot)))) & 0xFF
# ---------------------------------


# 인자로 준 상대경로는 실행 위치 기준, 기본값은 이 파일 기준으로 푼다.
path = FN if len(sys.argv) > 1 else os.path.join(HERE, FN)
d = np.load(path)
print("=== %s (%.1f MB) ===" % (FN, os.path.getsize(path) / 1e6))
for k in d.files:
    v = d[k]
    if v.ndim == 0:
        print("  %-10s %s" % (k, v))
    else:
        print("  %-10s shape=%-18s dtype=%-9s" % (k, str(v.shape), v.dtype), end="")
        if v.ndim <= 2 and v.size:
            print(" min=%s max=%s" % (np.min(v), np.max(v)))
        else:
            print()

traces = d["traces"]
pt_all = d["pt"]
group = d["group"] if "group" in d.files else np.ones(len(traces), dtype=np.uint8)

print("\n그룹: 고정평문 %d, 랜덤평문 %d" % (int((group == 0).sum()), int((group == 1).sum())))

sel = group == 1                     # CPA 는 평문이 변하는 그룹만 의미가 있다
trace = np.asarray(traces[sel], dtype=np.float64)
pt = np.asarray(pt_all[sel])
print("CPA 입력: %d 트레이스 x %d 샘플" % trace.shape)

# 정렬 품질 (트레이스 간 평균 상관)
sub = trace[:200]
c = np.corrcoef(sub)
print("정렬 품질(트레이스 간 평균상관): %.4f" % ((c.sum() - len(c)) / (len(c) ** 2 - len(c))))

# ---- 가설 (모델 선택: HW 기본, CPA_MODEL=HD 로 HD 모델) ----
MODEL = os.environ.get("CPA_MODEL", "HW")
Fl0 = np.bitwise_and(ROL8(pt[:, 0].astype(np.int64), 1),
                     ROL8(pt[:, 0].astype(np.int64), 7)) \
      ^ ROL8(pt[:, 0].astype(np.int64), 2)           # F(l0)
if MODEL == "HD":
    # HD: l1 레지스터 천이  HW(l1_old ^ s0) = HW(F(l0) ^ k)
    base = Fl0
else:
    # HW: HW(s0) = HW(F(l0) ^ l1 ^ k)
    base = Fl0 ^ pt[:, 1]
H = np.stack([hypohw(base ^ i) for i in range(256)], axis=1)
print("모델: %s,  가설 행렬: %s" % (MODEL, H.shape))

ret_corr = corr(trace, H)            # (samples, 256)
a = np.abs(ret_corr).max(axis=0)
peaks = np.abs(ret_corr).argmax(axis=0)
order = np.argsort(-a)
rank = int(np.where(order == TRUE_K0)[0][0]) + 1

print("\n=== CPA 결과 (전체 %d 샘플) ===" % trace.shape[1])
print("  정답 0x0D : |rho| = %.4f  @샘플 %d" % (a[TRUE_K0], peaks[TRUE_K0]))
print("  상위 5:")
for i in range(5):
    k = order[i]
    tag = " <-- 정답" if k == TRUE_K0 else (" (0x0D 보수)" if k == (TRUE_K0 ^ 0xFF) else "")
    print("    %d위 0x%02X |rho|=%.4f @샘플 %d%s" % (i + 1, k, a[k], peaks[k], tag))
print("  정답 랭크 : %d / 256" % rank)

# 앞부분(연산 구간)만 따로
for hi in (200, 400, 800, 2000):
    if hi >= trace.shape[1]:
        continue
    r2 = ret_corr[:hi]
    a2 = np.abs(r2).max(axis=0)
    o2 = np.argsort(-a2)
    rk2 = int(np.where(o2 == TRUE_K0)[0][0]) + 1
    print("  샘플 0-%-5d : 정답 |rho|=%.4f @%d, 랭크 %d" %
          (hi, a2[TRUE_K0], int(np.abs(r2[:, TRUE_K0]).argmax()), rk2))

# ---- 결과 시각화 저장 (PNG) ----
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

name = os.path.basename(FN)
name = name[:-4] if name.endswith('.npz') else name
name = name[:-7] if name.endswith('_traces') else name  # masking_ISW_traces -> masking_ISW
base = os.path.normpath(os.path.join(HERE, '..', 'results', name))
comp = TRUE_K0 ^ 0xFF                       # 정답키의 비트보수 (HW 모델에서 동률)
absc = np.abs(ret_corr)                     # (samples, 256)

fig, ax = plt.subplots(2, 1, figsize=(12, 7))
# (위) 샘플별 |상관|: 오답키 회색, 정답키 빨강, 보수 주황
ax[0].plot(absc, color='0.78', lw=0.25)
ax[0].plot(absc[:, TRUE_K0], color='r', lw=1.1, label='correct key 0x%02X' % TRUE_K0)
ax[0].plot(absc[:, comp], color='tab:orange', lw=0.9, label='complement 0x%02X' % comp)
ax[0].set_title('CPA  |correlation| vs sample   %s' % name)
ax[0].set_xlabel('sample'); ax[0].set_ylabel('|corr|'); ax[0].margins(x=0)
ax[0].legend(fontsize=8, loc='upper right')
# (아래) 키 추측별 최대 |상관|
ax[1].bar(range(256), a, color='0.7', width=1.0)
ax[1].bar([TRUE_K0], [a[TRUE_K0]], color='r', width=2.5,
          label='correct 0x%02X (rank %d)' % (TRUE_K0, rank))
ax[1].bar([comp], [a[comp]], color='tab:orange', width=2.5, label='complement 0x%02X' % comp)
ax[1].set_title('max |correlation| per key guess (0-255)')
ax[1].set_xlabel('key guess'); ax[1].set_ylabel('max |corr|'); ax[1].set_xlim(-1, 256)
ax[1].legend(fontsize=8, loc='upper right')

fig.tight_layout(); png = base + ('_cpaHD' if MODEL == 'HD' else '_cpa') + '.png'
fig.savefig(png, dpi=120); plt.close(fig)
print("  PNG 저장: %s" % png)
