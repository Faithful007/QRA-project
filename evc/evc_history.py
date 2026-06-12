"""
evc_history.py
==============
Per-timestep evacuation-history support for the QRA Python engine, to
reproduce the VB `P*_*_DAT.TEC` evacuation-outcome files.

This module is intentionally standalone so the change to evc_engine.py is
minimal: evc_engine records a list of raw per-step snapshots into
RunResult.history (when record_history=True), and the two helpers here

  • smoke_front(fdb, t_now, threshold)  -> (smds_max, smds_min)
  • write_dat_tec(result, path, fire_x)  -> writes a VB-layout .TEC file

turn that raw history into the VB columns.

VB DAT.TEC column layout (from the uploaded P1_x_DAT.TEC references):
  time, EVC_MAN, Fatals, DN0_1..DN0_9, DN1_0, UP1_0, EQ_FATAL, FED_MAX,
  MEVC_MAX, MEVC_MIN, PEVC_MAX, PEVC_MIN, SMDS_MAX, SMDS_MIN, PSIN_SMK,
  EXNO_01, EXNO_02

NOTE on the smoke threshold:
  SMDS = SMoke Down-Stream front edges (max = downstream extent, min =
  upstream edge / backlayering). It is the soot-field property, not an
  occupant property, so it is computed by scanning the FDB soot row at
  t_now for where soot exceeds SMOKE_SOOT_THRESHOLD. The exact VB value
  is not yet pinned (the reference TEC uses an EVC coordinate frame whose
  scenario/position mapping was not confirmed); SMOKE_SOOT_THRESHOLD is a
  tunable default. To calibrate: pick the value whose front trajectory
  matches a known VB SMDS_MAX trace on the SAME scenario.
"""
from __future__ import annotations
import numpy as np

# Tunable: soot value (FDB raw units) above which a cell counts as "in smoke".
# Default chosen mid-range; calibrate against a VB SMDS trace per note above.
SMOKE_SOOT_THRESHOLD = 5.0

# FED band edges for the DN0_1..DN1_0 columns (0.1 .. 1.0).
FED_BANDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def smoke_front(fdb, t_now, threshold: float = SMOKE_SOOT_THRESHOLD):
    """Return (smds_max, smds_min): downstream and upstream x [m] where the
    FDB soot field at time t_now first/last exceeds `threshold`. If no cell
    is above threshold, both default to the fire centre (front not yet
    established), matching the VB convention of seeding SMDS at the fire."""
    x = np.asarray(fdb.x_coords, dtype=float)
    # nearest FDB time index
    t = np.asarray(fdb.times, dtype=float)
    ti = int(np.argmin(np.abs(t - t_now)))
    row = np.asarray(fdb.soot[ti], dtype=float)
    idx = np.where(row > threshold)[0]
    if idx.size == 0:
        fc = float(fdb.fire_center) if fdb.fire_center is not None else float(x[len(x) // 2])
        return fc, fc
    return float(x[idx[-1]]), float(x[idx[0]])


def snapshot(t_now, escaped, fed_total, current_pos, exit_pos,
             soot_at_occ, smds_max, smds_min,
             smoke_occ_threshold: float = SMOKE_SOOT_THRESHOLD):
    """Build one per-timestep history record from in-loop arrays.

    All occupant arrays are 1-D, length n_occ. Returns a plain dict so the
    engine has zero new dependencies and the record is trivially picklable.
    """
    escaped = np.asarray(escaped, dtype=bool)
    fed = np.asarray(fed_total, dtype=float)
    n_in = (~escaped)                              # still in tunnel
    # FED-band counts among occupants still in the tunnel
    bands = []
    for lo in FED_BANDS:
        hi = lo + 0.1 if lo < 1.0 else np.inf
        bands.append(int(np.sum(n_in & (fed >= lo) & (fed < hi))))
    return {
        "time":     float(t_now),
        "evc_man":  int(np.sum(escaped)),
        "fatals":   int(np.sum(fed >= 1.0)),
        "fed_bands": bands,                         # DN0_1..DN1_0 (10 values)
        "eq_fatal": float(np.sum(np.clip(fed, 0.0, 1.0))),
        "fed_max":  float(fed.max()) if fed.size else 0.0,
        "pevc_max": float(np.max(current_pos)) if np.any(n_in) else 0.0,
        "pevc_min": float(np.min(current_pos[n_in])) if np.any(n_in) else 0.0,
        "smds_max": float(smds_max),
        "smds_min": float(smds_min),
        "psin_smk": int(np.sum(n_in & (np.asarray(soot_at_occ) > smoke_occ_threshold))),
    }


def write_dat_tec(history, path, zone_name="ALL"):
    """Write a VB-compatible DAT.TEC file from a list of snapshot() dicts."""
    cols = ("time, EVC_MAN, Fatals, "
            "DN0_1, DN0_2, DN0_3, DN0_4, DN0_5, DN0_6, DN0_7, DN0_8, DN0_9, "
            "DN1_0, UP1_0, EQ_FATAL, FED_MAX, MEVC_MAX, MEVC_MIN, "
            "PEVC_MAX, PEVC_MIN, SMDS_MAX, SMDS_MIN, PSIN_SMK")
    lines = [f"Variables = {cols}",
             f'ZONE T="{zone_name}" I = {len(history)} J =  1 K = 1 F = Point']
    for h in history:
        b = h["fed_bands"]
        row = [h["time"], h["evc_man"], h["fatals"],
               *b[:9],                # DN0_1..DN0_9
               b[9],                  # DN1_0
               0,                     # UP1_0 (up/down split not tracked separately yet)
               h["eq_fatal"], h["fed_max"],
               0.0, 0.0,              # MEVC_MAX/MIN (monitoring-evac dist; not tracked)
               h["pevc_max"], h["pevc_min"],
               h["smds_max"], h["smds_min"], h["psin_smk"]]
        lines.append(" ".join(f"{v:8.2f}" if isinstance(v, float) else f"{v:6d}"
                              for v in row))
    with open(path, "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    return path