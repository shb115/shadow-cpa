# -*- coding: utf-8 -*-
# NOTE (artifact): paths adjusted to this repository's layout.  The script flashes the image
#   it finds in firmware/ (build it there: TARGET = masking_ISW_v2, masking_ISW_v2_KAT
#   (EXTRA_OPTS=SHADOW32_KAT), masking_ISW_v2_FULL (EXTRA_OPTS=SHADOW32_FULL), the same three
#   for masking_ISWLUT, and shadow32_nop_O0; see the README) and writes the trace files to
#   data/masked/ (masked sets) and data/shadow32_fixedkey/ (unprotected set), with a copy of
#   the console output in capture/logs/.  The deposited sets are the runs of the commands
#   listed in the docstring below with their default trace and sample counts (the file names
#   are listed under data/ in the README); `kat` and `katfull` passed for both ISW and ISWLUT.
#   The second argument of `unprot` is the optimization level digit only (0 -> shadow32_nop_O0).
#   `--fixedphase` takes the clock phase found at power-on without any selection; `--noclip`
#   resets the phase until all sixteen probe traces of an attempt stay within |trace| <= 0.47,
#   so that no sample reaches the largest ADC value (the criterion recorded in the `phase`
#   field of the deposited set).
"""ChipWhisperer-Nano acquisition script of the masked sets and of the two further fixed-key
sets (the re-acquisition of the revision). It uses the settings of capture_exp.py (clkout
7.5 MHz / adc 7.5 MHz, one sample per cycle). Every random byte is supplied by this script and
stored with the traces.

  python capture_lab.py kat    ISW|ISWLUT            one-round known-answer test on the KAT build
                                                     (every random byte, the key masks included, random)
  python capture_lab.py katfull ISW|ISWLUT           16-round ciphertext check on the FULL build
  python capture_lab.py masked ISW|ISWLUT [N] [S]    N fixed-plaintext and N random-plaintext traces of
                                                     S samples (default ISW 8192 x 10000, ISWLUT 8192 x
                                                     46000); the second, independent acquisition is --seed 2
  python capture_lab.py full   ISW|ISWLUT [N] [S]    FULL build, the first S samples of the full 16-round
                                                     encryption (default 8192 x 46000); the 192 random
                                                     bytes go up in four 'q' pieces and 'p' carries 8 bytes
                                                     (the stored pt has 200 bytes)
  python capture_lab.py unprot 0 2048 --fixedphase   unprotected -O0 build without phase selection (the
                                                     clock phase found at power-on)
  python capture_lab.py unprot 0 2048 --noclip       unprotected -O0 build at a phase without clipping
                                                     (max|trace| <= 0.47)

Output: .npz files under data/ (traces float16, pt, group, key, samples, version, ...) in the
format of the published trace sets, and a copy of the console output of every run in
capture/logs/.
"""
import os, sys, time, argparse
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shadow32_ref as ref
import chipwhisperer as cw

CLKOUT = 7.5e6
ADCFREQ = 7.5e6
HEXDIR = os.path.join(HERE, "..", "firmware")   # images built from firmware/ (as capture_exp.py)
OUT = os.path.join(HERE, "..", "data")          # data/masked/, data/shadow32_fixedkey/
LOGDIR = os.path.join(HERE, "logs")             # capture/logs/, a copy of the console output per run
FIXED_PT = [0x11, 0x22, 0x33, 0x44]              # the fixed plaintext of the published masked sets
KEY4 = ref.RK32_DEFAULT[:4]                       # Round-1 key 0D 3B 60 33


def connect(hexname, samples):
    scope = cw.scope(); scope.default_setup()
    scope.adc.clk_src = "int"
    scope.io.clkout = CLKOUT
    scope.adc.clk_freq = ADCFREQ
    scope.adc.samples = samples
    target = cw.target(scope, cw.targets.SimpleSerial)
    print("[SCOPE] clkout=%g adc=%g samples=%d" % (scope.io.clkout, scope.adc.clk_freq, scope.adc.samples), flush=True)
    if scope.adc.samples != samples:
        print("[WARN] the requested sample count %d was not accepted (board limit?); the scope has %d" % (samples, scope.adc.samples), flush=True)
    path = os.path.join(HEXDIR, hexname)
    cw.program_target(scope, cw.programmers.STM32FProgrammer, path)
    print("[FLASH] %s" % hexname, flush=True)
    return scope, target


