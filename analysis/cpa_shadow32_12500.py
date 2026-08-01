# -*- coding: utf-8 -*-
"""
Shadow-32 : 12500-샘플 캡처에 대한 라운드 1~4 라운드키 전체 복구
============================================================================
대상 : data/shadow32_fixedkey/s32_ref_12500.npz      (2048 x 12500, 고정키)
       data/shadow32_10keys/s32_key01..10_12500.npz  (2048 x 12500, 랜덤키 10개)
방식 : 노트북(cwnano-shadow32-cpa.ipynb) 과 동일
        - 라운드 1,2 : 8-bit CPA (256 후보, HW(F(x)^k) 누설모델)
        - 라운드 3,4 : 4-bit CPA (상위 4-bit = 앞 라운드 키로 키스케줄(NX)에서 계산)
        - 창(window) : 노트북과 같은 prefix 창  W1..W4 = 1100, 1850, 2750, 3500
검증 : npz 의 참조 라운드키 rk[:16] (= RK1..RK4) 와 대조
부가 : 64-bit master 키 등가class 확인 (NX 비가역 -> master 유일복구 불가,
       참 master 는 class 에 포함)

실행 :  python cpa_shadow32_12500.py
출력 :  콘솔 표 + results/RESULTS_shadow32_12500.md
        + figures/shadow32_10keys/fig_fullkey_rounds.png
        + figures/shadow32_10keys/fig_success.png
"""
import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")        # 콘솔 cp949 회피
except Exception:
    pass
import numpy as np

# ----------------------------------------------------------------------------
# 경로 / 데이터셋
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT  = os.path.join(HERE, "..", "results")
FIG  = os.path.join(HERE, "..", "figures", "shadow32_10keys")
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

FIXED  = os.path.join(DATA, "shadow32_fixedkey", "s32_ref_12500.npz")
KEYSET = [os.path.join(DATA, "shadow32_10keys", "s32_key%02d_12500.npz" % i)
          for i in range(1, 11)]

# 라운드별 누설 구간(샘플). 노트북과 동일한 prefix 창 trace[:, :W]
W = [1100, 1850, 2750, 3500]

# ============================================================================
# 1. 노트북 CPA 함수 (bit_rol / F / matlab_like_corr / cpa_on_target)
# ============================================================================
def bit_rol(val, rot, n_bit):
    val = np.asarray(val, dtype=np.int64)
    return (np.left_shift(val, rot) ^ np.right_shift(val, n_bit - rot)) & (2 ** n_bit - 1)

def F8(x):                                   # Shadow F : (x<<<1 & x<<<7) ^ (x<<<2)
    return (bit_rol(x, 1, 8) & bit_rol(x, 7, 8)) ^ bit_rol(x, 2, 8)

_PC = np.array([bin(i).count('1') for i in range(256)], dtype=np.float64)
def HW(a):
    return _PC[np.asarray(a, dtype=np.uint8)]

def matlab_like_corr(A, B):                  # A:(N,S) B:(N,K) -> (S,K) Pearson
    np.seterr(divide='ignore', invalid='ignore')
    DA = A - np.mean(A, axis=0); DB = B - np.mean(B, axis=0)
    CV = np.dot(DA.T, DB) / np.double(len(A))
    VA = np.mean(np.square(DA), axis=0)[:, np.newaxis]
    VB = np.mean(np.square(DB), axis=0)[np.newaxis, :]
    r = CV / np.sqrt(np.dot(VA, VB)); r[np.isnan(r)] = 0
    return r

def cpa_on_target(keys, power_trace, hypo_value):
    H = HW(hypo_value[:, None] ^ np.array(keys, dtype=np.uint8)[None, :])
    return matlab_like_corr(power_trace, H)

def signed_peak_per_key(c):
    idx = np.argmax(np.abs(c), axis=0)
    return c[idx, np.arange(c.shape[1])]

def peak_pos(c, col):
    return int(np.argmax(np.abs(c[:, col])))

