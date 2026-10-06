# -*- coding: utf-8 -*-
"""
Shadow-32 : recovery of the round keys RK1..RK4 from the 12500-sample captures
============================================================================
Data   : data/shadow32_fixedkey/s32_ref_12500.npz      (2048 x 12500, fixed key)
         data/shadow32_10keys/s32_key01..10_12500.npz  (2048 x 12500, ten random keys)
Method : Algorithm 1 of the paper, 13 CPAs and 768 candidate evaluations in total.
  Round 1, five 7-bit CPAs over the 128 representatives 0..127 (HW of a byte):
    h0 -> the complement pair {g0, g0^0xFF} of RK1_0;  h1 -> the pair of RK1_1;
    h2 built with the positive-peak member p of the RK1_0 pair and h2* built with p^0xFF;
    D = max|rho|(h2) - max|rho|(h2*) decides RK1_0 = p (D >= 0, alpha = +1) or
    RK1_0 = p^0xFF (D < 0, alpha = -1).  RK1_2 is the best candidate of the CPA selected
    by D, RK1_1 the member of its pair selected by the sign, and h3 built with RK1_1 gives
    RK1_3.  The h2* CPA returns no value.
  Round 2, four 4-bit CPAs of 16 candidates each:
    RK2_1 = RK1_2, the lower nibble of RK2_0 and the upper nibble of RK2_3 come from
    RK1_3 (key schedule).  The upper nibble of RK2_0 is attacked with the full-byte HW and
    the lower nibble fixed; the lower nibble of RK2_2 FIRST with the HW of the lower nibble
    only of F(S0^2) ^ L0^2 ^ cand (the unmodeled upper nibble acts as noise), then the
    upper nibble of RK2_2 with the lower nibble fixed and the full-byte HW; the lower
    nibble of RK2_3 with the upper nibble fixed.
  Rounds 3 and 4, two 4-bit CPAs each: RK_1^r = RK_2^{r-1}; the upper nibbles of RK_0^r
    and RK_2^r come from the NX module applied to the lower nibbles of RK_0^{r-2} and
    RK_1^{r-2}, the lower nibble of RK_0^r from the upper nibble of RK_3^{r-1}; the lower
    nibbles of RK_2^r and RK_3^r are attacked with the upper nibble fixed.
  Ranking : every CPA ranks its candidates by alpha times the signed correlation at the
    sample where |rho| of that candidate peaks ("alpha-signed peak", the rule of the
    paper).  success_rate.py ranks by the maximum over the samples of alpha * rho(t);
    the two rules give the same recovered values on all eleven sets at 2,048 traces.
  Samples : a Round-r CPA runs over the samples of Round r, [b0 + (r-1)P, b0 + rP), with
    the period P and the boundary b0 taken from the mean trace of each set alone
    (round_structure.py).  Neither the key nor the outcome of an attack is used.
Cross-check : RK2_1 is fixed by the key schedule; a 7-bit CPA on it is run and reported
    as a labeled check but does not enter the count of 13 CPAs.
Verification : the recovered RK1..RK4 are compared with the reference rk[:16] of the npz;
    the NX-equivalence class of the master key is computed by inverting the key schedule,
    and every member of the class is expanded with the key schedule (shadow32_ks.ks32) and
    must give the same 64 round-key bytes, equal to the stored rk[:64].

Usage :  python cpa_shadow32_12500.py           (about one minute for the eleven sets)
         python cpa_shadow32_12500.py --figs    (redraw the figures from the cached peaks)
Output:  console + results/RESULTS_shadow32_12500.md + results/_peaks_12500.json
         figures/shadow32_10keys/fig_success.pdf (+ .png)    (12 value-returning CPAs per key)
         figures/shadow32_10keys/fig_fullkey_rounds.pdf (+ .png)
"""
import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")        # console may be cp949
except Exception:
    pass
import numpy as np

# ----------------------------------------------------------------------------
# paths / data sets
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT  = os.path.join(HERE, "..", "results")
FIG  = os.path.join(HERE, "..", "figures", "shadow32_10keys")

def _ensure_dirs():
    """Create results/ and figures/shadow32_10keys/ (called by main() and --figs only, so
    that importing this module, as cpa_s64_analysis.py, trace_stats.py and phase_compare.py do,
    writes nothing)."""
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)

FIXED  = os.path.join(DATA, "shadow32_fixedkey", "s32_ref_12500.npz")
KEYSET = [os.path.join(DATA, "shadow32_10keys", "s32_key%02d_12500.npz" % i)
          for i in range(1, 11)]

sys.path.insert(0, HERE)
from round_structure import round_structure, round_interval   # noqa: E402
from shadow32_ks import ks32, nx8, nx_bits                     # noqa: E402,F401

# ============================================================================
# 1. CPA primitives (bit_rol / F / matlab_like_corr / cpa_on_target)
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

def cpa_on_target(keys, power_trace, hypo_value, mask=0xFF):
    """Correlation (S, K) of HW((hypo_value ^ key) & mask) with the traces.
    mask = 0x0F models the lower nibble only (the upper nibble is left unmodeled)."""
    H = HW((hypo_value[:, None] ^ np.array(keys, dtype=np.uint8)[None, :]) & mask)
    return matlab_like_corr(power_trace, H)

def signed_peak_per_key(c):
    idx = np.argmax(np.abs(c), axis=0)
    return c[idx, np.arange(c.shape[1])]

def peak_pos(c, col):
    return int(np.argmax(np.abs(c[:, col])))

