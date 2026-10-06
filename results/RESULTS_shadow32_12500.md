# Shadow-32 CPA : 12500-sample capture, recovery of round keys RK1..RK4

- Method : Algorithm 1 of the paper. Round 1: five 7-bit CPAs over the 128 representatives
  (h0, h1, h2, h2*, h3; the h2* CPA is rejected by the decision on D and returns no value).
  Round 2: four 4-bit CPAs of 16 candidates (upper nibble of RK2_0; lower nibble of RK2_2 with the
  upper nibble unmodeled, then its upper nibble with the lower fixed; lower nibble of RK2_3).
  Rounds 3 and 4: two 4-bit CPAs each (lower nibbles of RK_2^r and RK_3^r). 13 CPAs, 12 of which
  return a value; 5 x 128 + 8 x 16 = 768 candidate evaluations. The other five bytes (RK2_1, RK3_0,
  RK3_1, RK4_0, RK4_1) and every fixed nibble come from the key schedule.
- Ranking : candidates ordered by alpha times the signed correlation at their peak; the rank column
  is the position of the correct candidate (Round 1: among the 256 values scored by the 128 curves).
- Cross-check : a 7-bit CPA on RK2_1, a byte the key schedule already fixes, is reported but not counted.
- Samples : a Round-r CPA runs over `[b0 + (r-1)P, b0 + rP)`, with the round period P and the round
  boundary b0 taken from each set's mean trace alone (`round_structure.py`); neither the key nor the
  outcome of an attack is used. Values per set are listed below.
- Class check : every member of the master-key equivalence class is expanded with the key schedule
  (`shadow32_ks.ks32`) and must give the same 64 round-key bytes, equal to the `rk` field of the traces.
- Capture : clkout 7.5MHz / adc 7.5MHz, seekclip phase, `-O0` firmware

## 1. Fixed-key set (`s32_ref_12500.npz`, 2048 x 12500)

Recovered RK1..RK4 : `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D`
Reference RK1..RK4 : `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D`
Matching bytes : **16/16**,  round period 748, round boundary 358