# ============================================================================
# 2. Shadow-32 키스케줄 NX (8->8bit) — 라운드 3,4 상위니블 계산
# ============================================================================
def nx8(x):
    k = [(x >> (7 - i)) & 1 for i in range(8)]
    nb = [k[0] & (k[0] ^ k[6]),          k[1] & (k[1] ^ k[7]),
          k[2] & (k[2] ^ k[0] ^ k[6]),   k[3] & (k[3] ^ k[1] ^ k[7]),
          k[4] & (k[4] ^ k[2] ^ k[0] ^ k[6]), k[5] & (k[5] ^ k[3] ^ k[1] ^ k[7]),
          k[6] & (k[4] ^ k[2] ^ k[0]),   k[7] & (k[5] ^ k[3] ^ k[1])]
    return sum(nb[i] << (7 - i) for i in range(8))

# ============================================================================
# 3. 풀키 복구 : RK1..RK4 (16바이트)
# ============================================================================
def _rstate(l0, l1, r0, r1, k):
    s0 = F8(l0) ^ l1 ^ k[0]; s1 = F8(r0) ^ r1 ^ k[1]
    return s1, (F8(s0) ^ l0 ^ k[2]) & 0xFF, s0, (F8(s1) ^ r0 ^ k[3]) & 0xFF

def recover_fullkey(trace, pt):
    """반환 : (라운드키 16바이트, alpha, 피크 |rho| dict, 피크 위치 dict)"""
    L0, L1, R0, R1 = (pt[:, i].astype(np.int64) for i in range(4))
    T = trace[:, :W[0]]
    h0 = F8(L0) ^ L1

    # RK1_0 : 7-bit CPA 로 보수쌍 {g0, g0^0xFF} 까지 압축
    c0  = cpa_on_target(range(256), T, h0)
    sp0 = signed_peak_per_key(c0); g0 = int(np.argmax(np.abs(sp0)))
    # h2 가설이 피크를 내는 쪽이 정답 (논문 4.3 절의 alpha 부호 결정)
    def h2peak(k0):
        return float(np.abs(signed_peak_per_key(
            cpa_on_target(range(256), T, F8(h0 ^ k0) ^ L0))).max())
    RK1_0 = g0 if h2peak(g0) >= h2peak(g0 ^ 0xFF) else (g0 ^ 0xFF)
    alpha = float(np.sign(sp0[RK1_0])) or 1.0

    pk = {}; ps = {}
    def key8(T, hyp, tag):
        c  = cpa_on_target(range(256), T, hyp)
        sp = signed_peak_per_key(c)
        k  = int(np.argmax(alpha * sp))
        pk[tag] = float(abs(sp[k])); ps[tag] = peak_pos(c, k)
        return k
    def cpa4(T, hyp, upper, tag):
        cands = [(upper << 4) | lo for lo in range(16)]
        c  = cpa_on_target(cands, T, hyp)
        sp = signed_peak_per_key(c)
        lo = int(np.argmax(alpha * sp))
        pk[tag] = float(abs(sp[lo])); ps[tag] = peak_pos(c, lo)
        return (upper << 4) | lo

    # Round 1 (8-bit)
    T = trace[:, :W[0]]
    pk['R1k0'] = float(abs(sp0[RK1_0])); ps['R1k0'] = peak_pos(c0, RK1_0)
    RK1_1 = key8(T, F8(R0) ^ R1, 'R1k1')
    s0 = h0 ^ RK1_0; s1 = (F8(R0) ^ R1) ^ RK1_1
    RK1_2 = key8(T, F8(s0) ^ L0, 'R1k2')
    RK1_3 = key8(T, F8(s1) ^ R0, 'R1k3')
    RK1 = [RK1_0, RK1_1, RK1_2, RK1_3]

    # Round 2 (8-bit)
    st = _rstate(L0, L1, R0, R1, RK1); T = trace[:, :W[1]]
    l0, l1, r0, r1 = st
    RK2_0 = key8(T, F8(l0) ^ l1, 'R2k0'); RK2_1 = key8(T, F8(r0) ^ r1, 'R2k1')
    s0 = F8(l0) ^ l1 ^ RK2_0; s1 = F8(r0) ^ r1 ^ RK2_1
    RK2_2 = key8(T, F8(s0) ^ l0, 'R2k2'); RK2_3 = key8(T, F8(s1) ^ r0, 'R2k3')
    RK2 = [RK2_0, RK2_1, RK2_2, RK2_3]

    # Round 3 (4-bit)
    st = _rstate(*st, RK2); T = trace[:, :W[2]]
    l0, l1, r0, r1 = st
    nxo = nx8(((RK1[0] & 0xF) << 4) | (RK1[1] & 0xF))
    RK3_0 = (((nxo >> 4) & 0xF) << 4) | ((RK2[3] >> 4) & 0xF); RK3_1 = RK2[2]
    s0 = F8(l0) ^ l1 ^ RK3_0; s1 = F8(r0) ^ r1 ^ RK3_1
    RK3_2 = cpa4(T, F8(s0) ^ l0, nxo & 0xF, 'R3k2')
    RK3_3 = cpa4(T, F8(s1) ^ r0, RK2[3] & 0xF, 'R3k3')
    RK3 = [RK3_0, RK3_1, RK3_2, RK3_3]

    # Round 4 (4-bit)
    st = _rstate(*st, RK3); T = trace[:, :W[3]]
    l0, l1, r0, r1 = st
    nxo4 = nx8(((RK2[0] & 0xF) << 4) | (RK2[1] & 0xF))
    RK4_0 = (((nxo4 >> 4) & 0xF) << 4) | ((RK3[3] >> 4) & 0xF); RK4_1 = RK3[2]
    s0 = F8(l0) ^ l1 ^ RK4_0; s1 = F8(r0) ^ r1 ^ RK4_1
    RK4_2 = cpa4(T, F8(s0) ^ l0, nxo4 & 0xF, 'R4k2')
    RK4_3 = cpa4(T, F8(s1) ^ r0, RK3[3] & 0xF, 'R4k3')
    RK4 = [RK4_0, RK4_1, RK4_2, RK4_3]
    return RK1 + RK2 + RK3 + RK4, alpha, pk, ps

