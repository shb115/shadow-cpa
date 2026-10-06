# Masked Shadow-32: fixed-versus-random t-test and the CPA of Algorithm 1 (Section 4.7)

Traces: `data/masked/`, one masked round per trace, 8,192 fixed-plaintext and 8,192 random-plaintext traces per set, round key `0D 3B 60 33`; seed 2 is an independent acquisition. Conventions: Welch t = mean(fixed) - mean(random), threshold |t| > 4.5; second order on the centered squared samples; the round window runs from the trigger to the start of the idle NOP loop (the round end below); CPA = 7-bit CPA over the 128 representatives with the hypothesis HW(h xor k), rank = position of the correct candidate among the 128 by max|rho| over the round; ADC rail = v >= 0.4959; 1 sample = 1 clock cycle.

## 1. Round end and table builds

| Set | Traces x samples | NOP period | Round end (cycles) | Table builds [start, end), length |
|---|---|---:|---:|---|
| ISW_seed1 | 16384 x 10000 | 14 | 3880 | - |
| ISW_seed2 | 16384 x 10000 | 14 | 3880 | - |
| ISWLUT_seed1 | 16384 x 46000 | 14 | 44176 | [229, 10708) 10479, [11195, 21674) 10479, [22162, 32641) 10479, [33131, 43610) 10479 |
| ISWLUT_seed2 | 16384 x 46000 | 14 | 44176 | [229, 10708) 10479, [11195, 21674) 10479, [22162, 32641) 10479, [33131, 43610) 10479 |

## 2. First-order t-test over the round, 8,192 traces per group

| Set | max\|t\| | at sample (sign) | samples over 4.5 | positions (t) | rail fraction at the max\|t\| sample | largest rail fraction over the exceeding samples |
|---|---:|---|---:|---|---:|---:|
| ISW_seed1 | 22.17 | 263 (-) | 64 | first 263, last 3838 | 0.000 | 0.487 |
| ISW_seed2 | 23.85 | 263 (-) | 71 | first 202, last 3838 | 0.000 | 0.510 |
| ISWLUT_seed1 | 6.75 | 10772 (-) | 2 | 3 (+4.63), 10772 (-6.75) | 0.000 | 0.000 |
| ISWLUT_seed2 | 6.03 | 21738 (-) | 2 | 10772 (-5.96), 21738 (-6.03) | 0.000 | 0.000 |

## 3. Second-order t-test (centered squared samples) over the round, 8,192 traces per group

| Set | max\|t\| | at sample (sign) | samples over 4.5 | positions (t) | rail fraction at the max\|t\| sample | largest rail fraction over the exceeding samples |
|---|---:|---|---:|---|---:|---:|
| ISW_seed1 | 21.13 | 2212 (-) | 518 | first 206, last 3838 | 0.000 | 0.525 |
| ISW_seed2 | 21.81 | 2212 (-) | 518 | first 206, last 3792 | 0.000 | 0.519 |
| ISWLUT_seed1 | 5.99 | 10771 (+) | 3 | 10771 (+5.99), 10772 (+5.43), 10833 (-5.02) | 0.000 | 0.000 |
| ISWLUT_seed2 | 6.02 | 21736 (+) | 4 | 10769 (+5.30), 10771 (+4.82), 21736 (+6.02), 21737 (+4.86) | 0.000 | 0.000 |

## 4. First-order t-test, first 4,096 traces per group

| Set | max\|t\| | at sample (sign) | samples over 4.5 | positions (t) | rail fraction at the max\|t\| sample | largest rail fraction over the exceeding samples |
|---|---:|---|---:|---|---:|---:|
| ISW_seed1 | 15.81 | 263 (-) | 44 | first 263, last 3838 | 0.000 | 0.000 |
| ISW_seed2 | 17.29 | 263 (-) | 41 | first 263, last 3838 | 0.000 | 0.000 |
| ISWLUT_seed1 | 5.20 | 10772 (-) | 2 | 3 (+4.70), 10772 (-5.20) | 0.000 | 0.000 |
| ISWLUT_seed2 | 4.66 | 21738 (-) | 2 | 10772 (-4.64), 21738 (-4.66) | 0.000 | 0.000 |