def rank_of(score, idx):
    """1-based position of candidate idx in the descending order of score (stable)."""
    order = np.argsort(-np.asarray(score), kind="stable")
    return int(np.where(order == idx)[0][0]) + 1

# ============================================================================
# 2. Full-key recovery : RK1..RK4 (16 bytes), Algorithm 1
# ============================================================================
G128 = list(range(128))

def _rstate(l0, l1, r0, r1, k):
    s0 = F8(l0) ^ l1 ^ k[0]; s1 = F8(r0) ^ r1 ^ k[1]
    return s1, (F8(s0) ^ l0 ^ k[2]) & 0xFF, s0, (F8(s1) ^ r0 ^ k[3]) & 0xFF

def rounds_of(trace):
    """Attack intervals [(a, b), ...] of Rounds 1..4 and (period, boundary); no key is used."""
    P, b0 = round_structure(trace)
    return [round_interval(r, P, b0, trace.shape[1]) for r in (1, 2, 3, 4)], (P, b0)

# The 13 CPAs of Algorithm 1 in the order they are run, and the labeled cross-check.
# 'R1k2s' is the rejected h2* CPA, which returns no value.
_ORDER13 = ['R1k0', 'R1k1', 'R1k2', 'R1k2s', 'R1k3',
            'R2k0hi', 'R2k2lo', 'R2k2hi', 'R2k3lo',
            'R3k2lo', 'R3k3lo', 'R4k2lo', 'R4k3lo']
_ORDER   = [t for t in _ORDER13 if t != 'R1k2s']          # the 12 that return a value
_CHECK   = 'R2k1chk'
_LBL = {'R1k0': r'$RK^1_0$', 'R1k1': r'$RK^1_1$', 'R1k2': r'$RK^1_2$ ($h_2$)',
        'R1k2s': r'$RK^1_2$ ($h_2^*$)', 'R1k3': r'$RK^1_3$',
        'R2k0hi': r'$RK^2_0$ upper', 'R2k2lo': r'$RK^2_2$ lower', 'R2k2hi': r'$RK^2_2$ upper',
        'R2k3lo': r'$RK^2_3$ lower', 'R3k2lo': r'$RK^3_2$ lower', 'R3k3lo': r'$RK^3_3$ lower',
        'R4k2lo': r'$RK^4_2$ lower', 'R4k3lo': r'$RK^4_3$ lower', 'R2k1chk': r'$RK^2_1$ (check)'}
_NAME = {'R1k0': 'RK1_0', 'R1k1': 'RK1_1', 'R1k2': 'RK1_2', 'R1k2s': 'RK1_2', 'R1k3': 'RK1_3',
         'R2k0hi': 'RK2_0', 'R2k2lo': 'RK2_2', 'R2k2hi': 'RK2_2', 'R2k3lo': 'RK2_3',
         'R3k2lo': 'RK3_2', 'R3k3lo': 'RK3_3', 'R4k2lo': 'RK4_2', 'R4k3lo': 'RK4_3',
         'R2k1chk': 'RK2_1'}

def correct_index(cpa, ref):
    """Index of the correct candidate of a CPA in its candidate order, from the reference
    round keys, or None if the CPA has no correct candidate (h2*) or its fixed nibble is
    wrong.  sel = ('byte', i) | ('hi', i, lo_fixed) | ('lo', i, hi_fixed) | ('lo_only', i)."""
    sel = cpa['sel']
    if sel is None:
        return None
    kind, i = sel[0], sel[1]
    if kind == 'byte':
        return ref[i]
    if kind == 'lo_only':
        return ref[i] & 0xF
    if kind == 'hi':
        return (ref[i] >> 4) if (ref[i] & 0xF) == sel[2] else None
    if kind == 'lo':
        return (ref[i] & 0xF) if (ref[i] >> 4) == sel[2] else None
    raise ValueError(sel)