Sign decision : h0 pair {0D, F2}, p = 0D (positive peak); max|rho| h2 (built with 0D) = 0.811, h2* (built with F2) = 0.088, D = +0.723 -> RK1_0 = 0D, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `0D` | 1 | 0.896 | 548 |
| R1k1 | RK1_1 | byte | 128 | `3B` | 1 | 0.900 | 709 |
| R1k2 | RK1_2 | byte | 128 | `60` | 1 | 0.811 | 636 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.088 | 594 |
| R1k3 | RK1_3 | byte | 128 | `33` | 1 | 0.795 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `43` | 1 | 0.904 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?5` | 1 | 0.546 | 1383 |
| R2k2hi | RK2_2 | upper nibble | 16 | `25` | 1 | 0.794 | 1384 |
| R2k3lo | RK2_3 | lower nibble | 16 | `3C` | 1 | 0.802 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `89` | 1 | 0.794 | 2132 |
| R3k3lo | RK3_3 | lower nibble | 16 | `C5` | 1 | 0.793 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `0D` | 1 | 0.798 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `5D` | 1 | 0.786 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `60` | 1 | 0.901 | 1457 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `60` | = RK1_2 |
| RK3_0 | `13` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `25` | = RK2_2 |
| RK4_0 | `3C` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `89` | = RK3_2 |

- Lower-nibble CPA of RK2_2 (upper nibble unmodeled) : |rho| 0.546
- The other 11 value-returning CPAs : |rho| 0.786 ~ 0.904
- All 12 value-returning CPAs : min 0.546, max 0.904, mean 0.802; every correct candidate ranks first
- Rejected h2* CPA : max|rho| 0.088
- RK2_1 cross-check (7-bit CPA, not counted) : `60`, |rho| 0.901, equals the derived value

Equivalence class size 81 (no master field, this set has the round keys hard-coded as constants in the firmware); every member expands to the stored 64 round-key bytes : verified

Members of the class (64-bit master keys), smallest `DC4A3DB3035C950E`, largest `DCD23DB3035C95C7`; the member named in the paper, `DC4A3DB3035C950E`, is in the class : yes

Running time : the thirteen CPAs of Algorithm 1 (with the cross-check) and the round location are timed by the script and printed to the console; the times are machine dependent and are not recorded here.

## 2. 10 random-key sets (`s32_key01..10_12500.npz`, 2048 x 12500 each)

| Set | master | RK1 | RK2 | RK3 | RK4 | Match | pair | D | alpha | min\|rho\| (12) | master in class (size) | class expands to rk | P, b0 |
|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|
| key01 | `E10020BD4E590E12` | `10 2B 04 DE` | `0D 04 05 E9` | `0E 05 20 9E` | `C9 20 4E E0` | 16/16 | {10, EF} | +0.694 | +1 | 0.572 | yes (24) | verified | 748, 358 |
| key02 | `10594F596EC32B72` | `4F 45 26 9E` | `19 26 8C E3` | `9E 8C 12 3B` | `13 12 21 B1` | 16/16 | {4F, B0} | +0.689 | +1 | 0.583 | yes (81) | verified | 748, 406 |
| key03 | `A899B352D3E180D4` | `C3 B5 4D 23` | `82 4D 1E 31` | `23 1E 48 10` | `21 48 1A 09` | 16/16 | {3C, C3} | +0.729 | +1 | 0.563 | yes (27) | verified | 748, 406 |
| key04 | `A04595F4836A0483` | `05 9F 28 43` | `04 28 46 3A` | `13 46 30 A4` | `4A 30 8A 41` | 16/16 | {05, FA} | +0.723 | +1 | 0.555 | yes (36) | verified | 748, 406 |
| key05 | `8B94533A86877F7D` | `33 53 18 A6` | `9A 18 08 67` | `06 08 37 7F` | `87 37 88 FA` | 16/16 | {33, CC} | +0.705 | +1 | 0.555 | yes (27) | verified | 748, 406 |
| key06 | `974E4B199238008C` | `8B 41 49 92` | `49 49 23 28` | `82 23 10 80` | `88 10 19 06` | 16/16 | {74, 8B} | +0.685 | +1 | 0.580 | yes (81) | verified | 748, 358 |
| key07 | `86B045954E53F9C4` | `C5 49 04 5E` | `95 04 05 E3` | `1E 05 8F 39` | `43 8F 48 97` | 16/16 | {3A, C5} | +0.713 | +1 | 0.553 | yes (81) | verified | 748, 358 |
| key08 | `911836FAFAE5AB8A` | `06 3F 8F AA` | `1A 8F 8E A5` | `0A 8E CA 5B` | `25 CA 39 B0` | 16/16 | {06, F9} | +0.721 | +1 | 0.585 | yes (54) | verified | 748, 358 |
| key09 | `E0DF051FEC09239E` | `15 01 8E FC` | `1F 8E 90 C9` | `1C 90 02 93` | `69 02 6E 31` | 16/16 | {15, EA} | +0.706 | +1 | 0.567 | yes (27) | verified | 748, 358 |
| key10 | `8BB298B21469FAE0` | `C8 9B 01 24` | `32 01 06 49` | `04 06 8F 9A` | `29 8F 08 AA` | 16/16 | {37, C8} | +0.708 | +1 | 0.568 | yes (81) | verified | 748, 406 |

Peak |rho| of the correct candidate in every CPA, rank of the correct candidate in brackets (h2*: its maximum |rho|, no correct candidate; RK2_1: the cross-check, not counted):

| Set | RK1_0 | RK1_1 | RK1_2 | RK1_2 (h2*) | RK1_3 | RK2_0 upper nibble | RK2_2 lower nibble | RK2_2 upper nibble | RK2_3 lower nibble | RK3_2 lower nibble | RK3_3 lower nibble | RK4_2 lower nibble | RK4_3 lower nibble | RK2_1 check |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| key01 | 0.898 [1] | 0.903 [1] | 0.799 [1] | 0.105 | 0.808 [1] | 0.898 [1] | 0.572 [1] | 0.802 [1] | 0.800 [1] | 0.799 [1] | 0.786 [1] | 0.802 [1] | 0.788 [1] | 0.901 [1] |
| key02 | 0.905 [1] | 0.899 [1] | 0.810 [1] | 0.121 | 0.788 [1] | 0.909 [1] | 0.583 [1] | 0.813 [1] | 0.805 [1] | 0.808 [1] | 0.800 [1] | 0.804 [1] | 0.803 [1] | 0.906 [1] |
| key03 | 0.907 [1] | 0.904 [1] | 0.812 [1] | 0.083 | 0.800 [1] | 0.901 [1] | 0.563 [1] | 0.804 [1] | 0.790 [1] | 0.801 [1] | 0.781 [1] | 0.812 [1] | 0.808 [1] | 0.898 [1] |
| key04 | 0.899 [1] | 0.898 [1] | 0.806 [1] | 0.084 | 0.799 [1] | 0.903 [1] | 0.555 [1] | 0.799 [1] | 0.800 [1] | 0.805 [1] | 0.799 [1] | 0.800 [1] | 0.794 [1] | 0.909 [1] |
| key05 | 0.905 [1] | 0.902 [1] | 0.796 [1] | 0.091 | 0.801 [1] | 0.909 [1] | 0.555 [1] | 0.806 [1] | 0.809 [1] | 0.825 [1] | 0.810 [1] | 0.800 [1] | 0.809 [1] | 0.900 [1] |
| key06 | 0.901 [1] | 0.899 [1] | 0.796 [1] | 0.111 | 0.797 [1] | 0.898 [1] | 0.580 [1] | 0.811 [1] | 0.802 [1] | 0.794 [1] | 0.801 [1] | 0.803 [1] | 0.777 [1] | 0.907 [1] |
| key07 | 0.907 [1] | 0.895 [1] | 0.807 [1] | 0.094 | 0.795 [1] | 0.901 [1] | 0.553 [1] | 0.801 [1] | 0.797 [1] | 0.813 [1] | 0.789 [1] | 0.804 [1] | 0.787 [1] | 0.903 [1] |
| key08 | 0.895 [1] | 0.903 [1] | 0.812 [1] | 0.091 | 0.794 [1] | 0.897 [1] | 0.585 [1] | 0.812 [1] | 0.800 [1] | 0.796 [1] | 0.805 [1] | 0.792 [1] | 0.805 [1] | 0.900 [1] |
| key09 | 0.901 [1] | 0.901 [1] | 0.802 [1] | 0.096 | 0.801 [1] | 0.906 [1] | 0.567 [1] | 0.796 [1] | 0.801 [1] | 0.797 [1] | 0.791 [1] | 0.794 [1] | 0.797 [1] | 0.900 [1] |
| key10 | 0.912 [1] | 0.907 [1] | 0.812 [1] | 0.104 | 0.789 [1] | 0.903 [1] | 0.568 [1] | 0.809 [1] | 0.789 [1] | 0.807 [1] | 0.796 [1] | 0.798 [1] | 0.806 [1] | 0.905 [1] |
| min | 0.895 | 0.895 | 0.796 | 0.083 | 0.788 | 0.897 | 0.553 | 0.796 | 0.789 | 0.794 | 0.781 | 0.792 | 0.777 | 0.898 |
| max | 0.912 | 0.907 | 0.812 | 0.121 | 0.808 | 0.909 | 0.585 | 0.813 | 0.809 | 0.825 | 0.810 | 0.812 | 0.809 | 0.909 |

- Full recovery of round keys RK1..RK4 : **10/10 sets**; the correct candidate ranks first in 120 of the 120 value-returning CPAs
- True 64-bit master in the NX equivalence class : **10/10 sets** (NX is not invertible, so the master key cannot be uniquely recovered)
- Equivalence class size : 24, 81, 27, 36, 27, 81, 81, 54, 27, 81; every member expands to the stored 64 round-key bytes on 10/10 sets
- Lower-nibble CPA of RK2_2 (upper nibble unmodeled, 10 values) : |rho| **0.553 ~ 0.585**, mean 0.568
- The other 11 value-returning CPAs (10 sets x 11 = 110 values) : |rho| **0.777 ~ 0.912**, mean 0.828
- All 12 value-returning CPAs (120 values) : min 0.553, max 0.912, mean 0.807
- Rejected h2* CPA : max|rho| 0.083 ~ 0.121; D = +0.685 ~ +0.729, alpha = +1 on 10/10 sets

### key01

Sign decision : pair {10, EF}, p = 10, max|rho| h2 = 0.799, h2* = 0.105, D = +0.694, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `10` | 1 | 0.898 | 548 |
| R1k1 | RK1_1 | byte | 128 | `2B` | 1 | 0.903 | 976 |
| R1k2 | RK1_2 | byte | 128 | `04` | 1 | 0.799 | 635 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.105 | 640 |
| R1k3 | RK1_3 | byte | 128 | `DE` | 1 | 0.808 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `0D` | 1 | 0.898 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?5` | 1 | 0.572 | 1383 |
| R2k2hi | RK2_2 | upper nibble | 16 | `05` | 1 | 0.802 | 1383 |
| R2k3lo | RK2_3 | lower nibble | 16 | `E9` | 1 | 0.800 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `20` | 1 | 0.799 | 2132 |
| R3k3lo | RK3_3 | lower nibble | 16 | `9E` | 1 | 0.786 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `4E` | 1 | 0.802 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `E0` | 1 | 0.788 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `04` | 1 | 0.901 | 1724 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `04` | = RK1_2 |
| RK3_0 | `0E` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `05` | = RK2_2 |
| RK4_0 | `C9` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `20` | = RK3_2 |