## 5. Second-order t-test, first 4,096 traces per group

| Set | max\|t\| | at sample (sign) | samples over 4.5 | positions (t) | rail fraction at the max\|t\| sample | largest rail fraction over the exceeding samples |
|---|---:|---|---:|---|---:|---:|
| ISW_seed1 | 15.51 | 2212 (-) | 311 | first 206, last 3792 | 0.000 | 0.487 |
| ISW_seed2 | 15.58 | 2212 (-) | 304 | first 206, last 3838 | 0.000 | 0.482 |
| ISWLUT_seed1 | 4.58 | 15456 (-) | 2 | 15456 (-4.58), 17813 (-4.53) | 0.000 | 0.000 |
| ISWLUT_seed2 | 5.46 | 21736 (+) | 2 | 21736 (+5.46), 21737 (+4.65) | 0.000 | 0.000 |

## 6. Position of the exceeding samples relative to the table builds (table recomputation)

| Set | Order | Sample | t | Builds completed before it | Cycles after the end of the last build | Inside a build |
|---|---|---:|---:|---:|---:|---|
| ISWLUT_seed1 | 1 | 3 | +4.63 | 0 | None | no |
| ISWLUT_seed1 | 1 | 10772 | -6.75 | 1 | 64 | no |
| ISWLUT_seed1 | 2 | 10771 | +5.99 | 1 | 63 | no |
| ISWLUT_seed1 | 2 | 10772 | +5.43 | 1 | 64 | no |
| ISWLUT_seed1 | 2 | 10833 | -5.02 | 1 | 125 | no |
| ISWLUT_seed2 | 1 | 10772 | -5.96 | 1 | 64 | no |
| ISWLUT_seed2 | 1 | 21738 | -6.03 | 2 | 64 | no |
| ISWLUT_seed2 | 2 | 10769 | +5.30 | 1 | 61 | no |
| ISWLUT_seed2 | 2 | 10771 | +4.82 | 1 | 63 | no |
| ISWLUT_seed2 | 2 | 21736 | +6.02 | 2 | 62 | no |
| ISWLUT_seed2 | 2 | 21737 | +4.86 | 2 | 63 | no |

## 7. Independent repetition: seed 1 against seed 2 over the round

| Implementation | Statistic | Over 4.5 in seed 1 / seed 2 | Over in both with the same sign | Pearson correlation of the t curves |
|---|---|---|---|---:|
| ISW | order 1, N = 8192 | 64 / 71 | 52 | 0.652 |
| ISW | order 2, N = 8192 | 518 / 518 | 439 | 0.901 |
| ISW | order 1, N = 4096 | 44 / 41 | 35 | 0.535 |
| ISW | order 2, N = 4096 | 311 / 304 | 238 | 0.828 |
| table recomputation | order 1, N = 8192 | 2 / 2 | 1 (sample 10772) | 0.035 |
| table recomputation | order 2, N = 8192 | 3 / 4 | 1 (sample 10771) | 0.019 |
| table recomputation | order 1, N = 4096 | 2 / 2 | 1 (sample 10772) | -0.069 |
| table recomputation | order 2, N = 4096 | 2 / 2 | 0 | 0.027 |

## 8. CPA of Algorithm 1, Round-1 stage, on the random group (8,192 traces)

h0 and h1 are the CPAs of Section 4.2; h2 is built with the positive-peak member p of the RK1_0 pair and h2* with p xor 0xFF (the decision on D of Section 4.3); h3 is built with the recovered RK1_1. The diagnostic rows build h2 with the true RK1_0 and h3 with the true RK1_1, which is what the attack would run had the earlier stage succeeded; they use the true value of the earlier stage, which is not available to the attacker (no mask is used by any CPA). Rank: position of the correct candidate among the 128 representatives by max|rho| over the round (in brackets: among the 256 values by the alpha-signed score, Section 4.3). Noise level 4.5/sqrt(N) = 0.0497.

