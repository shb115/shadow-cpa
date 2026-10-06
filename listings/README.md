# Disassembly listings of the capture firmwares

Rebuilt from the sources in `firmware/` with the `makefile` there (`PLATFORM=CWNANO`,
`CRYPTO_TARGET=TINYAES128C`, `OPT=0`) in the ChipWhisperer 6.0.0 firmware tree (git
`3c8e4347`) with arm-none-eabi-gcc 15.2.1. The rebuilt images of the two masked firmwares are
byte for byte the images with which the masked traces of this version were acquired
(`masking_ISW_v2-CWNANO.hex`, `masking_ISWLUT_v2-CWNANO.hex`, the `firmware` field of the
one-round trace files), and so are the `KAT` and `FULL` builds (`EXTRA_OPTS=SHADOW32_KAT`,
`SHADOW32_FULL`) with which the known-answer tests and the full-encryption traces were made.
The unprotected traces were acquired with an image built by arm-none-eabi-gcc
10.2.1 in the ChipWhisperer 5.6.1 tree; the rebuilt `shadow32_round` and `ROL8` of
`shadow32_nop` are byte-identical to that image. The Fig. 1 firmware was built with its own
`makefile` (`CRYPTO_TARGET=NONE`); the measurement image was compiled by arm-none-eabi-gcc
14.2.1 and the rebuild with 15.2.1 has the same instruction stream in the three event
functions (`ev_table`, the measured sequence, `ev_fixed`, `ev_table_pre`) and in `main`; the
command handler `get_pt` differs (the stack slot of `mode`, one `str` more in the layout of the
table-selection branch, and the pc-relative offset of one literal load), but the four
instructions between `bl trigger_high` and the call of the event function (`ldr`, `ldr`, `movs`,
`movs`) have the same mnemonics and the same timing, one of them with a different stack-slot
offset, so the measured window is unchanged; the HAL code differs.

For the three Shadow-32 firmwares `<target>_O0_<target>_O0-CWNANO.lss` is the full
`objdump -h -S -z` listing of the linked image (written by the default target of the
ChipWhisperer makefile together with the `.hex`) and `<target>_O0_dis_<function>.txt` the
disassembly of one function (`objdump -d -S --disassemble=<function>`); no source text is
interleaved, so the listings are unaffected by the comments of the sources. These three were
built with the target names `shadow32_nop_O0`, `masking_ISW_O0` and `masking_ISWLUT_O0`, which
only change the file names of the image: the hex built as `masking_ISW_O0` is byte-identical to
the one built as `masking_ISW_v2`, and the same holds for `masking_ISWLUT`. The Fig. 1 image was
built with its own `makefile` in `firmware/hwchar/` as target `simpleserial-hwchar-tbl`; its
listings are `hwchar_tbl_O0_simpleserial-hwchar-tbl-CWNANO.lss` and
`hwchar_tbl_O0_dis_<function>.txt`, where the prefix `hwchar_tbl_O0` is added for the file name
only. The full listings include the disassembly of the linked ChipWhisperer SimpleSerial and HAL
objects (see the license section of the main README); the per-function listings cover our own
functions only. The deposited sources differ from the copies in the build folders of the
acquisition in their comments only (the comments were translated into English); comments do
not enter the compiled code, and the images rebuilt from the deposited sources are the ones
compared above.

| Firmware | Functions listed |
|---|---|
| `shadow32_nop` | `enc`, `shadow32_encrypt`, `shadow32_round`, `ROL8` |
| `masking_ISW` (v2) | `get_pt`, `shadow32_round_masked`, `ISW_AND`, `mask_refreshing`, `masked_ROL8`, `masked_xor`, `masked_xor_key`, `mask_byte`, `ROL8` |
| `masking_ISWLUT` (v3) | `get_pt`, `shadow32_round_masked`, `masked_F`, `tableG`, `masked_xor_w`, `masked_rol2_w`, `masked_xor_key`, `mask_refreshing`, `masked_copy_w`, `g_plain_init`, `mask_byte`, `ROL8` |
| `hwchar_tbl` (Fig. 1) | `get_pt`, `ev_table`, `ev_fixed`, `ev_table_pre` |

`ROL8` is the same 56-byte function in all three Shadow-32 firmwares; in the masked ones it is
called by the construction of the table of g (`g_plain_init`, table recomputation) and by
`masked_ROL8` (ISW). The source of `masking_ISWLUT.c` is revision v3 of the file; the build
target and the trace files keep the name `masking_ISWLUT_v2`.

