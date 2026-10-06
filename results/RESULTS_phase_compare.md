# Unprotected Shadow-32 at three clock phases: the Round-1 attack (Section 4.1)

Traces: `data/shadow32_fixedkey/`, 2,048 traces of 12,500 samples per set, the same firmware image (`shadow32_nop`, -O0) and the same plaintext sequence; round key `0D 3B 60 33`. Plaintext and round-key arrays identical across the sets: yes. ADC rail = v >= 0.4959 (largest code 0.4961); 1 sample = 1 cycle.

## 1. Sets, amplitude and round structure

| Set | File | `phase` field | max | min | At the rail, all samples | At the rail, Rounds 1-4 | Negative rail | Period, boundary | Round-1 window |
|---|---|---|---:|---:|---:|---:|---|---|---|
| selected phase (the paper's set) | `s32_ref_12500.npz` | `seekclip` | 0.4961 | -0.2227 | 0.0206 | 0.0204 | never reached | 748, 358 | [358, 1106) |
| phase at power-on, not selected | `s32_shadow32_O0_fixedphase_12500.npz` | `fixed (no phase selection)` | 0.4961 | -0.2305 | 0.0201 | 0.0197 | never reached | 748, 358 | [358, 1106) |
| phase at which no sample reaches the largest value | `s32_shadow32_O0_noclipphase_12500.npz` | `noclip (|trace|<=0.47) @try1` | 0.2773 | -0.2461 | 0.0000 | 0.0000 | never reached | 748, 361 | [361, 1109) |

## 2. Algorithm 1 on all 2,048 traces

Round-1 CPAs: |rho| of the correct candidate at its peak sample, its rank among the 256 values (alpha-signed score), the best wrong representative; noise level 4.5/sqrt(2048) = 0.0994.

| Set | Recovered RK1..RK4 | h0 | h1 | h2 | h3 | Best wrong (h0, h1, h2, h3) | Decision: pair, p, max\|rho\| h2, h2*, D | Traces at the rail at the four peaks |
|---|---|---|---|---|---|---|---|---:|
| selected phase (the paper's set) | `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D` (16/16) | 0.896 @ 548 [rank 1] | 0.900 @ 709 [rank 1] | 0.811 @ 636 [rank 1] | 0.795 @ 796 [rank 1] | 0.79, 0.77, 0.63, 0.62 | {0D, F2}, 0D, 0.811, 0.088, +0.723 | 0 |
| phase at power-on, not selected | `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D` (16/16) | 0.894 @ 548 [rank 1] | 0.902 @ 976 [rank 1] | 0.806 @ 635 [rank 1] | 0.802 @ 796 [rank 1] | 0.78, 0.77, 0.62, 0.61 | {0D, F2}, 0D, 0.806, 0.091, +0.715 | 0 |
| phase at which no sample reaches the largest value | `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D` (16/16) | 0.598 @ 548 [rank 1] | 0.627 @ 709 [rank 1] | 0.477 @ 636 [rank 1] | 0.571 @ 797 [rank 1] | 0.56, 0.55, 0.40, 0.48 | {0D, F2}, 0D, 0.477, 0.085, +0.391 | 0 |

## 3. Success rate restricted to Round 1 (evaluation of Section 4.6)

Disjoint contiguous subsets, min(2048/N, 20) per point. Joint = the decision on D returns the true RK1_0 with alpha = +1 and the four Round-1 CPAs, each with the true earlier values, rank the correct candidate first among the 256 values (rule of success_rate.py: maximum over the samples of alpha rho(t)). The last column applies the ranking rule of cpa_shadow32_12500.py (alpha-signed peak) on the same subsets.

| Set | N | Subsets | RK1_0 | RK1_1 | RK1_2 | RK1_3 | Pair | Decision | Joint | Joint, signed-peak rule |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selected phase (the paper's set) | 16 | 20 | 8 | 17 | 10 | 3 | 8 | 6 | 1 | 1 |
| selected phase (the paper's set) | 24 | 20 | 15 | 20 | 14 | 13 | 15 | 13 | 6 | 6 |
| selected phase (the paper's set) | 32 | 20 | 18 | 20 | 20 | 17 | 18 | 18 | 15 | 15 |
| selected phase (the paper's set) | 48 | 20 | 20 | 19 | 19 | 18 | 20 | 20 | 16 | 16 |
| selected phase (the paper's set) | 64 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| selected phase (the paper's set) | 96 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| selected phase (the paper's set) | 128 | 16 | 16 | 16 | 16 | 16 | 16 | 16 | 16 | 16 |
| selected phase (the paper's set) | 192 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| selected phase (the paper's set) | 256 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| selected phase (the paper's set) | 384 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| selected phase (the paper's set) | 512 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 |
| selected phase (the paper's set) | 768 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| selected phase (the paper's set) | 1024 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| selected phase (the paper's set) | 2048 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| phase at power-on, not selected | 16 | 20 | 11 | 12 | 8 | 3 | 11 | 5 | 0 | 0 |
| phase at power-on, not selected | 24 | 20 | 17 | 17 | 19 | 13 | 17 | 14 | 9 | 9 |
| phase at power-on, not selected | 32 | 20 | 18 | 19 | 20 | 18 | 18 | 18 | 16 | 16 |
| phase at power-on, not selected | 48 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| phase at power-on, not selected | 64 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| phase at power-on, not selected | 96 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| phase at power-on, not selected | 128 | 16 | 16 | 16 | 16 | 16 | 16 | 16 | 16 | 16 |
| phase at power-on, not selected | 192 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| phase at power-on, not selected | 256 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| phase at power-on, not selected | 384 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| phase at power-on, not selected | 512 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 |
| phase at power-on, not selected | 768 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| phase at power-on, not selected | 1024 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| phase at power-on, not selected | 2048 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| phase at which no sample reaches the largest value | 16 | 20 | 2 | 4 | 0 | 0 | 2 | 1 | 0 | 0 |
| phase at which no sample reaches the largest value | 24 | 20 | 4 | 3 | 1 | 1 | 4 | 0 | 0 | 0 |
| phase at which no sample reaches the largest value | 32 | 20 | 6 | 8 | 4 | 6 | 6 | 2 | 0 | 0 |
| phase at which no sample reaches the largest value | 48 | 20 | 12 | 14 | 10 | 10 | 12 | 11 | 3 | 3 |
| phase at which no sample reaches the largest value | 64 | 20 | 13 | 14 | 15 | 14 | 13 | 11 | 3 | 3 |
| phase at which no sample reaches the largest value | 96 | 20 | 16 | 19 | 17 | 19 | 16 | 16 | 13 | 13 |
| phase at which no sample reaches the largest value | 128 | 16 | 15 | 15 | 14 | 16 | 15 | 15 | 13 | 13 |
| phase at which no sample reaches the largest value | 192 | 10 | 9 | 9 | 10 | 10 | 9 | 9 | 9 | 9 |
| phase at which no sample reaches the largest value | 256 | 8 | 7 | 8 | 7 | 8 | 7 | 7 | 7 | 7 |
| phase at which no sample reaches the largest value | 384 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| phase at which no sample reaches the largest value | 512 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 |
| phase at which no sample reaches the largest value | 768 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| phase at which no sample reaches the largest value | 1024 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| phase at which no sample reaches the largest value | 2048 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

First N from which the rate stays at 1.0 for every larger N:

| Set | Joint | Joint, signed-peak rule | Decision | RK1_0 | RK1_1 | RK1_2 | RK1_3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| selected phase (the paper's set) | **64** | 64 | 48 | 48 | 64 | 64 | 64 |
| phase at power-on, not selected | **48** | 48 | 48 | 48 | 48 | 32 | 48 |
| phase at which no sample reaches the largest value | **384** | 384 | 384 | 384 | 256 | 384 | 128 |

## 4. Signal-to-noise ratio of the h0 leakage over Round 1

Variance of the class means over the mean within-class variance, traces grouped by HW(s0), s0 = h0 xor RK1_0; class counts [3, 59, 192, 465, 568, 443, 250, 59, 9].

| Set | SNR, classes with more than 5 traces (at sample) | SNR, all nine classes (at sample) |
|---|---|---|
| selected phase (the paper's set) | 12.42 (548) | 20.60 (548) |
| phase at power-on, not selected | 11.49 (548) | 15.85 (548) |
| phase at which no sample reaches the largest value | 1.66 (812) | 2.62 (493) |

- SNR ratio, classes with more than 5 traces: selected / non-clipping = 7.49, power-on / non-clipping = 6.93 (all nine classes: 7.88, 6.06)
- Correct-candidate |rho| of the four Round-1 CPAs: selected phase (the paper's set) 0.80 to 0.90; phase at power-on, not selected 0.80 to 0.90; phase at which no sample reaches the largest value 0.48 to 0.63
- Joint Round-1 success rate 1.0 from: selected phase (the paper's set) 64 traces; phase at power-on, not selected 48 traces; phase at which no sample reaches the largest value 384 traces

