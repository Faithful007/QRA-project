"""
evc_history.py
==============
Per-timestep evacuation-history support for the QRA Python engine, faithful to
VB's per-frame loop FUN_0049c8f0 (which writes the .DAT live during the run).

Verified semantics (against real 100CFV0_P1 .SET/.DAT ground truth):

  * EQ_FATAL is a LIVE, LATCHED quantity: each frame it is the band-weighted
    sum over ALL occupants by their CURRENT (monotonic) FED, so it never
    decreases and an occupant counted once stays counted after it escapes —
    matching VB's increment-only DAT_004a661c.

  * The DN/UP columns are a FED DOSE-LEVEL binning, NOT a spatial split:
        DN0_1 = FED in [0.0, 0.1)   DN0_2 = [0.1, 0.2) ...  DN1_0 = [0.9, 1.0)
        UP1_0 = FED >= 1.0   (the incapacitated / "1.0 and up" bucket)
    Bins cover ALL occupants (escaped retain their latched band), so the row
    sums to n_occ — exactly as VB's .DAT does (sum = 331 on the test cell).

  * EXNO_01 / EXNO_02 = cumulative escapees via portal-0 and the far portal.

The plain VB `.DAT` writer (`write_dat_plain`) emits the exact column order and
header of the native VB file (the format the simulation writes to logical
file #1), distinct from the Tecplot `.TEC` variant (`write_dat_tec`, retained).
"""
from __future__ import annotations
import numpy as np

# Tunable: soot value (FDB raw units) above which a cell counts as "in smoke".
SMOKE_SOOT_THRESHOLD = 5.0

# Dose-level bin edges. The 10 DN columns are [edges[i], edges[i+1]) for
# i = 0..9, i.e. [0,0.1),[0.1,0.2),...,[0.9,1.0). UP1_0 is FED >= 1.0.
DN_EDGES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

# Default EQ_FATAL band table (VB shifted frame). The engine passes its own
# EQ_FATAL_BANDS through; this is only the fallback.
DEFAULT_EQ_BANDS = ((0.2, 0.01), (0.3, 0.10), (0.4, 1.00))


def band_weight(fed, bands=DEFAULT_EQ_BANDS):
    """Per-occupant EQ_FATAL weight: highest band threshold the FED meets."""
    fed = np.asarray(fed, dtype=float)
    w = np.zeros_like(fed, dtype=float)
    for th, wt in sorted(bands):
        w = np.where(fed >= th, wt, w)
    return w