def recover_fullkey(trace, pt):
    """Algorithm 1 on one trace set.
    Returns (RK1..RK4 as 16 ints, alpha, pk, ps, (period, boundary), cpas) where
      pk, ps : dict tag -> peak |rho| and absolute peak sample of the recovered candidate
               (for the rejected h2* CPA: of its global maximum),
      cpas   : list of one record per CPA in the order run (13 of Algorithm 1 and the
               RK2_1 cross-check), each with tag, target, cands, score (alpha-signed, one
               entry per candidate value), value, nib, rho, peak, sel, counted, kind."""
    L0, L1, R0, R1 = (pt[:, i].astype(np.int64) for i in range(4))
    IV, rs = rounds_of(trace)
    pk, ps, cpas = {}, {}, []
    off = [0]                                   # start sample of the current round

    def use_round(r):
        a, b = IV[r - 1]; off[0] = a
        return trace[:, a:b]

    def record(tag, target, cands, score, value, nib, c, col, sel, counted=True, kind='measured'):
        """c: correlation (S, K) of the CPA, col: the column whose peak is reported (the
        recovered candidate, or the global maximum for the rejected h2*).  Round-1 CPAs
        enumerate 128 representatives but score all 256 values (cands = range(256))."""
        pk[tag] = float(abs(c[peak_pos(c, col), col])); ps[tag] = off[0] + peak_pos(c, col)
        cpas.append(dict(tag=tag, name=_NAME[tag], target=target, ncand=c.shape[1],
                         cands=list(cands), score=np.asarray(score, dtype=np.float64),
                         value=value, nib=nib, rho=pk[tag], peak=ps[tag], sel=sel,
                         counted=counted, kind=kind, samples=IV[int(tag[1]) - 1]))

    def rep_of(v):
        return v if v < 128 else v ^ 0xFF

    # ---------------------------------------------------------------- Round 1
    T = use_round(1)
    h0 = F8(L0) ^ L1; h1 = F8(R0) ^ R1

    def r1(hyp, alpha):
        """7-bit CPA over the 128 representatives; the alpha-signed peak of representative g
        scores value g, its negative scores g^0xFF (HW(v^0xFF) = 8 - HW(v))."""
        c = cpa_on_target(G128, T, hyp)
        sp = signed_peak_per_key(c)
        s256 = np.empty(256); s256[:128] = alpha * sp; s256[128:] = (-alpha * sp)[::-1]
        return c, sp, s256

    # RK1_0 : the complement pair, p = the member with the positive peak
    c0, sp0, _ = r1(h0, +1.0)
    g0 = int(np.argmax(np.abs(sp0)))
    p = g0 if sp0[g0] > 0 else (g0 ^ 0xFF)
    # h2 (built with p) against h2* (built with p ^ 0xFF): the sign decision on D
    c2, sp2, _ = r1(F8(h0 ^ p) ^ L0, +1.0)
    c2s, sp2s, _ = r1(F8(h0 ^ p ^ 0xFF) ^ L0, -1.0)
    P2, P2s = float(np.abs(sp2).max()), float(np.abs(sp2s).max())
    D = P2 - P2s
    alpha = 1.0 if D >= 0 else -1.0
    RK1_0 = p if D >= 0 else (p ^ 0xFF)
    s256_0 = np.concatenate([alpha * sp0, (-alpha * sp0)[::-1]])
    record('R1k0', 'byte', range(256), s256_0, RK1_0, None, c0, rep_of(RK1_0), ('byte', 0))
    cpas[-1].update(pair=(g0, g0 ^ 0xFF), p=p)
    # RK1_1 from its pair by the sign
    c1, sp1, s256_1 = r1(h1, alpha)
    RK1_1 = int(np.argmax(s256_1))
    record('R1k1', 'byte', range(256), s256_1, RK1_1, None, c1, rep_of(RK1_1), ('byte', 1))
    # RK1_2 from the CPA selected by D; the other one is recorded as rejected
    cw, spw = (c2, sp2) if D >= 0 else (c2s, sp2s)
    cr, spr = (c2s, sp2s) if D >= 0 else (c2, sp2)
    s256_2 = np.concatenate([alpha * spw, (-alpha * spw)[::-1]])
    RK1_2 = int(np.argmax(s256_2))
    record('R1k2', 'byte', range(256), s256_2, RK1_2, None, cw, rep_of(RK1_2), ('byte', 2))
    cpas[-1].update(built_with=RK1_0, maxrho=float(np.abs(spw).max()))
    gr = int(np.argmax(np.abs(spr)))
    record('R1k2s', 'byte', range(256), np.zeros(256), None, None, cr, gr, None, kind='rejected')
    cpas[-1].update(built_with=RK1_0 ^ 0xFF, maxrho=float(np.abs(spr).max()))
    # RK1_3 from h3 built with RK1_1
    c3, sp3, s256_3 = r1(F8(h1 ^ RK1_1) ^ R0, alpha)
    RK1_3 = int(np.argmax(s256_3))
    record('R1k3', 'byte', range(256), s256_3, RK1_3, None, c3, rep_of(RK1_3), ('byte', 3))
    RK1 = [RK1_0, RK1_1, RK1_2, RK1_3]
    dec = dict(pair=(g0, g0 ^ 0xFF), p=p, P2=P2, P2s=P2s, D=D, alpha=alpha)

    # ---------------------------------------------------------------- 4-bit CPA routines
    def cpa_hi(T, hyp, lo_fixed, tag, sel):
        """upper nibble, lower nibble fixed, full-byte HW; returns the byte"""
        cands = [(hi << 4) | lo_fixed for hi in range(16)]
        c = cpa_on_target(cands, T, hyp); sp = signed_peak_per_key(c)
        hi = int(np.argmax(alpha * sp))
        record(tag, 'upper nibble', cands, alpha * sp, cands[hi], hi, c, hi, sel)
        return cands[hi]

    def cpa_lo(T, hyp, hi_fixed, tag, sel):
        """lower nibble, upper nibble fixed, full-byte HW; returns the byte"""
        cands = [(hi_fixed << 4) | lo for lo in range(16)]
        c = cpa_on_target(cands, T, hyp); sp = signed_peak_per_key(c)
        lo = int(np.argmax(alpha * sp))
        record(tag, 'lower nibble', cands, alpha * sp, cands[lo], lo, c, lo, sel)
        return cands[lo]

    def cpa_lo_only(T, hyp, tag, sel):
        """lower nibble with the upper nibble unmodeled: HW of the lower nibble only of
        hyp ^ lo; returns the nibble"""
        cands = list(range(16))
        c = cpa_on_target(cands, T, hyp, mask=0x0F); sp = signed_peak_per_key(c)
        lo = int(np.argmax(alpha * sp))
        record(tag, 'lower nibble', cands, alpha * sp, None, lo, c, lo, sel)
        return lo

    # ---------------------------------------------------------------- Round 2 (four 4-bit CPAs)
    st = _rstate(L0, L1, R0, R1, RK1); T = use_round(2)
    l0, l1, r0, r1_ = st
    RK2_1 = RK1_2                                            # key schedule
    RK2_0 = cpa_hi(T, F8(l0) ^ l1, RK1_3 >> 4, 'R2k0hi', ('hi', 4, RK1_3 >> 4))
    s0 = F8(l0) ^ l1 ^ RK2_0; s1 = F8(r0) ^ r1_ ^ RK2_1
    h22 = F8(s0) ^ l0
    lo22 = cpa_lo_only(T, h22, 'R2k2lo', ('lo_only', 6))
    RK2_2 = cpa_hi(T, h22, lo22, 'R2k2hi', ('hi', 6, lo22))
    RK2_3 = cpa_lo(T, F8(s1) ^ r0, RK1_3 & 0xF, 'R2k3lo', ('lo', 7, RK1_3 & 0xF))
    RK2 = [RK2_0, RK2_1, RK2_2, RK2_3]
    # cross-check only: 7-bit CPA on RK2_1, which the key schedule already fixes
    cchk = cpa_on_target(G128, T, F8(r0) ^ r1_); spc = signed_peak_per_key(cchk)
    s256_c = np.concatenate([alpha * spc, (-alpha * spc)[::-1]])
    vchk = int(np.argmax(s256_c))
    record(_CHECK, 'byte', range(256), s256_c, vchk, None, cchk, rep_of(vchk),
           ('byte', 5), counted=False, kind='check')

    # ---------------------------------------------------------------- Rounds 3 and 4 (two 4-bit CPAs each)
    RKs = [RK1, RK2]
    for rnd in (3, 4):
        st = _rstate(*st, RKs[-1]); T = use_round(rnd)
        l0, l1, r0, r1_ = st
        kp, kq = RKs[-2], RKs[-1]                            # keys of rounds rnd-2 and rnd-1
        nxo = nx8(((kp[0] & 0xF) << 4) | (kp[1] & 0xF))
        K0 = ((nxo >> 4) << 4) | (kq[3] >> 4); K1 = kq[2]    # key schedule
        s0 = F8(l0) ^ l1 ^ K0; s1 = F8(r0) ^ r1_ ^ K1
        K2 = cpa_lo(T, F8(s0) ^ l0, nxo & 0xF, 'R%dk2lo' % rnd, ('lo', 4 * (rnd - 1) + 2, nxo & 0xF))
        K3 = cpa_lo(T, F8(s1) ^ r0, kq[3] & 0xF, 'R%dk3lo' % rnd, ('lo', 4 * (rnd - 1) + 3, kq[3] & 0xF))
        RKs.append([K0, K1, K2, K3])
    rec = RKs[0] + RKs[1] + RKs[2] + RKs[3]
    for cp in cpas:
        cp['decision'] = dec
    return rec, alpha, pk, ps, rs, cpas

