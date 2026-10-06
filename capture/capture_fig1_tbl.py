# -*- coding: utf-8 -*-
# NOTE (artifact): paths adjusted to this repository's layout.  The script flashes
#   firmware/hwchar/simpleserial-hwchar-tbl-CWNANO.hex (build it from firmware/hwchar/ with the
#   makefile there), reads the permutation table firmware/hwchar/tbl_perm.npy and the phase
#   template data/hwchar/phase_template.npz, and writes the trace files to data/hwchar/ with a
#   copy of the console output in capture/logs/.  The deposited Fig. 1 set was acquired with
#     python capture_fig1_tbl.py lock 1000 1      -> data/hwchar/fig1_lock_tbl1_1000.npz
#   (method 1, the identity table; 1,000 traces per Hamming weight; phase locked to the template).
"""Re-acquisition of Fig. 1 with the table-lookup firmware (firmware/hwchar/hwchar_tbl.c): the power
at the moment r0 changes from 0 to v, measured by three methods in one session.

  method 0: ldrb r0,[p]           fixed address (reference)
  method 1: ldrb r0,[T_id, v]     identity table, low byte of the address = v
  method 2: ldrb r0,[T_perm, i]   permuted table, i = sigma^-1(v), address independent of HW(v)

The three methods x HW 0..8 x per_hw traces are shuffled at random and acquired at one clock
phase (the amplitude differs between phases, so one phase keeps the comparison fair). The values
of one Hamming weight are used almost equally often (the counts differ by at most 1).

  python capture_fig1_tbl.py [seekclip|noclip|lock] [per_hw=2000 | pv<N>: N traces per value] [methods, e.g. 13] [savetpl]
    method 3: unrelated operations on random data (pt[2..5]) immediately before the identity-table lookup.
    savetpl: store the mean probe traces of the chosen phase as data/hwchar/phase_template.npz.
    lock: reset the phase until the mean probe traces are within RMS 0.009 of the template (the same
          phase across sessions).

Output: data/hwchar/fig1tbl_<phase>_<per_hw>.npz (traces, value, index, mode, hw, ...), and, split
by method, data/hwchar/fig1_<phase>_tbl<m>_<per_hw>.npz (the files analysis/fig_hw_boxplot.py reads).
"""
import os, sys, time
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import numpy as np
import chipwhisperer as cw
from capture_fig1 import Tee, reset_phase, CLK, SAMPLES, HW

HERE = os.path.dirname(os.path.abspath(__file__))
FWDIR = os.path.join(HERE, "..", "firmware", "hwchar")
DATADIR = os.path.join(HERE, "..", "data", "hwchar")
HEX = os.path.join(FWDIR, "simpleserial-hwchar-tbl-CWNANO.hex")
PERM = np.load(os.path.join(FWDIR, "tbl_perm.npy")); INV = np.argsort(PERM)
OPS = {0: "ldrb r0,[p] (fixed address)", 1: "ldrb r0,[T_id,v] (identity table)", 2: "ldrb r0,[T_perm,s^-1(v)] (permuted table)",
       3: "ldrb r0,[T_id,v] after random ops (identity table)"}
TPL = os.path.join(DATADIR, "phase_template.npz")   # phase-lock template (mean probe traces)
TPL_TOL = 0.009   # RMS tolerance between the mean probe traces and the template. Observed: at RMS <= 0.009 the
                  # value at the measured sample is within one ADC code of the template (2 of 30 resets pass)


def probe(scope, target, n=16):
    """Mean traces [2, 400] of two fixed inputs (v = 0x00 and 0xFF, method 1), used as the phase-lock
    template and for the comparison against it."""
    out = []
    for v in (0x00, 0xFF):
        ts = [one(scope, target, v, 1) for _ in range(n)]
        if any(t is None for t in ts): return None
        out.append(np.mean([t[:400] for t in ts], 0))
    return np.array(out)


def one(scope, target, idx, mode, extra=(0, 0, 0, 0)):
    msg = bytearray([idx, mode] + [int(x) for x in extra] + [0] * 10)   # extra = pt[2..5], the data of the unrelated operations of method 3
    scope.arm(); target.simpleserial_write('p', msg)
    if scope.capture():
        target.simpleserial_read('r', 16, timeout=200); return None
    r = target.simpleserial_read('r', 16, timeout=200)
    if r is None or r[0] != idx or r[1] != mode: return None
    t = scope.get_last_trace()
    return t if len(t) == SAMPLES else None