def seek_clip_phase(scope, target, ptlen, samples, full=False):
    """Same as capture_exp.seek_clip_phase: reset the clock phase until a probe trace reaches 98% of
    the ADC full scale in at least one sample."""
    for att in range(60):
        p = np.random.default_rng(9).integers(0, 256, ptlen, dtype=np.uint8)
        if full: p = np.frombuffer(send_full(target, p), dtype=np.uint8)
        scope.arm(); target.simpleserial_write('p', bytearray(p.tobytes()))
        to = scope.capture()
        target.simpleserial_read('r', 16, timeout=1000)
        t = scope.get_last_trace()
        if (not to) and len(t) == samples:
            t = np.asarray(t, float)
            if t.max() >= 0.49 or t.min() <= -0.49:
                print("[PHASE] seekclip @try%d max=%.3f min=%.3f" % (att, t.max(), t.min()), flush=True)
                return "seekclip"
        print("[PHASE] try%d -> reset" % att, flush=True)
        try:
            scope.reset_clock_phase()
            scope.io.nrst = 0; time.sleep(0.02); scope.io.nrst = None; time.sleep(0.1)
        except Exception as e:
            print("[PHASE] exception %r" % e, flush=True)
        try: target.flush()
        except Exception: pass
    print("[WARN] no seekclip phase found", flush=True)
    return "seekclip-failed"


def seek_noclip_phase(scope, target, ptlen, samples, limit=0.47, nprobe=16):
    """The opposite criterion: reset the clock phase until all `nprobe` probe traces stay within
    |trace| <= limit, so that no sample reaches the largest ADC value (0.496).  Returns the
    string stored in the `phase` field, 'noclip (|trace|<=0.47) @tryN'."""
    prng = np.random.default_rng(9)
    for att in range(60):
        amx = 0.0; ok = True
        for _ in range(nprobe):
            p = prng.integers(0, 256, ptlen, dtype=np.uint8)
            res = one(scope, target, p, samples, 300)
            if res is None: ok = False; break
            amx = max(amx, float(np.abs(np.asarray(res[0], float)).max()))
        if ok and amx <= limit:
            print("[PHASE] noclip @try%d max|trace|=%.3f <= %.2f" % (att, amx, limit), flush=True)
            return "noclip (|trace|<=%.2f) @try%d" % (limit, att)
        print("[PHASE] try%d max|trace|=%.3f -> reset" % (att, amx), flush=True)
        try:
            scope.reset_clock_phase()
            scope.io.nrst = 0; time.sleep(0.02); scope.io.nrst = None; time.sleep(0.1)
        except Exception as e:
            print("[PHASE] exception %r" % e, flush=True)
        try: target.flush()
        except Exception: pass
    print("[WARN] no noclip phase found", flush=True)
    return "noclip-failed"


def send_full(target, p200):
    """FULL firmware: of the 200-byte input, the 192 random bytes go up in four 'q' pieces and only
    8 bytes are sent with 'p'."""
    p200 = bytes(p200)
    for c in range(4):
        target.simpleserial_write('q', bytearray(bytes([c]) + p200[8 + 48 * c: 8 + 48 * (c + 1)]))
        try: target.simpleserial_wait_ack(timeout=500)
        except Exception: time.sleep(0.005)
    return p200[:8]


def one(scope, target, p, samples, timeout, full=False):
    """One trace: (trace, response) on success, None otherwise."""
    if full: p = send_full(target, p)
    scope.arm(); target.simpleserial_write('p', bytearray(bytes(p)))
    if scope.capture():
        target.simpleserial_read('r', 16, timeout=timeout); return None
    r = target.simpleserial_read('r', 16, timeout=timeout)
    if r is None: return None
    t = scope.get_last_trace()
    if len(t) != samples: return None
    return t, r