# ============================================================================
# 3. 64-bit master key : NX-equivalence class by inverting the key schedule
# ============================================================================
PERM = [56,57,58,59,16,17,18,19,20,21,22,23,24,25,26,27,
        60,61,62,63,28,29,30,31,32,33,34,35,36,37,38,39,
        40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,
         0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15]
Ks = [[0,1,2,3,8,9,10,11],[4,5,6,7,12,13,14,15],
      [16,17,18,19,24,25,26,27],[20,21,22,23,28,29,30,31]]

_nx_bits = nx_bits

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

def verify_class(cls, rk64):
    """Expand every member of the class with the key schedule.  Returns (same, equal):
    same  = every member gives the same 64 round-key bytes (the property of the class),
    equal = those 64 bytes are the schedule rk64 stored with the traces."""
    exp = {tuple(ks32(list(c))) for c in cls}
    same = len(exp) == 1
    return same, same and next(iter(exp)) == tuple(rk64)

# ============================================================================
# 4. One set : attack, check, class
# ============================================================================
def run_one(path):
    d  = np.load(path)
    tr = d['traces'].astype(np.float64)
    pt = d['pt']
    rk64 = [int(x) for x in d['rk']]
    ref = rk64[:16]
    master = [int(x) for x in np.ravel(d['master'])] if d['master'].size else None
    import time
    t0 = time.perf_counter(); rounds_of(tr); t_rounds = time.perf_counter() - t0
    t0 = time.perf_counter(); rec, alpha, pk, ps, rs, cpas = recover_fullkey(tr, pt); t_attack = time.perf_counter() - t0
    cls = {tuple(_bits_to_bytes(m)) for m in master_class([rec[4*j:4*j+4] for j in range(4)])}
    same, class_ok = verify_class(cls, rk64)
    assert same, "members of the equivalence class expand to different round keys: " + path
    rank = {}
    for cp in cpas:
        idx = correct_index(cp, ref)
        rank[cp['tag']] = None if idx is None else rank_of(cp['score'], idx)
    dec = cpas[0]['decision']
    return dict(ref=ref, rec=rec, ok=(rec == ref), alpha=alpha, pk=pk, ps=ps, rank=rank,
                value={cp['tag']: cp['value'] for cp in cpas},
                nib={cp['tag']: cp['nib'] for cp in cpas},
                target={cp['tag']: cp['target'] for cp in cpas},
                ncand={cp['tag']: cp['ncand'] for cp in cpas},
                pair=list(dec['pair']), p=dec['p'], P2=dec['P2'], P2s=dec['P2s'], D=dec['D'],
                period=rs[0], boundary=rs[1],
                master=master, csz=len(cls), class_ok=class_ok,
                min_=(tuple(master) in cls) if master else None,
                members=sorted("".join("%02X" % b for b in c) for c in cls),
                t_rounds=t_rounds, t_attack=t_attack,
                ntr=tr.shape[0], nsm=tr.shape[1])