def main():
    mode_ph = sys.argv[1] if len(sys.argv) > 1 else "seekclip"
    arg2 = sys.argv[2] if len(sys.argv) > 2 else "2000"
    per_value = int(arg2[2:]) if arg2.startswith("pv") else None          # "pv100": 100 traces per value
    per_hw = None if per_value else int(arg2)
    MODES = [int(c) for c in sys.argv[3]] if len(sys.argv) > 3 else [0, 1, 2]
    save_tpl = len(sys.argv) > 4 and sys.argv[4] == "savetpl"     # store the chosen phase as the template
    tag = "%s_%s" % (mode_ph, arg2)
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    log = os.path.join(HERE, "logs", "fig1tbl_%s_%s.log" % (tag, time.strftime("%Y%m%d_%H%M%S")))
    sys.stdout = Tee(log, sys.stdout); sys.stderr = Tee(log, sys.stderr)
    print("[RUN] capture_fig1_tbl.py %s %s modes=%s" % (mode_ph, arg2, MODES), flush=True)
    scope = cw.scope(); scope.default_setup()
    scope.adc.clk_src = "int"; scope.io.clkout = CLK; scope.adc.clk_freq = CLK; scope.adc.samples = SAMPLES
    target = cw.target(scope, cw.targets.SimpleSerial)
    print("[SCOPE] clkout=%g adc=%g samples=%d" % (scope.io.clkout, scope.adc.clk_freq, scope.adc.samples), flush=True)
    cw.program_target(scope, cw.programmers.STM32FProgrammer, HEX)
    print("[FLASH] %s" % os.path.basename(HEX), flush=True)
    bad = sum(one(scope, target, v, m) is None for v in (0, 0x55, 0xFF) for m in (0, 1, 2, 3))
    print("[CHECK] failed responses %d/12" % bad, flush=True)

    prng = np.random.default_rng(7); phase = None
    tpl = np.load(TPL)["probe"] if mode_ph == "lock" else None
    for att in range(200 if mode_ph == "lock" else 80):
        if mode_ph == "lock":                                     # reset the phase until it matches the template
            pr = probe(scope, target)
            if pr is not None:
                rms = float(np.sqrt(np.mean((pr - tpl) ** 2)))
                if rms <= TPL_TOL: phase = "lock (probe RMS %.4f <= %.4f vs template) @try%d" % (rms, TPL_TOL, att)
                print("[PHASE] try%d RMS vs template %.4f%s" % (att, rms, "  <- selected" if phase else ""), flush=True)
                if phase: break
            reset_phase(scope, target); continue
        ts = [one(scope, target, int(prng.integers(0, 256)), int(prng.integers(0, 3))) for _ in range(16)]
        if all(t is not None for t in ts):
            mx = max(float(np.max(t)) for t in ts); amx = max(float(np.abs(t).max()) for t in ts)
            if mode_ph == "seekclip" and mx >= 0.49: phase = "seekclip (probe max %.3f >= 0.49) @try%d" % (mx, att)
            elif mode_ph == "noclip" and amx <= 0.47: phase = "noclip (max|trace| %.3f <= 0.47) @try%d" % (amx, att)
            print("[PHASE] try%d max=%.3f max|.|=%.3f%s" % (att, mx, amx, "  <- selected" if phase else ""), flush=True)
            if phase: break
        reset_phase(scope, target)
    if phase is None:
        print("[WARN] no phase found", flush=True); target.dis(); scope.dis(); sys.exit(1)
    if save_tpl:
        pr = probe(scope, target, 64)
        np.savez(TPL, probe=pr, phase=phase, made=time.strftime("%Y-%m-%d %H:%M:%S"))
        print("[TPL] phase template stored as %s" % os.path.basename(TPL), flush=True)

    vrng = np.random.default_rng(11); items = []
    for m in MODES:
        if per_value:
            items += [(v, m) for v in range(256) for _ in range(per_value)]
            continue
        for k in range(9):
            vs = np.where(HW == k)[0]; q, r = divmod(per_hw, len(vs))
            extra = vrng.choice(vs, r, replace=False) if r else np.array([], int)
            items += [(int(v), m) for v in list(np.repeat(vs, q)) + list(extra)]
    items = [items[i] for i in np.random.default_rng(2026).permutation(len(items))]
    vals = np.array([v for v, m in items], np.uint8); modes = np.array([m for v, m in items], np.uint8)
    idxs = np.where(modes == 2, INV[vals], vals).astype(np.uint8)
    rnd = np.random.default_rng(99).integers(0, 256, (len(items), 4), dtype=np.uint8)   # pt[2..5], sent with every trace
    n = len(items); tr = np.zeros((n, SAMPLES), np.float32); to = 0; t0 = time.time(); i = 0
    while i < n:
        t = one(scope, target, int(idxs[i]), int(modes[i]), rnd[i])
        if t is None: to += 1; continue
        tr[i] = t; i += 1
        if i % 5120 == 0:
            print("[PROG] %d/%d timeout%d max|trace|=%.3f %.0fs" % (i, n, to, np.abs(tr[:i]).max(), time.time() - t0), flush=True)
    os.makedirs(DATADIR, exist_ok=True)
    common = dict(phase=phase, clkout=CLK, adc_freq=CLK, samples=SAMPLES, per_hw=(per_hw or -1), per_value=(per_value or -1), firmware=os.path.basename(HEX),
                  nop_encoding="0xBF00")
    out = os.path.join(DATADIR, "fig1tbl_%s.npz" % tag)
    np.savez_compressed(out, traces=tr.astype(np.float16), value=vals, index=idxs, mode=modes, rand=rnd, hw=HW[vals].astype(np.uint8), **common)
    for m in MODES:
        s = modes == m
        np.savez_compressed(os.path.join(DATADIR, "fig1_%s_tbl%d_%s.npz" % (mode_ph, m, arg2)), traces=tr[s].astype(np.float16),
                            value=vals[s], index=idxs[s], rand=rnd[s], hw=HW[vals[s]].astype(np.uint8), op=OPS[m], **common)
    print("[SAVE] %s  shape=%s min=%+.3f max=%+.3f at-max=%.3f%%  timeouts %d, %.1f min"
          % (os.path.basename(out), tr.shape, tr.min(), tr.max(), (tr >= 0.4959).mean() * 100, to, (time.time() - t0) / 60), flush=True)
    target.dis(); scope.dis()


if __name__ == "__main__":
    main()