def save(path, tr, pts, group, samples, version, extra=None):
    d = dict(traces=tr, pt=pts, group=group, key=np.array(KEY4, np.uint8), rk=np.array(ref.RK32_DEFAULT, np.uint8),
             clkout=CLKOUT, adc_freq=ADCFREQ, samples=samples, version=version)
    if extra: d.update(extra)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, **d)
    f = tr.astype(np.float64)
    print("[SAVE] %s  shape=%s min=%+.3f max=%+.3f clip=%.3f%%  %.1fMB"
          % (os.path.basename(path), tr.shape, f.min(), f.max(), (np.abs(f) >= 0.4959).mean() * 100, os.path.getsize(path) / 1e6), flush=True)


# ---------------------------------------------------------------- KAT
def kat(tag, full):
    hexname = "masking_%s_v2_%s-CWNANO.hex" % (tag, "FULL" if full else "KAT")
    scope, target = connect(hexname, 1000)
    rng = np.random.default_rng(42); bad = 0; n = 32
    for i in range(n):
        if full:
            p = [int(x) for x in rng.integers(0, 256, 200)]
            exp = ref.enc32(p[:4], ref.RK32_DEFAULT)
        else:
            p = [int(x) for x in rng.integers(0, 256, 20)]       # every random byte random, r_key included
            exp = ref.round32(p[:4], KEY4)
        if full: p = list(send_full(target, p))
        target.simpleserial_write('p', bytearray(bytes(p)))
        r = target.simpleserial_read('r', 16, timeout=2000)
        got = list(r[:4]) if r is not None else None
        if got != exp:
            bad += 1
            if bad <= 3: print("   mismatch: pt=%s exp=%s got=%s" % ([hex(x) for x in p[:4]], [hex(x) for x in exp], got))
    print("[KAT] %s %s: %d/%d mismatches -> %s" % (tag, "FULL(16 rounds)" if full else "one round", bad, n, "PASS" if bad == 0 else "FAIL"), flush=True)
    target.dis(); scope.dis()
    return bad == 0


# ---------------------------------------------------------------- masked sets (fixed vs random)
def masked(tag, n, samples, seed, full):
    hexname = "masking_%s_v2%s-CWNANO.hex" % (tag, "_FULL" if full else "")
    ptlen = 200 if full else 20
    scope, target = connect(hexname, samples)
    phase = seek_clip_phase(scope, target, ptlen, samples, full)
    rng = np.random.default_rng(seed)
    order = rng.permutation(np.r_[np.zeros(n, np.uint8), np.ones(n, np.uint8)])   # 0 = fixed, 1 = random, in random order
    tr = np.zeros((2 * n, samples), np.float16); pts = np.zeros((2 * n, ptlen), np.uint8); grp = np.zeros(2 * n, np.uint8)
    k = to = 0; t0 = time.time(); timeout = 2000 if full else 500
    while k < 2 * n:
        g = int(order[k])
        p = rng.integers(0, 256, ptlen, dtype=np.uint8)            # every random byte (masks, refresh, r_key, overwriting values) random
        if g == 0: p[:4] = FIXED_PT
        res = one(scope, target, p, samples, timeout, full)
        if res is None: to += 1; continue
        tr[k] = res[0]; pts[k] = p; grp[k] = g; k += 1
        if k % 1024 == 0:
            print("[PROG] %s %d/%d timeout%d %.0fs" % (tag, k, 2 * n, to, time.time() - t0), flush=True)
    version = "masking_%s_v2%s" % (tag, "_full" if full else "")
    name = "%s_seed%d_%dx%d.npz" % (version, seed, 2 * n, samples)
    save(os.path.join(OUT, "masked", name), tr, pts, grp, samples, version,
         dict(phase=phase, fixed_pt=np.array(FIXED_PT, np.uint8), seed=seed, firmware=hexname))
    print("[DONE] %s timeouts %d, %.1f min" % (name, to, (time.time() - t0) / 60), flush=True)
    target.dis(); scope.dis()