def smoke_front(fdb, t_now, threshold: float = SMOKE_SOOT_THRESHOLD):
    """Return (smds_max, smds_min): downstream/upstream x [m] where the FDB soot
    field at t_now exceeds `threshold`; seeded at the fire centre if none."""
    x = np.asarray(fdb.x_coords if hasattr(fdb, "x_coords") else fdb.xs, dtype=float)
    t = np.asarray(fdb.times, dtype=float)
    ti = int(np.argmin(np.abs(t - t_now)))
    row = np.asarray(fdb.soot[ti], dtype=float)
    idx = np.where(row > threshold)[0]
    if idx.size == 0:
        fc = float(fdb.fire_center) if getattr(fdb, "fire_center", None) is not None \
            else float(x[len(x) // 2])
        return fc, fc
    return float(x[idx[-1]]), float(x[idx[0]])


def snapshot(t_now, escaped, fed_total, current_pos, exit_pos,
             soot_at_occ, smds_max, smds_min,
             fire_x=None, eq_bands=DEFAULT_EQ_BANDS, latched_w=None,
             smoke_occ_threshold: float = SMOKE_SOOT_THRESHOLD):
    """Build one per-frame VB-faithful history record.

    All occupant arrays are length n_occ. FED is monotonic, so binning the
    CURRENT FED over ALL occupants reproduces VB's latched per-frame counts.

    latched_w (optional): the caller-maintained latched EQ weight array. If
    given, EQ_FATAL = sum(latched_w) (live + latched, increment-only). If not,
    it is computed from the current FED via `eq_bands` (equivalent while FED is
    monotonic, but the caller form is the faithful one).
    """
    escaped = np.asarray(escaped, dtype=bool)
    fed = np.asarray(fed_total, dtype=float)
    pos = np.asarray(current_pos, dtype=float)

    # ── DN/UP dose-level bins over ALL occupants (escaped retain their band) ──
    dn = []
    for i in range(len(DN_EDGES) - 1):
        lo, hi = DN_EDGES[i], DN_EDGES[i + 1]
        dn.append(int(np.sum((fed >= lo) & (fed < hi))))
    up1_0 = int(np.sum(fed >= 1.0))               # the "1.0 and up" bucket

    # ── live + latched EQ_FATAL ──
    if latched_w is not None:
        eq_fatal = float(np.sum(np.asarray(latched_w, dtype=float)))
    else:
        eq_fatal = float(np.sum(band_weight(fed, eq_bands)))

    # ── per-portal cumulative escapees (EXNO_01 = portal 0, EXNO_02 = far) ──
    if exit_pos is not None:
        ep = np.asarray(exit_pos, dtype=float)
        far = ep.max() if ep.size else 0.0
        exno_01 = int(np.sum(escaped & (ep <= far * 0.5)))
        exno_02 = int(np.sum(escaped & (ep > far * 0.5)))
    else:
        exno_01 = exno_02 = 0

    n_in = ~escaped
    return {
        "time":     float(t_now),
        "evc_man":  int(np.sum(escaped)),
        "fatals":   int(np.sum(fed >= 1.0)),
        "dn_bands": dn,                            # DN0_1..DN1_0  (10 values)
        "up1_0":    up1_0,                         # UP1_0
        "eq_fatal": eq_fatal,
        "fed_max":  float(fed.max()) if fed.size else 0.0,
        "mevc_max": 0.0, "mevc_min": 0.0,          # monitoring-dist: not tracked
        "pevc_max": float(np.max(pos[n_in])) if np.any(n_in) else 0.0,
        "pevc_min": float(np.min(pos[n_in])) if np.any(n_in) else 0.0,
        "smds_max": float(smds_max),
        "smds_min": float(smds_min),
        "psin_smk": int(np.sum(n_in & (np.asarray(soot_at_occ) > smoke_occ_threshold))),
        "exno_01":  exno_01,
        "exno_02":  exno_02,
        # legacy alias so write_dat_tec keeps working
        "fed_bands": dn,
    }


# ── plain VB .DAT writer (native layout, logical file #1) ────────────────────
_DAT_HDR = ("    time EVC_MAN   Fatals    0.1DN    0.2DN    0.3DN    0.4DN    "
            "0.5DN    0.6DN    0.7DN    0.8DN    0.9DN    1.0DN    1.0UP EQ_FATAL"
            "  FED_MAX MEVC_MAX MEVC_MIN PEVC_MAX PEVC_MIN SMDS_MAX SMDS_MIN "
            "PSIN_SMK  EXNO_01  EXNO_02")


def write_dat_plain(history, path):
    """Write the native VB `.DAT` (the file the simulation writes to logical #1):
    one fixed-width row per frame, header first. Column order matches the
    reverse-engineered FUN_00480510 / real .DAT exactly."""
    lines = [_DAT_HDR]
    for h in history:
        dn = h["dn_bands"]
        vals = [h["time"], h["evc_man"], h["fatals"],
                *dn,                       # 0.1DN .. 1.0DN  (10)
                h["up1_0"],                # 1.0UP
                h["eq_fatal"], h["fed_max"],
                h["mevc_max"], h["mevc_min"],
                h["pevc_max"], h["pevc_min"],
                h["smds_max"], h["smds_min"], h["psin_smk"],
                h["exno_01"], h["exno_02"]]
        # match VB widths: floats .2f in 9-wide, integer-ish counts in fixed cols
        parts = [f"{vals[0]:8.1f}", f"{vals[1]:7.1f}", f"{vals[2]:8.2f}"]
        for v in vals[3:14]:               # 10 DN + UP1_0 as NN.00
            parts.append(f"{float(v):8.2f}")
        for v in vals[14:23]:              # EQ_FATAL .. PSIN_SMK
            parts.append(f"{float(v):8.2f}")
        parts.append(f"{int(vals[23]):8d}")
        parts.append(f"{int(vals[24]):8d}")
        lines.append("".join(parts))
    with open(path, "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    return path


# ── per-occupant trajectory writer (.LOC) ────────────────────────────────────
def write_loc(loc_frames, path, occ_types=None):
    """Write a per-occupant trajectory `.LOC`: one block per frame, each row
    `time  id  x  status` (status 0=in tunnel, 1=escaped). `loc_frames` is a
    list of (t, pos_array, escaped_array). NOTE: column layout is a faithful
    plain-text trajectory; the exact VB byte format awaits a real .LOC
    reference (we have .SET-exact but no .LOC sample yet)."""
    lines = ["    time      id        x  status"]
    for (t, pos, esc) in loc_frames:
        pos = np.asarray(pos, dtype=float)
        esc = np.asarray(esc, dtype=bool)
        for i in range(len(pos)):
            lines.append(f"{t:8.1f}{i + 1:8d}{pos[i]:9.1f}{int(esc[i]):8d}")
    with open(path, "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    return path


# ── legacy Tecplot DAT.TEC writer (retained for back-compat) ─────────────────
def write_dat_tec(history, path, zone_name="ALL", fire_x=None):
    cols = ("time, EVC_MAN, Fatals, "
            "DN0_1, DN0_2, DN0_3, DN0_4, DN0_5, DN0_6, DN0_7, DN0_8, DN0_9, "
            "DN1_0, UP1_0, EQ_FATAL, FED_MAX, MEVC_MAX, MEVC_MIN, "
            "PEVC_MAX, PEVC_MIN, SMDS_MAX, SMDS_MIN, PSIN_SMK, EXNO_01, EXNO_02")
    lines = [f"Variables = {cols}",
             f'ZONE T="{zone_name}" I = {len(history)} J =  1 K = 1 F = Point']
    for h in history:
        dn = h["dn_bands"]
        row = [h["time"], h["evc_man"], h["fatals"], *dn, h["up1_0"],
               h["eq_fatal"], h["fed_max"], h["mevc_max"], h["mevc_min"],
               h["pevc_max"], h["pevc_min"], h["smds_max"], h["smds_min"],
               h["psin_smk"], h["exno_01"], h["exno_02"]]
        lines.append(" ".join(f"{v:8.2f}" if isinstance(v, float) else f"{v:6d}"
                              for v in row))
    with open(path, "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    return path