def hx(v):
    return " ".join("%02X" % x for x in v)

_DERIVED = [('RK2_1', 5, '= RK1_2'),
            ('RK3_0', 8, 'upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3'),
            ('RK3_1', 9, '= RK2_2'),
            ('RK4_0', 12, 'upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3'),
            ('RK4_1', 13, '= RK3_2')]

def _cpa_table(r):
    """Markdown rows of the 13 CPAs, the cross-check and the derived bytes of one set."""
    L = ["| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \\|rho\\| | Peak sample |",
         "|---|---|---|---:|---|---:|---:|---:|"]
    for t in _ORDER13:
        val = r['value'][t]; nib = r['nib'][t]
        if t == 'R1k2s':
            shown = "none (rejected by D)"
        elif r['target'][t] == 'lower nibble' and val is None:
            shown = "`0x?%X`" % nib
        else:
            shown = "`%02X`" % val
        L.append("| %s | %s | %s | %d | %s | %s | %.3f | %d |" % (
            t, _NAME[t], r['target'][t], r['ncand'][t],
            shown, "-" if r['rank'][t] is None else r['rank'][t], r['pk'][t], r['ps'][t]))
    t = _CHECK
    L.append("| %s | %s (check only, not counted) | byte | 128 | `%02X` | %s | %.3f | %d |" % (
        t, _NAME[t], r['value'][t], r['rank'][t], r['pk'][t], r['ps'][t]))
    L += ["", "| Derived byte | Value | From |", "|---|---|---|"]
    for name, i, how in _DERIVED:
        L.append("| %s | `%02X` | %s |" % (name, r['rec'][i], how))
    return L

