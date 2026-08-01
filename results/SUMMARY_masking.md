# Shadow32 masked side-channel analysis: masking_ISW vs masking_ISWLUT

- **Target**: ChipWhisperer-Nano (STM32F030F4, Cortex-M0), Shadow32 round 1
- **Acquisition**: **4096 fixed + 4096 random = 8192 traces** per version, `samples=10000`, `clkout=adc_freq=7.5MHz`, `clk_src=int`, **-O0**
- **Plaintext**: `pt[0:4]` (fixed in the fixed group only), the masks and randomness `pt[4:20]` are random in both groups

## The two versions

| Implementation | AND construction | Countermeasure |
|---|---|---|
| `masking_ISW` | **arithmetic ISW** AND | none (refresh only) |
| `masking_ISWLUT` | **ISW LUT** AND (masked table lookup) | **register and bus overwriting** |

## Result summary (4096 per set)

| Metric | masking_ISW (arithmetic) | masking_ISWLUT (LUT + overwriting) |
|---|---|---|
| **TVLA** max\|t\| | **13.46** | **3.61** |
| **TVLA** samples with \|t\|>4.5 | **18** (leakage) | **0** (pass) |
| **CPA HW** correct-key rank | 133 / 256 (not recovered) | 170 / 256 (not recovered) |
| **CPA HD** correct-key rank | 208 / 256 (not recovered) | 112 / 256 (not recovered) |
| state l0 correlation | 0.187 | 0.056 (noise) |
| state r0 correlation | 0.210 (leakage) | 0.044 (noise) |
| key s0 correlation | 0.062 (noise) | 0.054 (noise) |

## Interpretation

1. **CPA does not recover the key on either version** (HW and HD alike). The correct key stays in the middle of the 256 candidates in all four attacks.
2. **This outcome cannot be attributed to the masking alone.** The firmware masks the round key with a fresh random byte on every encryption, `rk[0] ^= r_key0` in `firmware/masking_ISW.c` lines 209 to 212 and in `masking_ISWLUT.c` lines 234 to 237, and `masked_xor_const_inplace` XORs that mask into one of the two shares only (`a->s0 ^= k`, `masking_ISW.c` lines 78 to 80), so it is never removed. The key-dependent intermediate is therefore re-randomised on every trace, independently of the masking. The failure of CPA on both versions is a fact of these measurements, but it does not establish that the masking is what prevents key recovery.
3. **Only masking_ISW exceeds the fixed versus random t-test** (leakage), masking_ISWLUT passes.
   - The t-test leakage of masking_ISW is the **plaintext state (l0/r0)** leaking at first order through the recombination of the two shares (Hamming distance, transitions), namely the plaintext and not the key. This is why the t-test fires while CPA on the key does not succeed.
   - masking_ISWLUT (a) replaces the arithmetic AND with a **table lookup** so that the two shares never meet at a gate, and (b) breaks the register and bus recombination transitions by **overwriting**, which removes the state leakage, hence 0 samples above the t-test threshold.
4. **Main conclusion**: ISW masking alone is not broken by CPA here, subject to finding 2, but **the t-test leakage of the plaintext state** remains, and removing it requires **a masked table plus register and bus overwriting**. (The masking algorithm can be written in pure C, the overwriting needs asm.)

## Files

```
data/masked/masking_ISW_traces.npz          arithmetic ISW, 8192 x 10000 (65 MB)
data/masked/masking_ISWLUT_traces.npz       ISW LUT + overwriting, 8192 x 10000 (64 MB)
firmware/masking_ISW.c                      source (arithmetic ISW)
firmware/masking_ISWLUT.c                   source (ISW LUT + register and bus overwriting)
analysis/analyze_wide.py                    t-test analysis code (Welch t + HW model correlation)
analysis/cpa_offline.py                     CPA attack code (HW/HD models)
results/SUMMARY_masking.md                  this file
results/masking_ISW_result.txt              numeric summary
results/masking_ISWLUT_result.txt           numeric summary
```

**`.npz` contents** (numpy `np.load`): `traces` (8192 × 10000, float16) for the waveforms,
`pt` (8192 × 20, uint8) for plaintext and randomness, `group` (8192, uint8) with 0=fixed/1=random,
`key` (4, uint8) for the round key, plus the `clkout`/`adc_freq`/`samples`/`version` metadata.
Loading example: `d = np.load('masking_ISW_traces.npz'); tr = d['traces']; g = d['group']`

## Reproducing the analysis (run from the `analysis/` folder)

The raw traces are published with this code, so the commands below reproduce the t-test and CPA
results of the tables above exactly.
(numpy and matplotlib are required. With the argument omitted, `masking_ISW` is the default.)

```
# TVLA (Welch t) - arguments: dataset path, number of samples
python analyze_wide.py ../data/masked/masking_ISW_traces.npz 10000
python analyze_wide.py ../data/masked/masking_ISWLUT_traces.npz 10000

# CPA - HW model by default
python cpa_offline.py ../data/masked/masking_ISW_traces.npz
python cpa_offline.py ../data/masked/masking_ISWLUT_traces.npz

# CPA - the HD (register transition) model is selected with the CPA_MODEL environment variable
#   POSIX shell: CPA_MODEL=HD python cpa_offline.py <dataset>
#   PowerShell : $env:CPA_MODEL="HD"; python cpa_offline.py <dataset>
#   cmd        : set CPA_MODEL=HD && python cpa_offline.py <dataset>
CPA_MODEL=HD python cpa_offline.py ../data/masked/masking_ISW_traces.npz
CPA_MODEL=HD python cpa_offline.py ../data/masked/masking_ISWLUT_traces.npz
```

Each run writes `<dataset>_tvla.png` / `_cpa.png` / `_cpaHD.png` into `results/`, which are
regenerated on every run and are not tracked here, and prints the
max |t| of the t-test with the number of samples above the threshold, and the correct-key
(0x0D) rank of the CPA.

> Note: on both versions the key-related correlation is at the 0.04 to 0.06 level of the table
> above, far below the state leakage (0.19 to 0.21), so the rank is decided by noise. The
> individual rank values (133/170/208/112) are therefore not a metric for comparing the two
> implementations; what matters is that the correct key does not reach the top guess, namely
> that it is not recovered.