# ============================================================================
# 4. (부가) 64-bit master 키 등가class : 키스케줄 역산
# ============================================================================
PERM = [56,57,58,59,16,17,18,19,20,21,22,23,24,25,26,27,
        60,61,62,63,28,29,30,31,32,33,34,35,36,37,38,39,
        40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,
         0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15]
Ks = [[0,1,2,3,8,9,10,11],[4,5,6,7,12,13,14,15],
      [16,17,18,19,24,25,26,27],[20,21,22,23,28,29,30,31]]

def _nx_bits(k):
    return [k[0]&(k[0]^k[6]), k[1]&(k[1]^k[7]), k[2]&(k[2]^k[0]^k[6]), k[3]&(k[3]^k[1]^k[7]),
            k[4]&(k[4]^k[2]^k[0]^k[6]), k[5]&(k[5]^k[3]^k[1]^k[7]),
            k[6]&(k[4]^k[2]^k[0]), k[7]&(k[5]^k[3]^k[1])]

def _unpack(RK4b):
    b = [0]*64
    for j in range(4):
        for i in range(8): b[Ks[j][i]] = (RK4b[j] >> (7 - i)) & 1
    return b

def master_class(RKs):
    from itertools import product
    origin = list(range(64)); flip = [0]*64; known = {}; nx_events = []
    for r in range(1, len(RKs)+1):
        for p, sh in [(3,4),(4,3),(5,2),(6,1),(7,0)]: flip[p] ^= (r >> sh) & 1
        nx_in = origin[56:64][:]
        for p in range(56, 64): origin[p] = -1; flip[p] = 0
        origin = [origin[PERM[i]] for i in range(64)]; flip = [flip[PERM[i]] for i in range(64)]
        br = _unpack(RKs[r-1])
        for p in range(32):
            m = origin[p]
            if m != -1 and m not in known: known[m] = br[p] ^ flip[p]
        nx_events.append((nx_in, [br[0],br[1],br[2],br[3],br[16],br[17],br[18],br[19]]))
    partial = []
    for nx_in, nx_out in nx_events:
        if all(m in known for m in nx_in): continue
        sols = []
        for k in range(256):
            ib = [(k >> (7 - i)) & 1 for i in range(8)]
            if _nx_bits(ib) != nx_out: continue
            d = {}; ok = True
            for i, m in enumerate(nx_in):
                if m in known and known[m] != ib[i]: ok = False; break
                d[m] = ib[i]
            if ok: sols.append(d)
        if sols: partial.append(sols)
    masters = []
    for combo in (product(*partial) if partial else [()]):
        mb = [known.get(i, 0) for i in range(64)]
        for d in combo:
            for m, v in d.items(): mb[m] = v
        masters.append(mb)
    return masters