def main():
    L = []
    L.append("# Shadow-32 CPA : 12500-sample capture, recovery of round keys RK1..RK4\n")
    L.append("- Method : Algorithm 1 of the paper. Round 1: five 7-bit CPAs over the 128 representatives")
    L.append("  (h0, h1, h2, h2*, h3; the h2* CPA is rejected by the decision on D and returns no value).")
    L.append("  Round 2: four 4-bit CPAs of 16 candidates (upper nibble of RK2_0; lower nibble of RK2_2 with the")
    L.append("  upper nibble unmodeled, then its upper nibble with the lower fixed; lower nibble of RK2_3).")
    L.append("  Rounds 3 and 4: two 4-bit CPAs each (lower nibbles of RK_2^r and RK_3^r). 13 CPAs, 12 of which")
    L.append("  return a value; 5 x 128 + 8 x 16 = 768 candidate evaluations. The other five bytes (RK2_1, RK3_0,")
    L.append("  RK3_1, RK4_0, RK4_1) and every fixed nibble come from the key schedule.")
    L.append("- Ranking : candidates ordered by alpha times the signed correlation at their peak; the rank column")
    L.append("  is the position of the correct candidate (Round 1: among the 256 values scored by the 128 curves).")
    L.append("- Cross-check : a 7-bit CPA on RK2_1, a byte the key schedule already fixes, is reported but not counted.")
    L.append("- Samples : a Round-r CPA runs over `[b0 + (r-1)P, b0 + rP)`, with the round period P and the round")
    L.append("  boundary b0 taken from each set's mean trace alone (`round_structure.py`); neither the key nor the")
    L.append("  outcome of an attack is used. Values per set are listed below.")
    L.append("- Class check : every member of the master-key equivalence class is expanded with the key schedule")
    L.append("  (`shadow32_ks.ks32`) and must give the same 64 round-key bytes, equal to the `rk` field of the traces.")
    L.append("- Capture : clkout 7.5MHz / adc 7.5MHz, seekclip phase, `-O0` firmware\n")

    # ---------------------------------------------------------------- fixed key
    print("[1/2] Fixed-key set ...", flush=True)
    r = run_one(FIXED); r['name'] = 'fixed'
    L.append("## 1. Fixed-key set (`s32_ref_12500.npz`, %d x %d)\n" % (r['ntr'], r['nsm']))
    L.append("Recovered RK1..RK4 : `%s`" % hx(r['rec']))
    L.append("Reference RK1..RK4 : `%s`" % hx(r['ref']))
    L.append("Matching bytes : **%d/16**,  round period %d, round boundary %d\n"
             % (sum(a == b for a, b in zip(r['rec'], r['ref'])), r['period'], r['boundary']))
    L.append("Sign decision : h0 pair {%02X, %02X}, p = %02X (positive peak); max|rho| h2 (built with %02X) = %.3f, "
             "h2* (built with %02X) = %.3f, D = %+.3f -> RK1_0 = %02X, alpha = %+d\n"
             % (r['pair'][0], r['pair'][1], r['p'], r['p'], r['P2'], r['p'] ^ 0xFF, r['P2s'], r['D'],
                r['rec'][0], int(r['alpha'])))
    L += _cpa_table(r)
    v12 = [r['pk'][t] for t in _ORDER]
    v11 = [r['pk'][t] for t in _ORDER if t != 'R2k2lo']
    L.append("")
    L.append("- Lower-nibble CPA of RK2_2 (upper nibble unmodeled) : |rho| %.3f" % r['pk']['R2k2lo'])
    L.append("- The other 11 value-returning CPAs : |rho| %.3f ~ %.3f" % (min(v11), max(v11)))
    L.append("- All 12 value-returning CPAs : min %.3f, max %.3f, mean %.3f; every correct candidate ranks %s"
             % (min(v12), max(v12), float(np.mean(v12)),
                "first" if all(r['rank'][t] == 1 for t in _ORDER) else "NOT first"))
    L.append("- Rejected h2* CPA : max|rho| %.3f" % r['pk']['R1k2s'])
    L.append("- RK2_1 cross-check (7-bit CPA, not counted) : `%02X`, |rho| %.3f, %s the derived value\n"
             % (r['value'][_CHECK], r['pk'][_CHECK], "equals" if r['value'][_CHECK] == r['rec'][5] else "DIFFERS from"))
    L.append("Equivalence class size %d (no master field, this set has the round keys hard-coded as constants "
             "in the firmware); every member expands to the stored 64 round-key bytes : %s\n"
             % (r['csz'], "verified" if r['class_ok'] else "FAILED"))
    named = "DC4A3DB3035C950E"       # the member of the class named in Section 4.4 of the paper
    L.append("Members of the class (64-bit master keys), smallest `%s`, largest `%s`; the member named in the "
             "paper, `%s`, is in the class : %s\n"
             % (r['members'][0], r['members'][-1], named, "yes" if named in r['members'] else "NO"))
    L.append("Running time : the thirteen CPAs of Algorithm 1 (with the cross-check) and the round location "
             "are timed by the script and printed to the console; the times are machine dependent and are not "
             "recorded here.\n")
    print("      16/16 = %s  |rho| %.3f~%.3f  D %+.3f  class %d %s"
          % (r['ok'], min(v12), max(v12), r['D'], r['csz'], "verified" if r['class_ok'] else "FAILED"), flush=True)
    print("      class member named in the paper %s : %s" % (named, "in the class" if named in r['members'] else "NOT in the class"), flush=True)
    print("      wall-clock time on %d traces: locating the rounds from the mean trace %.2f s; Algorithm 1 "
          "(thirteen CPAs, the cross-check and the round location) %.2f s" % (r['ntr'], r['t_rounds'], r['t_attack']), flush=True)

    # ---------------------------------------------------------------- ten keys
    print("[2/2] 10 random-key sets ...", flush=True)
    rows = []
    for i, p in enumerate(KEYSET):
        rr = run_one(p); rr['name'] = "key%02d" % (i + 1); rows.append(rr)
        print("      %s  %s  |rho|min %.3f  D %+.3f  master@class(%d) %s  class %s"
              % (rr['name'], "OK " if rr['ok'] else "FAIL",
                 min(rr['pk'][t] for t in _ORDER), rr['D'], rr['csz'],
                 "O" if rr['min_'] else "X", "verified" if rr['class_ok'] else "FAILED"), flush=True)

    n_full = sum(x['ok'] for x in rows)
    n_min  = sum(bool(x['min_']) for x in rows)
    n_cls  = sum(bool(x['class_ok']) for x in rows)
    all12  = [x['pk'][t] for x in rows for t in _ORDER]
    all11  = [x['pk'][t] for x in rows for t in _ORDER if t != 'R2k2lo']
    lo22   = [x['pk']['R2k2lo'] for x in rows]
    h2s    = [x['pk']['R1k2s'] for x in rows]
    n_rank1 = sum(x['rank'][t] == 1 for x in rows for t in _ORDER)

    L.append("## 2. 10 random-key sets (`s32_key01..10_12500.npz`, %d x %d each)\n"
             % (rows[0]['ntr'], rows[0]['nsm']))
    L.append("| Set | master | RK1 | RK2 | RK3 | RK4 | Match | pair | D | alpha | min\\|rho\\| (12) | "
             "master in class (size) | class expands to rk | P, b0 |")
    L.append("|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|")
    for x in rows:
        L.append("| %s | `%s` | `%s` | `%s` | `%s` | `%s` | %s | {%02X, %02X} | %+.3f | %+d | %.3f | %s (%d) | %s | %d, %d |" % (
            x['name'], "".join("%02X" % b for b in x['master']),
            hx(x['rec'][0:4]), hx(x['rec'][4:8]), hx(x['rec'][8:12]), hx(x['rec'][12:16]),
            "16/16" if x['ok'] else "FAIL", x['pair'][0], x['pair'][1], x['D'], int(x['alpha']),
            min(x['pk'][t] for t in _ORDER),
            "yes" if x['min_'] else "no", x['csz'], "verified" if x['class_ok'] else "FAILED",
            x['period'], x['boundary']))
    L.append("")
    L.append("Peak |rho| of the correct candidate in every CPA, rank of the correct candidate in brackets "
             "(h2*: its maximum |rho|, no correct candidate; RK2_1: the cross-check, not counted):\n")
    tg = rows[0]['target']
    L.append("| Set | " + " | ".join(_NAME[t] + (" " + tg[t] if tg[t] != 'byte' else "")
                                      + (" (h2*)" if t == 'R1k2s' else "") for t in _ORDER13)
             + " | RK2_1 check |")
    L.append("|---|" + "---:|" * (len(_ORDER13) + 1))
    for x in rows:
        cells = []
        for t in _ORDER13:
            cells.append("%.3f" % x['pk'][t] if x['rank'][t] is None else "%.3f [%d]" % (x['pk'][t], x['rank'][t]))
        cells.append("%.3f [%d]" % (x['pk'][_CHECK], x['rank'][_CHECK]))
        L.append("| %s | %s |" % (x['name'], " | ".join(cells)))
    L.append("| min | " + " | ".join("%.3f" % min(x['pk'][t] for x in rows) for t in _ORDER13 + [_CHECK]) + " |")
    L.append("| max | " + " | ".join("%.3f" % max(x['pk'][t] for x in rows) for t in _ORDER13 + [_CHECK]) + " |")
    L.append("")
    L.append("- Full recovery of round keys RK1..RK4 : **%d/10 sets**; the correct candidate ranks first in "
             "%d of the %d value-returning CPAs" % (n_full, n_rank1, 12 * len(rows)))
    L.append("- True 64-bit master in the NX equivalence class : **%d/10 sets** "
             "(NX is not invertible, so the master key cannot be uniquely recovered)" % n_min)
    L.append("- Equivalence class size : %s; every member expands to the stored 64 round-key bytes on %d/10 sets"
             % (", ".join(str(x['csz']) for x in rows), n_cls))
    L.append("- Lower-nibble CPA of RK2_2 (upper nibble unmodeled, 10 values) : |rho| **%.3f ~ %.3f**, mean %.3f"
             % (min(lo22), max(lo22), float(np.mean(lo22))))
    L.append("- The other 11 value-returning CPAs (10 sets x 11 = %d values) : |rho| **%.3f ~ %.3f**, mean %.3f"
             % (len(all11), min(all11), max(all11), float(np.mean(all11))))
    L.append("- All 12 value-returning CPAs (%d values) : min %.3f, max %.3f, mean %.3f"
             % (len(all12), min(all12), max(all12), float(np.mean(all12))))
    L.append("- Rejected h2* CPA : max|rho| %.3f ~ %.3f; D = %+.3f ~ %+.3f, alpha = +1 on %d/10 sets"
             % (min(h2s), max(h2s), min(x['D'] for x in rows), max(x['D'] for x in rows),
                sum(x['alpha'] > 0 for x in rows)))
    L.append("")
    for x in rows:
        L += ["### %s\n" % x['name'],
              "Sign decision : pair {%02X, %02X}, p = %02X, max|rho| h2 = %.3f, h2* = %.3f, D = %+.3f, alpha = %+d\n"
              % (x['pair'][0], x['pair'][1], x['p'], x['P2'], x['P2s'], x['D'], int(x['alpha']))]
        L += _cpa_table(x) + [""]

    txt = "\n".join(L)
    open(os.path.join(OUT, "RESULTS_shadow32_12500.md"), "w", encoding="utf-8").write(txt)
    print("\n" + txt)

    import json
    keep = ['name', 'ntr', 'nsm', 'ref', 'rec', 'ok', 'alpha', 'pk', 'ps', 'rank', 'value', 'nib',
            'target', 'ncand', 'pair', 'p', 'P2', 'P2s', 'D', 'period', 'boundary', 'master',
            'csz', 'class_ok', 'min_']
    json.dump([{k: x[k] for k in keep} for x in rows + [r]],
              open(os.path.join(OUT, "_peaks_12500.json"), "w", encoding="utf-8"), indent=1)
    _fig_success(rows)
    _fig_rounds(rows)
    print("\nResult : results/RESULTS_shadow32_12500.md")
    print("Cache  : results/_peaks_12500.json")
    print("Figs   : figures/shadow32_10keys/fig_success.pdf (+ .png)")
    print("         figures/shadow32_10keys/fig_fullkey_rounds.pdf (+ .png)")