### key02

Sign decision : pair {4F, B0}, p = 4F, max|rho| h2 = 0.810, h2* = 0.121, D = +0.689, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `4F` | 1 | 0.905 | 1136 |
| R1k1 | RK1_1 | byte | 128 | `45` | 1 | 0.899 | 709 |
| R1k2 | RK1_2 | byte | 128 | `26` | 1 | 0.810 | 636 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.121 | 890 |
| R1k3 | RK1_3 | byte | 128 | `9E` | 1 | 0.788 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `19` | 1 | 0.909 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?C` | 1 | 0.583 | 1383 |
| R2k2hi | RK2_2 | upper nibble | 16 | `8C` | 1 | 0.813 | 1384 |
| R2k3lo | RK2_3 | lower nibble | 16 | `E3` | 1 | 0.805 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `12` | 1 | 0.808 | 2131 |
| R3k3lo | RK3_3 | lower nibble | 16 | `3B` | 1 | 0.800 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `21` | 1 | 0.804 | 2880 |
| R4k3lo | RK4_3 | lower nibble | 16 | `B1` | 1 | 0.803 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `26` | 1 | 0.906 | 1457 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `26` | = RK1_2 |
| RK3_0 | `9E` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `8C` | = RK2_2 |
| RK4_0 | `13` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `12` | = RK3_2 |

### key03

Sign decision : pair {3C, C3}, p = C3, max|rho| h2 = 0.812, h2* = 0.083, D = +0.729, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `C3` | 1 | 0.907 | 1136 |
| R1k1 | RK1_1 | byte | 128 | `B5` | 1 | 0.904 | 976 |
| R1k2 | RK1_2 | byte | 128 | `4D` | 1 | 0.812 | 636 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.083 | 727 |
| R1k3 | RK1_3 | byte | 128 | `23` | 1 | 0.800 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `82` | 1 | 0.901 | 1884 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?E` | 1 | 0.563 | 1383 |
| R2k2hi | RK2_2 | upper nibble | 16 | `1E` | 1 | 0.804 | 1383 |
| R2k3lo | RK2_3 | lower nibble | 16 | `31` | 1 | 0.790 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `48` | 1 | 0.801 | 2131 |
| R3k3lo | RK3_3 | lower nibble | 16 | `10` | 1 | 0.781 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `1A` | 1 | 0.812 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `09` | 1 | 0.808 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `4D` | 1 | 0.898 | 1724 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `4D` | = RK1_2 |
| RK3_0 | `23` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `1E` | = RK2_2 |
| RK4_0 | `21` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `48` | = RK3_2 |