def _bits_to_bytes(mb):
    return [sum(mb[8*j+i] << (7-i) for i in range(8)) for j in range(8)]

# ============================================================================
# 5. 실행 : 고정키 1셋 + 랜덤키 10셋
# ============================================================================
_ORDER = ['R1k0','R1k1','R1k2','R1k3','R2k0','R2k1','R2k2','R2k3',
          'R3k2','R3k3','R4k2','R4k3']
# 논문 그림용 : 공격에 실제로 필요한 11개. $RK_1^2$(R2k1)는 키 스케줄이 이미 정하므로
# CPA 로 확인만 하고 그림에서는 제외한다.
_ORDER_FIG = [t for t in _ORDER if t != 'R2k1']
_LBL   = [r'$RK^1_0$', r'$RK^1_1$', r'$RK^1_2$', r'$RK^1_3$',
          r'$RK^2_0$', r'$RK^2_1$', r'$RK^2_2$', r'$RK^2_3$',
          r'$RK^3_2$', r'$RK^3_3$', r'$RK^4_2$', r'$RK^4_3$']

def run_one(path):
    d  = np.load(path)
    tr = d['traces'].astype(np.float64)
    pt = d['pt']
    ref = [int(x) for x in d['rk'][:16]]
    master = [int(x) for x in np.ravel(d['master'])] if d['master'].size else None
    rec, alpha, pk, ps = recover_fullkey(tr, pt)
    cls = {tuple(_bits_to_bytes(m)) for m in master_class([rec[4*j:4*j+4] for j in range(4)])}
    return dict(ref=ref, rec=rec, ok=(rec == ref), alpha=alpha, pk=pk, ps=ps,
                master=master, csz=len(cls),
                min_=(tuple(master) in cls) if master else None,
                ntr=tr.shape[0], nsm=tr.shape[1])

def hx(v):
    return " ".join("%02X" % x for x in v)

