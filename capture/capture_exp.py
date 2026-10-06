# -*- coding: utf-8 -*-
# NOTE (artifact): acquisition script of the three unprotected trace sets (Shadow-32 fixed key,
#   Shadow-32 ten keys, Shadow-64), ChipWhisperer-Nano.  The images are flashed from firmware/
#   (not included; build them there with the makefile) and the trace files are written to
#   data/shadow32_fixedkey/, data/shadow32_10keys/ and data/shadow64/.  The phase selection is
#   recorded as `seekclip` in the `phase` field of the trace files, and the target is verified
#   against the reference implementation with a known-answer test before capturing.
# NOTE (artifact): Shadow-64 branch updated to match the deposited capture.
#   firmware  shadow64_nop-CWNANO.hex -> shadow64_newkey-CWNANO.hex
#   RK64      reference key 000102..0F -> random master key
#             07E9A4B27E3FCB472DA757EA31CAF4ED (first round key 872C E3FB 644A 72D7)
"""Acquisition of the unprotected experiments with the NOP-padded firmwares (clkout = adc =
7.5 MHz, the high-amplitude `seekclip` phase).

  python capture_exp.py s32d      -> Shadow-32, the baked round-key table ('d'),  2048 x 12500
  python capture_exp.py s32k      -> Shadow-32, ten different master keys ('k'),  2048 x 12500 each (ten sets)
  python capture_exp.py s64 4096  -> Shadow-64, the baked round keys ('p'),       4096 x 25000

The trace count is overridden by the second argument (default 2048); the published Shadow-64 set
has 4096 traces. The masked sets in data/masked/ and the two further fixed-key sets in
data/shadow32_fixedkey/ were acquired with capture_lab.py, not with this script.

Common settings: clkout 7.5 MHz / adc 7.5 MHz (one sample per cycle); the clock phase is reset
until one sample of a probe trace reaches 98% of the ADC full scale (seekclip, seek_clip_phase).
"""
import os, sys, time
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import numpy as np
import chipwhisperer as cw

HERE     = os.path.dirname(os.path.abspath(__file__))
N_TRACES = 2048
CLKOUT   = 7.5e6
ADCFREQ  = 7.5e6

# ---------------- Shadow-32 ----------------
M8 = 0xFF
def ROL8(v, r): return ((v << r) | (v >> (8 - r))) & M8
def F8(x):      return (ROL8(x, 1) & ROL8(x, 7)) ^ ROL8(x, 2)

RK32_DEFAULT = [
    0x0D,0x3B,0x60,0x33, 0x43,0x60,0x25,0x3C, 0x13,0x25,0x89,0xC5, 0x3C,0x89,0x0D,0x5D,
    0x25,0x0D,0x40,0xD1, 0x8D,0x40,0x14,0x15, 0x11,0x14,0x91,0x56, 0xC5,0x91,0x03,0x6D,
    0x16,0x03,0x02,0xD6, 0x1D,0x02,0x08,0x63, 0x06,0x08,0x31,0x39, 0x43,0x31,0x2C,0x90,
    0x69,0x2C,0x01,0x0A, 0x20,0x01,0x11,0xAB, 0x9A,0x11,0x00,0xBC, 0x0B,0x00,0x04,0xCE,
]
PERM32 = [
    56,57,58,59,16,17,18,19,20,21,22,23,24,25,26,27,
    60,61,62,63,28,29,30,31,32,33,34,35,36,37,38,39,
    40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,
     0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15]

def _pack8(b, idx):
    v = 0
    for i in range(8): v = (v << 1) | (b[idx[i]] & 1)
    return v