In `masking_ISWLUT` every operation on a masked value is an inline assembly sequence, and the
listings show it verbatim: in `masked_xor_w`, `masked_rol2_w`, `masked_xor_key`,
`mask_refreshing`, `masked_copy_w` and the lookup part of `tableG`, the working registers are
loaded with the overwriting value `w` between the access to share 0 (`ldrb ..., [rX, #0]`) and
the access to share 1 (`ldrb ..., [rX, #4]`), and share 1 of the output is first written with
the overwriting value before the share-1 loads that produce it, so that the store bus does not
carry the two shares in succession. The register that holds `w` differs per routine: r5 in
`masked_xor_w` and `tableG` (`movs r3, r5`, `movs r2, r5`), r4 in `masked_rol2_w`,
`masked_xor_key` and `mask_refreshing` (`movs r3, r4`, `movs r2, r4`; in `mask_refreshing` r0
holds the refresh byte `r`, `eors r3, r0`), and r0 in `masked_copy_w` (`movs r3, r0`);
`mask_refreshing` and `masked_copy_w` use the single working register r3 and write the
overwriting value with `strb r3, [r2, #4]` instead of `strb r3, [r1, #4]`. In `masked_xor_key`,
which XORs the masked key pair into its first operand in place, the overwriting store
`strb r3, [r1, #4]` sits between the load of share 1 of the operand and the load of share 1 of
the key. No halfword or word access to a masked byte (`ldrh`, `strh`, `ldm`, `stm`) occurs in
these routines; the registers saved by `push` and `pop` hold the caller's pointers and
overwriting values, and the only share that passes through a callee-saved register is the fresh
output mask `y0` of `tableG` (`ldrb r4, [r3, #0]`, `strb r4, [r1, #0]`), share 0 of its output,
which is uniformly random and independent of the shared value. The
compiled C code of
`shadow32_round_masked` and `masked_F` passes pointers only, and the C loop of `tableG` that
builds the table handles share 0 of the refreshed input only. In `masking_ISW` (v2) the C
functions `masked_xor`, `masked_ROL8` and `masked_xor_key` move both shares through the same
registers, which is the transition leakage that Section 4.7 of the paper measures.

The sample 10,772 at which the first-order test of the table-recomputation sets exceeds the
threshold in both acquisitions (`results/RESULTS_masked_eval.md`, 64 cycles after the end of
the first table build as the detector of `masked_eval.py` reports it) is tied to the
instructions of `tableG` as follows. Counting Cortex-M0 cycles on the listing (`ldr`, `str`,
`ldrb`, `strb` two cycles, a taken branch three, every other instruction one; the count
reproduces the 41 cycles per iteration of the build loop at `0x8000554` to `0x800058a`), the
lookup `ldrb r3, [r6, r3]` at `0x80005b4` starts 30 cycles after the loop exit (the `movs r3,
#19` at `0x800058c`) and the store of its result `strb r3, [r1, #4]` at `0x80005b6` 32 cycles
after it. On the mean trace of either one-round set the 256 iterations of the first build are
marked by one sample per iteration at which the mean trace reaches the ADC rail, at samples
274 + 41k for k = 0 to 255, which the cycle count identifies as the first cycle of the store of
the table entry (`strb r2, [r3, #0]` at `0x800057e`, offset 28 of the 41-cycle body; the first
store after the loop, `strb r2, [r3, #0]` at `0x8000596`, then lands on the rail sample 10,746,
which agrees). The last iteration leaves the loop two cycles early (its `ble` is not taken), so
the exit falls at sample 10,740, which is 32 cycles after the detector's build end of 10,708
(the detector stops where the 41-periodicity of the mean trace ends, before the last iteration
completes). That places the lookup at samples 10,770 and 10,771 and the store at 10,772 and
10,773: the first-order sample 10,772 is the first cycle of the store of `T[t1]`, and the
second-order samples 10,771 and 10,772 are the second cycle of the lookup and the first cycle
of the store, consistent with Section 4.7 of the paper, which places the sample at the lookup
of `T[t1]` and the store of its result. The second build repeats this 10,966 cycles later (its
detected end 21,674 and the exceedance 21,738 of the second acquisition).

Code size as quoted in the paper is the sum of the sizes of the round function, the functions
it calls and the input sharing (`mask_byte`), plus the construction of the table of g
(`g_plain_init` and `ROL8`) for the table-recomputation version, read from the object file
(named after the source file, not the target) with

```
arm-none-eabi-nm -S --size-sort objdir-CWNANO/<source>.o      (masking_ISW.o, masking_ISWLUT.o, shadow32_nop.o)
```

The ISW round's four calls to the C library `memcpy`, which write the round state back
(`*l0 = lo0; ...` in `masking_ISW.c`), are not counted; the unprotected and the
table-recomputation rounds call no library function.

| Firmware | Functions summed | Bytes |
|---|---|---:|
| `shadow32_nop` | `shadow32_round` 338 + `ROL8` 56 | 394 |
| `masking_ISW` (v2) | `shadow32_round_masked` 746 + `ISW_AND` 156 + `mask_refreshing` 96 + `masked_ROL8` 100 + `masked_xor` 88 + `masked_xor_key` 66 + `ROL8` 56 + `mask_byte` 58 | 1,366 |
| `masking_ISWLUT` (v3) | `shadow32_round_masked` 286 + `masked_F` 106 + `tableG` 160 + `masked_xor_w` 66 + `masked_rol2_w` 68 + `masked_xor_key` 60 + `mask_refreshing` 66 + `masked_copy_w` 44 + `g_plain_init` 80 + `ROL8` 56 + `mask_byte` 58 | 1,050 |

The previous ISW source (v1, with the one-share key addition `masked_xor_const_inplace`, 36
bytes, and a 722-byte round function) summed to 1,312 bytes; the corrected key addition of v2
adds 54 bytes.