### key04

Sign decision : pair {05, FA}, p = 05, max|rho| h2 = 0.806, h2* = 0.084, D = +0.723, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `05` | 1 | 0.899 | 548 |
| R1k1 | RK1_1 | byte | 128 | `9F` | 1 | 0.898 | 709 |
| R1k2 | RK1_2 | byte | 128 | `28` | 1 | 0.806 | 635 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.084 | 874 |
| R1k3 | RK1_3 | byte | 128 | `43` | 1 | 0.799 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `04` | 1 | 0.903 | 1884 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?6` | 1 | 0.555 | 1383 |
| R2k2hi | RK2_2 | upper nibble | 16 | `46` | 1 | 0.799 | 1384 |
| R2k3lo | RK2_3 | lower nibble | 16 | `3A` | 1 | 0.800 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `30` | 1 | 0.805 | 2131 |
| R3k3lo | RK3_3 | lower nibble | 16 | `A4` | 1 | 0.799 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `8A` | 1 | 0.800 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `41` | 1 | 0.794 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `28` | 1 | 0.909 | 1457 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `28` | = RK1_2 |
| RK3_0 | `13` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `46` | = RK2_2 |
| RK4_0 | `4A` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `30` | = RK3_2 |

### key05

Sign decision : pair {33, CC}, p = 33, max|rho| h2 = 0.796, h2* = 0.091, D = +0.705, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `33` | 1 | 0.905 | 548 |
| R1k1 | RK1_1 | byte | 128 | `53` | 1 | 0.902 | 709 |
| R1k2 | RK1_2 | byte | 128 | `18` | 1 | 0.796 | 636 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.091 | 441 |
| R1k3 | RK1_3 | byte | 128 | `A6` | 1 | 0.801 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `9A` | 1 | 0.909 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?8` | 1 | 0.555 | 1384 |
| R2k2hi | RK2_2 | upper nibble | 16 | `08` | 1 | 0.806 | 1384 |
| R2k3lo | RK2_3 | lower nibble | 16 | `67` | 1 | 0.809 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `37` | 1 | 0.825 | 2131 |
| R3k3lo | RK3_3 | lower nibble | 16 | `7F` | 1 | 0.810 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `88` | 1 | 0.800 | 2880 |
| R4k3lo | RK4_3 | lower nibble | 16 | `FA` | 1 | 0.809 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `18` | 1 | 0.900 | 1457 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `18` | = RK1_2 |
| RK3_0 | `06` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `08` | = RK2_2 |
| RK4_0 | `87` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `37` | = RK3_2 |

