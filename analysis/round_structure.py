# -*- coding: utf-8 -*-
"""
Key-independent location of the rounds in a Shadow-32 trace.

Every CPA in this repository is run over the samples of the round its subkey belongs to.
Where those samples are is found from the traces alone, without the key and without the
outcome of any attack:

  period   : the lag of the largest peak of the mean trace's autocorrelation
             (the 16 rounds repeat with this period);
  boundary : the quietest point between two rounds, i.e. the minimum of the mean
             absolute trace folded over the 16 round periods.

A Round-r subkey (r = 1, 2, ...) is then attacked over the samples

        [boundary + (r-1) * period,  boundary + r * period)

Only the mean over all traces is used.  The plaintexts are random, so this mean carries
no information about the key.  On the published Shadow-32 data every set gives
period = 748; the boundary is 358 or 406 depending on the set (two nearly equally quiet
points), and both place every subkey's leakage inside its round.
"""
import numpy as np

NROUNDS = 16


def round_structure(traces, pmin=200, pmax=2000, nrounds=NROUNDS):
    """Return (period, boundary) derived from the mean of `traces` (N x S)."""
    m = np.asarray(traces, dtype=np.float64).mean(axis=0)
    x = m - m.mean()
    ac = np.correlate(x, x, mode="full")[len(x) - 1:]
    period = pmin + int(np.argmax(ac[pmin:pmax]))

    # phase that best aligns the 16 periods, then the quietest point of the folded envelope
    best_ph, best_score = 0, -1.0
    for ph in range(period):
        if ph + nrounds * period > len(x):
            break
        M = x[ph:ph + nrounds * period].reshape(nrounds, period)
        score = M.mean(0).var() / M.var(0).mean()
        if score > best_score:
            best_ph, best_score = ph, score
    M = x[best_ph:best_ph + nrounds * period].reshape(nrounds, period)
    quiet = int(np.argmin(np.abs(M).mean(0)))
    boundary = (best_ph + quiet) % period
    return period, boundary


def round_interval(r, period, boundary, nsamples=None):
    """Sample range (a, b) of Round r (1-based)."""
    a = boundary + (r - 1) * period
    b = a + period
    if nsamples is not None:
        a, b = max(0, a), min(nsamples, b)
    return a, b
