# Trace statistics of the unprotected sets

ADC rail: |v| >= 0.4959 (the threshold used by capture_exp.save(); the largest code is 0.4961).

```
fixedkey   2048 x 12500  phase seekclip                         P = 748, b0 = 358, Rounds 1-4 = [358, 3350);  at the positive rail: 2.06% of all samples, 2.04% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2227, max 0.4961)
key01      2048 x 12500  phase seekclip                         P = 748, b0 = 358, Rounds 1-4 = [358, 3350);  at the positive rail: 2.07% of all samples, 2.04% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2266, max 0.4961)
key02      2048 x 12500  phase seekclip                         P = 748, b0 = 406, Rounds 1-4 = [406, 3398);  at the positive rail: 2.02% of all samples, 1.99% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2227, max 0.4961)
key03      2048 x 12500  phase seekclip                         P = 748, b0 = 406, Rounds 1-4 = [406, 3398);  at the positive rail: 2.10% of all samples, 2.06% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2227, max 0.4961)
key04      2048 x 12500  phase seekclip                         P = 748, b0 = 406, Rounds 1-4 = [406, 3398);  at the positive rail: 2.03% of all samples, 1.99% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2266, max 0.4961)
key05      2048 x 12500  phase seekclip                         P = 748, b0 = 406, Rounds 1-4 = [406, 3398);  at the positive rail: 2.01% of all samples, 1.98% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2266, max 0.4961)
key06      2048 x 12500  phase seekclip                         P = 748, b0 = 358, Rounds 1-4 = [358, 3350);  at the positive rail: 2.13% of all samples, 2.11% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2227, max 0.4961)
key07      2048 x 12500  phase seekclip                         P = 748, b0 = 358, Rounds 1-4 = [358, 3350);  at the positive rail: 1.98% of all samples, 1.94% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2227, max 0.4961)
key08      2048 x 12500  phase seekclip                         P = 748, b0 = 358, Rounds 1-4 = [358, 3350);  at the positive rail: 2.09% of all samples, 2.06% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2266, max 0.4961)
key09      2048 x 12500  phase seekclip                         P = 748, b0 = 358, Rounds 1-4 = [358, 3350);  at the positive rail: 2.04% of all samples, 2.00% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2266, max 0.4961)
key10      2048 x 12500  phase seekclip                         P = 748, b0 = 406, Rounds 1-4 = [406, 3398);  at the positive rail: 2.00% of all samples, 1.97% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2266, max 0.4961)
shadow64   4096 x 25000  phase seekclip                         P = 741, b0 = 354, Rounds 1-4 = [354, 3318);  at the positive rail: 2.16% of all samples, 2.25% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2109, max 0.4961)
fixedphase 2048 x 12500  phase fixed (no phase selection)       P = 748, b0 = 358, Rounds 1-4 = [358, 3350);  at the positive rail: 2.01% of all samples, 1.97% within Rounds 1-4, 100.0% of the traces have at least one;  negative rail: never reached  (min -0.2305, max 0.4961)
noclip     2048 x 12500  phase noclip (|trace|<=0.47) @try1     P = 748, b0 = 361, Rounds 1-4 = [361, 3353);  at the positive rail: 0.00% of all samples, 0.00% within Rounds 1-4, 0.0% of the traces have at least one;  negative rail: never reached  (min -0.2461, max 0.2773)
```

The two sets at the other clock phases (`fixedphase`: the phase at power-on, not selected; `noclip`: a phase at which no sample reaches the largest value) are analyzed in results/RESULTS_phase_compare.md.

Fixed-key set, samples at which the CPAs of Algorithm 1 peak (results/_peaks_12500.json):

| CPA | peak sample | traces at the rail there |
|---|---:|---:|
| R1k0 | 548 | 0 |
| R1k1 | 709 | 0 |
| R1k2 | 636 | 0 |
| R1k2s | 594 | 0 |
| R1k3 | 796 | 0 |
| R2k0hi | 1296 | 0 |
| R2k2lo | 1383 | 0 |
| R2k2hi | 1384 | 0 |
| R2k3lo | 1544 | 0 |
| R2k1chk | 1457 | 0 |
| R3k2lo | 2132 | 0 |
| R3k3lo | 2292 | 0 |
| R4k2lo | 2879 | 0 |
| R4k3lo | 3040 | 0 |

- None of the 14 peak samples is saturated in any trace.