### ISW_seed1 (window [0, 3880), expected maximum of noise over 128 x 3880 = 0.0566)

| Order | CPA | Built with | Rank of correct (of 128) [of 256] | \|rho\| correct @ sample | Best wrong \|rho\| | max\|rho\| over the NOP padding |
|---|---|---|---:|---|---:|---:|
| 1 | h0 (RK1_0 = 0D) | - | 1 [1] | 0.2343 @ 2032 | 0.1967 | 0.0496 |
| 1 | h1 (RK1_1 = 3B) | - | 1 [1] | 0.2295 @ 3073 | 0.1971 | 0.0509 |
| 1 | h2 (RK1_2 = 60) | 0D | 14 [14] | 0.1157 @ 2702 | 0.1903 | 0.0604 |
| 1 | h2* (rejected by D) | F2 | 105 [152] (no correct candidate) | 0.0363 @ 2764 | 0.0505 | 0.0548 |
| 1 | h3 (RK1_3 = 33) | 3B | 84 [84] | 0.0557 @ 3839 | 0.1834 | 0.0485 |
| 1 | h2 diagnostic, true RK1_0 (not available to the attacker) | - | 14 [14] | 0.1157 @ 2702 | 0.1903 | 0.0604 |
| 1 | h3 diagnostic, true RK1_1 (not available to the attacker) | - | 84 [84] | 0.0557 @ 3839 | 0.1834 | 0.0485 |
| 1 | decision | | pair {0D, F2}, p = 0D: max\|rho\| h2 = 0.1903, h2* = 0.0505, D = +0.1397, alpha = +1 | recovered `0D 3B 00 00` (true `0D 3B 60 33`), bytes correct 1100 | | |
| 2 | h0 (RK1_0 = 0D) | - | 6 [6] | 0.1528 @ 2786 | 0.1662 | 0.0513 |
| 2 | h1 (RK1_1 = 3B) | - | 8 [8] | 0.1685 @ 1909 | 0.1811 | 0.0555 |
| 2 | h2 (RK1_2 = 60) | FF | 64 [64] (no correct candidate) | 0.0414 @ 49 | 0.0548 | 0.0522 |
| 2 | h2* (rejected by D) | 00 | 114 [143] (no correct candidate) | 0.0415 @ 3593 | 0.0987 | 0.0609 |
| 2 | h3 (RK1_3 = 33) | 3C | 84 [173] (no correct candidate) | 0.0497 @ 3594 | 0.0855 | 0.0517 |
| 2 | h2 diagnostic, true RK1_0 (not available to the attacker) | - | 17 [17] | 0.1103 @ 3732 | 0.1663 | 0.0513 |
| 2 | h3 diagnostic, true RK1_1 (not available to the attacker) | - | 22 [22] | 0.1017 @ 3826 | 0.1521 | 0.0522 |
| 2 | decision | | pair {00, FF}, p = FF: max\|rho\| h2 = 0.0548, h2* = 0.0987, D = -0.0439, alpha = -1 | recovered `00 3C 2E 99` (true `0D 3B 60 33`), bytes correct 0000 | | |

### ISW_seed2 (window [0, 3880), expected maximum of noise over 128 x 3880 = 0.0566)