# ---------------------------------------------------------------- unprotected Shadow-32 (fixed key); the argument is the
# optimization level digit of the image name (0 -> shadow32_nop_O0; only -O0 sets are deposited)
def unprot(opt, n, fixedphase, noclip=False):
    samples = 12500
    hexname = "shadow32_nop_O%s-CWNANO.hex" % opt
    scope, target = connect(hexname, samples)
    def setd():
        target.simpleserial_write('d', bytearray()); time.sleep(0.02)
        try: target.flush()
        except Exception: pass
    setd()
    rng = np.random.default_rng(42); bad = 0
    for _ in range(8):
        p = [int(x) for x in rng.integers(0, 256, 4)]
        target.simpleserial_write('p', bytearray(p)); r = target.simpleserial_read('r', 16, timeout=400)
        if r is None or list(r[:4]) != ref.enc32(p, ref.RK32_DEFAULT): bad += 1
    print("[KAT] unprotected O%s mismatches=%d -> %s" % (opt, bad, "PASS" if bad == 0 else "FAIL"), flush=True)
    if fixedphase:
        phase = "fixed (no phase selection)"
    elif noclip:
        phase = seek_noclip_phase(scope, target, 4, samples)
    else:
        phase = seek_clip_phase(scope, target, 4, samples)
    if not fixedphase: setd()
    rng = np.random.default_rng(1234)
    tr = np.zeros((n, samples), np.float16); pts = np.zeros((n, 4), np.uint8); k = to = 0; t0 = time.time()
    while k < n:
        p = rng.integers(0, 256, 4, dtype=np.uint8)
        res = one(scope, target, p, samples, 300)
        if res is None: to += 1; continue
        tr[k] = res[0]; pts[k] = p; k += 1
        if k % 1024 == 0: print("[PROG] O%s %d/%d timeout%d %.0fs" % (opt, k, n, to, time.time() - t0), flush=True)
    version = "shadow32_O%s%s" % (opt, "_fixedphase" if fixedphase else ("_noclipphase" if noclip else ""))
    name = "s32_%s_12500.npz" % version
    d = dict(traces=tr, pt=pts, rk=np.array(ref.RK32_DEFAULT, np.uint8), clkout=CLKOUT, adc_freq=ADCFREQ, samples=samples,
             phase=phase, cipher="shadow32", version=version, firmware=hexname)
    os.makedirs(os.path.join(OUT, "shadow32_fixedkey"), exist_ok=True)
    np.savez_compressed(os.path.join(OUT, "shadow32_fixedkey", name), **d)
    f = tr.astype(np.float64)
    print("[SAVE] %s min=%+.3f max=%+.3f clip=%.3f%%" % (name, f.min(), f.max(), (np.abs(f) >= 0.4959).mean() * 100), flush=True)
    print("[DONE] %s timeouts %d, %.1f min" % (name, to, (time.time() - t0) / 60), flush=True)
    target.dis(); scope.dis()


class _Tee:
    """Copy of the console output to a log file in capture/logs/."""
    def __init__(self, path, stream):
        self.f = open(path, "a", encoding="utf-8"); self.o = stream
    def write(self, t):
        self.o.write(t); self.f.write(t); self.f.flush()
    def flush(self):
        self.o.flush(); self.f.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["kat", "katfull", "masked", "full", "unprot"])
    ap.add_argument("which")
    ap.add_argument("n", nargs="?", type=int)
    ap.add_argument("samples", nargs="?", type=int)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--fixedphase", action="store_true")
    ap.add_argument("--noclip", action="store_true")
    a = ap.parse_args()
    os.makedirs(LOGDIR, exist_ok=True)
    log = os.path.join(LOGDIR, "%s_%s_%s.log" % (a.cmd, a.which, time.strftime("%Y%m%d_%H%M%S")))
    sys.stdout = _Tee(log, sys.stdout); sys.stderr = _Tee(log, sys.stderr)
    print("[RUN] " + " ".join(sys.argv[1:]) + "  (log: " + log + ")")
    if a.cmd in ("kat", "katfull"):
        kat(a.which, a.cmd == "katfull")
    elif a.cmd == "masked":
        n = a.n or 8192; s = a.samples or (10000 if a.which == "ISW" else 46000)
        masked(a.which, n, s, a.seed, False)
    elif a.cmd == "full":
        n = a.n or 8192; s = a.samples or 46000
        masked(a.which, n, s, a.seed, True)
    elif a.cmd == "unprot":
        unprot(a.which, a.n or 2048, a.fixedphase, a.noclip)


if __name__ == "__main__":
    main()
