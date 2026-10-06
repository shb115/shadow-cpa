# Masked Shadow-32, full 16-round encryption: fixed-versus-random t-test (Section 4.7)

Traces: `data/masked/masking_*_v2_full_seed1_16384x46000.npz`, the first 46,000 cycles of a 16-round masked encryption, 8,192 fixed-plaintext and 8,192 random-plaintext traces per set. Welch t = mean(fixed) - mean(random), threshold |t| > 4.5; second order on the centered squared samples; 1 sample = 1 cycle.

## 1. Rounds covered

| Set | Traces x samples | Round period (cycles) | Autocorrelation | Rounds in 46,000 samples | Complete rounds | Table builds [start, end) |
|---|---|---:|---:|---:|---:|---|
| ISW_full | 16384 x 46000 | 3929 | 0.913 | 11.71 | 11 | - |
| ISWLUT_full | 16384 x 46000 | 44192 | 0.039 | 1.04 | 1 | [284, 10763), [11250, 21729), [22217, 32696), [33186, 43665) |

## 2. t-test over all 46,000 samples, 8,192 traces per group

| Set | Order | max\|t\| | at sample (sign) | Samples over 4.5 | First, last | Per round | Positions (t) |
|---|---|---:|---|---:|---|---|---|
| ISW_full | 1 | 37.47 | 42080 (-) | 1064 | 290, 45985 | 78 98 89 84 97 88 108 97 78 96 90 61 | - |
| ISW_full | 2 | 35.49 | 27888 (-) | 6925 | 238, 45997 | 594 581 600 604 620 607 651 634 535 571 573 355 | - |
| ISWLUT_full | 1 | 6.33 | 10827 (-) | 3 | 10827, 21793 | 3 0 | 10827 (-6.33), 21790 (-4.93), 21793 (-5.83) |
| ISWLUT_full | 2 | 6.28 | 10827 (+) | 6 | 10826, 21792 | 6 0 | 10826 (+5.30), 10827 (+6.28), 10888 (-5.19), 10889 (-4.51), 10891 (-4.82), 21792 (+4.55) |

## 3. Position of the exceeding samples of the table-recomputation implementation

Builds completed before the sample and its distance from the end of the last of them (cycles); the one-round columns give the same for the exceeding samples of the one-round acquisitions.

| Capture | Order | Sample | t | Builds completed | Cycles after the end of the last build |
|---|---|---:|---:|---:|---:|
| full encryption | 1 | 10827 | -6.33 | 1 | 64 |
| full encryption | 1 | 21790 | -4.93 | 2 | 61 |
| full encryption | 1 | 21793 | -5.83 | 2 | 64 |
| full encryption | 2 | 10826 | +5.30 | 1 | 63 |
| full encryption | 2 | 10827 | +6.28 | 1 | 64 |
| full encryption | 2 | 10888 | -5.19 | 1 | 125 |
| full encryption | 2 | 10889 | -4.51 | 1 | 126 |
| full encryption | 2 | 10891 | -4.82 | 1 | 128 |
| full encryption | 2 | 21792 | +4.55 | 2 | 63 |
| ISWLUT_seed1 (one round) | 1 | 3 | | 0 | None |
| ISWLUT_seed1 (one round) | 1 | 10772 | | 1 | 64 |
| ISWLUT_seed1 (one round) | 2 | 10771 | | 1 | 63 |
| ISWLUT_seed1 (one round) | 2 | 10772 | | 1 | 64 |
| ISWLUT_seed1 (one round) | 2 | 10833 | | 1 | 125 |
| ISWLUT_seed2 (one round) | 1 | 10772 | | 1 | 64 |
| ISWLUT_seed2 (one round) | 1 | 21738 | | 2 | 64 |
| ISWLUT_seed2 (one round) | 2 | 10769 | | 1 | 61 |
| ISWLUT_seed2 (one round) | 2 | 10771 | | 1 | 63 |
| ISWLUT_seed2 (one round) | 2 | 21736 | | 2 | 62 |
| ISWLUT_seed2 (one round) | 2 | 21737 | | 2 | 63 |

## 4. Noise and samples at the ADC rail

| Set | Noise sd of the random group (ADC units, codes) | Detectable difference at n = 8,192 (sd, codes) | Fraction of samples at the rail | Samples at the rail in every trace |
|---|---|---|---:|---:|
| ISW_full | 0.01056, 2.70 | 0.0703 sd, 0.19 codes | 0.0205 | 395 |
| ISWLUT_full | 0.01340, 3.43 | 0.0703 sd, 0.24 codes | 0.0253 | 418 |