| Order | CPA | Built with | Rank of correct (of 128) [of 256] | \|rho\| correct @ sample | Best wrong \|rho\| | max\|rho\| over the NOP padding |
|---|---|---|---:|---|---:|---:|
| 1 | h0 (RK1_0 = 0D) | - | 1 [1] | 0.2289 @ 2546 | 0.1909 | 0.0475 |
| 1 | h1 (RK1_1 = 3B) | - | 1 [1] | 0.2422 @ 3431 | 0.2033 | 0.0504 |
| 1 | h2 (RK1_2 = 60) | 0D | 12 [12] | 0.1190 @ 2702 | 0.1987 | 0.0681 |
| 1 | h2* (rejected by D) | F2 | 78 [179] (no correct candidate) | 0.0365 @ 1289 | 0.0523 | 0.0563 |
| 1 | h3 (RK1_3 = 33) | 3B | 41 [41] | 0.0693 @ 3839 | 0.1881 | 0.0485 |
| 1 | h2 diagnostic, true RK1_0 (not available to the attacker) | - | 12 [12] | 0.1190 @ 2702 | 0.1987 | 0.0681 |
| 1 | h3 diagnostic, true RK1_1 (not available to the attacker) | - | 41 [41] | 0.0693 @ 3839 | 0.1881 | 0.0485 |
| 1 | decision | | pair {0D, F2}, p = 0D: max\|rho\| h2 = 0.1987, h2* = 0.0523, D = +0.1464, alpha = +1 | recovered `0D 3B 00 00` (true `0D 3B 60 33`), bytes correct 1100 | | |
| 2 | h0 (RK1_0 = 0D) | - | 8 [8] | 0.1528 @ 2264 | 0.1616 | 0.0544 |
| 2 | h1 (RK1_1 = 3B) | - | 8 [8] | 0.1630 @ 1909 | 0.1911 | 0.0531 |
| 2 | h2 (RK1_2 = 60) | 73 | 12 [245] (no correct candidate) | 0.0468 @ 3388 | 0.0521 | 0.0519 |
| 2 | h2* (rejected by D) | 8C | 115 [142] (no correct candidate) | 0.0435 @ 2773 | 0.1359 | 0.0525 |
| 2 | h3 (RK1_3 = 33) | 3D | 55 [55] (no correct candidate) | 0.0594 @ 3602 | 0.0965 | 0.0516 |
| 2 | h2 diagnostic, true RK1_0 (not available to the attacker) | - | 20 [20] | 0.1112 @ 3732 | 0.1809 | 0.0592 |
| 2 | h3 diagnostic, true RK1_1 (not available to the attacker) | - | 32 [225] | 0.0834 @ 3600 | 0.1380 | 0.0574 |
| 2 | decision | | pair {73, 8C}, p = 73: max\|rho\| h2 = 0.0521, h2* = 0.1359, D = -0.0838, alpha = -1 | recovered `8C 3D C6 3C` (true `0D 3B 60 33`), bytes correct 0000 | | |

### ISWLUT_seed1 (window [0, 44176), expected maximum of noise over 128 x 44176 = 0.0616)

| Order | CPA | Built with | Rank of correct (of 128) [of 256] | \|rho\| correct @ sample | Best wrong \|rho\| | max\|rho\| over the NOP padding |
|---|---|---|---:|---|---:|---:|
| 1 | h0 (RK1_0 = 0D) | - | 63 [63] | 0.0459 @ 38276 | 0.0584 | 0.0406 |
| 1 | h1 (RK1_1 = 3B) | - | 40 [40] | 0.0474 @ 15832 | 0.0601 | 0.0488 |
| 1 | h2 (RK1_2 = 60) | F7 | 74 [183] (no correct candidate) | 0.0443 @ 18061 | 0.0581 | 0.0527 |
| 1 | h2* (rejected by D) | 08 | 82 [175] (no correct candidate) | 0.0445 @ 15300 | 0.0570 | 0.0526 |
| 1 | h3 (RK1_3 = 33) | BD | 29 [228] (no correct candidate) | 0.0479 @ 28538 | 0.0564 | 0.0519 |
| 1 | h2 diagnostic, true RK1_0 (not available to the attacker) | - | 31 [226] | 0.0504 @ 7700 | 0.0603 | 0.0481 |
| 1 | h3 diagnostic, true RK1_1 (not available to the attacker) | - | 86 [86] | 0.0450 @ 20147 | 0.0624 | 0.0526 |
| 1 | decision | | pair {08, F7}, p = F7: max\|rho\| h2 = 0.0581, h2* = 0.0570, D = +0.0010, alpha = +1 | recovered `F7 BD 20 F3` (true `0D 3B 60 33`), bytes correct 0000 | | |
| 2 | h0 (RK1_0 = 0D) | - | 43 [43] | 0.0494 @ 16217 | 0.0584 | 0.0510 |
| 2 | h1 (RK1_1 = 3B) | - | 62 [195] | 0.0479 @ 9443 | 0.0610 | 0.0498 |
| 2 | h2 (RK1_2 = 60) | 0B | 78 [78] (no correct candidate) | 0.0476 @ 11193 | 0.0622 | 0.0512 |
| 2 | h2* (rejected by D) | F4 | 124 [133] (no correct candidate) | 0.0427 @ 17323 | 0.0563 | 0.0455 |
| 2 | h3 (RK1_3 = 33) | 6B | 78 [78] (no correct candidate) | 0.0468 @ 15905 | 0.0581 | 0.0493 |
| 2 | h2 diagnostic, true RK1_0 (not available to the attacker) | - | 102 [102] | 0.0451 @ 6723 | 0.0572 | 0.0493 |
| 2 | h3 diagnostic, true RK1_1 (not available to the attacker) | - | 27 [230] | 0.0503 @ 1313 | 0.0562 | 0.0540 |
| 2 | decision | | pair {0B, F4}, p = 0B: max\|rho\| h2 = 0.0622, h2* = 0.0563, D = +0.0059, alpha = +1 | recovered `0B 6B B4 E4` (true `0D 3B 60 33`), bytes correct 0000 | | |

