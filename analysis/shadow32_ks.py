# -*- coding: utf-8 -*-
"""
Shadow-32 key schedule, in the form used by the capture firmware.

`ks32` is the function of capture/capture_exp.py (which cannot be imported here because it
imports the ChipWhisperer package), copied without change.  `nx8` is the 8-bit NX module on
its own, as used by the attack to derive the upper nibbles of RK^r_0 and RK^r_2 for r = 3, 4.

cpa_shadow32_12500.py uses `ks32` to verify the master-key equivalence class: every member
of the class must expand to the same 64 round-key bytes, and those must equal the `rk`
field stored with the traces.
"""

PERM32 = [
    56, 57, 58, 59, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
    60, 61, 62, 63, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
    40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15]

# bit positions (after the permutation) that form the four round-key bytes of a round
K0 = [0, 1, 2, 3, 8, 9, 10, 11]
K1 = [4, 5, 6, 7, 12, 13, 14, 15]
K2 = [16, 17, 18, 19, 24, 25, 26, 27]
K3 = [20, 21, 22, 23, 28, 29, 30, 31]


def _pack8(b, idx):
    v = 0
    for i in range(8):
        v = (v << 1) | (b[idx[i]] & 1)
    return v


def nx_bits(k):
    """NX on eight bits k[0..7] (k[0] is the most significant), as in the firmware."""
    return [k[0] & (k[0] ^ k[6]),                 k[1] & (k[1] ^ k[7]),
            k[2] & (k[2] ^ k[0] ^ k[6]),          k[3] & (k[3] ^ k[1] ^ k[7]),
            k[4] & (k[4] ^ k[2] ^ k[0] ^ k[6]),   k[5] & (k[5] ^ k[3] ^ k[1] ^ k[7]),
            k[6] & (k[4] ^ k[2] ^ k[0]),          k[7] & (k[5] ^ k[3] ^ k[1])]


def nx8(x):
    """NX as an 8-bit function."""
    k = [(x >> (7 - i)) & 1 for i in range(8)]
    nb = nx_bits(k)
    return sum(nb[i] << (7 - i) for i in range(8))


def ks32(master8):
    """8-byte master key -> the 64 round-key bytes rk[0..63] (identical to the firmware
    shadow32_key_schedule and to capture/capture_exp.py)."""
    b = [(master8[i >> 3] >> (7 - (i & 7))) & 1 for i in range(64)]
    rk = []
    for r in range(16):
        rc = r + 1
        b[3] ^= (rc >> 4) & 1; b[4] ^= (rc >> 3) & 1; b[5] ^= (rc >> 2) & 1
        b[6] ^= (rc >> 1) & 1; b[7] ^= rc & 1
        b[56:64] = nx_bits(b[56:64])
        b = [b[PERM32[i]] for i in range(64)]
        rk += [_pack8(b, K0), _pack8(b, K1), _pack8(b, K2), _pack8(b, K3)]
    return rk


if __name__ == "__main__":
    # the master key of the first random-key set and its stored round keys
    m = [0xE1, 0x00, 0x20, 0xBD, 0x4E, 0x59, 0x0E, 0x12]
    print(" ".join("%02X" % v for v in ks32(m)[:16]))