# ============================================================================
# 5. Figures (paper rcParams)
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
        # figsize is kept as is (no bbox='tight'), so that the fonts match the other
        # figures when the paper places the figure at \columnwidth.
        "figure.constrained_layout.use": True,
        "figure.constrained_layout.h_pad": 0.01,
        "figure.constrained_layout.w_pad": 0.01,
    })
    return plt

def _fig_success(rows):
    """Peak |rho| of the correct candidate in each of the 12 value-returning CPAs of Algorithm 1,
    per key set, with the lower-nibble CPA of RK2_2 marked and the 4/sqrt(N) line."""
    plt = _rc()
    rows = [x for x in rows if x['name'].startswith('key')]
    thr = 4.0 / np.sqrt(rows[0]['ntr'])
    fig, ax = plt.subplots(figsize=(W_FULL, 2.10))
    ax.axhline(thr, color='#d62728', ls='--', lw=0.8, label=r'$4/\sqrt{N} = %.3f$' % thr)
    ilo = _ORDER.index('R2k2lo')
    for i, x in enumerate(rows):
        ys = [x['pk'][k] for k in _ORDER]
        xs = (i + 1) + np.linspace(-0.22, 0.22, len(ys))
        ax.scatter(xs, ys, s=5, color='#1f77b4', alpha=0.85, edgecolor='none', zorder=3)
        ax.scatter([xs[ilo]], [ys[ilo]], s=9, color='#ff7f0e', edgecolor='none', zorder=4)
    ax.scatter([], [], s=5, color='#1f77b4', label=r'correct-candidate $|\rho|$, 12 CPAs per key')
    ax.scatter([], [], s=9, color='#ff7f0e', label=r'lower nibble of $RK^2_2$ (upper nibble unmodeled)')  # paper spelling
    ax.set_xticks(range(1, len(rows) + 1))
    ax.set_xticklabels(['%d' % (i + 1) for i in range(len(rows))])
    ax.set_xlim(0.4, len(rows) + 0.6); ax.set_ylim(0, 1.0)
    ax.set_xlabel('Key set'); ax.set_ylabel(r'Correct-candidate $|\rho|$')
    ax.grid(True, axis='y', alpha=0.35)
    ax.legend(loc='lower center', ncol=3, handlelength=1.4, borderpad=0.25, labelspacing=0.2,
              columnspacing=0.8, bbox_to_anchor=(0.5, 0.13))
    fig.savefig(os.path.join(FIG, "fig_success.pdf"))
    fig.savefig(os.path.join(FIG, "fig_success.png"), dpi=DPI); plt.close(fig)