def main():
    L = []
    L.append("# Shadow-32 CPA : 12500-sample capture, recovery of round keys RK1..RK4\n")
    L.append("- Method : rounds 1,2 = 8-bit CPA / rounds 3,4 = 4-bit CPA "
             "(the upper nibble is computed from the key schedule NX)")
    L.append("- CPA is run on 12 subkeys, but RK2_1 is a value the key schedule already fixes,")
    L.append("  so it is only a cross-check. The 11 \"subkeys recovered by CPA\" counted in the paper are these 12 minus RK2_1.")
    L.append("- Window : prefix window `trace[:, :W]`, W1..W4 = %s" % ", ".join(map(str, W)))
    L.append("- Capture : clkout 7.5MHz / adc 7.5MHz, seekclip phase, `-O0` firmware\n")

    # ---------------------------------------------------------------- 고정키
    print("[1/2] Fixed-key set ...", flush=True)
    r = run_one(FIXED)
    L.append("## 1. Fixed-key set (`s32_ref_12500.npz`, %d x %d)\n" % (r['ntr'], r['nsm']))
    L.append("Recovered RK1..RK4 : `%s`" % hx(r['rec']))
    L.append("Reference RK1..RK4 : `%s`" % hx(r['ref']))
    L.append("Matching bytes : **%d/16**,  alpha = %+d\n" % (sum(a == b for a, b in
             zip(r['rec'], r['ref'])), int(r['alpha'])))
    L.append("| Subkey | Mode | Recovered | Peak \\|rho\\| | Peak sample |")
    L.append("|---|---|---|---|---|")
    for i, t in enumerate(_ORDER):
        idx = [0,1,2,3,4,5,6,7,10,11,14,15][i]
        mode = '8-bit' if t[1] in '12' else '4-bit'
        L.append("| %s | %s | `%02X` | %.3f | %d |" %
                 (_LBL[i].replace('$','').replace('RK^','RK').replace('_','_'),
                  mode, r['rec'][idx], r['pk'][t], r['ps'][t]))
    v1 = [r['pk'][t] for t in _ORDER]
    v_r34 = [r['pk'][t] for t in ('R3k2','R3k3','R4k2','R4k3')]
    v_r12 = [r['pk'][t] for t in _ORDER[:8]]
    L.append("")
    L.append("- Rounds 1 and 2 (8-bit CPA, 8 subkeys) : |rho| %.3f ~ %.3f" % (min(v_r12), max(v_r12)))
    L.append("- Rounds 3 and 4 (4-bit CPA, 4 subkeys) : |rho| %.3f ~ %.3f" % (min(v_r34), max(v_r34)))
    L.append("- All 12 : min %.3f, max %.3f, mean %.3f\n" %
             (min(v1), max(v1), float(np.mean(v1))))
    L.append("Equivalence class size %d (no master field, this set has the round keys "
             "hard-coded as constants in the firmware)\n"
             % r['csz'])
    print("      16/16 = %s  |rho| %.3f~%.3f" % (r['ok'], min(v1), max(v1)), flush=True)

    # ---------------------------------------------------------------- 10키
    print("[2/2] 10 random-key sets ...", flush=True)
    rows = []
    for i, p in enumerate(KEYSET):
        rr = run_one(p); rr['name'] = "key%02d" % (i + 1); rows.append(rr)
        print("      %s  %s  |rho|min %.3f  master@class(%d) %s"
              % (rr['name'], "OK " if rr['ok'] else "FAIL",
                 min(rr['pk'].values()), rr['csz'],
                 "O" if rr['min_'] else "X"), flush=True)

    n_full = sum(x['ok'] for x in rows)
    n_min  = sum(bool(x['min_']) for x in rows)
    allpk  = [v for x in rows for v in x['pk'].values()]

    L.append("## 2. 10 random-key sets (`s32_key01..10_12500.npz`, %d x %d each)\n"
             % (rows[0]['ntr'], rows[0]['nsm']))
    L.append("| Set | master | RK1 | RK2 | RK3 | RK4 | Match | min\\|rho\\| | "
             "alpha | master∈class(size) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for x in rows:
        L.append("| %s | `%s` | `%s` | `%s` | `%s` | `%s` | %s | %.3f | %+d | %s (%d) |" % (
            x['name'], "".join("%02X" % b for b in x['master']),
            hx(x['rec'][0:4]), hx(x['rec'][4:8]), hx(x['rec'][8:12]), hx(x['rec'][12:16]),
            "16/16" if x['ok'] else "FAIL", min(x['pk'].values()), int(x['alpha']),
            "O" if x['min_'] else "X", x['csz']))
    L.append("")
    L.append("- Full recovery of round keys RK1..RK4 : **%d/10 sets**" % n_full)
    L.append("- True 64-bit master ∈ NX equivalence class : **%d/10 sets** "
             "(NX is not invertible -> the master key cannot be uniquely recovered)" % n_min)
    L.append("- Equivalence class size : %s" % ", ".join(str(x['csz']) for x in rows))
    L.append("- Subkey peak \\|rho\\| (10 sets x 12 = %d values) : "
             "**min %.3f, max %.3f**, mean %.3f" %
             (len(allpk), min(allpk), max(allpk), float(np.mean(allpk))))
    L.append("")

    txt = "\n".join(L)
    open(os.path.join(OUT, "RESULTS_shadow32_12500.md"), "w", encoding="utf-8").write(txt)
    print("\n" + txt)

    import json
    json.dump([{'name': x['name'], 'pk': x['pk'], 'ntr': x['ntr']} for x in rows],
              open(os.path.join(OUT, "_peaks_12500.json"), "w"))
    _fig_success(rows)
    _fig_rounds(rows)
    print("\nResult : results/RESULTS_shadow32_12500.md")
    print("Figs : figures/shadow32_10keys/fig_success.png")
    print("       figures/shadow32_10keys/fig_fullkey_rounds.png")

# ============================================================================
# 6. 그림 — 논문 그림 규격(노트북 rcParams 와 동일)
# ============================================================================
FONT = 7
W_FULL, H_FULL = 7.09, 2.30
DPI = 600

def _rc():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": FONT, "axes.labelsize": FONT, "axes.titlesize": FONT,
        "xtick.labelsize": FONT - 1, "ytick.labelsize": FONT - 1,
        "legend.fontsize": FONT - 1, "axes.linewidth": 0.5,
        "xtick.major.width": 0.5, "ytick.major.width": 0.5,
        "xtick.major.size": 2.0, "ytick.major.size": 2.0,
        "xtick.major.pad": 1.5, "ytick.major.pad": 1.5,
        "axes.labelpad": 1.5, "grid.linewidth": 0.35,
        "legend.frameon": True, "legend.framealpha": 0.9, "legend.borderaxespad": 0.3,
        "axes.unicode_minus": False,
        # 노트북과 동일 : bbox='tight' 로 잘라내지 않고 figsize 를 그대로 유지해야
        # 논문에서 \columnwidth 로 배치했을 때 글자 크기가 다른 그림들과 맞는다.
        "figure.constrained_layout.use": True,
        "figure.constrained_layout.h_pad": 0.01,
        "figure.constrained_layout.w_pad": 0.01,
    })
    return plt