def ks32(master8):
    """8-byte master key -> rk[64] (the same function as shadow32_key_schedule in the firmware)."""
    K0=[0,1,2,3,8,9,10,11]; K1=[4,5,6,7,12,13,14,15]
    K2=[16,17,18,19,24,25,26,27]; K3=[20,21,22,23,28,29,30,31]
    b=[(master8[i>>3]>>(7-(i&7)))&1 for i in range(64)]; rk=[]
    for r in range(16):
        rc=r+1
        b[3]^=(rc>>4)&1; b[4]^=(rc>>3)&1; b[5]^=(rc>>2)&1; b[6]^=(rc>>1)&1; b[7]^=rc&1
        k=[b[56],b[57],b[58],b[59],b[60],b[61],b[62],b[63]]
        b[56]=k[0]&(k[0]^k[6]); b[57]=k[1]&(k[1]^k[7])
        b[58]=k[2]&(k[2]^k[0]^k[6]); b[59]=k[3]&(k[3]^k[1]^k[7])
        b[60]=k[4]&(k[4]^k[2]^k[0]^k[6]); b[61]=k[5]&(k[5]^k[3]^k[1]^k[7])
        b[62]=k[6]&(k[4]^k[2]^k[0]); b[63]=k[7]&(k[5]^k[3]^k[1])
        b=[b[PERM32[i]] for i in range(64)]
        rk += [_pack8(b,K0),_pack8(b,K1),_pack8(b,K2),_pack8(b,K3)]
    return rk

def enc32(pt, rk):
    l0,l1,r0,r1 = pt
    for i in range(16):
        k0,k1,k2,k3 = rk[4*i:4*i+4]
        s0=F8(l0)^l1^k0; s1=F8(r0)^r1^k1
        l1=F8(s0)^l0^k2; r1=F8(s1)^r0^k3
        l0,r0 = s1,s0
    return [r0,l1,l0,r1]

# The ten master keys. The seed is fixed, so every run produces the same ten.
_kr = np.random.default_rng(0x5241)
MASTERS = [[int(x) for x in _kr.integers(0, 256, 8)] for _ in range(10)]

# ---------------- Shadow-64 ----------------
M16 = 0xFFFF
def ROL16(v, r): return ((v << r) | (v >> (16 - r))) & M16
def F16(x):      return (ROL16(x,1) & ROL16(x,7)) ^ ROL16(x,2)

MASTER64 = [0x07,0xE9,0xA4,0xB2,0x7E,0x3F,0xCB,0x47,
            0x2D,0xA7,0x57,0xEA,0x31,0xCA,0xF4,0xED]
RK64 = [
    0x872C,0xE3FB,0x644A,0x72D7,0x6604,0x472D,0x8A47,0x725E,
    0x2814,0xA725,0x273A,0xE843,0x0263,0x7E84,0x0A01,0x3020,
    0x8030,0xA302,0x0106,0x0498,0x6060,0x1049,0x0685,0x8496,
    0x2018,0x6849,0x2505,0x6112,0x0200,0x5611,0x650C,0x2000,
    0x2600,0x5200,0x1C07,0x0008,0x1120,0xC000,0x0716,0x8816,
    0x4021,0x7881,0x0607,0x6012,0xC000,0x6601,0x0708,0x2000,
    0x3000,0x7200,0x280B,0x0002,0x2240,0x8000,0x0B0C,0x2001,
    0x6000,0xB200,0x0C0A,0x1014,0x8000,0xC101,0x4A0C,0x400C,
    0x9420,0xA400,0x0C0D,0xC003,0x8010,0xCC00,0x0D0E,0x3002,
    0x8040,0xD300,0x2E0D,0x2007,0xC200,0xE200,0x1D00,0x7009,
    0xC110,0xD700,0x0001,0x9008,0xC020,0x0900,0x0106,0x8009,
    0xC040,0x1800,0x1603,0x9009,0x0190,0x6900,0x0304,0x900D,
    0x1080,0x3900,0x0407,0xD00D,0x6000,0x4D00,0x9707,0xD00D,
    0x3900,0x7D00,0x8707,0xD00D,0x4890,0x7D00,0x0708,0xD001,
    0x6040,0x7D00,0x0808,0x1000,0x6040,0x8100,0x980A,0x0007,
    0x6940,0x8000,0x4A0B,0x7002,0x8410,0xA700,0x0B05,0x2005]

def enc64(pt4):
    l0,l1,r0,r1 = pt4
    for i in range(32):
        k0,k1,k2,k3 = RK64[4*i:4*i+4]
        s0=F16(l0)^l1^k0; s1=F16(r0)^r1^k1
        l1=F16(s0)^l0^k2; r1=F16(s1)^r0^k3
        l0,r0 = s1,s0
    return [r0,l1,l0,r1]


