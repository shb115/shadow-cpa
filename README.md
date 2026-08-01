# Side-channel analysis of the Shadow lightweight block cipher

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21731940.svg)](https://doi.org/10.5281/zenodo.21731940)

Firmware, acquisition and analysis code for the paper

> *Practical Key Recovery on the Shadow Lightweight Block Cipher with Non-Profiling
> Correlation Power Analysis*
>
> Hanbeom Shin, Insung Kim, Sunyeop Kim, Jihoon Jang, Myoungsu Shin and Donggeun Kwon
> Correspondence: dgkwon@kunsan.ac.kr

The work covers three experiments on unprotected implementations — Shadow-32 with a fixed key,
Shadow-32 with ten independently chosen keys, and Shadow-64 — together with the leakage
assessment of two masked Shadow-32 implementations.

This repository holds the code. The power traces it analyses are about 470 MB and are archived
separately:

| | |
|---|---|
| **Power traces** | https://doi.org/10.5281/zenodo.21721710 |
| **This code** | https://doi.org/10.5281/zenodo.21731940 — archived release `v1.0` |

## Getting the traces

Download `shadow-cpa-traces.zip` (495 MB) from the Zenodo record above and unpack it in the
root of this repository. It contains the `data/` tree, so this is all it takes:

```
data/
  shadow32_fixedkey/  s32_ref_12500.npz
  shadow32_10keys/    s32_key01_12500.npz … s32_key10_12500.npz
  shadow64/           s64_ref_25000.npz
  masked/             masking_ISW_traces.npz, masking_ISWLUT_traces.npz
```

Every script in `analysis/` looks for the traces at those paths by default; nothing else needs
configuring. They are not tracked here because of their size.

One part of the repository runs without any download: `reference/selftest.c` reproduces the
round keys reported in the paper from the key schedule alone.

## Quick start

```
gcc -O2 -o selftest reference/selftest.c reference/shadow32.c reference/shadow64.c && ./selftest

cd analysis
python cpa_shadow32_12500.py        # Shadow-32, fixed key and all ten key sets
python viz_10keys.py                # success rate and guessing entropy
python cpa_s64_analysis.py          # Shadow-64 two-stage CPA
python analyze_wide.py ../data/masked/masking_ISW_traces.npz 10000   # masked t-test
```

**Licence** — MIT, see `LICENSE`, with the attributions noted at the end of this file. The
traces on Zenodo are CC BY 4.0 and carry their own licence note.

**Environment** — Python 3.10 with NumPy 1.26.4 and Matplotlib 3.5.1; the notebook also needs
Jupyter, ipywidgets and tqdm. See `requirements.txt`. Acquisition additionally needs a
ChipWhisperer-Nano and the ChipWhisperer package (5.6.1 was used), and building the firmware
needs `arm-none-eabi-gcc` 10.2.1 inside the ChipWhisperer firmware tree.

## Measurement setup

All traces were acquired on a ChipWhisperer-Nano capture board with its on-board STM32F030F4
target, which implements the ARM Cortex-M0 core. Power is measured by the capture board's own
ADC through its integrated shunt, so no external probe or oscilloscope is involved. The
target clock and the ADC both run at 7.5 MHz, giving exactly one sample per clock cycle. Every
trace file records these settings in its `clkout`, `adc_freq` and `samples` fields.

The firmware raises a GPIO trigger immediately before the cryptographic operation and lowers
it immediately afterwards, and acquisition is triggered by this signal. Because the capture
board also supplies the target clock, the traces are aligned as acquired, and no realignment,
filtering or averaging is applied before the analysis.

Before each acquisition the capture script resets the clock phase until the trace shows
clipping. This high-amplitude phase was measured to give about six times the signal-to-noise
ratio of an arbitrary phase, and the three unprotected trace sets record it in their
`phase` field as `seekclip`. The masked sets were acquired separately and carry no
`phase` field. The script also verifies the target against the reference implementation with a
known-answer test before capturing, so a wrong key or a broken build is detected up front.

All firmware is built at optimisation level `-O0`. This is deliberate. At `-O0` every
intermediate value is written to stack memory on each operation, which produces the strong
Hamming-weight leakage the attack targets and a correct-key correlation of about 0.9. At
`-O2` or `-Os` the intermediates stay in registers, the leakage weakens and the peak drops to
about 0.6. The `makefile` in `firmware/` carries the same note.

## Layout

```
capture/     acquisition script for all three experiments
firmware/    capture firmware sources and build file
reference/   reference implementations of Shadow-32 and Shadow-64, with a self-test
analysis/    CPA and leakage-assessment code
data/        power traces — not tracked here, download from Zenodo
results/     recorded output of the analysis code
```

The analysis code also writes its plots to `figures/`. Those are regenerated on every run and
are not tracked here; the versions used in the paper are the figures of the paper itself.

### capture/

`capture_exp.py` performs all three acquisitions.

```
python capture_exp.py s32d         Shadow-32, fixed key,  2048 x 12500
python capture_exp.py s32k         Shadow-32, ten keys,   2048 x 12500 each
python capture_exp.py s64 4096     Shadow-64,             4096 x 25000
```

The trace count defaults to 2048 and is overridden by the optional second argument, which is why the Shadow-64 line carries an explicit `4096`. The number of samples per trace is fixed per experiment inside the script.

The ten master keys are drawn from a fixed seed, so the same ten keys are reproduced on every
run. The Shadow-64 branch of this script was corrected when the traces were archived: the
original copy still referred to the earlier reference key `000102…0F`, whereas the published
Shadow-64 traces were captured with the random master key `07E9A4B27E3FCB472DA757EA31CAF4ED`. The
script now loads `shadow64_newkey-CWNANO.hex` and carries the matching `rk[128]`, which is
byte-for-byte identical to the table in the firmware and to the `rk` field of the trace file.
A note at the top of the file records the change.

### firmware/

| File | Description |
|---|---|
| `shadow32_nop.c` | Shadow-32 capture firmware. Accepts a master key over the serial link, so one image serves both the fixed-key and the ten-key experiment. |
| `shadow64_nop_newkey.c` | Shadow-64 capture firmware. The round keys are precomputed on the host and baked in, because the Shadow-64 key schedule needs more stack than the target has. |
| `makefile` | Build file, including the reason for `-O0`. |
| `masking_ISW.c`, `masking_ISWLUT.c` | The two masked Shadow-32 implementations used for the leakage assessment. Both take all randomness from the input buffer, so no random number generator runs on the device. |

Source only; the compiled images are not included. Each file builds to `<TARGET>-CWNANO.hex`
inside the ChipWhisperer firmware tree, as described at the top of the `makefile`. The traces
here were acquired with images built by `arm-none-eabi-gcc` 10.2.1 in the ChipWhisperer 5.6.1
firmware tree; use the same versions to reproduce the build. `capture/capture_exp.py` flashes
the image it finds in `firmware/`, so build it there before capturing.

### reference/

`shadow32.c` and `shadow64.c` are self-contained reference implementations including the key
expansion. They were **not** used to record any trace. They are included so that the round
keys, the key schedule inversion and the ciphertexts reported in the paper can be checked
independently.

`selftest.c` does exactly that, without any hardware:

```
gcc -O2 -o selftest selftest.c shadow32.c shadow64.c
./selftest
```

It runs the key schedule on the master keys of the published trace sets and compares the
result with the round keys reported in the paper — `0D 3B 60 33 / 43 60 25 3C / 13 25 89 C5 /
3C 89 0D 5D` for the fixed-key set and `872C E3FB 644A 72D7` for Shadow-64 — then checks that
decryption inverts encryption for both ciphers. It exits non-zero if any check fails.

### analysis/

| File | Description |
|---|---|
| `cwnano-shadow32-cpa.ipynb` | Shadow-32 CPA over Rounds 1 to 4 on the fixed-key set, and the figures for it. |
| `cpa_shadow32_12500.py` | The same attack scripted over the fixed-key set and all ten key sets. Reports the peak correlation of every recovered subkey, checks each recovery against the stored round keys, and computes the NX-equivalence class of the master key. One full run writes `results/_peaks_12500.json`; `--figs` then redraws the summary figure from that cache instead of re-attacking all eleven sets. It still recomputes the per-round correlation curves of the representative key set, so it needs `data/shadow32_10keys/s32_key01_12500.npz` and takes about a minute. |
| `viz_10keys.py` | Success rate and guessing entropy over the ten key sets. |
| `cpa_s64_analysis.py`, `shadow64_ks.py` | Shadow-64 two-stage CPA and its key schedule. |
| `fig_shadow64_trace.py` | Shadow-64 power-trace figures, and the round period measured by autocorrelation. |
| `analyze_wide.py` | Fixed-versus-random Welch *t*-test on the masked traces. |
| `cpa_offline.py` | CPA on the masked traces, Hamming-weight or Hamming-distance model. |

### data/

Not tracked here — download it from the Zenodo record named at the top. Once unpacked:

| Folder | Contents |
|---|---|
| `shadow32_fixedkey/` | `s32_ref_12500.npz`, 2048 traces of 12500 samples. Round keys `0D 3B 60 33 / 43 60 25 3C / 13 25 89 C5 / 3C 89 0D 5D`. |
| `shadow32_10keys/` | `s32_key01_12500.npz` … `s32_key10_12500.npz`, 2048 traces of 12500 samples per key. |
| `shadow64/` | `s64_ref_25000.npz`, 4096 traces of 25000 samples. Master key `07E9A4B27E3FCB472DA757EA31CAF4ED`, first round key `872C E3FB 644A 72D7`. |
| `masked/` | `masking_ISW_traces.npz` and `masking_ISWLUT_traces.npz`, 8192 traces each, split into 4096 fixed-plaintext and 4096 random-plaintext traces. |

Fields of the Shadow-32 and Shadow-64 files:

- `traces` — float16 power samples
- `pt` — plaintexts, four bytes for Shadow-32 and eight for Shadow-64
- `rk` — the full round key schedule, `uint8` for Shadow-32 and `uint16` for Shadow-64
- `master` — the master key, empty for the fixed-key set whose round keys are baked in
- `clkout`, `adc_freq`, `samples`, `phase`, `cipher` — acquisition metadata

Fields of the masked files:

- `traces`, `pt` — as above, with `pt` bytes 0 to 3 the plaintext and bytes 4 to 19 the masks
  and fresh randomness. Only the plaintext is fixed in the fixed group.
- `group` — 0 for the fixed group and 1 for the random group
- `key` — the round key
- `clkout`, `adc_freq`, `samples`, `version` — acquisition metadata

## Reported results

Shadow-32, fixed key. All sixteen round-key bytes of Rounds 1 to 4 are recovered,
`0D 3B 60 33 / 43 60 25 3C / 13 25 89 C5 / 3C 89 0D 5D`. Eleven of them are strictly needed
from CPA and the other five follow from the key schedule, as stated in the paper. The script
runs CPA on twelve subkeys rather than eleven: `RK2_1` is also fixed by the key schedule and
is attacked only as a cross-check. The correct-key correlation is between 0.79 and 0.90 over
these twelve. `results/RESULTS_shadow32_12500.md` lists the peak correlation and the peak
sample of each.

Shadow-32, ten keys. All ten sets are recovered in full, with correct-key correlations between
0.78 and 0.91 across the 120 subkeys taken by CPA. Each Round-1 subkey reaches a success rate
of 1.0 at about 100 traces and all sixteen round-key bytes at about 500, while the guessing
entropy reaches one at about 50. The true master key
lies in the NX-equivalence class obtained by inverting the key schedule in every set. The
class is not a singleton because the NX module is not injective — its size ranges from 24 to
81 here — but every member of it produces the same round keys.

Shadow-64. All four words of the first round key are recovered by the two-stage method,
`872C E3FB 644A 72D7`. `results/RESULTS_shadow64.md` records the per-word correlations of both
stages. It also keeps a comparison against a 16-bit exhaustive search over all 65536
candidates, which ranks the correct value of one word only eighth while the two-stage method
recovers it; that comparison is supplementary material and is not part of the paper.

Masked Shadow-32. The ISW implementation does not pass the *t*-test, with 18 samples above
the 4.5 threshold and a maximum absolute *t* of 13.46. The table-lookup implementation with
register overwriting passes, with no sample above the threshold and a maximum absolute *t* of
3.61.

## Environment

The analysis code needs Python 3 with NumPy and Matplotlib only. Acquisition additionally
needs the ChipWhisperer package and the hardware. The traces are stored as float16 and the
analysis converts them to float64, so one Shadow-32 trace set occupies about 200 MB of memory,
one masked set about 650 MB and the Shadow-64 set about 800 MB. Allow roughly twice that for
the hypothesis matrices built during the correlation.

## Licence and attributions

This repository is MIT licensed; see `LICENSE`. Three things about it are worth stating
explicitly.

**`firmware/masking_ISW.c` and `firmware/masking_ISWLUT.c`** were started from a ChipWhisperer
example target and still carry its original header, which is left in place:

> This file is part of the ChipWhisperer Example Targets
> Copyright (C) 2012-2017 NewAE Technology Inc.
> Licensed under the GNU General Public License, version 3 or (at your option) any later
> version.

That header governs whatever remains of the original scaffold. The rest of these files is our
own work under the MIT terms: the Shadow-32 cipher, the masked tables and the register-wiping
routines were written for this paper, and the ISW gadget and the mask-refreshing routine are
our two-share specialisation of the construction of Ishai, Sahai and Wagner, written following
the structure of the PIPO reference code — see the comments in `masking_ISW.c` for the specific
correspondences. PIPO is described in H. Kim et al., *PIPO: A Lightweight Block Cipher with
Efficient Higher-Order Masking Software Implementations*, ICISC 2020.

`firmware/shadow32_nop.c` and `firmware/shadow64_nop_newkey.c` were written for this work
rather than adapted from an example. They call the SimpleSerial and HAL entry points, which is
how any target firmware talks to the platform, but contain no ChipWhisperer code and carry no
NewAE header.

**`firmware/makefile`** — the lower half, the `EXTRA_OPTS` and `CRYPTO_TARGET` handling and the
two `include` lines, is the ChipWhisperer target-makefile template with `TARGET`, `SRC` and
`OPT` filled in for this work. It is a project fragment that only means anything inside the
ChipWhisperer firmware tree, and the same terms apply to it as to the template it came from.

**ChipWhisperer** is a product of NewAE Technology Inc. and is GPL-3.0-or-later:
https://github.com/newaetech/chipwhisperer. All firmware here builds inside its firmware tree
and uses its SimpleSerial protocol and HAL. Those headers, sources and build files are **not**
redistributed here; obtain them from the ChipWhisperer project under its own licence. No
compiled firmware image is included either — the images used for the acquisition were linked
against ChipWhisperer's GPL sources, so rebuilding them from the sources here reproduces that
situation on your own machine and under those terms.

`figures/` and `results/` are computed from the traces, which are CC BY 4.0 on Zenodo. The MIT
grant covers them, but if you reuse them please also credit the trace deposit.