def _fig_success(rows):
    """10개 키 x 12개 서브키의 정답키 |rho| 와 오답키 기준선."""
    plt = _rc()
    thr = 4.0 / np.sqrt(rows[0]['ntr'])
    fig, ax = plt.subplots(figsize=(W_FULL, 2.10))
    ax.axhline(thr, color='#d62728', ls='--', lw=0.8,
               label=r'wrong-key level $4/\sqrt{N} = %.3f$' % thr)
    for i, x in enumerate(rows):
        ys = [x['pk'][k] for k in _ORDER_FIG]
        xs = (i + 1) + np.linspace(-0.22, 0.22, len(ys))
        ax.scatter(xs, ys, s=5, color='#1f77b4', alpha=0.85, edgecolor='none', zorder=3)
    ax.scatter([], [], s=5, color='#1f77b4', label='correct-key $|\\rho|$ (11 per key)')
    ax.set_xticks(range(1, len(rows) + 1))
    ax.set_xticklabels(['%d' % (i + 1) for i in range(len(rows))])
    ax.set_xlim(0.4, len(rows) + 0.6); ax.set_ylim(0, 1.0)
    ax.set_xlabel('Key set'); ax.set_ylabel(r'Correct-key $|\rho|$')
    ax.grid(True, axis='y', alpha=0.35)
    ax.legend(loc='center right', handlelength=1.4, borderpad=0.25, labelspacing=0.2)
    fig.savefig(os.path.join(FIG, "fig_success.png"), dpi=DPI); plt.close(fig)

