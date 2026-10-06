# -*- coding: utf-8 -*-
"""Shadow-32 reference functions for the capture scripts, and a share-level simulation of the masked
firmwares that shows the defect of v1, the firmware of the previous version of the paper, and the
correction of the deposited firmwares: v2 of masking_ISW.c and v3 of masking_ISWLUT.c, which add
the key mask into share 1 (`version=2` below covers both, `lut` selects the table-recomputation
gadget).

  round32(state4, k4)         one round on [l0, l1, r0, r1] with round-key bytes [k0..k3],
                              returns the state after the round [l0', l1', r0', r1']
                              (what the one-round KAT firmware returns)
  enc32(pt4, rk64)            16 rounds, returns [r0, l1, l0, r1] (capture_exp.enc32 order,
                              what the SHADOW32_FULL firmware returns)
  masked_round_sim(...)       share-level simulation of shadow32_round_masked (v1 or v2)

Usage :  python shadow32_ref.py          (self-test)
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
M8 = 0xFF
def ROL8(v, r): return ((v << r) | (v >> (8 - r))) & M8
def F8(x):      return (ROL8(x, 1) & ROL8(x, 7)) ^ ROL8(x, 2)
def g8(x):      return ROL8(x, 1) & ROL8(x, 7)

RK32_DEFAULT = [
    0x0D,0x3B,0x60,0x33, 0x43,0x60,0x25,0x3C, 0x13,0x25,0x89,0xC5, 0x3C,0x89,0x0D,0x5D,
    0x25,0x0D,0x40,0xD1, 0x8D,0x40,0x14,0x15, 0x11,0x14,0x91,0x56, 0xC5,0x91,0x03,0x6D,
    0x16,0x03,0x02,0xD6, 0x1D,0x02,0x08,0x63, 0x06,0x08,0x31,0x39, 0x43,0x31,0x2C,0x90,
    0x69,0x2C,0x01,0x0A, 0x20,0x01,0x11,0xAB, 0x9A,0x11,0x00,0xBC, 0x0B,0x00,0x04,0xCE,
]

def round32(state, k):
    l0, l1, r0, r1 = state
    k0, k1, k2, k3 = k
    s0 = F8(l0) ^ l1 ^ k0
    s1 = F8(r0) ^ r1 ^ k1
    lo1 = F8(s0) ^ l0 ^ k2
    ro1 = F8(s1) ^ r0 ^ k3
    return [s1, lo1, s0, ro1]           # l0' = s1, l1' = lo1, r0' = s0, r1' = ro1

def enc32(pt, rk):
    st = list(pt)
    for i in range(16):
        st = round32(st, rk[4*i:4*i+4])
    l0, l1, r0, r1 = st
    return [r0, l1, l0, r1]

# ---------------------------------------------------------------- share-level simulation
class MB:
    """MaskedByte: value = s0 ^ s1"""
    def __init__(self, s0, s1): self.s0, self.s1 = s0 & M8, s1 & M8
    def val(self): return self.s0 ^ self.s1

def mask_byte(v, r): return MB(r, v ^ r)
def m_rol(a, rot): return MB(ROL8(a.s0, rot), ROL8(a.s1, rot))
def m_xor(a, b): return MB(a.s0 ^ b.s0, a.s1 ^ b.s1)
def m_refresh(a, r): return MB(a.s0 ^ r, a.s1 ^ r)
def isw_and(a, b, r):
    r10 = (r ^ (a.s0 & b.s1)) ^ (a.s1 & b.s0)
    return MB((a.s0 & b.s0) ^ r, (a.s1 & b.s1) ^ r10)
def table_g(a, y0):
    # tableG of masking_ISWLUT.c: T[x] = g(x ^ s0) ^ y0, out = (y0, T[s1])
    return MB(y0, g8(a.s1 ^ a.s0) ^ y0)
def key_add_v1(a, k, q): return MB(a.s0 ^ k, a.s1)          # v1: masked key into share 0 only
def key_add_v2(a, k, q): return MB(a.s0 ^ k, a.s1 ^ q)      # v2: its mask into share 1 as well

def masked_F(a, m, f, lut):
    """g(a) with the AND either as ISW (refresh then ISW_AND) or as the masked table"""
    if lut:
        t = m_refresh(a, f)
        and_v = table_g(t, m)
    else:
        a1 = m_refresh(m_rol(a, 1), f)
        and_v = isw_and(a1, m_rol(a, 7), m)
    return and_v, m_rol(a, 2)

def masked_round_sim(ml0, ml1, mr0, mr1, m, k, q, f, version=2, lut=False):
    """shadow32_round_masked on shares. m, k, q, f: 4 bytes each; k = RK ^ q (as in the firmware)."""
    key_add = key_add_v2 if version == 2 else key_add_v1
    and_v, rol2 = masked_F(ml0, m[0], f[0], lut); s0 = key_add(m_xor(m_xor(and_v, ml1), rol2), k[0], q[0])
    and_v, rol2 = masked_F(mr0, m[1], f[1], lut); s1 = key_add(m_xor(m_xor(and_v, mr1), rol2), k[1], q[1])
    and_v, rol2 = masked_F(s0, m[2], f[2], lut);  lo1 = key_add(m_xor(m_xor(and_v, ml0), rol2), k[2], q[2])
    and_v, rol2 = masked_F(s1, m[3], f[3], lut);  ro1 = key_add(m_xor(m_xor(and_v, mr0), rol2), k[3], q[3])
    return s1, lo1, s0, ro1                     # l0' = s1, l1' = lo1, r0' = s0, r1' = ro1

def firmware_one_round_sim(pt20, version=2, lut=False):
    """get_pt of the one-round firmware on a 20-byte input; returns the unmasked state after the round."""
    p = [int(x) for x in pt20]
    m, r_in, q, f = p[4:8], p[8:12], p[12:16], p[16:20]
    k = [RK32_DEFAULT[j] ^ q[j] for j in range(4)]
    st = [mask_byte(p[j], r_in[j]) for j in range(4)]
    out = masked_round_sim(*st, m=m, k=k, q=q, f=f, version=version, lut=lut)
    return [x.val() for x in out]

def firmware_full_sim(pt200, version=2, lut=False):
    """get_pt of the SHADOW32_FULL firmware on a 200-byte input; returns the ciphertext [r0, l1, l0, r1]."""
    p = [int(x) for x in pt200]
    st = [mask_byte(p[j], p[4 + j]) for j in range(4)]
    for i in range(16):
        rr = p[8 + 12*i: 8 + 12*i + 12]
        m, f, q = rr[0:4], rr[4:8], rr[8:12]
        k = [RK32_DEFAULT[4*i + j] ^ q[j] for j in range(4)]
        st = list(masked_round_sim(*st, m=m, k=k, q=q, f=f, version=version, lut=lut))
    l0, l1, r0, r1 = [x.val() for x in st]
    return [r0, l1, l0, r1]

def selftest(n=2000, seed=1):
    rng = np.random.default_rng(seed)
    bad = {"v1_isw": 0, "v1_lut": 0, "v2_isw": 0, "v2_lut": 0, "v2_full_isw": 0, "v2_full_lut": 0, "v1_zero_mask": 0}
    for _ in range(n):
        p = rng.integers(0, 256, 20, dtype=np.uint8)
        ref = round32([int(x) for x in p[:4]], RK32_DEFAULT[:4])
        bad["v1_isw"] += firmware_one_round_sim(p, 1, False) != ref
        bad["v1_lut"] += firmware_one_round_sim(p, 1, True) != ref
        bad["v2_isw"] += firmware_one_round_sim(p, 2, False) != ref
        bad["v2_lut"] += firmware_one_round_sim(p, 2, True) != ref
        p0 = p.copy(); p0[12:16] = 0                       # v1 is correct only when r_key = 0
        bad["v1_zero_mask"] += firmware_one_round_sim(p0, 1, False) != ref
        P = rng.integers(0, 256, 200, dtype=np.uint8)
        refc = enc32([int(x) for x in P[:4]], RK32_DEFAULT)
        bad["v2_full_isw"] += firmware_full_sim(P, 2, False) != refc
        bad["v2_full_lut"] += firmware_full_sim(P, 2, True) != refc
    print("share-level simulation, %d random inputs, mismatches against the reference:" % n)
    for kk, v in bad.items():
        print("  %-14s %5d  %s" % (kk, v, "(expected: all wrong, the deposited defect)" if kk in ("v1_isw", "v1_lut") else ""))
    assert bad["v2_isw"] == bad["v2_lut"] == bad["v2_full_isw"] == bad["v2_full_lut"] == bad["v1_zero_mask"] == 0
    assert bad["v1_isw"] > 0.99 * n and bad["v1_lut"] > 0.99 * n
    print("OK: v2 matches the reference for every input; v1 only when the key mask is zero.")

if __name__ == "__main__":
    selftest()
