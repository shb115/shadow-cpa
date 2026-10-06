# Shadow-64 CPA results: first round key recovery

- Data : `s64_ref_25000.npz` (4096 traces x 25000 samples)
- Master key : `07E9A4B27E3FCB472DA757EA31CAF4ED` (random)
- True RK1 : `872C E3FB 644A 72D7`
- Acquisition : clkout 7.5MHz / adc 7.5MHz, seekclip phase, `-O0` firmware + NOP padding
- Samples : Round 1, `[354, 1095)`, from the mean trace alone (round period 741, boundary 354, `round_structure.py`);
  used for stages 1 and 2 and for the exhaustive search. Neither the key nor an attack outcome is used.

## 1. Recovery results

**4/4 words, 8/8 bytes recovered.**

| Word | stage 1 low (8-bit) \|r\| | stage 2 high (16-bit) \|r\| | recovered | true | result |
|---|---|---|---|---|---|
| RK1_0 | `2C` 0.720 | `87` 0.888 | `872C` | `872C` | full recovery |
| RK1_1 | `FB` 0.732 | `E3` 0.898 | `E3FB` | `E3FB` | full recovery |
| RK1_2 | `4A` 0.518 | `64` 0.675 | `644A` | `644A` | full recovery |
| RK1_3 | `D7` 0.517 | `72` 0.668 | `72D7` | `72D7` | full recovery |

Stage 1 (byte HW) gives a low correlation (0.5~0.7) because the upper 8 bits enter as noise,
while stage 2, which fixes the low byte and searches the high byte with the **full 16-bit HW**, raises it sharply (0.67~0.90).

In stage 2 of RK1_0 the candidate `002C`, with the correct lower byte and the upper byte `00`, reaches only
|rho| = 0.620 (rank 52 of 256 by the alpha-signed score, 52 by |rho|), below the 0.720 of the lower byte alone in
stage 1, because its hypothesis includes the Hamming weight of a wrong upper byte (the comparison of Section 5.3 of the paper).

## 2. Method

```
h  = F16(L0) ^ L1                     # intermediate value before the key XOR
① low byte  : CPA with HW8(h&0xFF ^ c)         -> klo
② high byte : rebuild the 16-bit value with klo fixed, then
              CPA with HW16(h ^ ((c<<8)|klo))  -> khi
   RK = (khi<<8) | klo
```
The next intermediate value is then built as `S1L = h ^ RK`, and the same steps continue for RK1_2 / RK1_3.

## 3. Complement ambiguity: why alpha is needed

The HW model carries a one-bit ambiguity that cannot be removed.

- 8-bit : `HW(x^(k^0xFF)) = 8 - HW(x^k)` → the r values of a complement pair differ **in sign only**
  (measured: true key `2C` +0.7197 / complement `D3` −0.7197, sum = 0.000000)
- 16-bit : `HW16(x^(k^0xFFFF)) = 16 - HW16(x^k)` → flipping the high and low bytes **at the same time**
  leaves `|rho|` exactly unchanged (measured difference = 0.0000)

So `|r|` alone cannot decide this bit at either stage, and running stage 2 twice does not
help. **The device sign alpha has to be known.**
alpha is a property of the measurement setup, not of the key. It is taken from the decision on D
of Section 4.3 of the paper, run without the key on the Shadow-32 fixed-key traces acquired on
the same board (`alpha_from_shadow32`), which gives alpha = +1.

> Note: flipping the low byte only does lower the fit (0.8878 → 0.5828). But the candidate
> in which the high byte is flipped as well keeps `|r|` unchanged, so this asymmetry cannot be used.
> Solving with `argmax|rho|` and no alpha recovers `RK ^ 0xFFFF` and drops to 2/4 words.

Without alpha, therefore, exactly **two** candidates (`{k, k^0xFFFF}`) remain for each word;
the paper fixes the sign by the decision on D of Section 4.3, as above.

## 4. Comparison with the 16-bit exhaustive search (supplementary, not part of the paper)

Rank of the true key when the 65536 candidates are swept with a single 16-bit HW model:

| Word | exhaustive rank 1 | rank 1 \|rho\| | true \|rho\| | true rank | complement rank |
|---|---|---|---|---|---|
| RK1_0 | `78D3` | 0.88777 | 0.88777 | **2** | 1 |
| RK1_1 | `1C04` | 0.89828 | 0.89828 | **2** | 1 |
| RK1_2 | `DFFF` | 0.68139 | 0.67474 | **8** | 7 |
| RK1_3 | `8D28` | 0.66795 | 0.66795 | **2** | 1 |

**The exhaustive search does not place the true key in the top 2 for `RK1_2`(rank 8).**
The two-stage decomposition recovers them exactly from the same data.
Stage 1 looks at the low byte on its own and isolates the leakage of that byte,
while the exhaustive search treats high and low together and loses the ranking on the weak words.

On this set the two-stage decomposition therefore cuts the work (65536 -> 128+256 = 384 candidate evaluations)
and also ranks the true value of these words first where the exhaustive search does not; this comparison is
supplementary material and is not part of the paper.

## 5. File layout

```
data/shadow64/s64_ref_25000.npz            traces 4096 x 25000
data/shadow32_fixedkey/s32_ref_12500.npz   Shadow-32 fixed-key traces, from which the sign of alpha is taken
firmware/shadow64_nop_newkey.c             acquisition firmware source (image not included)
reference/shadow64.c                       reference implementation (not used for acquisition)
analysis/cpa_s64_analysis.py               two-stage CPA + 16-bit exhaustive search
analysis/shadow64_ks.py                    key schedule
analysis/fig_shadow64_trace.py             power trace figures, round period autocorrelation
results/RESULTS_shadow64.md                this document
figures/shadow64/
  stage1_8bit/stage1_RK1_*.pdf (+ .png)    stage 1 low byte 8-bit CPA (per word)
  stage2_16bit/stage2_RK1_*.pdf (+ .png)   stage 2 16-bit CPA, low byte fixed (per word)
  exhaustive_16bit/exh_RK1_2_*.png         16-bit exhaustive search (RK1_2 only: |r| curves top256 /
                                           rank bars top24)
  trace.pdf, trace.png, trace_zoom.png     power traces (fig_shadow64_trace.py; trace.pdf is Fig. 15 of the paper)
```

Reproduction : run `python cpa_s64_analysis.py` in `analysis/` (the default paths point to the layout above;
the script also reads `data/shadow32_fixedkey/s32_ref_12500.npz` for the sign of alpha).
The 16-bit exhaustive search comparison in Section 4 is supplementary and is not part of the paper.