def _fig_rounds(rows):
    """대표 세트(key01) 라운드 1~4 CPA 상관곡선 (정답키 강조)."""
    plt = _rc()
    d  = np.load(KEYSET[0])
    tr = d['traces'].astype(np.float64); pt = d['pt']
    ref = [int(x) for x in d['rk'][:16]]
    L0, L1, R0, R1 = (pt[:, i].astype(np.int64) for i in range(4))
    rec, alpha, _, _ = recover_fullkey(tr, pt)

    fig, axs = plt.subplots(1, 4, figsize=(W_FULL, 1.70), sharey=True)
    # 라운드 1 : 7-bit CPA (후보 0~127). 보수쌍 압축을 쓰는 논문의 공격과 같다.
    assert ref[0] < 128, '대표 세트의 RK^1_0 이 7-bit 범위 밖이다'
    T = tr[:, :W[0]]; h0 = F8(L0) ^ L1
    _panel(axs[0], cpa_on_target(range(128), T, h0), ref[0],
           r'Round 1: $RK^1_0$ (7-bit)')
    # 라운드 2 : 4-bit CPA. 키 스케줄에서 RK^1_3 의 상위 니블이 RK^2_0 의 하위 니블이므로
    # 상위 니블 16개만 열거한다.
    st = _rstate(L0, L1, R0, R1, rec[0:4]); T = tr[:, :W[1]]
    lo2 = (rec[3] >> 4) & 0xF
    assert (ref[4] & 0xF) == lo2, '키 스케줄 관계가 성립하지 않는다'
    _panel(axs[1], cpa_on_target([(hi << 4) | lo2 for hi in range(16)], T,
           F8(st[0]) ^ st[1]), ref[4], r'Round 2: $RK^2_0$ (4-bit)', hi4=True)
    st2 = _rstate(*st, rec[4:8]); T = tr[:, :W[2]]
    nxo = nx8(((rec[0] & 0xF) << 4) | (rec[1] & 0xF))
    RK3_0 = (((nxo >> 4) & 0xF) << 4) | ((rec[7] >> 4) & 0xF)
    s0 = F8(st2[0]) ^ st2[1] ^ RK3_0
    _panel(axs[2], cpa_on_target([((nxo & 0xF) << 4) | lo for lo in range(16)], T,
           F8(s0) ^ st2[0]), ref[10], r'Round 3: $RK^3_2$ (4-bit)', lo4=True)
    st3 = _rstate(*st2, rec[8:12]); T = tr[:, :W[3]]
    nxo4 = nx8(((rec[4] & 0xF) << 4) | (rec[5] & 0xF))
    RK4_0 = (((nxo4 >> 4) & 0xF) << 4) | ((rec[11] >> 4) & 0xF)
    s0 = F8(st3[0]) ^ st3[1] ^ RK4_0
    _panel(axs[3], cpa_on_target([((nxo4 & 0xF) << 4) | lo for lo in range(16)], T,
           F8(s0) ^ st3[0]), ref[14], r'Round 4: $RK^4_2$ (4-bit)', lo4=True)
    axs[0].set_ylabel('Absolute correlation')
    fig.savefig(os.path.join(FIG, "fig_fullkey_rounds.png"), dpi=DPI); plt.close(fig)

def _panel(ax, c, correct, title, lo4=False, hi4=False):
    if lo4:
        col = correct & 0xF          # 하위 니블을 탐색한 경우
    elif hi4:
        col = (correct >> 4) & 0xF   # 상위 니블을 탐색한 경우
    else:
        col = correct
    y   = np.abs(c)
    for i in range(c.shape[1]):
        if i != col:
            ax.plot(y[:, i], color=[0.88, 0.88, 0.88], lw=0.25, rasterized=True)
    ax.plot(y[:, col], color='#d62728', lw=0.7, label='0x%02X' % correct)
    ax.set_ylim([-0.05, 0.95]); ax.set_xlim([0, c.shape[0]])
    ax.grid(True, alpha=0.35)
    ax.set_title(title)
    ax.set_xlabel('Sample index')
    ax.legend(handlelength=1.1, borderpad=0.2, handletextpad=0.3, labelspacing=0.2,
              loc='upper left')

if __name__ == "__main__":
    # "--figs" : 이미 계산된 피크(results/_peaks_12500.json)로 그림만 다시 그린다
    if "--figs" in sys.argv:
        import json
        rows = json.load(open(os.path.join(OUT, "_peaks_12500.json")))
        _fig_success(rows); _fig_rounds(rows)
        print("Figures regenerated")
    else:
        main()