# ======================================================================
def connect(hexfile, samples):
    scope = cw.scope(); scope.default_setup()
    scope.adc.clk_src  = "int"
    scope.io.clkout    = CLKOUT
    scope.adc.clk_freq = ADCFREQ
    scope.adc.samples  = samples
    target = cw.target(scope, cw.targets.SimpleSerial)
    print("[SCOPE] clkout=%g adc=%g (%.2f s/cyc) samples=%d"
          % (scope.io.clkout, scope.adc.clk_freq,
             scope.adc.clk_freq/scope.io.clkout, scope.adc.samples), flush=True)
    # The images are not included; building with the makefile in firmware/ puts them there.
    cw.program_target(scope, cw.programmers.STM32FProgrammer,
                      os.path.join(HERE, "..", "firmware", hexfile))
    print("[FLASH] %s" % hexfile, flush=True)
    return scope, target


def seek_clip_phase(scope, target, cmdfn, ptlen, samples):
    """Reset the clock phase until a high-amplitude phase, one at which the probe trace clips, is found."""
    for att in range(60):
        p = np.random.default_rng(9).integers(0, 256, ptlen, dtype=np.uint8)
        scope.arm(); target.simpleserial_write('p', bytearray(p.tobytes()))
        to = scope.capture()
        target.simpleserial_read('r', 16, timeout=200)
        t = scope.get_last_trace()
        if (not to) and len(t) == samples:
            t = np.asarray(t, float)
            if t.max() >= 0.49 or t.min() <= -0.49:
                print("[PHASE] seekclip found @try%d max=%.3f min=%.3f"
                      % (att, t.max(), t.min()), flush=True)
                return
        print("[PHASE] try%d -> reset" % att, flush=True)
        try:
            scope.reset_clock_phase()
            scope.io.nrst = 0; time.sleep(0.02); scope.io.nrst = None; time.sleep(0.1)
        except Exception as e:
            print("[PHASE] exception %r" % e, flush=True)
        try: target.flush()
        except Exception: pass
        cmdfn()
    print("[WARN] no seekclip phase found", flush=True)


def run_capture(scope, target, samples, ptlen, n=N_TRACES, seed=1234, tag=""):
    rng = np.random.default_rng(seed)
    tr  = np.zeros((n, samples), np.float16)
    pts = np.zeros((n, ptlen), np.uint8)
    k = to = 0; t0 = time.time()
    while k < n:
        p = rng.integers(0, 256, ptlen, dtype=np.uint8)
        scope.arm(); target.simpleserial_write('p', bytearray(p.tobytes()))
        if scope.capture():
            to += 1; target.simpleserial_read('r', 16, timeout=200); continue
        if target.simpleserial_read('r', 16, timeout=300) is None:
            to += 1; continue
        t = scope.get_last_trace()
        if len(t) != samples: to += 1; continue
        tr[k] = t; pts[k] = p; k += 1
        if k % 1024 == 0:
            print("[PROG] %s %d/%d timeout%d %.0fs" % (tag, k, n, to, time.time()-t0), flush=True)
    return tr, pts, to, time.time()-t0


def save(path, tr, pts, rk, samples, extra=None):
    d = dict(traces=tr, pt=pts, rk=np.array(rk), clkout=CLKOUT, adc_freq=ADCFREQ,
             samples=samples, phase="seekclip")
    if extra: d.update(extra)
    np.savez_compressed(path, **d)
    f = tr.astype(np.float64)
    print("[SAVE] %s  min=%+.3f max=%+.3f clip=%.3f%%  %.1fMB"
          % (os.path.basename(path), f.min(), f.max(),
             (np.abs(f) >= 0.4959).mean()*100, os.path.getsize(path)/1e6), flush=True)


