# Side-channel analysis of the Shadow lightweight block cipher

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21731939.svg)](https://doi.org/10.5281/zenodo.21731939)

Firmware, acquisition and analysis code for the paper

> *Practical Key Recovery on the Shadow Lightweight Block Cipher with Non-Profiling
> Correlation Power Analysis*
>
> Hanbeom Shin, Insung Kim, Sunyeop Kim, Jihoon Jang, Myoungsu Shin and Donggeun Kwon
> Correspondence: dgkwon@kunsan.ac.kr

The work covers three experiments on unprotected implementations, Shadow-32 with a fixed key,
Shadow-32 with ten independently chosen keys, and Shadow-64, the same fixed-key attack at two
further clock phases, the characterization of the leakage model (Fig. 1 of the paper), and
the attack and the leakage assessment of two masked Shadow-32 implementations, each measured
over one whole masked round in two independent acquisitions and over the full 16-round
encryption.

This repository holds the code. The power traces it analyzes are about 3.4 GB and are archived
separately:

| | |
|---|---|
| **Power traces** | https://doi.org/10.5281/zenodo.21721709, all versions |
| **This code** | https://doi.org/10.5281/zenodo.21731939, archived releases, all versions |
| **Source repository** | https://github.com/shb115/shadow-cpa |

Both DOIs are concept DOIs and resolve to the latest version of each record.

## Getting the traces

Download the trace archive of the latest version of the Zenodo record above
(`shadow-cpa-traces-v2.zip`) and unpack it into the `data/` folder of this repository. The
files listed under `data/` below are those of that version (the first version,
https://doi.org/10.5281/zenodo.21721710, holds the unprotected sets and the superseded masked
sets of the previous version of the paper). The archive holds the subfolders of `data/`
(`masked/`, `shadow32_fixedkey/`, `shadow32_10keys/`, `shadow64/`, `hwchar/`), so this is all it takes:

```
data/
  shadow32_fixedkey/  s32_ref_12500.npz, s32_shadow32_O0_fixedphase_12500.npz, s32_shadow32_O0_noclipphase_12500.npz
  shadow32_10keys/    s32_key01_12500.npz ... s32_key10_12500.npz
  shadow64/           s64_ref_25000.npz
  masked/             masking_ISW_v2_seed{1,2}_16384x10000.npz, masking_ISWLUT_v2_seed{1,2}_16384x46000.npz,
                      masking_ISW_v2_full_seed1_16384x46000.npz, masking_ISWLUT_v2_full_seed1_16384x46000.npz
  hwchar/             fig1_lock_tbl1_1000.npz, phase_template.npz
```

Every script in `analysis/` looks for the traces at those paths by default; nothing else needs
configuring. They are not tracked here because of their size. The file sizes and checksums are
listed under `data/` below.

One part of the repository runs without any download: `reference/selftest.c` reproduces the
round keys reported in the paper from the key schedule alone.

## Quick start

```
gcc -O2 -o selftest reference/selftest.c reference/shadow32.c reference/shadow64.c && ./selftest

cd analysis
python cpa_shadow32_12500.py        # Shadow-32, fixed key and all ten key sets (about a minute)
python fig_fixedkey_cpa.py          # Shadow-32 correlation figures of the fixed-key set
python success_rate.py              # success rate, guessing entropy and sign decision (about ten minutes)
python trace_stats.py               # ADC-rail fraction and round structure of the unprotected sets
python phase_compare.py             # the Round-1 attack at the three clock phases of the fixed-key set
python cpa_s64_analysis.py          # Shadow-64 two-stage CPA
python fig_shadow64_trace.py        # Shadow-64 power trace (Fig. 15)
python masked_eval.py               # masked sets: t-tests, repetition, CPA of Algorithm 1 (about ten minutes)
python full_encryption.py           # masked sets: t-tests on the full 16-round encryption (one to two minutes)
python fig_tvla.py                  # Fig. 14 from the curves cached by masked_eval.py
python fig_hw_boxplot.py            # Fig. 1 and the statistics behind it
```

**License**: MIT, see `LICENSE`, with the attributions noted at the end of this file. The
traces on Zenodo are CC BY 4.0 and carry their own license note.

**Environment**: Python 3.10 with NumPy 1.26.4 and Matplotlib 3.5.1. See `requirements.txt`.
Acquisition additionally needs a ChipWhisperer-Nano and the ChipWhisperer package, and building
the firmware needs `arm-none-eabi-gcc` inside the ChipWhisperer firmware tree; the versions used
for each image are given under `firmware/` below.

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

Before each acquisition the capture script resets the clock phase of the target relative to the
ADC until a probe trace reaches at least 98% of the ADC full scale in at least one sample, which
selects the phase at which the sampling instant falls on the current peak of each clock cycle
(`seek_clip_phase` in `capture/capture_exp.py` and `capture/capture_lab.py`). In the deposited
unprotected traces about 2.1% of all samples sit at the positive rail of the ADC, the negative
rail is never reached, and none of the samples at which the CPAs peak is saturated in any trace
(`analysis/trace_stats.py`). The sets acquired this way record the phase selection in their
`phase` field as `seekclip`: the three unprotected experiments and the six masked sets. Two
further sets of the fixed-key experiment record a different phase: `fixed (no phase selection)`,
the phase the board happened to be at after power-on, which turned out to clip as well (2.0% of
the samples at the rail), and `noclip (|trace|<=0.47) @try1`, a phase at which no sample reaches
the largest value (largest value 0.277). All three fixed-key sets were acquired with the same
image and the same plaintext sequence, so the comparison between them is paired. The Fig. 1 set
locks the phase to a stored probe template of the 98% phase (`lock ... vs template` in its
`phase` field). The scripts of the unprotected acquisitions verify the target against the
reference implementation with a known-answer test in the same session, before capturing, so a
wrong key or a broken build is detected up front. For the masked firmwares the test is a
separate command (`capture_lab.py kat` and `katfull`), run before each acquisition: the
one-round test uses the `KAT` build, which returns the unmasked state after the round (the
capture image echoes its input and returns no state), and the 16-round test runs on the `FULL`
capture image itself.

All firmware is built at optimization level `-O0`. This is deliberate. At `-O0` every
intermediate value is written to stack memory on each operation, which produces the strong
Hamming-weight leakage the attack targets and a correct-key correlation of about 0.9 on the
deposited traces. An optimized build (`-O2` or `-Os`) keeps intermediate values in registers
and is expected to leak less; no traces of such a build are deposited, and the paper reports
its figures as those of the `-O0` build only. The `makefile` in `firmware/` carries the same
note.

## Layout

```
capture/     acquisition scripts for every trace set
firmware/    capture firmware sources and build files
reference/   reference implementations of Shadow-32 and Shadow-64, with a self-test
analysis/    CPA and leakage-assessment code
data/        power traces, not tracked here, download from Zenodo
results/     recorded output of the analysis code
listings/    -O0 disassembly of the capture firmwares (rebuilt; see listings/README.md)
```

The analysis code also writes its plots to `figures/`. Those are regenerated on every run and
are not tracked here; the versions used in the paper are the figures of the paper itself. The
data figures of the paper come from the following scripts and output files (the paper's own
file names differ; Figs. 2 to 4 and 17 are diagrams, not generated by code):

| Figure of the paper | Script | Output file under `figures/` |
|---|---|---|
| Fig. 1 | `fig_hw_boxplot.py` | `hw_boxplot.pdf` |
| Fig. 5 | `fig_fixedkey_cpa.py` | `shadow32_fixedkey/shadow-power-trace.pdf` |
| Figs. 6(a), (b) | `fig_fixedkey_cpa.py` | `shadow32_fixedkey/shadow-cpa-k0-128.pdf`, `-k0-256.pdf` |
| Fig. 7 | `fig_fixedkey_cpa.py` | `shadow32_fixedkey/shadow-cpa-k1.pdf` |
| Figs. 8(a) to (d) | `fig_fixedkey_cpa.py` | `shadow32_fixedkey/shadow-cpa-k2.pdf`, `-k2-bar.pdf`, `-k3.pdf`, `-k3-bar.pdf` |
| Figs. 9(a) to (d) | `fig_fixedkey_cpa.py` | `shadow32_fixedkey/shadow-cpa-r2-k0-hi.pdf`, `-r2-k2-lo.pdf`, `-r2-k2-hi.pdf`, `-r2-k3-lo.pdf` |
| Figs. 10(a) to (d) | `fig_fixedkey_cpa.py` | `shadow32_fixedkey/shadow-cpa-r3-k2.pdf`, `-r3-k3.pdf`, `-r4-k2.pdf`, `-r4-k3.pdf` |
| Fig. 11 | `cpa_shadow32_12500.py` | `shadow32_10keys/fig_fullkey_rounds.pdf` |
| Fig. 12 | `cpa_shadow32_12500.py` | `shadow32_10keys/fig_success.pdf` |
| Figs. 13(a), (b), (c) | `success_rate.py` | `shadow32_10keys/fig13a_success_rate.pdf`, `fig13b_guessing_entropy.pdf`, `fig13c_sign_decision.pdf` |
| Fig. 14 | `fig_tvla.py` | `shadow-tvla.pdf` |
| Fig. 15 | `fig_shadow64_trace.py` | `shadow64/trace.pdf` |
| Figs. 16(a), (b) | `cpa_s64_analysis.py` | `shadow64/stage1_8bit/stage1_RK1_0.pdf`, `shadow64/stage2_16bit/stage2_RK1_0.pdf` |

### capture/

`capture_exp.py` performs the three unprotected acquisitions.

```
python capture_exp.py s32d         Shadow-32, fixed key,  2048 x 12500
python capture_exp.py s32k         Shadow-32, ten keys,   2048 x 12500 each
python capture_exp.py s64 4096     Shadow-64,             4096 x 25000
```

The trace count defaults to 2048 and is overridden by the optional second argument, which is
why the Shadow-64 line carries an explicit `4096`. The number of samples per trace is fixed per
experiment inside the script.

The ten master keys are drawn from a fixed seed, so the same ten keys are reproduced on every
run. The Shadow-64 branch of this script was corrected when the traces were archived: the
original copy still referred to the earlier reference key `000102...0F`, whereas the published
Shadow-64 traces were captured with the random master key `07E9A4B27E3FCB472DA757EA31CAF4ED`. The
script now loads `shadow64_newkey-CWNANO.hex` and carries the matching `rk[128]`, which is
byte-for-byte identical to the table in the firmware and to the `rk` field of the trace file.
A note at the top of the file records the change.

`capture_lab.py` performs the masked acquisitions and the two further fixed-key acquisitions
of the unprotected cipher, with the same scope settings as `capture_exp.py`. It supplies every
random byte from the host (the masks, the refresh bytes and the key masks) and stores them with
the traces. `capture_lab.py` and `capture_fig1_tbl.py` write a copy of their console output to
`capture/logs/`, which is not tracked.

```
python capture_lab.py kat ISW                 known-answer test of the one-round build (also ISWLUT, katfull)
python capture_lab.py masked ISW              16384 x 10000, 8192 fixed + 8192 random plaintexts
python capture_lab.py masked ISWLUT           16384 x 46000
python capture_lab.py masked ISW --seed 2     independent repetition (also ISWLUT)
python capture_lab.py full ISW                16-round build, first 46000 samples (also ISWLUT)
python capture_lab.py unprot 0 2048 --fixedphase   Shadow-32 fixed key at the power-on phase
python capture_lab.py unprot 0 2048 --noclip       Shadow-32 fixed key at a phase without clipping
```

The script flashes the image it finds in `firmware/` (see there for the target names) and
writes to `data/masked/` and `data/shadow32_fixedkey/`. `shadow32_ref.py` is its reference
model: Shadow-32 and a share-level simulation of both masked firmwares; `python shadow32_ref.py`
runs its self-test. The two further fixed-key sets were acquired with the same image and the
same plaintext sequence as the set of the paper (their `pt` and `rk` fields are identical to
its); their `firmware` field, `shadow32_nop_O0-CWNANO.hex`, is the image of the first
acquisition under the file name `capture_lab.py` expects, not a rebuild. `--fixedphase` takes
the clock phase found at power-on without any selection; `--noclip` resets the phase until all
sixteen probe traces of an attempt stay within |trace| <= 0.47, so that no sample reaches the
largest ADC value, and the `phase` field of that set, `noclip (|trace|<=0.47) @try1`, records
the criterion under which its phase was accepted.

`capture_fig1_tbl.py` performs the Fig. 1 acquisition (`python capture_fig1_tbl.py lock 1000 1`:
phase locked to `data/hwchar/phase_template.npz`, 1,000 traces per Hamming weight, method 1,
the identity table). `capture_fig1.py` holds the routines it imports (`Tee`, `reset_phase`,
`CLK`, `SAMPLES`, `HW`).

### firmware/

| File | Description |
|---|---|
| `shadow32_nop.c` | Shadow-32 capture firmware. Accepts a master key over the serial link, so one image serves both the fixed-key and the ten-key experiment. |
| `shadow64_nop_newkey.c` | Shadow-64 capture firmware. The round keys are precomputed on the host and baked in, because the Shadow-64 key schedule needs more stack than the target has. |
| `makefile` | Build file, including the reason for `-O0`. |
| `masking_ISW.c` | Masked Shadow-32 with the ISW AND gadget (v2). The round key is added as a masked pair: the masked key byte into share 0 and its mask into share 1 (`masked_xor_key`). Builds with `EXTRA_OPTS=SHADOW32_KAT` return the unmasked state after the round, builds with `EXTRA_OPTS=SHADOW32_FULL` run the 16-round encryption. |
| `masking_ISWLUT.c` | Masked Shadow-32 with the table-recomputation gadget and register overwriting (v3). Every operation on a masked value (refresh, lookup, rotation, XOR, key addition, copy) is an inline assembly sequence that overwrites the working registers and the store bus with the refresh byte between its access to one share and its access to the other; the two shares of a byte are kept in different words. Same `KAT` and `FULL` variants. The source is revision v3 of the file; the build target and the trace files keep the name `masking_ISWLUT_v2`. |
| `hwchar/` | The Fig. 1 firmware `hwchar_tbl.c` with its permutation table (`tbl_perm.h`, `tbl_perm.npy`) and its own `makefile`. |

Both masked firmwares take all randomness from the input buffer, so no random number generator
runs on the device.

Source only; the compiled images are not included. Each file builds to `<TARGET>-CWNANO.hex`
inside the ChipWhisperer firmware tree, as described at the top of the `makefile`; the capture
scripts flash the image they find in `firmware/`, so build it there before capturing. The
comments in the sources are in English; they do not affect the compiled code, and the images
rebuilt from the deposited sources are byte-identical to those of the acquisition where
`listings/README.md` says so. The
target names the scripts expect are `shadow32_nop`, `shadow64_newkey`, and, for the masked
firmwares, `masking_ISW_v2`, `masking_ISW_v2_KAT`, `masking_ISW_v2_FULL` (the same three for
`masking_ISWLUT`) and `shadow32_nop_O0` for `capture_lab.py`. The Fig. 1 firmware builds from
`firmware/hwchar/` with the makefile there (`make PLATFORM=CWNANO CRYPTO_TARGET=NONE`, target
`simpleserial-hwchar-tbl`). The unprotected traces were acquired with images built by
`arm-none-eabi-gcc` 10.2.1 in the ChipWhisperer 5.6.1 firmware tree, the masked traces with
images built by 15.2.1 in the 6.0.0 tree, and the Fig. 1 traces with an image built by 14.2.1;
`listings/README.md` records which of these a rebuild reproduces byte for byte.

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
result with the round keys reported in the paper, `0D 3B 60 33 / 43 60 25 3C / 13 25 89 C5 /
3C 89 0D 5D` for the fixed-key set and `872C E3FB 644A 72D7` for Shadow-64, then checks that
decryption inverts encryption for both ciphers. It exits non-zero if any check fails.

### analysis/

| File | Description |
|---|---|
| `round_structure.py` | Locates the rounds in a trace without the key: the round period is the largest peak of the mean-trace autocorrelation and the round boundary is the quietest point of the mean trace folded over the rounds. Every CPA below runs over the samples of the round its subkey belongs to. |
| `fig_fixedkey_cpa.py` | The thirteen CPAs of Algorithm 1 on the fixed-key set and their correlation figures: the Round-1 complement pairs and the sign decision *D* of Section 4.3, the four 4-bit CPAs of Round 2, and the 4-bit CPAs of Rounds 3 and 4. Also prints the 7-bit cross-check on `RK2_1`. |
| `cpa_shadow32_12500.py` | Algorithm 1 scripted over the fixed-key set and all ten key sets. Records the target, candidates, recovered value, rank of the correct candidate, peak correlation and peak sample of every CPA, checks each recovery against the stored round keys, computes the NX-equivalence class of the master key and verifies that every member of the class expands to the stored round keys. One full run writes `results/_peaks_12500.json`; `--figs` then redraws the summary figure from that cache instead of re-attacking all eleven sets. It still recomputes the per-round correlation curves of the representative key set, so it needs `data/shadow32_10keys/s32_key01_12500.npz` and takes about a minute. |
| `shadow32_ks.py` | Shadow-32 key schedule, the function of the capture script, used to verify the equivalence class. |
| `success_rate.py` | Success rate, guessing entropy and the sign decision against the number of traces over the ten key sets, for each of the thirteen CPAs of Algorithm 1 and for their joint success, with the attack count and a Wilson 95% interval at every point. The point of interest is taken without the key; the rule of the previous version, which took it from the correct key, is kept only as a comparison curve. |
| `trace_stats.py` | Fraction of samples at the ADC rail, round period and boundary of every unprotected set, including the two fixed-key sets at the other clock phases, and whether any CPA peak sample of the fixed-key set is saturated. |
| `phase_compare.py` | The fixed-key set at its three clock phases: amplitude and rail fraction, Algorithm 1 on all 2,048 traces (reusing `cpa_shadow32_12500.recover_fullkey`), the success rate of the Round-1 attack against the number of traces with the evaluation of Section 4.6 (reusing the functions of `success_rate.py`), and the signal-to-noise ratio of the *h0* leakage. |
| `cpa_s64_analysis.py`, `shadow64_ks.py` | Shadow-64 two-stage CPA and its key schedule. The sign of alpha is taken from the decision on *D* run without the key on `data/shadow32_fixedkey/s32_ref_12500.npz`, so the script reads that file as well. For `RK1_0` it also reports the candidate with the correct lower byte and the upper byte `0x00`, the comparison of Section 5.3. |
| `fig_shadow64_trace.py` | Shadow-64 power-trace figure (Fig. 15), and the round period measured by autocorrelation. |
| `masked_tools.py` | Routines shared by the three scripts below: column-chunked Welch *t*-tests (first order, and second order on the centered squared samples), the round end from the idle loop that follows the round, the 41-cycle table builds, and the chunked 7-bit CPA. The conventions are stated in its docstring. |
| `masked_eval.py` | The four one-round masked sets: round end, first- and second-order *t*-tests over the round with 8,192 and with the first 4,096 traces per group, the replication between the two acquisitions, the attacker-model CPA of the Round-1 stage of Algorithm 1 at both orders with the decision on *D*, the success rate against the number of traces of the CPAs that rank the correct candidate first, the effect size and the rail fraction. Writes `results/_masked_ttest.npz`, the *t* curves that `fig_tvla.py` draws. |
| `full_encryption.py` | The two full-encryption masked sets: *t*-tests over all 46,000 samples, round period and rounds covered, exceeding samples per round and, for the table-recomputation set, their position relative to the table builds next to the positions found in the one-round sets. |
| `fig_tvla.py` | Fig. 14 from the cached *t* curves (recomputed from the traces if the cache is absent). |
| `fig_hw_boxplot.py` | Fig. 1 from `data/hwchar/`, with the metadata checks and the statistics quoted in Section 2.1. |

Every script that reads a masked set processes the float16 array in column chunks and never
converts a whole set to float64; `masked_eval.py` needs about 3 GB of memory for the largest
set.

### data/

Not tracked here; download it from the Zenodo record named at the top. Once unpacked:

| File | Traces x samples | Size | md5 | Contents | Used by |
|---|---|---:|---|---|---|
| `shadow32_fixedkey/s32_ref_12500.npz` | 2048 x 12500 | 23.9 MB | `233c7ae999db67be4da150782542dd4a` | Shadow-32, round keys `0D 3B 60 33 / 43 60 25 3C / 13 25 89 C5 / 3C 89 0D 5D`, phase `seekclip` (unchanged since the first version) | Sections 4.1 to 4.5, Figs. 5 to 10, Table 1 (`cpa_shadow32_12500.py`, `fig_fixedkey_cpa.py`); `trace_stats.py`; `phase_compare.py`; `cpa_s64_analysis.py` (sign of alpha) |
| `shadow32_fixedkey/s32_shadow32_O0_fixedphase_12500.npz` | 2048 x 12500 | 23.9 MB | `9f2c9eb720796b4c1738f91069a15bc6` | the same key and plaintexts at the power-on phase (`fixed (no phase selection)`) | supplementary, not reported in the paper; `phase_compare.py` |
| `shadow32_fixedkey/s32_shadow32_O0_noclipphase_12500.npz` | 2048 x 12500 | 21.1 MB | `87f279a7f9096218354711d359a1383e` | the same key and plaintexts at a phase without clipping (`noclip (\|trace\|<=0.47) @try1`) | Section 4.1; `phase_compare.py` |
| `shadow32_10keys/s32_key01_12500.npz` | 2048 x 12500 | 24.0 MB | `13600dbfd248ed9bfa7876b81d1e84b9` | ten random master keys, one per file (unchanged since the first version) | Section 4.6, Figs. 11 to 13 (`cpa_shadow32_12500.py`, `success_rate.py`; Fig. 11 is drawn from this first set) |
| `shadow32_10keys/s32_key02_12500.npz` | 2048 x 12500 | 24.0 MB | `342b19c4363fe35b7b9866b63296d8b1` | | |
| `shadow32_10keys/s32_key03_12500.npz` | 2048 x 12500 | 24.0 MB | `4692e5108a699a46b08bb1096352c920` | | |
| `shadow32_10keys/s32_key04_12500.npz` | 2048 x 12500 | 24.0 MB | `8da60b9bb03c731ab7b94d02a703708c` | | |
| `shadow32_10keys/s32_key05_12500.npz` | 2048 x 12500 | 24.0 MB | `b3104fa5b7e8c62d2f034e17fa56ab23` | | |
| `shadow32_10keys/s32_key06_12500.npz` | 2048 x 12500 | 24.0 MB | `962d22f966ee9861a0e6d7b6b2d6bf9e` | | |
| `shadow32_10keys/s32_key07_12500.npz` | 2048 x 12500 | 23.9 MB | `fd0a35bd17390f2eb5ceb0f7785b4196` | | |
| `shadow32_10keys/s32_key08_12500.npz` | 2048 x 12500 | 24.0 MB | `449f486c6bf284d2d5aba46d1a3bd749` | | |
| `shadow32_10keys/s32_key09_12500.npz` | 2048 x 12500 | 24.0 MB | `f4e85e7be04ec32f7fedb989853de28c` | | |
| `shadow32_10keys/s32_key10_12500.npz` | 2048 x 12500 | 23.9 MB | `87555f7db93c9367105199f9e9bc17eb` | | |
| `shadow64/s64_ref_25000.npz` | 4096 x 25000 | 96.8 MB | `9ad4b5b6f7cb90982f05ee95a216ae9b` | master key `07E9A4B27E3FCB472DA757EA31CAF4ED`, first round key `872C E3FB 644A 72D7` (unchanged) | Section 5 |
| `masked/masking_ISW_v2_seed1_16384x10000.npz` | 16384 x 10000 | 138.3 MB | `727545a3f62494e306bcc868881b4608` | ISW implementation, one round, 8192 fixed + 8192 random, seed 1 | Section 4.7, Fig. 14(a), Table 2 |
| `masked/masking_ISW_v2_seed2_16384x10000.npz` | 16384 x 10000 | 138.4 MB | `b88b1ddd19e95e6c6452a2e09e9df554` | the same, independent acquisition | Section 4.7 |
| `masked/masking_ISWLUT_v2_seed1_16384x46000.npz` | 16384 x 46000 | 639.9 MB | `408842dbb23016adac190d7e875dce49` | table-recomputation implementation, one round, seed 1 | Section 4.7, Fig. 14(b), Table 2 |
| `masked/masking_ISWLUT_v2_seed2_16384x46000.npz` | 16384 x 46000 | 641.5 MB | `56372dbb0aa9b9a3ca507e73ce17269a` | the same, independent acquisition | Section 4.7 |
| `masked/masking_ISW_v2_full_seed1_16384x46000.npz` | 16384 x 46000 | 761.5 MB | `e7a4380863563f6176c84d507d005d43` | ISW implementation, 16-round encryption, first 46,000 cycles | Section 4.7 |
| `masked/masking_ISWLUT_v2_full_seed1_16384x46000.npz` | 16384 x 46000 | 640.6 MB | `38150dfd12bb23a43c32a28f0db84d38` | table-recomputation implementation, 16-round encryption, first 46,000 cycles | Section 4.7 |
| `hwchar/fig1_lock_tbl1_1000.npz` | 9000 x 600 | 4.5 MB | `34209c61e1052aafd6b77efb86d6134f` | Fig. 1: 1,000 traces per Hamming weight of the loaded byte | Section 2.1, Fig. 1 |
| `hwchar/phase_template.npz` | 2 x 400 | 7 kB | `35460ecdf3ab484f952ac43917858ee6` | probe template of the clock phase the Fig. 1 acquisition locked to: `probe` (2 x 400, the mean probe traces of the values 0x00 and 0xFF), `phase` (the `seekclip` criterion of the session that stored it) and `made` | `capture_fig1_tbl.py` |

Fields of the Shadow-32 and Shadow-64 files:

- `traces`, float16 power samples
- `pt`, plaintexts, four bytes for Shadow-32 and eight for Shadow-64
- `rk`, the full round key schedule, `uint8` for Shadow-32 and `uint16` for Shadow-64
- `master`, the master key, empty for the fixed-key set whose round keys are baked in and
  absent from the two further fixed-key sets
- `clkout`, `adc_freq`, `samples`, `phase`, `cipher`, acquisition metadata; the two
  further fixed-key sets carry `version` and `firmware` instead of `master`

Fields of the masked files:

- `traces`, `pt`, as above; in the one-round sets `pt` has 20 bytes per trace, bytes 0 to 3
  the plaintext, 4 to 7 the fresh random byte of each of the four AND gadgets (the ISW
  randomness in the ISW sets, the output mask of the recomputed table in the
  table-recomputation sets), 8 to 11 the input masks, 12 to 15 the key masks and 16 to 19
  the refresh bytes, which in the table-recomputation sets also serve as the overwriting
  values; in the full-encryption sets it has 200 bytes, the plaintext, the four input masks
  and 12 bytes per round (gadget randomness, refresh bytes, key masks). Only the plaintext is
  fixed in the fixed group.
- `group`, 0 for the fixed group and 1 for the random group, in acquisition order (the two
  groups are interleaved at random)
- `key`, the Round-1 key, and `rk`, the full schedule
- `clkout`, `adc_freq`, `samples`, `version`, `phase`, `fixed_pt` (the plaintext of the
  fixed group, `11 22 33 44`), `seed`, `firmware`, acquisition metadata

Fields of the Fig. 1 file:

- `traces`, float16, 600 samples per trace
- `value`, the byte loaded into the register; `hw`, its Hamming weight; `index`, the table
  index (equal to `value` for the identity table); `rand`, four random bytes sent with every
  command and unused by method 1
- `op`, `phase`, `clkout`, `adc_freq`, `samples`, `per_hw`, `per_value` (-1: the traces
  were counted per Hamming weight, not per value), `firmware`, `nop_encoding`, acquisition
  metadata

## Reported results

Shadow-32, fixed key. All sixteen round-key bytes of Rounds 1 to 4 are recovered,
`0D 3B 60 33 / 43 60 25 3C / 13 25 89 C5 / 3C 89 0D 5D`, by the thirteen CPAs of Algorithm 1:
five 7-bit CPAs over 128 representatives in Round 1, one of which, on `h2*`, is rejected by
the sign decision and returns no value, and eight 4-bit CPAs of 16 candidates, four in Round 2
and two each in Rounds 3 and 4. That is 5 x 128 + 8 x 16 = 768 candidate evaluations, the cost
reported in the paper. Eleven subkey bytes are measured wholly or in part by these CPAs and the
other five (`RK2_1`, `RK3_0`, `RK3_1`, `RK4_0`, `RK4_1`) follow from the key schedule. The
script also runs a 7-bit CPA on `RK2_1`, a byte the key schedule already fixes, as a
cross-check of that relation; it is reported but not counted. The correct candidate ranks first
in every CPA. Its correlation is 0.546 in the lower-nibble CPA of `RK2_2`, whose upper nibble
is not modeled, and between 0.786 and 0.904 in the other eleven CPAs that return a value.
`results/RESULTS_shadow32_12500.md` lists the target, the candidates, the recovered value, the
rank of the correct candidate, the peak correlation and the peak sample of each.

`fig_fixedkey_cpa.py` draws, in addition to these CPAs, the figures of Section 4.2 that exhibit
the complementary duals, the candidates 128 to 255 of `h0` and the CPA on `h3*`; those are not
part of the attack and are not counted.

Shadow-32, ten keys. All ten sets are recovered in full; the correct candidate ranks first in
all 120 value-returning CPAs, with correlations between 0.553 and 0.585 for the lower-nibble
CPA of `RK2_2` and between 0.777 and 0.912 for the other eleven. Each Round-1 subkey reaches a
success rate of 1.0 at 96 traces, and all sixteen round-key bytes, that is the joint event
that all thirteen CPAs of Algorithm 1 succeed on the same subset of traces, at 192; the
guessing entropy of the Round-1 subkeys is below 1.1 at 40 traces and equal to one at 96, and
the sign decision is correct on every attack from 64 traces (`results/RESULTS_success_rate.md`).
The true master key lies in the NX-equivalence class obtained by inverting the key schedule in
every set. The class is not a singleton because the NX module is not injective, its size
ranges from 24 to 81 here, but every member of it produces the same round keys: the script
expands each member with the key schedule and checks that all give the 64 round-key bytes
stored with the traces. For the fixed-key set the class has 81 members, among them
`DC4A3DB3035C950E`, the member named in Section 4.4 of the paper. The script also prints the
wall-clock time of the thirteen CPAs and of locating the rounds from the mean trace on the
fixed-key set (about half a second and under a second on a desktop processor; the times are
machine dependent and are not recorded in the results file).

Shadow-32, clock phase. On the fixed-key set at the selected phase the Round-1 attack, scored
on one set with the evaluation of Section 4.6 (disjoint subsets, at most 20 per point), reaches
a joint success rate of 1.0 from 64 traces; at the power-on phase, which happened to clip as
well, from 48; at the phase without clipping from 384. The correct candidates of the four
Round-1 CPAs peak at |rho| 0.80 to 0.90 at the two clipping phases and 0.48 to 0.63 at the
phase without clipping. All sixteen round-key bytes are recovered at 2,048 traces at every
phase (`results/RESULTS_phase_compare.md`, which also records, as a supplementary statistic
with its definition, the signal-to-noise ratio of the `h0` leakage at each phase). The paper
(Section 4.1) reports the selected phase and the phase without clipping; the power-on phase
is supplementary and is not reported there.

Shadow-64. All four words of the first round key are recovered by the two-stage method,
`872C E3FB 644A 72D7`. `results/RESULTS_shadow64.md` records the per-word correlations of both
stages, and for `RK1_0` the candidate `002C` with the correct lower byte and the upper byte
`00`, which reaches only |rho| = 0.62, rank 52 of 256, the comparison of Section 5.3. It also
keeps a comparison against a 16-bit exhaustive search over all 65536
candidates, which ranks the correct value of one word only eighth while the two-stage method
recovers it; that comparison is supplementary material and is not part of the paper.

Masked Shadow-32, cycles and code. Read from the traces at one sample per cycle, from the
trigger to the start of the idle loop that follows the round, the ISW round takes 3,880 cycles
and the table-recomputation round 44,176 (`masked_eval.py`); the unprotected round takes 748,
the round period of the 16-round capture from the autocorrelation of its mean trace
(`round_structure.py`, `P = 748` in `results/RESULTS_trace_stats.md`), since the unprotected
image runs the whole encryption and has no idle loop after the round. The four table builds
of the table-recomputation round are 256 entries at 41 cycles each, 41,984 cycles by
construction (the 41-periodic runs the script detects are 10,479 samples long, 17 cycles
shorter than 256 x 41, from the edge rule of the detector). Code size, from `arm-none-eabi-nm -S` on the object of a rebuild with
arm-none-eabi-gcc 15.2.1 (`listings/README.md` lists the functions summed), is 394 bytes
unprotected, 1,366 bytes for the ISW version and 1,050 bytes for the table-recomputation
version, which also reserves 512 bytes of RAM for its two tables. Table 2 of the paper gives
these three figures. The previous version of the paper quoted 1,312 bytes for the ISW version,
the size of the v1 source with the one-share key addition; the corrected key addition of v2
adds 54 bytes (`listings/README.md`). The four calls of the ISW round to the C library
`memcpy`, which write the round state back, are not counted.

Masked Shadow-32, attack. The CPA of Algorithm 1 is run on the random group of each one-round
set, 8,192 traces, with the leakage model and the round samples of the unprotected attack. On
the ISW implementation the 7-bit CPAs on `h0` and `h1` rank the correct candidate first in both
acquisitions, at |rho| 0.234 and 0.229 (seed 1) and 0.229 and 0.242 (seed 2) against a noise
level of 0.050, and the decision on *D* returns the correct sign, so `RK1_0` and `RK1_1` are
recovered; their success rate is 1.0 from 1,024 traces. The CPAs on `h2` and `h3` rank the
correct candidate 14th and 84th (seed 1) and 12th and 41st (seed 2), their best candidate being
the value before the key addition, so `RK1_2` and `RK1_3` come out wrong (`0D 3B 00 00`) and
the attack does not reach Round 2. On the table-recomputation implementation no first-order
CPA ranks the correct candidate first: the correct candidates peak at |rho| 0.041 to 0.050, at
the noise level, and rank between 13th and 113th; the second-order CPAs on seed 2 rank the
correct candidate of `h1` and of the diagnostic `h3` (built with the true `RK1_1`, the value of
the earlier stage, which the attacker does not have) first at 0.061, the expected maximum of
noise over 128 candidates and 44,176 samples being 0.062, with a success rate of 0 or 1 of 20
at every smaller trace count and no counterpart on seed 1. The chain returns four wrong bytes
on every run (`results/RESULTS_masked_eval.md`, section 8). No CPA uses the masks stored with
the traces; the diagnostic rows differ from the attack rows only in taking the true value of
the earlier stage.

Masked Shadow-32, leakage test. With 8,192 traces per group over the whole round, the ISW
implementation exceeds the 4.5 threshold of the first-order *t*-test at 64 samples with
max|t| = 22.17 and, in the independent acquisition, at 71 samples with 23.85; 52 samples
exceed in both with the same sign and the two *t* curves correlate at 0.65. At second order
(centered squared samples) it exceeds at 518 samples in both with max|t| = 21.13 and 21.81,
439 of them in common. The table-recomputation implementation exceeds at two samples per
acquisition, max|t| = 6.75 and 6.03; sample 10,772 (t = -6.75 and -5.96) exceeds in both, and
in the second acquisition sample 21,738 as well (-6.03), each 64 cycles after the end of the
first and the second table build as the detector reports it; `listings/README.md` ties these
samples to the lookup of `T[t1]` and the store of its result from the cycle count of the
compiled code and the position of the build loop on the mean trace, which is where the paper
places them. The other exceedance of the first acquisition is sample 3
(+4.63), three cycles after the trigger and before any masked operation; it is not replicated
in the second acquisition (+1.35 there). Its second-order test exceeds at three and four
samples (max|t| = 5.99 and 6.02): in seed 2 at 10,769, 10,771, 21,736 and 21,737, within
three cycles of its first-order positions, and in seed 1 at 10,771 and 10,772 plus one more
at 10,833, 61 cycles after 10,772, which is not a first-order position. On the first 4,096 traces per group, the trace
count of the previous version, the figures are 15.81 and 17.29 with 44 and 41 samples for the
ISW implementation and 5.20 and 4.66 with 2 and 2 samples, 10,772 among them in both, for the
table-recomputation implementation. On the full 16-round encryption (8,192 traces per group,
46,000 samples) the ISW implementation exceeds at 1,064 samples with max|t| = 37.47 across its
eleven complete rounds (round length 3,929 cycles; 6,925 samples and 35.49 at second order),
and the table-recomputation implementation at three samples with max|t| = 6.33, at 10,827,
21,790 and 21,793, the same positions relative to its table builds as in the one-round sets
(six samples, 6.28, at second order); its round takes 44,192 cycles in that build, so the
capture covers its first round only. The noise standard deviation of the random group over the
round is 2.70 ADC codes for the ISW sets and 3.41 for the table-recomputation sets, so the
smallest mean difference the test detects at 8,192 traces per group, 0.070 noise standard
deviations, is about one fifth and one quarter of an ADC code. All six masked sets were
acquired at the clipping phase (at the rail: 5.3% of the samples in the two ISW one-round
sets, 2.4% in the two table-recomputation one-round sets, 2.0% and 2.5% in the ISW and the
table-recomputation full-encryption sets, with one sample of every idle-loop iteration at the
rail in every trace); no sample at which a max|t| is reported
is at the rail in any trace (`results/RESULTS_masked_eval.md`, `results/RESULTS_full_encryption.md`).

Fig. 1. The leakage model was characterized on the same device by loading each byte value
from an identity table in RAM, 256-byte aligned so that the low byte of the address equals the
value, into a register previously cleared to zero, with `ldrb r0, [r1, r2]` in a fixed inline
assembly sequence padded with NOPs; the Hamming distance of the transition is the Hamming
weight of the value. 1,000 traces per Hamming weight 0 to 8 were acquired in random order, the
values of one weight almost equally often, at the clock phase of Section 4.1 (locked to a
stored probe template of the 98% full-scale phase). The power at the cycle of the load, sample
255 after the trigger, where rho(HW, power) is largest (+0.918), has medians 0.055, 0.059,
0.066, 0.070, 0.078, 0.086, 0.090, 0.098 and 0.106 for the nine weights, strictly increasing,
the per-weight means lie on a line of slope +0.0064 per unit with R^2 = 0.999, and no trace is
at the largest ADC value at that sample (`results/RESULTS_hwchar.md`). The sample shown is
the cycle of largest correlation; the sample before it, the current peak of the preceding
cycle, is at the rail in 3,130 of the 9,000 traces and is not used.

Trace statistics. In the fixed-key set 2.1% of all samples, and 2.0% of those within Rounds 1
to 4, sit at the positive rail of the ADC, and the other unprotected sets at the selected phase
lie between 2.0% and 2.2%; the negative rail is never reached, and none of the samples at
which the CPAs of Algorithm 1 peak is saturated in any trace (`analysis/trace_stats.py`).

## Changes in this version

The masked experiment of Section 4.7 was re-acquired with corrected firmware, the leakage model
of Fig. 1 was re-measured, and the fixed-key attack was repeated at two further clock phases;
the attack evaluation of the earlier sections was revised as listed further down.

- Both masked firmwares of the previous version added the masked key byte `RK xor q` to one
  share only and the mask `q` to neither, so that the shares recombined to `value xor RK xor q`
  and every encryption ran under a different key. `masking_ISW.c` (v2) adds `q` into the other
  share (`masked_xor_key`). `masking_ISWLUT.c` (v3) corrects the same line and, in addition,
  moves every operation on a masked value, the refresh, the table lookup, the rotation, the
  XOR with the other branch, the key addition and the copy of the round state, into inline
  assembly that overwrites the working registers and the store bus between the two share
  accesses; in the previous version the XOR and the rotation were plain C and the compiled
  code passed both shares through one register. `capture/shadow32_ref.py` simulates both
  firmwares at the share level and shows the defect and the correction; the known-answer
  tests of the one-round and the 16-round builds passed before every acquisition.
- The masked sets were re-acquired with 8,192 traces per group over the whole masked round,
  10,000 samples for the ISW implementation and 46,000 for the table-recomputation one, whose
  round the previous 10,000-sample capture did not contain (it ended inside the first table
  build), and the acquisition was repeated independently (seed 2). Two further sets record the
  first 46,000 cycles of the full 16-round encryption of each implementation. The previous
  masked sets `masking_ISW_traces.npz` and `masking_ISWLUT_traces.npz` are superseded and are
  no longer analyzed here; the first version of the Zenodo record keeps them.
- `masked_eval.py` and `full_encryption.py` replace `analyze_wide.py` and `cpa_offline.py`,
  which read the superseded sets and loaded whole arrays as float64. The new scripts process the
  traces in column chunks, report the round end from the idle loop that follows the round and
  the table builds, the first- and second-order tests over the round and on the first 4,096
  traces per group, the replication between the two acquisitions, the attacker-model CPA of
  Algorithm 1 at both orders with its success rate against the number of traces, the effect
  size and the rail fraction (`results/RESULTS_masked_eval.md`,
  `results/RESULTS_full_encryption.md`). `fig_tvla.py` draws Fig. 14 from the cached curves.
  The ISW result of the previous version (18 samples over the threshold, max|t| = 13.46)
  stands in substance and is replaced by the numbers above; the previous table-recomputation
  result (no sample over the threshold at 4,096 traces per group within 10,000 samples) is
  superseded: the whole round now shows two first-order exceedances per acquisition, one of
  them at the first table lookup in both, and the CPA still recovers no subkey.
- The fixed-key experiment was repeated at the clock phase found at power-on, without the
  selection of Section 4.1, and at a phase at which no sample reaches the largest ADC value,
  with the same image and the same plaintexts; `phase_compare.py` compares the three
  (`results/RESULTS_phase_compare.md`). `capture_lab.py` and `shadow32_ref.py` are the scripts
  of these acquisitions.
- Fig. 1 was re-acquired with a firmware that fixes the measured instruction in inline assembly
  (`firmware/hwchar/`, `capture/capture_fig1_tbl.py`), and `fig_hw_boxplot.py` draws it and
  prints the statistics quoted in Section 2.1 (`results/RESULTS_hwchar.md`).
- `trace_stats.py` now covers the unprotected sets only, including the two sets at the other
  phases; the statistics of the masked sets moved to `masked_eval.py` and `full_encryption.py`.
  `results/SUMMARY_masking.md`, `results/masking_ISW_result.txt` and
  `results/masking_ISWLUT_result.txt`, which described the superseded sets, are removed.
- The listings in `listings/` are rebuilt from the v2 and v3 sources; the six rebuilt masked
  images (the one-round, `KAT` and `FULL` builds of both firmwares) are byte-identical to the
  images the masked traces and their known-answer tests were acquired with. The code sizes are
  measured from these builds (394 / 1,366 / 1,050 bytes; `listings/README.md` lists the
  functions summed and the size of the v1 source).
- The comments and docstrings of the firmware sources and the capture scripts, which were in
  Korean, are now in English; the code is unchanged, and the images rebuilt from the
  translated sources are byte-identical to those built from the acquisition copies.
  `capture_lab.py` writes its console log to `capture/logs/`, as `capture_fig1_tbl.py` does,
  instead of into `data/`.

Changes to the attack evaluation of Sections 4.1 to 4.6 and 5, made in the same revision: the
Round-2 attack now uses the four 4-bit CPAs the paper describes, the success-rate evaluation
follows Algorithm 1, and every CPA chooses where to look in the trace without the key.

- The previous version attacked the four Round-2 subkeys with 8-bit CPAs of 256 candidates
  (`key8` in `cpa_shadow32_12500.py`, 128 candidates in `fig_fixedkey_cpa.py`), although the
  cost of 768 candidate evaluations stated in the paper counts four 4-bit CPAs in Round 2.
  `recover_fullkey` now takes `RK2_1` from `RK1_2` and the lower nibble of `RK2_0` and the
  upper nibble of `RK2_3` from `RK1_3`, as the key schedule dictates, and runs the four 4-bit
  CPAs: the upper nibble of `RK2_0`; the lower nibble of `RK2_2` with the hypothesis restricted
  to the Hamming weight of the lower nibble, so that the unmodeled upper nibble acts as noise;
  then the upper nibble of `RK2_2` with the lower nibble fixed; and the lower nibble of `RK2_3`.
  The recovered keys are unchanged on all eleven sets. The 7-bit CPA on `RK2_1` is kept as a
  labeled cross-check that does not enter the count. `fig_fixedkey_cpa.py` draws Fig. 9 from
  these four CPAs (`shadow-cpa-r2-k0-hi`, `-r2-k2-lo`, `-r2-k2-hi`, `-r2-k3-lo`) instead of
  four 128-candidate CPAs, and the summary figure of the ten key sets shows the twelve
  value-returning CPAs per key instead of eleven 8-bit subkeys.
- `success_rate.py` evaluates the thirteen CPAs of Algorithm 1, each in its own candidate set
  (the 128 representatives with the sign of alpha in Round 1, 16 candidates for the nibble
  CPAs) and with the true values of the earlier stages, together with the sign decision on the
  same subset of traces. The previous version ranked all sixteen bytes against 256 candidates
  each, including the five bytes that the key schedule supplies and Algorithm 1 never attacks.
  The trace count at which all sixteen bytes reach a success rate of 1.0 moves from 512 to
  192 for that reason: every failure of the previous evaluation between 128 and 256 traces was in
  the 256-candidate byte CPA on `RK2_3`, which Algorithm 1 ranks among 16 candidates with its upper
  nibble fixed from the NX module, while the binding stage is now the lower-nibble CPA of `RK2_2`,
  at 0.955 at 96 traces and 1.0 from 192. The Round-1 numbers
  (success rate 1.0 at 96 traces, guessing entropy below 1.1 at 40 and equal to one at 96) and
  the sign decision (correct from 64 traces) are unchanged, under both point-of-interest rules.
- The equivalence class of the master key is now verified: every member is expanded with the
  key schedule (`shadow32_ks.py`, the function of the capture script) and must give the same
  64 round-key bytes as stored with the traces. This holds on all eleven sets.
- The previous version attacked a Round-r subkey of Shadow-32 over a prefix of the trace,
  `trace[:, :W_r]` with `W = 1100, 1850, 2750, 3500`. Those prefixes had been set from the
  measured leakage positions of the correct key on the fixed-key capture. They are replaced by
  the samples of Round r, `[b0 + (r-1)P, b0 + rP)`, with the period P and the boundary b0
  taken from each set's mean trace (`round_structure.py`). All recovered keys and every value
  quoted in the paper are unchanged; four of the 120 correct-key peaks of that version change
  in the third decimal.
- The success-rate figure used a point of interest located from the correct key over all
  traces. `success_rate.py` replaces `viz_10keys.py` and uses the round samples instead; the
  old rule is kept only as a labeled comparison, and both give the same trace counts.
- The correlation figures of the fixed-key set were drawn by the notebook
  `cwnano-shadow32-cpa.ipynb` over the same prefixes. `fig_fixedkey_cpa.py` replaces it.
- Shadow-64 used the prefix `[0, 1500)` and located the window of the exhaustive search from the
  correct key. Both now use the Round-1 samples; the recovered words, their correlations and
  the exhaustive-search ranks are unchanged.
- Shadow-64 fixed the sign of alpha to +1 after checking the correct-key correlations of known
  Shadow-32 keys. It now takes the sign from the decision on D of Section 4.3, run without the
  key on the Shadow-32 fixed-key traces of the same board; the result is again +1.
- The correlation now guards the hypothesis variance as well as the trace variance, so that a
  constant hypothesis column on a small subset gives 0 instead of propagating nan.

## Environment

The analysis code needs Python 3 with NumPy and Matplotlib only. Acquisition additionally
needs the ChipWhisperer package and the hardware. The traces are stored as float16. The
unprotected scripts convert a set to float64, so one Shadow-32 trace set occupies about 200 MB
of memory and the Shadow-64 set about 800 MB; allow roughly twice that for the hypothesis
matrices built during the correlation. The masked scripts keep the float16 array (up to 1.5 GB
for a 16,384 x 46,000 set) and convert column chunks only, so they need about 3 GB at most.

## License and attributions

This repository is MIT licensed; see `LICENSE`. Three things about it are worth stating
explicitly.

**`firmware/masking_ISW.c` and `firmware/masking_ISWLUT.c`** were started from a ChipWhisperer
example target and still carry its original header, which is left in place:

> This file is part of the ChipWhisperer Example Targets
> Copyright (C) 2012-2017 NewAE Technology Inc.
> Licensed under the GNU General Public License, version 3 or (at your option) any later
> version.

That header governs whatever remains of the original scaffold. The rest of these files is our
own work under the MIT terms: the Shadow-32 cipher, the masked tables, the inline assembly
sequences of `masking_ISWLUT.c` and the register-overwriting routines were written for this
paper, and the ISW gadget and the mask-refreshing routine of `masking_ISW.c` are our two-share
specialization of the construction of Ishai, Sahai and Wagner, written following the structure
of the PIPO reference code; see the comments in `masking_ISW.c` for the specific
correspondences. PIPO is described in H. Kim et al., *PIPO: A Lightweight Block Cipher with
Efficient Higher-Order Masking Software Implementations*, ICISC 2020.

`firmware/shadow32_nop.c`, `firmware/shadow64_nop_newkey.c` and `firmware/hwchar/hwchar_tbl.c`
were written for this work rather than adapted from an example. They call the SimpleSerial and
HAL entry points, which is how any target firmware talks to the platform, but contain no
ChipWhisperer code and carry no NewAE header.

**`firmware/makefile` and `firmware/hwchar/makefile`**: the lower half, the `EXTRA_OPTS` and
`CRYPTO_TARGET` handling and the two `include` lines, is the ChipWhisperer target-makefile
template with `TARGET`, `SRC` and `OPT` filled in for this work. It is a project fragment that
only means anything inside the ChipWhisperer firmware tree, and the same terms apply to it as
to the template it came from.

**ChipWhisperer** is a product of NewAE Technology Inc. and is GPL-3.0-or-later:
https://github.com/newaetech/chipwhisperer. All firmware here builds inside its firmware tree
and uses its SimpleSerial protocol and HAL. Those headers, sources and build files are **not**
redistributed here; obtain them from the ChipWhisperer project under its own license. No
compiled firmware image is included either; the images used for the acquisition were linked
against ChipWhisperer's GPL sources, so rebuilding them from the sources here reproduces that
situation on your own machine and under those terms. The four full listings
`listings/*.lss` are disassemblies of linked images and therefore also contain the machine
code of the ChipWhisperer SimpleSerial and HAL objects (GPL-3.0-or-later, with the source
available upstream); no ChipWhisperer source text is interleaved in them. The per-function
listings `listings/*_dis_*.txt` cover our own functions only.

`figures/` and `results/` are computed from the traces, which are CC BY 4.0 on Zenodo. The MIT
grant covers them, but if you reuse them please also credit the trace deposit.
