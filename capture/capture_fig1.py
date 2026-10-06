# -*- coding: utf-8 -*-
# NOTE (artifact): this module holds the routines that capture_fig1_tbl.py imports (Tee,
#   reset_phase, CLK, SAMPLES, HW).  It has no acquisition of its own; the Fig. 1 set was
#   acquired with capture_fig1_tbl.py.
"""Routines shared by the Fig. 1 acquisition: the copy of the console output (Tee), the clock-phase
reset (reset_phase), the acquisition settings (clkout = adc = 7.5 MHz, one sample per cycle, 600
samples) and the byte Hamming-weight table HW."""
import time
import numpy as np

CLK = 7.5e6
SAMPLES = 600
HW = np.array([bin(i).count("1") for i in range(256)])


class Tee:
    """Copy of the console output to a log file."""
    def __init__(self, path, s): self.f = open(path, "a", encoding="utf-8"); self.o = s
    def write(self, t): self.o.write(t); self.f.write(t); self.f.flush()
    def flush(self): self.o.flush(); self.f.flush()


def reset_phase(scope, target):
    """Reset the clock phase of the target relative to the ADC and restart the target."""
    scope.reset_clock_phase()
    scope.io.nrst = 0; time.sleep(0.02); scope.io.nrst = None; time.sleep(0.1)
    try: target.flush()
    except Exception: pass