def main():
    which = sys.argv[1]
    global N_TRACES
    if len(sys.argv) > 2:            # trace count override
        N_TRACES = int(sys.argv[2])
        print('[CFG] N_TRACES=%d' % N_TRACES, flush=True)

    if which == "s32d":
        SAMPLES = 12500
        outdir = os.path.join(HERE, "..", "data", "shadow32_fixedkey")
        os.makedirs(outdir, exist_ok=True)
        scope, target = connect("shadow32_nop-CWNANO.hex", SAMPLES)
        def setd():
            target.simpleserial_write('d', bytearray()); time.sleep(0.02)
            try: target.flush()
            except Exception: pass
        setd()
        rng = np.random.default_rng(42); bad = 0
        for _ in range(8):
            p=[int(x) for x in rng.integers(0,256,4)]
            target.simpleserial_write('p', bytearray(p))
            r=target.simpleserial_read('r',16,timeout=400)
            if r is None or list(r[:4]) != enc32(p, RK32_DEFAULT): bad += 1
        print("[KAT] mismatches=%d -> %s" % (bad, "PASS" if bad==0 else "FAIL"), flush=True)
        seek_clip_phase(scope, target, setd, 4, SAMPLES); setd()
        tr, pts, to, el = run_capture(scope, target, SAMPLES, 4, n=N_TRACES, tag="s32d")
        save(os.path.join(outdir, "s32_ref_12500.npz"), tr, pts,
             np.array(RK32_DEFAULT, np.uint8), SAMPLES,
             dict(cipher="shadow32", master=np.zeros(0, np.uint8)))
        print("[DONE] s32d  timeouts %d %.1f min" % (to, el/60), flush=True)
        target.dis(); scope.dis()

    elif which == "s32k":
        SAMPLES = 12500
        outdir = os.path.join(HERE, "..", "data", "shadow32_10keys")
        os.makedirs(outdir, exist_ok=True)
        scope, target = connect("shadow32_nop-CWNANO.hex", SAMPLES)
        def setd():
            target.simpleserial_write('d', bytearray()); time.sleep(0.02)
            try: target.flush()
            except Exception: pass
        setd()
        seek_clip_phase(scope, target, setd, 4, SAMPLES)
        for j, m in enumerate(MASTERS, 1):
            target.simpleserial_write('k', bytearray(m)); time.sleep(0.05)
            try: target.flush()
            except Exception: pass
            rk = ks32(m)
            rng = np.random.default_rng(42); bad = 0
            for _ in range(6):
                p=[int(x) for x in rng.integers(0,256,4)]
                target.simpleserial_write('p', bytearray(p))
                r=target.simpleserial_read('r',16,timeout=400)
                if r is None or list(r[:4]) != enc32(p, rk): bad += 1
            print("[KAT] key%02d mismatches=%d %s" % (j, bad, "PASS" if bad==0 else "FAIL"), flush=True)
            tr, pts, to, el = run_capture(scope, target, SAMPLES, 4, n=N_TRACES,
                                          seed=2000+j, tag="key%02d" % j)
            save(os.path.join(outdir, "s32_key%02d_12500.npz" % j), tr, pts,
                 np.array(rk, np.uint8), SAMPLES,
                 dict(cipher="shadow32", master=np.array(m, np.uint8)))
            print("[DONE] key%02d timeouts %d %.1f min" % (j, to, el/60), flush=True)
        target.dis(); scope.dis()

    elif which == "s64":
        SAMPLES = 25000
        outdir = os.path.join(HERE, "..", "data", "shadow64")
        os.makedirs(outdir, exist_ok=True)
        scope, target = connect("shadow64_newkey-CWNANO.hex", SAMPLES)
        rng = np.random.default_rng(42); bad = 0
        for _ in range(8):
            p8=[int(x) for x in rng.integers(0,256,8)]
            w=[(p8[2*i]<<8)|p8[2*i+1] for i in range(4)]
            target.simpleserial_write('p', bytearray(p8))
            r=target.simpleserial_read('r',16,timeout=500)
            exp=enc64(w); got=[(r[2*i]<<8)|r[2*i+1] for i in range(4)] if r is not None else None
            if got != exp: bad += 1
        print("[KAT] mismatches=%d -> %s" % (bad, "PASS" if bad==0 else "FAIL"), flush=True)
        seek_clip_phase(scope, target, lambda: None, 8, SAMPLES)
        tr, pts, to, el = run_capture(scope, target, SAMPLES, 8, n=N_TRACES, tag="s64")
        save(os.path.join(outdir, "s64_ref_25000.npz"), tr, pts,
             np.array(RK64, np.uint16), SAMPLES,
             dict(cipher="shadow64", master=np.array(MASTER64, np.uint8)))
        print("[DONE] s64 timeouts %d %.1f min" % (to, el/60), flush=True)
        target.dis(); scope.dis()

    else:
        raise SystemExit("usage: capture_exp.py s32d|s32k|s64 [n_traces]")


if __name__ == "__main__":
    main()
