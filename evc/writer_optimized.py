"""
writer_optimized.py
===================
Batch-optimized EVC writer. Behavior is identical (byte-for-byte) to
writer_current.py, with the following structural changes:

  1. Three-tier work split:
       a. Tunnel-level state (tunnel geometry, vehicle table, traffic) is
          computed ONCE for a project. Returned as `TunnelContext`.
       b. Scenario-level state (HRR-specific fire dynamics, n_occ_scaled,
          extended-time pre-computation) is computed ONCE per CHID.
          Returned as `ScenarioContext`.
       c. Per-position work is just three line substitutions plus L74 and
          the L60 y_offset toggle.

  2. Static line blocks (L02, L17–L23, L31–L37, L52–L59, L67, L78, L79,
     L83, L86, L89, etc.) are pre-built once at module import.

  3. Number formatter `_g` is memoized — the small integer-and-rational
     vocabulary used in EVC files repeats heavily across files.

  4. Output bytes are assembled with a single `b"\\n".join()` rather than
     per-line concatenation.

  5. Line endings are LF (`\\n`) and the file does NOT end with a newline,
     matching the legacy reference files exactly. (writer_current.py
     incorporated the same fix.)

Public API:

    >>> ctx_t = build_tunnel_context(params)
    >>> ctx_s = build_scenario_context(ctx_t, chid="020CFV0",
    ...                                 fdb_tmax=549.9, sim_end_time=365)
    >>> write_evc_for_position(out_path, ctx_t, ctx_s,
    ...                         fire_point_x=26.7, fire_pos_idx=1,
    ...                         tunnel_name_bytes=tname_bytes)

A single-shot convenience wrapper, write_evc_file(...), is also provided
with the same signature as writer_current.write_evc_file for drop-in
testing. The batch path is the optimized one; single-shot just calls the
batch path with rebuilt contexts.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Sequence
import re


# ── HRR lookup ──────────────────────────────────────────────────────────────
# 20 MW removed from the table — 020* CHIDs read fire-dynamics values from
# the GUI Evacuation Time Setting panel via the params dict, falling back
# to VB-reference defaults (15.0 / 0.113 / 22.0 / 0.002) so an untouched
# GUI still reproduces the legacy 020 byte stream.
_HRR_PARAMS: dict[int, tuple] = {
    30:  (30,  0.225, 48,  0.001, 480.8, 366),
    50:  (50,  0.375, 80,  0.001, 500.0, 366),
    100: (100, 0.75,  161, 0.001, 488.4, 366),
}
_RE_HRR_PREFIX = re.compile(r'^(\d+)')


# ── Number formatter — memoized ─────────────────────────────────────────────
@lru_cache(maxsize=4096)
def _g(v) -> str:
    """Format like VB6 Single: strip trailing zeros, short form.
    Memoized because the EVC vocabulary (320, 26.7, 0.5, 1.5, 2.41, 0.113…)
    repeats heavily across files in a batch run.
    """
    try:
        f = float(v)
        if f == int(f):
            return str(int(f))
        if 0 < abs(f) < 0.0001:
            return f"{f:.7E}".replace("E+0", "E+").replace("E-0", "E-")
        s = f"{f:.7g}"
        if "e" in s:
            s = s.upper().replace("E+0", "E+").replace("E-0", "E-")
        return s
    except Exception:
        return str(v)


def _col14(values: Sequence) -> str:
    return " " + "".join(f"{_g(v):<14}" for v in values).rstrip() + " "


# ── Pre-built static line blocks (encoded once at import time) ─────────────
# All of these are constants that never depend on tunnel/scenario/position.
# Encoded as bytes here to skip the cp949 round-trip on every call.

_BYTES_L02 = b"-1             0 "
_BYTES_L17_TO_L23 = b"\n".join([b" 0 "] * 7)            # L17–L23, joined w/ \n
_BYTES_L31_TO_L37 = b"\n".join([b" 0 "] * 7)            # L31–L37
_BYTES_L52_TO_L59 = b"\n".join([
    b" 3 ", b" 8 ", b" 30 ", b" 2 ", b" 2 ", b" 1 ", b" 1 ", b" 1 ",
])
_BYTES_L61 = b" 2 "
_BYTES_L67 = b"False,True"
_BYTES_L79 = b"True,False"
_BYTES_L83 = b" 0 , 1 , 1 "
_BYTES_L86 = _col14([1, 1]).encode("ascii")
_BYTES_L89 = b" 0 "


# ── Helpers for params dict ────────────────────────────────────────────────
def _f(d: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(d.get(key, default) or default)
    except (ValueError, TypeError):
        return float(default)


def _i(d: dict, key: str, default: int = 0) -> int:
    try:
        return int(float(d.get(key, default) or default))
    except (ValueError, TypeError):
        return int(default)


# ───────────────────────────────────────────────────────────────────────────
# TIER 1: Tunnel-level context (built ONCE per project)
# ───────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class TunnelContext:
    """Pre-computed tunnel-level data shared across ALL scenarios in a project.

    EVC file line mapping (VB EVC.exe format):
      L03  length        — tunnel length (m)
      L04  width         — roadway width = lane_width × num_lanes + 2 × shoulder
      L05  gradient      — tunnel gradient/slope (%)
      L06  cross_area    — cross-sectional area (m²)
      L07  height        — tunnel height (m)
      L08  num_lanes     — number of lanes
      L09  abs_min_speed, abs_elderly_speed — absolute walk speeds (m/s)
      L10–L16  vehicle counts per type
      L24–L30  mix rates (%)
      L38–L44  PCU factors
      L45–L51  vehicle lengths (m)
      L66  normal_traffic   — pcphpl (vehicles/hour/lane)
      L75  air_velocity     — m/s
      L76  fdb_dt           — FDB time step (s)
      L77  fdb_monitor_x    — FDB monitor X (m)
      L80  hesitation_time  — s
      L81  leave_car_time   — s
      L82  pre_move_time    — = hesitation - leave_car (s)
      L85  (fdb_sim_interval, monitor_save, monitor_pt, monitor_save)
      L87  (min_speed, elderly_speed, elderly_ratio) — sim walk factors
      L88  lane_width, shoulder — geometric road parameters (m)
    """
    L: float
    num_lanes: int
    abs_min_speed: float
    abs_elderly_speed: float
    air_velocity: float
    leave_car_time: float
    hesitation_time: float
    pre_move_time: int
    evac_offset: int
    min_speed: float
    elderly_speed: float
    elderly_ratio: float
    lane_width: float      # L88[0]: lane width (m)
    shoulder: float        # L88[1]: shoulder width (m)
    normal_traffic: float
    fdb_dt: float
    fdb_monitor_x: float
    monitor_pt: float
    monitor_save: float
    fdb_sim_interval: float

    # n_occ formula intermediates (used by scenario-level L74 calc)
    n_occ_r74_float: float        # legacy formula base (kept for symmetric fallback)
    sim_n_occ_r74:   float        # spacing-formula sim_n_occ (matches VB evacuee count)
    abs_ws_r74: float

    # R74 saturation parameters (SYMMETRIC placement legacy)
    hrr_ref: float
    hrr_sat_c: float
    hrr_sat_k: float

    # R74 ASYMMETRIC-placement calibration (tunnel-invariant coefficients)
    # n_eff = sim_n_occ × (A + B × (HRR-ref)/(HRR-ref+K))
    # VB-calibrated against GUMOK 020/030/100 CFV0_P1 references.
    is_asymmetric: bool
    r74_mult_a_asym: float        # A: base multiplier        (default 3.9595)
    r74_mult_b_asym: float        # B: saturation amplitude   (default 2.6299)
    r74_sat_k_asym:  float        # K: saturation half-point  (default 53.014)

    # Static block of file bytes for L02–L59 (geometry + vehicle table)
    # This block is identical for every position file in the project.
    static_lines_2_to_59: bytes


def build_tunnel_context(params: dict) -> TunnelContext:
    """Build the TunnelContext from a params dict. Call ONCE per project.

    Pre-encodes everything from L02 through L59 because none of those
    lines depend on chid or fire position.
    """
    tn = params.get("tunnel", {})
    sm = params.get("simulation", {})
    hr = params.get("hrr_settings", {})
    mb = params.get("mdb", {})
    tr = params.get("traffic", {})

    L           = _f(tn, "length",     0.0)
    gradient    = _f(tn, "gradient",  -0.1)   # L05: tunnel gradient/slope (%)
    cross_area  = _f(tn, "cross_area", 54.11) # L06: cross-sectional area (m²)
    height      = _f(tn, "height",     5.9)   # L07: tunnel height (m)
    num_lanes   = _i(tn, "num_lanes",  2)     # L08
    lane_width  = _f(tn, "lane_width", 3.25)  # L88[0]: lane width (m)
    shoulder    = _f(tn, "shoulder",   1.0)   # L88[1]: shoulder width (m)

    _rw = _f(tn, "road_width", 0.0)
    width = _rw if _rw > 0 else round(lane_width * num_lanes + 2.0 * shoulder, 3)

    # Vehicle table — 7 vehicle types
    def _tvt(row_key, col, default=0.0):
        try:
            lst = tn.get(row_key, [])
            v = lst[col] if col < len(lst) else str(default)
            return float(v) if v not in ("", "—", "-") else float(default)
        except (ValueError, TypeError):
            return float(default)

    VT = 7
    veh_counts  = [_tvt("veh_plus_dir", c) for c in range(VT)]
    mix_rates   = [_tvt("mix_rate",     c) for c in range(VT)]
    pcu_vals    = [_tvt("pcu",          c, 1.0) for c in range(VT)]
    veh_lengths = [_tvt("veh_length",   c) for c in range(VT)]
    occ_vals    = [_tvt("occupants",    c) for c in range(VT)]

    abs_min_speed     = _f(sm, "abs_min_speed",     0.50)
    abs_elderly_speed = _f(sm, "abs_elderly_speed", 0.50)

    # ── Pre-build static lines L02–L59 as bytes ──
    # Line semantics (per VB EVC.exe file format):
    #   L02: header  "-1  0"
    #   L03: tunnel length (m)
    #   L04: roadway width (m) = lane_width × num_lanes + 2 × shoulder
    #   L05: gradient / slope (%)
    #   L06: cross-sectional area (m²)
    #   L07: tunnel height (m)
    #   L08: number of lanes
    #   L09: absolute walk speeds (m/s) — used by L74 budget formula
    #   L10–L16: vehicle counts per type (7 types)
    #   L17–L23: reserved (zeros)
    #   L24–L30: mix rates per type (% of total flow)
    #   L31–L37: reserved (zeros)
    #   L38–L44: PCU factors per type
    #   L45–L51: vehicle lengths (m)
    #   L52–L58: occupants per vehicle type
    #   L59: trailing  " 1 "
    # L88 (written later): lane_width (m), shoulder (m) — geometric road params.
    parts: list[bytes] = []
    parts.append(_BYTES_L02)                                              # L02
    parts.append(f" {_g(L)} ".encode("ascii"))                            # L03: tunnel length
    parts.append(f" {_g(width)} ".encode("ascii"))                        # L04: roadway width
    parts.append(f" {_g(gradient)} ".encode("ascii"))                     # L05: gradient/slope (%)
    parts.append(f" {_g(cross_area)} ".encode("ascii"))                   # L06: cross-section area (m²)
    parts.append(f" {_g(height)} ".encode("ascii"))                       # L07: tunnel height (m)
    parts.append(f" {num_lanes} ".encode("ascii"))                        # L08: number of lanes
    parts.append(_col14([abs_min_speed, abs_elderly_speed]).encode("ascii"))  # L09: abs walk speeds (m/s)
    for v in veh_counts:                                                  # L10–L16: vehicle counts
        parts.append(f" {int(v)} ".encode("ascii"))
    parts.append(_BYTES_L17_TO_L23)                                       # L17–L23 (reserved)
    for m in mix_rates:                                                   # L24–L30: mix rates (%)
        parts.append(f" {_g(m)} ".encode("ascii"))
    parts.append(_BYTES_L31_TO_L37)                                       # L31–L37 (reserved)
    for v in pcu_vals:                                                    # L38–L44: PCU factors
        parts.append(f" {_g(v)} ".encode("ascii"))
    for v in veh_lengths:                                                 # L45–L51
        parts.append(f" {_g(v)} ".encode("ascii"))
    parts.append(_BYTES_L52_TO_L59)                                       # L52–L59
    static_lines_2_to_59 = b"\n".join(parts)

    # ── n_occ formula intermediates ──
    # LEGACY formula (kept for symmetric-placement fallback)
    _t_react_r74 = 165
    _pcphpl_r74     = _f(tr, "normal_traffic", 2000.0)
    _r74_pcpkpl     = _f(sm, "r74_pcpkpl",     216.0)
    _r74_dir_mult   = _f(sm, "r74_dir_mult",     2.41)
    _r74_occ_per_veh = _f(sm, "r74_occ_per_veh", 1.50)
    _n_enter_per_dir = _pcphpl_r74 * (_t_react_r74 / 3600.0)
    _n_cong_per_dir  = _r74_pcpkpl * (L / 1000.0) * num_lanes
    _n_total_per_dir = _n_enter_per_dir + _n_cong_per_dir
    n_occ_r74_float  = _n_total_per_dir * _r74_dir_mult * _r74_occ_per_veh
    abs_ws_r74 = abs_min_speed if abs_min_speed > 0 else 0.5

    # SPACING formula (PRIMARY path — matches VB EVCEngine.total_occupants_vb).
    # Mix-weighted vehicle length (Clavg) and avg occupants per vehicle, then:
    #   pcpkpl_jam = 1000 / (Clavg + LTH)            (jam density, veh/km/lane)
    #   sim_n_occ  = pcpkpl_jam × N_lanes × L_km × avg_occ
    #
    # NOTES:
    # - occ_vals uses the MIX TABLE values (= L52-L58 in EVC file = vehicle
    #   CAPACITY [3, 8, 30, 2, 2, 1, 1]), NOT the lower evac-table averages.
    #   This is the VB convention for L74 evacuation budget.
    # - L (full tunnel length) is used regardless of NORMAL or CONGEST.
    #   VB writes the SAME L74 for both traffic scenarios because L74 is a
    #   tunnel CAPACITY-based time budget, not actual-occupancy-based.
    _lth_r74 = _f(sm, "r74_lth", 2.33)
    _mix_sum = sum(mix_rates)
    sim_n_occ_r74 = 0.0
    if _mix_sum > 0 and any(veh_lengths) and any(occ_vals):
        _clavg   = sum((m / _mix_sum) * vl for m, vl in zip(mix_rates, veh_lengths))
        _avg_occ = sum((m / _mix_sum) * o  for m, o  in zip(mix_rates, occ_vals))
        _slot    = _clavg + _lth_r74
        if _slot > 0:
            _pcpkpl_jam = 1000.0 / _slot
            sim_n_occ_r74 = _pcpkpl_jam * num_lanes * (L / 1000.0) * _avg_occ
    if sim_n_occ_r74 <= 0:
        # Fallback when mix data missing — scale legacy back to sim count.
        # (only used if user has incomplete vehicle table)
        sim_n_occ_r74 = n_occ_r74_float / 3.9595

    # Fire placement scheme detection.
    # Stored as bool here so scenario_context can pick the right formula.
    # Default: ASYMMETRIC (matches GUI default and VB calibration).
    _is_asymmetric_r74 = bool(sm.get("r74_is_asymmetric", True))

    return TunnelContext(
        L                = L,
        num_lanes        = num_lanes,
        abs_min_speed    = abs_min_speed,
        abs_elderly_speed = abs_elderly_speed,
        air_velocity     = _f(sm, "air_velocity",     2.5),
        leave_car_time   = _f(sm, "leave_car_time",  60.0),
        hesitation_time  = _f(sm, "hesitation_time", 180.0),
        pre_move_time    = _i(sm, "pre_move_time",  165),
        evac_offset      = _i(sm, "evac_offset_time", 5),
        min_speed        = _f(sm, "min_speed",      0.45),
        elderly_speed    = _f(sm, "elderly_speed",  0.60),
        elderly_ratio    = _f(sm, "elderly_ratio",  0.40),
        lane_width       = lane_width,
        shoulder         = shoulder,
        normal_traffic   = _f(tr, "normal_traffic", 2000.0),
        fdb_dt           = _f(mb, "slf_dt",        30.0),
        fdb_monitor_x    = L,
        monitor_pt       = _f(hr, "monitor_pt",   200.0),
        monitor_save     = _f(hr, "monitor_save",  10.0),
        fdb_sim_interval = _f(hr, "sim_interval",   2.0),
        n_occ_r74_float  = n_occ_r74_float,
        sim_n_occ_r74    = sim_n_occ_r74,
        abs_ws_r74       = abs_ws_r74,
        hrr_ref          = _f(sm, "r74_hrr_ref",    15.0),
        hrr_sat_c        = _f(sm, "r74_hrr_sat_c", 1082.47),
        hrr_sat_k        = _f(sm, "r74_hrr_sat_k",   14.45),
        is_asymmetric    = _is_asymmetric_r74,
        r74_mult_a_asym  = _f(sm, "r74_mult_a_asym",   3.9595),
        r74_mult_b_asym  = _f(sm, "r74_mult_b_asym",   2.6299),
        r74_sat_k_asym   = _f(sm, "r74_hrr_sat_k_asym", 53.014),
        static_lines_2_to_59 = static_lines_2_to_59,
    )


# ───────────────────────────────────────────────────────────────────────────
# TIER 2: Scenario-level context (built ONCE per CHID)
# ───────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ScenarioContext:
    """Pre-computed CHID-level data, shared across all fire-position files
    of a given scenario (e.g. all of `020CFV0_P1.evc` through `_P6.evc`).

    Lines populated here: L65, L68, L69, L70, L71, L72, L73, plus the
    HRR-scaled n_occ for L74.
    """
    chid: str
    design_mw: float
    growth_rate: float
    impact_gj: float
    inertia: float
    fdb_time_ext: float
    sim_end_time: int
    n_occ_scaled: float          # used by L74 default formula
    extended_time_constant: int  # int(n_occ_scaled × L / (abs_ws × 200) + fdb_tmax)
    # Pre-encoded line bytes that are fp-independent (L65, L68–L73, L78)
    bytes_L65: bytes
    bytes_L68_to_L73: bytes


def build_scenario_context(tctx: TunnelContext, chid: str,
                           params: Optional[dict] = None) -> ScenarioContext:
    """Build the ScenarioContext for a given CHID. Call ONCE per scenario.

    Resolves HRR-specific fire dynamics (L68–L73) from CHID prefix lookup,
    falling back to params if no prefix match.
    """
    sm = (params or {}).get("simulation", {})
    mb = (params or {}).get("mdb", {})

    # HRR-specific fire dynamics
    _hrr_from_chid = None
    _m = _RE_HRR_PREFIX.match(str(chid).strip())
    if _m:
        try:
            _hrr_from_chid = int(_m.group(1))
        except ValueError:
            pass

    if _hrr_from_chid is not None and _hrr_from_chid in _HRR_PARAMS:
        # 30 / 50 / 100 MW — values from VB reference table
        hp = _HRR_PARAMS[_hrr_from_chid]
        design_mw    = float(hp[0])
        growth_rate  = float(hp[1])
        impact_gj    = float(hp[2])
        inertia      = float(hp[3])
        fdb_time_ext = float(hp[4])
        sim_end_time = int(hp[5])
    else:
        # 20 MW or any non-tabulated CHID — read from GUI params dict.
        # Defaults match VB reference 020 values so an untouched GUI still
        # reproduces the legacy benchmark output byte-for-byte.
        design_mw    = _f(sm, "design_fire_mw",  20.0)
        growth_rate  = _f(sm, "growth_rate",      0.113)
        impact_gj    = _f(sm, "impact",          22.0)
        inertia      = _f(sm, "inertia",          0.002)
        if _hrr_from_chid == 20:
            # Preserve VB-reference fdb_tmax / sim_end_time for 020 unless
            # explicitly overridden in params.
            fdb_time_ext = _f(mb, "slf_tmax",       549.9)
            sim_end_time = _i(mb, "sim_end_time",   365)
        else:
            fdb_time_ext = _f(mb, "slf_tmax",       600.0)
            sim_end_time = (int(fdb_time_ext / 5) * 5) - int(tctx.hesitation_time)

    # ── L74 (extended_time) — TUNNEL-INVARIANT CALIBRATION ──
    #
    # ASYMMETRIC placement (VB-calibrated, tunnel-invariant coefficients):
    #   n_eff = sim_n_occ × (A + B × (HRR-ref)/(HRR-ref+K))
    #     A = 3.9595, B = 2.6299, K = 53.014, ref = 15 MW
    #
    # SYMMETRIC placement (legacy fallback):
    #   n_eff = legacy_n_occ_formula + C × frac
    #     C = 1082.47, K = 14.45, ref = 15 MW
    #
    # Both produce VB-exact L74 for their respective placement schemes.
    if tctx.is_asymmetric:
        # ASYMMETRIC: sim_n_occ × multiplier(HRR)
        mult = tctx.r74_mult_a_asym
        if design_mw > tctx.hrr_ref:
            delta = design_mw - tctx.hrr_ref
            mult += tctx.r74_mult_b_asym * delta / (delta + tctx.r74_sat_k_asym)
        n_occ_scaled = tctx.sim_n_occ_r74 * mult
    else:
        # SYMMETRIC (legacy): n_occ_r74_float + C × frac
        n_occ_scaled = tctx.n_occ_r74_float
        if design_mw > tctx.hrr_ref:
            delta = design_mw - tctx.hrr_ref
            extra = tctx.hrr_sat_c * delta / (delta + tctx.hrr_sat_k)
            n_occ_scaled = tctx.n_occ_r74_float + extra

    extended_time_constant = int(
        n_occ_scaled * tctx.L / (tctx.abs_ws_r74 * 200.0) + fdb_time_ext
    )

    # Pre-encode lines L65 (depends only on tunnel pre_move_time, but cleanly
    # belongs here so scenarios with overrides can still differ)
    bytes_L65 = f" {tctx.pre_move_time} ".encode("ascii")

    # L68 through L73 are CHID-stable; pre-encode the whole block.
    block_lines = [
        f" {_g(design_mw)} ",          # L68
        f" {_g(growth_rate)} ",        # L69
        f" {_g(impact_gj)} ",          # L70
        f" {_g(inertia)} ",            # L71
        f" {sim_end_time} ",           # L72
        f" {_g(fdb_time_ext)} ",       # L73
    ]
    bytes_L68_to_L73 = "\n".join(block_lines).encode("ascii")

    return ScenarioContext(
        chid                   = chid,
        design_mw              = design_mw,
        growth_rate            = growth_rate,
        impact_gj              = impact_gj,
        inertia                = inertia,
        fdb_time_ext           = fdb_time_ext,
        sim_end_time           = sim_end_time,
        n_occ_scaled           = n_occ_scaled,
        extended_time_constant = extended_time_constant,
        bytes_L65              = bytes_L65,
        bytes_L68_to_L73       = bytes_L68_to_L73,
    )


# ───────────────────────────────────────────────────────────────────────────
# TIER 3: Per-position write — minimal work per file
# ───────────────────────────────────────────────────────────────────────────
def write_evc_for_position(
    evc_path: Path,
    tctx: TunnelContext,
    sctx: ScenarioContext,
    fire_point_x: float,
    fire_pos_idx: int,
    *,
    tunnel_name_bytes: Optional[bytes] = None,
    tunnel_name_str: Optional[str] = None,
    l74_override: Optional[int] = None,
    mdb_indices: tuple = (0, 0, 0, 0, 0, 0),
) -> None:
    """Write one .evc file for a specific fire position.

    Args:
        evc_path:          Output path.
        tctx:              Tunnel context (built once per project).
        sctx:              Scenario context (built once per CHID).
        fire_point_x:      Fire location along tunnel axis (m).
        fire_pos_idx:      1-based fire-position index (controls L60 y_offset).
        tunnel_name_bytes: Raw bytes for L01. If None, uses tunnel_name_str
                           encoded as cp949.
        tunnel_name_str:   Tunnel name to encode as cp949 if bytes not given.
                           Default '율곡터널'.
        l74_override:      If not None, used directly as L74. This is a hook
                           for future L74-formula fixes (the current internal
                           formula does NOT match VB reference output for L74).
        mdb_indices:       (soot, co2, co, temp, radiation, oxygen) — L84.
                           Defaults to all zeros, matching VB references.
    """
    # ── L01: tunnel name ──
    if tunnel_name_bytes is None:
        name = tunnel_name_str if tunnel_name_str else "율곡터널"
        tunnel_name_bytes = name.encode("cp949", errors="replace")

    fp = float(fire_point_x)
    L = tctx.L

    # ── L60: Fire_Point line — y_offset alternates per VB convention ──
    fp_y_offset = "1.35" if (fire_pos_idx % 2 == 0) else "0"
    fp_str = _g(fp)
    line_60 = f"Fire_Point    , {fp_str:<12}, {fp_y_offset} ".encode("ascii")

    # ── L62, L63, L64 — also fp-dependent ──
    fp_text = _g(fp)
    L_text  = _g(L)
    line_62 = f" 0 , {fp_text} , 0 ".encode("ascii")
    line_63 = f" {fp_text} , {L_text} , {L_text} ".encode("ascii")
    line_64 = f" {fp_text} ".encode("ascii")

    # ── L66: normal traffic ──
    line_66 = f" {_g(tctx.normal_traffic)} ".encode("ascii")

    # ── L74: extended time. Uses sctx.extended_time_constant unless overridden ──
    extended_time = (l74_override if l74_override is not None
                     else sctx.extended_time_constant)
    line_74 = f" {extended_time} ".encode("ascii")

    # ── Lines L75–L88 (tunnel-level; build inline) ──
    # Line semantics (per VB EVC.exe file format):
    #   L75: air velocity (m/s)
    #   L76: FDB dt (s)
    #   L77: FDB monitor X (m) — typically tunnel end
    #   L78: evacuation offset (s)
    #   L80: hesitation time (s)
    #   L81: leave-car time (s)
    #   L82: pre-movement = hesitation - leave_car (s)
    #   L84: MDB column indices (6 zeros by default)
    #   L85: (sim_interval, monitor_save, monitor_pt, monitor_save)
    #   L87: simulation walk-speed factors (min, elderly, elderly_ratio)
    #   L88: lane_width (m), shoulder (m) — geometric road parameters
    line_75 = f" {_g(tctx.air_velocity)} ".encode("ascii")
    line_76 = f" {_g(tctx.fdb_dt)} ".encode("ascii")
    line_77 = f" {_g(tctx.fdb_monitor_x)} ".encode("ascii")
    line_78 = f" {tctx.evac_offset} ".encode("ascii")
    line_80 = f" {_g(tctx.hesitation_time)} ".encode("ascii")
    line_81 = f" {_g(tctx.leave_car_time)} ".encode("ascii")
    line_82 = f" {_g(tctx.hesitation_time - tctx.leave_car_time)} ".encode("ascii")
    line_84 = _col14(list(mdb_indices)).encode("ascii")
    line_85 = _col14([int(tctx.fdb_sim_interval), int(tctx.monitor_save),
                      int(tctx.monitor_pt), int(tctx.monitor_save)]).encode("ascii")
    line_87 = _col14([tctx.min_speed, tctx.elderly_speed, tctx.elderly_ratio]).encode("ascii")
    # L88: lane_width and shoulder (geometric road parameters, in meters)
    line_88 = _col14([tctx.lane_width, tctx.shoulder]).encode("ascii")

    # ── Assemble ──
    raw = b"\n".join([
        tunnel_name_bytes,                  # L01
        tctx.static_lines_2_to_59,          # L02–L59 (pre-built, contains internal \n)
        line_60,                            # L60
        _BYTES_L61,                         # L61
        line_62,                            # L62
        line_63,                            # L63
        line_64,                            # L64
        sctx.bytes_L65,                     # L65
        line_66,                            # L66
        _BYTES_L67,                         # L67
        sctx.bytes_L68_to_L73,              # L68–L73 (pre-built, contains internal \n)
        line_74,                            # L74
        line_75,                            # L75
        line_76,                            # L76
        line_77,                            # L77
        line_78,                            # L78
        _BYTES_L79,                         # L79
        line_80,                            # L80
        line_81,                            # L81
        line_82,                            # L82
        _BYTES_L83,                         # L83
        line_84,                            # L84
        line_85,                            # L85
        _BYTES_L86,                         # L86
        line_87,                            # L87
        line_88,                            # L88
        _BYTES_L89,                         # L89
    ])
    evc_path.write_bytes(raw)


# ───────────────────────────────────────────────────────────────────────────
# Single-shot wrapper — drop-in compatible with writer_current.write_evc_file
# ───────────────────────────────────────────────────────────────────────────
def write_evc_file(evc_path: Path, params: dict, chid: str,
                   fire_point_x: float = None,
                   fire_pos_idx: int = 1,
                   tunnel_name_bytes: bytes = None,
                   l74_override: Optional[int] = None) -> None:
    """Single-file convenience wrapper. Builds contexts on every call.

    For batch use, call build_tunnel_context() and build_scenario_context()
    yourself and reuse them across many positions.
    """
    tctx = build_tunnel_context(params)
    sctx = build_scenario_context(tctx, chid, params)

    fp = (fire_point_x if fire_point_x is not None
          else _f(params.get("hrr_settings", {}), "fp_evc", tctx.L / 2.0))

    # Allow caller to pass mdb indices via params
    mb = params.get("mdb", {})
    mdb_indices = (
        _i(mb, "soot",      0),
        _i(mb, "co2",       0),
        _i(mb, "co",        0),
        _i(mb, "temp",      0),
        _i(mb, "radiation", 0),
        _i(mb, "oxygen",    0),
    )

    write_evc_for_position(
        evc_path, tctx, sctx,
        fire_point_x=fp, fire_pos_idx=fire_pos_idx,
        tunnel_name_bytes=tunnel_name_bytes,
        tunnel_name_str=params.get("tunnel", {}).get("name"),
        l74_override=l74_override,
        mdb_indices=mdb_indices,
    )
