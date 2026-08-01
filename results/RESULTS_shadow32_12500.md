# Shadow-32 CPA : 12500-sample capture, recovery of round keys RK1..RK4

- Method : rounds 1,2 = 8-bit CPA / rounds 3,4 = 4-bit CPA (the upper nibble is computed from the key schedule NX)
- CPA is run on 12 subkeys, but RK2_1 is a value the key schedule already fixes,
  so it is only a cross-check. The 11 "subkeys recovered by CPA" counted in the paper are these 12 minus RK2_1.
- Window : prefix window `trace[:, :W]`, W1..W4 = 1100, 1850, 2750, 3500
- Capture : clkout 7.5MHz / adc 7.5MHz, seekclip phase, `-O0` firmware

## 1. Fixed-key set (`s32_ref_12500.npz`, 2048 x 12500)

Recovered RK1..RK4 : `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D`
Reference RK1..RK4 : `0D 3B 60 33 43 60 25 3C 13 25 89 C5 3C 89 0D 5D`
Matching bytes : **16/16**,  alpha = +1

| Subkey | Mode | Recovered | Peak \|rho\| | Peak sample |
|---|---|---|---|---|
| RK1_0 | 8-bit | `0D` | 0.896 | 548 |
| RK1_1 | 8-bit | `3B` | 0.900 | 709 |
| RK1_2 | 8-bit | `60` | 0.811 | 636 |
| RK1_3 | 8-bit | `33` | 0.795 | 796 |
| RK2_0 | 8-bit | `43` | 0.904 | 1296 |
| RK2_1 | 8-bit | `60` | 0.901 | 1457 |
| RK2_2 | 8-bit | `25` | 0.794 | 1384 |
| RK2_3 | 8-bit | `3C` | 0.802 | 1544 |
| RK3_2 | 4-bit | `89` | 0.794 | 2132 |
| RK3_3 | 4-bit | `C5` | 0.793 | 2292 |
| RK4_2 | 4-bit | `0D` | 0.798 | 2879 |
| RK4_3 | 4-bit | `5D` | 0.786 | 3040 |

- Rounds 1 and 2 (8-bit CPA, 8 subkeys) : |rho| 0.794 ~ 0.904
- Rounds 3 and 4 (4-bit CPA, 4 subkeys) : |rho| 0.786 ~ 0.798
- All 12 : min 0.786, max 0.904, mean 0.831

Equivalence class size 81 (no master field, this set has the round keys hard-coded as constants in the firmware)

## 2. 10 random-key sets (`s32_key01..10_12500.npz`, 2048 x 12500 each)

| Set | master | RK1 | RK2 | RK3 | RK4 | Match | min\|rho\| | alpha | master∈class(size) |
|---|---|---|---|---|---|---|---|---|---|
| key01 | `E10020BD4E590E12` | `10 2B 04 DE` | `0D 04 05 E9` | `0E 05 20 9E` | `C9 20 4E E0` | 16/16 | 0.786 | +1 | O (24) |
| key02 | `10594F596EC32B72` | `4F 45 26 9E` | `19 26 8C E3` | `9E 8C 12 3B` | `13 12 21 B1` | 16/16 | 0.788 | +1 | O (81) |
| key03 | `A899B352D3E180D4` | `C3 B5 4D 23` | `82 4D 1E 31` | `23 1E 48 10` | `21 48 1A 09` | 16/16 | 0.781 | +1 | O (27) |
| key04 | `A04595F4836A0483` | `05 9F 28 43` | `04 28 46 3A` | `13 46 30 A4` | `4A 30 8A 41` | 16/16 | 0.794 | +1 | O (36) |
| key05 | `8B94533A86877F7D` | `33 53 18 A6` | `9A 18 08 67` | `06 08 37 7F` | `87 37 88 FA` | 16/16 | 0.796 | +1 | O (27) |
| key06 | `974E4B199238008C` | `8B 41 49 92` | `49 49 23 28` | `82 23 10 80` | `88 10 19 06` | 16/16 | 0.777 | +1 | O (81) |
| key07 | `86B045954E53F9C4` | `C5 49 04 5E` | `95 04 05 E3` | `1E 05 8F 39` | `43 8F 48 97` | 16/16 | 0.787 | +1 | O (81) |
| key08 | `911836FAFAE5AB8A` | `06 3F 8F AA` | `1A 8F 8E A5` | `0A 8E CA 5B` | `25 CA 39 B0` | 16/16 | 0.792 | +1 | O (54) |
| key09 | `E0DF051FEC09239E` | `15 01 8E FC` | `1F 8E 90 C9` | `1C 90 02 93` | `69 02 6E 31` | 16/16 | 0.791 | +1 | O (27) |
| key10 | `8BB298B21469FAE0` | `C8 9B 01 24` | `32 01 06 49` | `04 06 8F 9A` | `29 8F 08 AA` | 16/16 | 0.789 | +1 | O (81) |

- Full recovery of round keys RK1..RK4 : **10/10 sets**
- True 64-bit master ∈ NX equivalence class : **10/10 sets** (NX is not invertible -> the master key cannot be uniquely recovered)
- Equivalence class size : 24, 81, 27, 36, 27, 81, 81, 54, 27, 81
- Subkey peak \|rho\| (10 sets x 12 = 120 values) : **min 0.777, max 0.912**, mean 0.835