### key06

Sign decision : pair {74, 8B}, p = 8B, max|rho| h2 = 0.796, h2* = 0.111, D = +0.685, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `8B` | 1 | 0.901 | 548 |
| R1k1 | RK1_1 | byte | 128 | `41` | 1 | 0.899 | 709 |
| R1k2 | RK1_2 | byte | 128 | `49` | 1 | 0.796 | 635 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.111 | 956 |
| R1k3 | RK1_3 | byte | 128 | `92` | 1 | 0.797 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `49` | 1 | 0.898 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?3` | 1 | 0.580 | 1383 |
| R2k2hi | RK2_2 | upper nibble | 16 | `23` | 1 | 0.811 | 1384 |
| R2k3lo | RK2_3 | lower nibble | 16 | `28` | 1 | 0.802 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `10` | 1 | 0.794 | 2132 |
| R3k3lo | RK3_3 | lower nibble | 16 | `80` | 1 | 0.801 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `19` | 1 | 0.803 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `06` | 1 | 0.777 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `49` | 1 | 0.907 | 1724 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `49` | = RK1_2 |
| RK3_0 | `82` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `23` | = RK2_2 |
| RK4_0 | `88` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `10` | = RK3_2 |

### key07

Sign decision : pair {3A, C5}, p = C5, max|rho| h2 = 0.807, h2* = 0.094, D = +0.713, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `C5` | 1 | 0.907 | 548 |
| R1k1 | RK1_1 | byte | 128 | `49` | 1 | 0.895 | 709 |
| R1k2 | RK1_2 | byte | 128 | `04` | 1 | 0.807 | 636 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.094 | 1018 |
| R1k3 | RK1_3 | byte | 128 | `5E` | 1 | 0.795 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `95` | 1 | 0.901 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?5` | 1 | 0.553 | 1383 |
| R2k2hi | RK2_2 | upper nibble | 16 | `05` | 1 | 0.801 | 1383 |
| R2k3lo | RK2_3 | lower nibble | 16 | `E3` | 1 | 0.797 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `8F` | 1 | 0.813 | 2131 |
| R3k3lo | RK3_3 | lower nibble | 16 | `39` | 1 | 0.789 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `48` | 1 | 0.804 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `97` | 1 | 0.787 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `04` | 1 | 0.903 | 1724 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `04` | = RK1_2 |
| RK3_0 | `1E` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `05` | = RK2_2 |
| RK4_0 | `43` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `8F` | = RK3_2 |

### key08