### ISWLUT_seed2 (window [0, 44176), expected maximum of noise over 128 x 44176 = 0.0616)

| Order | CPA | Built with | Rank of correct (of 128) [of 256] | \|rho\| correct @ sample | Best wrong \|rho\| | max\|rho\| over the NOP padding |
|---|---|---|---:|---|---:|---:|
| 1 | h0 (RK1_0 = 0D) | - | 13 [244] | 0.0488 @ 5920 | 0.0512 | 0.0627 |
| 1 | h1 (RK1_1 = 3B) | - | 113 [144] | 0.0411 @ 36337 | 0.0569 | 0.0467 |
| 1 | h2 (RK1_2 = 60) | 91 | 75 [75] (no correct candidate) | 0.0440 @ 5425 | 0.0582 | 0.0459 |
| 1 | h2* (rejected by D) | 6E | 49 [208] (no correct candidate) | 0.0493 @ 850 | 0.0597 | 0.0509 |
| 1 | h3 (RK1_3 = 33) | E1 | 3 [3] (no correct candidate) | 0.0549 @ 13733 | 0.0576 | 0.0482 |
| 1 | h2 diagnostic, true RK1_0 (not available to the attacker) | - | 42 [215] | 0.0478 @ 41749 | 0.0650 | 0.0533 |
| 1 | h3 diagnostic, true RK1_1 (not available to the attacker) | - | 44 [44] | 0.0462 @ 27654 | 0.0604 | 0.0494 |
| 1 | decision | | pair {6E, 91}, p = 91: max\|rho\| h2 = 0.0582, h2* = 0.0597, D = -0.0015, alpha = -1 | recovered `6E E1 13 8F` (true `0D 3B 60 33`), bytes correct 0000 | | |
| 2 | h0 (RK1_0 = 0D) | - | 2 [255] | 0.0573 @ 10190 | 0.0575 | 0.0536 |
| 2 | h1 (RK1_1 = 3B) | - | 1 [256] | 0.0612 @ 43737 | 0.0607 | 0.0461 |
| 2 | h2 (RK1_2 = 60) | 09 | 1 [256] (no correct candidate) | 0.0573 @ 3893 | 0.0570 | 0.0506 |
| 2 | h2* (rejected by D) | F6 | 26 [231] (no correct candidate) | 0.0506 @ 3954 | 0.0577 | 0.0537 |
| 2 | h3 (RK1_3 = 33) | C4 | 59 [59] (no correct candidate) | 0.0468 @ 39569 | 0.0559 | 0.0536 |
| 2 | h2 diagnostic, true RK1_0 (not available to the attacker) | - | 122 [122] | 0.0436 @ 43783 | 0.0590 | 0.0610 |
| 2 | h3 diagnostic, true RK1_1 (not available to the attacker) | - | 1 [256] | 0.0608 @ 5383 | 0.0555 | 0.0518 |
| 2 | decision | | pair {09, F6}, p = 09: max\|rho\| h2 = 0.0573, h2* = 0.0577, D = -0.0004, alpha = -1 | recovered `F6 C4 9D D1` (true `0D 3B 60 33`), bytes correct 0000 | | |