def _fig_rounds(rows):
    """One CPA per round on the representative set (key01), correct candidate highlighted."""
    plt = _rc()
    d  = np.load(KEYSET[0])
    tr = d['traces'].astype(np.float64); pt = d['pt']
    ref = [int(x) for x in d['rk'][:16]]
    L0, L1, R0, R1 = (pt[:, i].astype(np.int64) for i in range(4))
    rec = recover_fullkey(tr, pt)[0]
    IV, _ = rounds_of(tr)

    fig, axs = plt.subplots(1, 4, figsize=(W_FULL, 1.70), sharey=True)
    # Round 1 : 7-bit CPA over the representatives 0..127, as in the attack
    assert ref[0] < 128, 'RK^1_0 of the representative set is not a representative'
    a, b = IV[0]; T = tr[:, a:b]; h0 = F8(L0) ^ L1
    _panel(axs[0], cpa_on_target(range(128), T, h0), ref[0],
           r'Round 1: $RK^1_0$ (7-bit)', x0=a)
    # Round 2 : 4-bit CPA on the upper nibble of RK^2_0; its lower nibble is the upper
    # nibble of RK^1_3 by the key schedule, so only 16 candidates are enumerated.
    st = _rstate(L0, L1, R0, R1, rec[0:4]); a, b = IV[1]; T = tr[:, a:b]
    lo2 = (rec[3] >> 4) & 0xF
    assert (ref[4] & 0xF) == lo2, 'key-schedule relation does not hold'
    _panel(axs[1], cpa_on_target([(hi << 4) | lo2 for hi in range(16)], T,
           F8(st[0]) ^ st[1]), ref[4], r'Round 2: $RK^2_0$ (4-bit)', hi4=True, x0=a)
    st2 = _rstate(*st, rec[4:8]); a, b = IV[2]; T = tr[:, a:b]
    nxo = nx8(((rec[0] & 0xF) << 4) | (rec[1] & 0xF))
    RK3_0 = (((nxo >> 4) & 0xF) << 4) | ((rec[7] >> 4) & 0xF)
    s0 = F8(st2[0]) ^ st2[1] ^ RK3_0
    _panel(axs[2], cpa_on_target([((nxo & 0xF) << 4) | lo for lo in range(16)], T,
           F8(s0) ^ st2[0]), ref[10], r'Round 3: $RK^3_2$ (4-bit)', lo4=True, x0=a)
    st3 = _rstate(*st2, rec[8:12]); a, b = IV[3]; T = tr[:, a:b]
    nxo4 = nx8(((rec[4] & 0xF) << 4) | (rec[5] & 0xF))
    RK4_0 = (((nxo4 >> 4) & 0xF) << 4) | ((rec[11] >> 4) & 0xF)
    s0 = F8(st3[0]) ^ st3[1] ^ RK4_0
    _panel(axs[3], cpa_on_target([((nxo4 & 0xF) << 4) | lo for lo in range(16)], T,
           F8(s0) ^ st3[0]), ref[14], r'Round 4: $RK^4_2$ (4-bit)', lo4=True, x0=a)
    axs[0].set_ylabel('Absolute correlation')
    fig.savefig(os.path.join(FIG, "fig_fullkey_rounds.pdf"))
    fig.savefig(os.path.join(FIG, "fig_fullkey_rounds.png"), dpi=DPI); plt.close(fig)

def _panel(ax, c, correct, title, lo4=False, hi4=False, x0=0):
    if lo4:
        col = correct & 0xF          # the lower nibble was enumerated
    elif hi4:
        col = (correct >> 4) & 0xF   # the upper nibble was enumerated
    else:
        col = correct
    y   = np.abs(c)
    xs  = x0 + np.arange(c.shape[0])            # absolute sample index
    for i in range(c.shape[1]):
        if i != col:
            ax.plot(xs, y[:, i], color=[0.88, 0.88, 0.88], lw=0.25, rasterized=True)
    ax.plot(xs, y[:, col], color='#d62728', lw=0.7, label='0x%02X' % correct)
    ax.set_ylim([-0.05, 0.95]); ax.set_xlim([xs[0], xs[-1] + 1])
    ax.grid(True, alpha=0.35)
    ax.set_title(title)
    ax.set_xlabel('Sample index')
    ax.legend(handlelength=1.1, borderpad=0.2, handletextpad=0.3, labelspacing=0.2,
              loc='upper left')

if __name__ == "__main__":
    # "--figs" : redraw the figures from the cached peaks (results/_peaks_12500.json)
    _ensure_dirs()
    if "--figs" in sys.argv:
        import json
        rows = json.load(open(os.path.join(OUT, "_peaks_12500.json"), encoding="utf-8"))
        _fig_success(rows); _fig_rounds(rows)
        print("Figures regenerated")
    else:
        main()