Sign decision : pair {06, F9}, p = 06, max|rho| h2 = 0.812, h2* = 0.091, D = +0.721, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `06` | 1 | 0.895 | 548 |
| R1k1 | RK1_1 | byte | 128 | `3F` | 1 | 0.903 | 709 |
| R1k2 | RK1_2 | byte | 128 | `8F` | 1 | 0.812 | 636 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.091 | 790 |
| R1k3 | RK1_3 | byte | 128 | `AA` | 1 | 0.794 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `1A` | 1 | 0.897 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?E` | 1 | 0.585 | 1383 |
| R2k2hi | RK2_2 | upper nibble | 16 | `8E` | 1 | 0.812 | 1384 |
| R2k3lo | RK2_3 | lower nibble | 16 | `A5` | 1 | 0.800 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `CA` | 1 | 0.796 | 2132 |
| R3k3lo | RK3_3 | lower nibble | 16 | `5B` | 1 | 0.805 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `39` | 1 | 0.792 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `B0` | 1 | 0.805 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `8F` | 1 | 0.900 | 1457 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `8F` | = RK1_2 |
| RK3_0 | `0A` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `8E` | = RK2_2 |
| RK4_0 | `25` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `CA` | = RK3_2 |

### key09

Sign decision : pair {15, EA}, p = 15, max|rho| h2 = 0.802, h2* = 0.096, D = +0.706, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `15` | 1 | 0.901 | 548 |
| R1k1 | RK1_1 | byte | 128 | `01` | 1 | 0.901 | 709 |
| R1k2 | RK1_2 | byte | 128 | `8E` | 1 | 0.802 | 635 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.096 | 850 |
| R1k3 | RK1_3 | byte | 128 | `FC` | 1 | 0.801 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `1F` | 1 | 0.906 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?0` | 1 | 0.567 | 1379 |
| R2k2hi | RK2_2 | upper nibble | 16 | `90` | 1 | 0.796 | 1383 |
| R2k3lo | RK2_3 | lower nibble | 16 | `C9` | 1 | 0.801 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `02` | 1 | 0.797 | 2131 |
| R3k3lo | RK3_3 | lower nibble | 16 | `93` | 1 | 0.791 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `6E` | 1 | 0.794 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `31` | 1 | 0.797 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `8E` | 1 | 0.900 | 1724 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `8E` | = RK1_2 |
| RK3_0 | `1C` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `90` | = RK2_2 |
| RK4_0 | `69` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `02` | = RK3_2 |

### key10

Sign decision : pair {37, C8}, p = C8, max|rho| h2 = 0.812, h2* = 0.104, D = +0.708, alpha = +1

| CPA | Subkey | Target | Candidates | Recovered | Rank of correct | Peak \|rho\| | Peak sample |
|---|---|---|---:|---|---:|---:|---:|
| R1k0 | RK1_0 | byte | 128 | `C8` | 1 | 0.912 | 548 |
| R1k1 | RK1_1 | byte | 128 | `9B` | 1 | 0.907 | 709 |
| R1k2 | RK1_2 | byte | 128 | `01` | 1 | 0.812 | 635 |
| R1k2s | RK1_2 | byte | 128 | none (rejected by D) | - | 0.104 | 455 |
| R1k3 | RK1_3 | byte | 128 | `24` | 1 | 0.789 | 796 |
| R2k0hi | RK2_0 | upper nibble | 16 | `32` | 1 | 0.903 | 1296 |
| R2k2lo | RK2_2 | lower nibble | 16 | `0x?6` | 1 | 0.568 | 1384 |
| R2k2hi | RK2_2 | upper nibble | 16 | `06` | 1 | 0.809 | 1384 |
| R2k3lo | RK2_3 | lower nibble | 16 | `49` | 1 | 0.789 | 1544 |
| R3k2lo | RK3_2 | lower nibble | 16 | `8F` | 1 | 0.807 | 2132 |
| R3k3lo | RK3_3 | lower nibble | 16 | `9A` | 1 | 0.796 | 2292 |
| R4k2lo | RK4_2 | lower nibble | 16 | `08` | 1 | 0.798 | 2879 |
| R4k3lo | RK4_3 | lower nibble | 16 | `AA` | 1 | 0.806 | 3040 |
| R2k1chk | RK2_1 (check only, not counted) | byte | 128 | `01` | 1 | 0.905 | 1457 |

| Derived byte | Value | From |
|---|---|---|
| RK2_1 | `01` | = RK1_2 |
| RK3_0 | `04` | upper nibble = upper nibble of NX(lo RK1_0 || lo RK1_1), lower nibble = upper nibble of RK2_3 |
| RK3_1 | `06` | = RK2_2 |
| RK4_0 | `29` | upper nibble = upper nibble of NX(lo RK2_0 || lo RK2_1), lower nibble = upper nibble of RK3_3 |
| RK4_1 | `8F` | = RK3_2 |
