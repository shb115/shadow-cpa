# Fig. 1: measured power against the Hamming weight of the register value (Section 2.1)

Traces: `data/hwchar/fig1_lock_tbl1_1000.npz`, 9000 x 600, firmware `firmware/hwchar/hwchar_tbl.c` (identity table in RAM, `ldrb r0,[r1,r2]` into r0 cleared to zero), phase `lock (probe RMS 0.0024 <= 0.0090 vs template) @try26`.

- metadata: hw = HW(value) True, index = value True, traces per Hamming weight [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000]
- traces per value within a weight (min, max): HW 0: 1 values, 1000 to 1000, HW 1: 8 values, 125 to 125, HW 2: 28 values, 35 to 36, HW 3: 56 values, 17 to 18, HW 4: 70 values, 14 to 15, HW 5: 56 values, 17 to 18, HW 6: 28 values, 35 to 36, HW 7: 8 values, 125 to 125, HW 8: 1 values, 1000 to 1000
- rho(HW, power) is largest at sample 255, rho = +0.9176 (the measured load); the other events: ldrb r2 at 152 (+0.788), clearing of r0 at 358 (+0.837)
- samples with |rho| > 0.5: 152 (+0.788), 253 (+0.716), 254 (+0.882), 255 (+0.918), 356 (+0.542), 357 (+0.575), 358 (+0.837), 382 (+0.657)

## Sample 255

| HW | traces | median | mean | sd | whisker low | Q1 | Q3 | whisker high | hidden fliers |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1000 | 0.0547 | 0.0525 | 0.0066 | 0.0391 | 0.0469 | 0.0547 | 0.0664 | 18 |
| 1 | 1000 | 0.0586 | 0.0592 | 0.0070 | 0.0430 | 0.0547 | 0.0625 | 0.0742 | 11 |
| 2 | 1000 | 0.0664 | 0.0659 | 0.0073 | 0.0430 | 0.0586 | 0.0703 | 0.0859 | 1 |
| 3 | 1000 | 0.0703 | 0.0725 | 0.0080 | 0.0508 | 0.0664 | 0.0781 | 0.0898 | 3 |
| 4 | 1000 | 0.0781 | 0.0791 | 0.0079 | 0.0586 | 0.0742 | 0.0859 | 0.1016 | 0 |
| 5 | 1000 | 0.0859 | 0.0858 | 0.0078 | 0.0703 | 0.0820 | 0.0898 | 0.1016 | 18 |
| 6 | 1000 | 0.0898 | 0.0917 | 0.0071 | 0.0781 | 0.0898 | 0.0977 | 0.1094 | 15 |
| 7 | 1000 | 0.0977 | 0.0981 | 0.0067 | 0.0820 | 0.0938 | 0.1016 | 0.1133 | 12 |
| 8 | 1000 | 0.1055 | 0.1032 | 0.0060 | 0.0859 | 0.0977 | 0.1055 | 0.1172 | 2 |

- medians strictly increasing with the Hamming weight: True; means: True
- line through the per-weight means: slope +0.00641 per unit of Hamming weight, R^2 = 0.9990
- over all 9000 traces: rho = +0.9176, R^2 = 0.842; the sign of the slope is positive, so alpha is positive on this device
- traces at the largest ADC value (0.4961) at sample 255: 0 (largest value there 0.1250)
- samples at the largest ADC value in every trace: [3, 41, 412, 469, 477, 498, 522, 526, 532, 583]; in some traces: 0 (609), 254 (3130), 529 (212), 589 (1381)
- box plot: 1.5 IQR whiskers, fliers hidden; figures/hw_boxplot.pdf

