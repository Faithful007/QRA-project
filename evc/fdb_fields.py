"""
fdb_field.py — FDB gas-field reader + spatiotemporal dose sampler.

Field half of the per-scenario pairing pipeline. Parses the ASCII FDB
(header + [time, x, soot, co2, co, temp, radi, o2] rows), builds a
[n_time, n_x] grid per species, and samples gas values along an occupant
trajectory [(t, x), ...] with linear interpolation in both t and x.

The alias map (which distinct field backs each of the 30 classes) is derived
from file content hashes, NOT hardcoded — because the FVM=NV0=NVC collapse is
not uniform (100N collapses NVC; 020N/030N do not).

NOT included / must be supplied to close the loop:
  - real .evc P1-P6 occupant trajectories  (currently synthetic in self-test)
  - Purser log-normal incapacitation constants from prior calibration
    (PURSER_MU / PURSER_SIGMA below are placeholders, flagged)
"""
import os, re, hashlib
import numpy as np

SPECIES = ['soot', 'co2', 'co', 'temp', 'radi', 'o2']

class FdbField:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path).replace('.FDB', '')
        self._parse()

    def _parse(self):
        rows = []
        started = False
        fire = None
        fire_header_seen = False
        with open(self.path, 'r', errors='replace') as f:
            for line in f:
                if not started:
                    if 'FIRE PT' in line:        # column header; values on next line
                        fire_header_seen = True
                        continue
                    if fire_header_seen:
                        # positive decimals only; fire extent = last two (after MIN_X, MAX_X)
                        nums = re.findall(r'\d+\.\d+', line)
                        if len(nums) >= 2:
                            fire = (float(nums[-2]), float(nums[-1]))
                            fire_header_seen = False
                        continue
                    if line.startswith('  [SEC]'):
                        started = True
                    continue
                # ---- data region ----
                p = line.split()
                if len(p) < 8:
                    continue
                try:
                    v = [float(x) for x in p[:8]]
                except ValueError:
                    continue
                if len(v) == 8:
                    rows.append(v)
        a = np.array(rows)
        if fire is None:
            raise ValueError(f"{self.name}: FIRE PT not found in FDB header")
        self.fire = fire
        self.fire_mid = 0.5 * (self.fire[0] + self.fire[1])
        self.times = np.unique(a[:, 0])
        self.xs = np.unique(a[:, 1])
        nt, nx = len(self.times), len(self.xs)
        # reshape each species to [nt, nx]; rows are ordered time-major, x-minor
        ti = {t: i for i, t in enumerate(self.times)}
        xi = {x: i for i, x in enumerate(self.xs)}
        grids = {s: np.full((nt, nx), np.nan) for s in SPECIES}
        for r in a:
            i, j = ti[r[0]], xi[r[1]]
            for k, s in enumerate(SPECIES):
                grids[s][i, j] = r[2 + k]
        self.grid = grids

    def sample(self, t, x, species):
        """Linear interp in t and x. Clamps to grid bounds."""
        g = self.grid[species]
        t = np.clip(t, self.times[0], self.times[-1])
        x = np.clip(x, self.xs[0], self.xs[-1])
        it = np.searchsorted(self.times, t)
        ix = np.searchsorted(self.xs, x)
        it0 = max(0, it - 1); it1 = min(len(self.times) - 1, it)
        ix0 = max(0, ix - 1); ix1 = min(len(self.xs) - 1, ix)
        ft = 0.0 if it1 == it0 else (t - self.times[it0]) / (self.times[it1] - self.times[it0])
        fx = 0.0 if ix1 == ix0 else (x - self.xs[ix0]) / (self.xs[ix1] - self.xs[ix0])
        v00, v01 = g[it0, ix0], g[it0, ix1]
        v10, v11 = g[it1, ix0], g[it1, ix1]
        return (v00*(1-ft)*(1-fx) + v01*(1-ft)*fx + v10*ft*(1-fx) + v11*ft*fx)


def build_alias_map(fdb_dir):
    """Map every (HRR,OCC,VENT) class -> the distinct field file backing it,
    derived from content hashes. Self-correcting for the non-uniform collapse."""
    def h(f): return hashlib.md5(open(os.path.join(fdb_dir, f), 'rb').read()).hexdigest()
    files = [f for f in os.listdir(fdb_dir) if f.endswith('.FDB')]
    by_hash = {}
    cls = {}
    for f in files:
        hv = h(f)
        by_hash.setdefault(hv, f)            # canonical file per distinct field
        cls[f.replace('.FDB', '')] = by_hash[hv]
    return cls  # class -> canonical FDB filename


# --- FED / Purser incapacitation -------------------------------------------
# Standard Purser FED mechanics. CO via Stewart-form accumulation; thermal FED
# from convective heat. Constants below are the well-known Purser forms; the
# *fatality* log-normal conversion constants MUST match the prior session's
# calibration and are left as flagged placeholders.
PURSER_MU = None      # <-- supply from prior calibration / VB fit
PURSER_SIGMA = None   # <-- supply from prior calibration / VB fit

def fed_increment(co_ppm, co2_pct, o2_pct, temp_c, dt_s):
    """Per-step FED increment (Purser). dt in seconds."""
    dt_min = dt_s / 60.0
    # CO (Purser): FED_CO per minute
    fed_co = 3.317e-5 * (max(co_ppm, 0.0) ** 1.036) * 25.0 * dt_min / 30.0  # RMV=25, D=30
    # CO2 hyperventilation multiplier (drives faster uptake)
    vco2 = np.exp(0.1903 * max(co2_pct, 0.0) + 2.0004) / 7.1
    # low-O2 FED
    o2 = max(o2_pct, 0.0)
    fed_o2 = dt_min / np.exp(8.13 - 0.54 * (20.9 - o2)) if o2 < 20.9 else 0.0
    # thermal (convective) FED
    t = max(temp_c, 0.0)
    fed_heat = dt_min / np.exp(5.1849 - 0.0273 * t) if t > 20.0 else 0.0
    return (fed_co * vco2 + fed_o2) + fed_heat

def fatality_prob(fed_total):
    """Log-normal incapacitation -> fatality (Phi-based). Needs calibrated mu/sigma."""
    if PURSER_MU is None or PURSER_SIGMA is None:
        return None  # not calibrated in this session
    from math import erf, log10, sqrt
    if fed_total <= 0:
        return 0.0
    z = (log10(fed_total) - PURSER_MU) / (PURSER_SIGMA * sqrt(2))
    return 0.5 * (1 + erf(z))

def dose_trajectory(field: 'FdbField', traj):
    """traj: list of (t_seconds, x_meters). Returns accumulated FED."""
    fed = 0.0
    for k in range(1, len(traj)):
        t0, x0 = traj[k-1]; t1, x1 = traj[k]
        tm, xm = 0.5*(t0+t1), 0.5*(x0+x1)
        dt = t1 - t0
        co  = field.sample(tm, xm, 'co')
        co2 = field.sample(tm, xm, 'co2')
        o2  = field.sample(tm, xm, 'o2')
        tp  = field.sample(tm, xm, 'temp')
        fed += fed_increment(co, co2, o2, tp, dt)
    return fed