## 9. Success rate against the number of traces, CPAs that rank the correct candidate first at 8,192 traces

Disjoint contiguous subsets of the random group, min(8192/N, 20) per point; success = the correct representative ranks first by max|rho| over the round. A diagnostic CPA (h2_diag, h3_diag) is built with the true value of the earlier stage, which is not available to the attacker.

| Set | CPA | N = 128 | N = 256 | N = 512 | N = 1024 | N = 2048 | N = 4096 | N = 8192 | Smallest N with rate 1.0 from there on |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ISW_seed1 | order 1 h0 | 2/20 | 9/20 | 13/16 | 8/8 | 4/4 | 2/2 | 1/1 | 1024 |
| ISW_seed1 | order 1 h1 | 0/20 | 5/20 | 11/16 | 8/8 | 4/4 | 2/2 | 1/1 | 1024 |
| ISW_seed2 | order 1 h0 | 1/20 | 8/20 | 15/16 | 8/8 | 4/4 | 2/2 | 1/1 | 1024 |
| ISW_seed2 | order 1 h1 | 2/20 | 5/20 | 11/16 | 8/8 | 4/4 | 2/2 | 1/1 | 1024 |
| ISWLUT_seed1 | none ranks first |  |  |  |  |  |  |  | - |
| ISWLUT_seed2 | order 2 h1 | 0/20 | 0/20 | 0/16 | 0/8 | 0/4 | 0/2 | 1/1 | 8192 |
| ISWLUT_seed2 | order 2 h3_diag (true earlier value, not available to the attacker) | 0/20 | 1/20 | 0/16 | 0/8 | 0/4 | 0/2 | 1/1 | 8192 |

## 10. Effect size and noise

Noise = mean over the round of the per-sample standard deviation of the random group; one ADC code = 1/256. Smallest detectable difference between the group means at |t| = 4.5 with n traces per group: 4.5 sqrt(2/n) noise sd.

| Set | Noise sd (ADC units) | Noise sd (codes) | Detectable at n = 4,096 (sd, codes) | Detectable at n = 8,192 (sd, codes) |
|---|---:|---:|---|---|
| ISW_seed1 | 0.01055 | 2.70 | 0.0994 sd, 0.27 codes | 0.0703 sd, 0.19 codes |
| ISW_seed2 | 0.01057 | 2.71 | 0.0994 sd, 0.27 codes | 0.0703 sd, 0.19 codes |
| ISWLUT_seed1 | 0.01333 | 3.41 | 0.0994 sd, 0.34 codes | 0.0703 sd, 0.24 codes |
| ISWLUT_seed2 | 0.01334 | 3.42 | 0.0994 sd, 0.34 codes | 0.0703 sd, 0.24 codes |

## 11. Samples at the ADC rail

Fraction of the samples at the positive rail, over all samples and within the round; the number of samples at which every trace is at the rail (one sample of every NOP iteration); the fraction of traces at the rail at the four max|t| samples (orders 1 and 2, N = 8,192 and 4,096) and the largest such fraction over all exceeding samples of the four statistics.

| Set | All samples | Within the round | Samples at the rail in every trace | At the max\|t\| samples | Largest over the exceeding samples |
|---|---:|---:|---:|---|---:|
| ISW_seed1 | 0.0530 | 0.0237 | 468 | 0.000, 0.000, 0.000, 0.000 | 0.525 |
| ISW_seed2 | 0.0529 | 0.0236 | 459 | 0.000, 0.000, 0.000, 0.000 | 0.519 |
| ISWLUT_seed1 | 0.0243 | 0.0253 | 434 | 0.000, 0.000, 0.000, 0.000 | 0.000 |
| ISWLUT_seed2 | 0.0242 | 0.0252 | 363 | 0.000, 0.000, 0.000, 0.000 | 0.000 |

