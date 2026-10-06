# Fixed-key Shadow-32 set: correlation figures and the sign decision

Round period 748, round boundary 358 (from the mean trace).  Round intervals: [358, 1106), [1106, 1854), [1854, 2602), [2602, 3350)

- Fig. 6(a) 0..127: max 0x0D (+0.896), min 0x72 (-0.793)
- Fig. 6(b) 128..255: max 0x8D (+0.793), min 0xF2 (-0.896)
- RK1_0 pair {0x0D, 0xF2} (|rho| 0.896), positive-peak member p = 0x0D
- Fig. 7 RK1_1 candidate pair {0x3B, 0xC4}, peak |rho| 0.900
- Fig. 8(a,b) decision: max|rho| h2 (built with 0x0D) = 0.811, h2* (built with 0xF2) = 0.088, D = +0.723 -> RK1_0 = 0x0D, alpha = +1
- Fig. 8(c,d): max|rho| h3 (built with RK1_1 = 0x3B) = 0.795, h3* = 0.093
- Round 1 recovered: RK1_0 0x0D, RK1_1 0x3B, RK1_2 0x60, RK1_3 0x33
- Fig. 9: Round-2 4-bit CPAs give RK2_0 0x43, RK2_2 lower nibble 0x?5 then 0x25, RK2_3 0x3C; RK2_1 = RK1_2 = 0x60 from the key schedule
- RK2_1 check (7-bit CPA, not counted): 0x60, |rho| 0.901, equals the key-schedule value

## The 13 CPAs of Algorithm 1 on this set

| CPA | Target | Candidates | Result | max \|rho\| | Figure |
|---|---|---:|---|---:|---|
| RK1_0 (h0) | byte, pair {0x0D, 0xF2} resolved by D | 128 | 0x0D | 0.896 | Fig. 6 |
| RK1_1 (h1) | byte, pair {0x3B, 0xC4} resolved by the sign | 128 | 0x3B | 0.900 | Fig. 7 |
| RK1_2 (h2, RK1_0 = 0x0D assumed) | byte | 128 | 0x60 | 0.811 | Fig. 8(a) |
| RK1_2 (h2*, RK1_0 = 0xF2 assumed) | byte | 128 | rejected by D | 0.088 | Fig. 8(b) |
| RK1_3 (h3, RK1_1 = 0x3B) | byte | 128 | 0x33 | 0.795 | Fig. 8(c) |
| RK2_0 | upper nibble (lower = 0x3 from RK1_3) | 16 | 0x43 | 0.904 | Fig. 9(a) |
| RK2_2 | lower nibble (upper unmodeled) | 16 | 0x?5 | 0.546 | Fig. 9(b) |
| RK2_2 | upper nibble (lower = 0x5 from the previous CPA) | 16 | 0x25 | 0.794 | Fig. 9(c) |
| RK2_3 | lower nibble (upper = 0x3 from RK1_3) | 16 | 0x3C | 0.802 | Fig. 9(d) |
| RK3_2 | lower nibble (upper = 0x8 from NX) | 16 | 0x89 | 0.794 | Fig. 10(a) |
| RK3_3 | lower nibble (upper = 0xC from RK2_3) | 16 | 0xC5 | 0.793 | Fig. 10(b) |
| RK4_2 | lower nibble (upper = 0x0 from NX) | 16 | 0x0D | 0.798 | Fig. 10(c) |
| RK4_3 | lower nibble (upper = 0x5 from RK3_3) | 16 | 0x5D | 0.786 | Fig. 10(d) |

Derived from the key schedule: RK2_1 = RK1_2 = 0x60; RK3_0 = 0x13, RK3_1 = RK2_2 = 0x25; RK4_0 = 0x3C, RK4_1 = RK3_2 = 0x89.

Recovered RK1..RK4 : `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D`
Reference RK1..RK4 : `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D`
Match : **16/16**
