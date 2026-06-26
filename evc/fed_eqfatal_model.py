"""
fed_eqfatal_model.py  (v3 — single VB-exact source of truth)
============================================================
FED (Fractional Effective Dose) and EQ_Fatal model for the tunnel-evacuation
engine in the VB6 program (QRA_Road).

This module is now the ONE place the FED rate lives. ``fed_rate_binary`` below
reproduces — arithmetic-for-arithmetic — the rate that ``evc_engine`` actually
runs and that was numerically validated against VB's own ``.SET`` output. The
engine method ``EVCEngine._fed_rate_binary`` should be reduced to a thin call
into this function (see "ENGINE WIRING" at the bottom) so the two can never
drift, exactly as ``l74_model.l74_time_from_neff`` did for the L74 budget.

Reconstructed from:
  1. Ghidra decompilation of the FED routines FUN_004956E0 / FUN_00497950
     (the two functions the .SET writers call; they share one model applied to
     two occupant arrays, DAT_004a60b4 and DAT_004a60d0).
  2. Float constants decoded directly from the binary (IEEE-754).
  3. Numerical validation against the real .SET output (020CFV0_P1, 332 occupant
     records; 020CFV0_P3 as a no-exposure control).

================================================================================
WHAT THE VB RATE IS  (per-minute FED rate, summed over terms)
================================================================================
    rate = r_CO + r_heat + r_rad + r_CO2hyp [+ r_O2]

  CO term  -> .SET FED2        (CONFIRMED, R^2 = 0.74 vs .SET)
      r_CO = (CO_ppm**1.036 / 36177.26) * RMV          for CO > 0, else 0
      RMV  = exp(0.1903 * CO2_pct + 2.004)   [ /7.1 when flag DAT_004a6000==0 ]
      In the validated decks CO2 ~ 0, so RMV is effectively exp(2.004)/7.1; the
      CO2 coupling is real in the binary but DORMANT at low CO2.

  HEAT term -> .SET FED4        (CONFIRMED form, R^2 = 0.76 vs .SET)
      r_heat = exp(0.0273 * T_degC - 5.1849)
      GUARD TENSION (read this): the *decompile* gates this with `If Temp > 40
      Then` (integer 0x28). But VB's *output distribution* shows FED>=0.1 for
      essentially ALL occupants in every FVM row — including P1 where EQ=0 —
      which only happens if the term accrues UNCONDITIONALLY (~0.0097/min at
      20 C). The engine resolves this empirically with heat_always=True (the
      tiny baseline is rendered harmless by the shifted EQ bands). Default here
      is therefore heat_always=True to match the validated engine path; set
      heat_always=False for the decompile-literal `T > 40` gate.

  RADIANT term -> occupant field +0x80  (engine addition; Purser radiant form)
      r_rad = q_kW**1.33 / 80.0           for q > 2.5 kW/m^2, else 0
      Needed because VB's near-fire FED>=0.4 groups (e.g. 030N/FV0 P6) sit in a
      clean-air upstream queue and are otherwise unreachable; only radiant flux
      during the pre-movement dwell doses them. Requires a RADI column in the
      field; if none is supplied this term is 0.

  CO2 hyperventilation -> small additive term  (binary; guard CO2 < 11)
      r_CO2hyp = exp((CO2_pct - 20.721) * 0.511 - 8.55)   for CO2 < 11, else 0

  O2 depletion -> DORMANT (constants from binary; depletion form NOT yet
      validated against a high-depletion .SET; off unless include_o2=True)
      r_O2 = exp(0.5189 * max(20.72 - O2_pct, 0) - 6.1623)

  FED_total = FED2 + FED4 + FED7 in the .SET (cols FED3/5/6 are unused zeros).
  FED7 (.SET col 30) is small (<=0.035) and fits nothing tried above R^2=0.04 —
  a trajectory-dependent term a single endpoint snapshot can't reconstruct. It
  is NOT produced here; it is a documented minor unknown.

THE FLAG (DAT_004a6000, default 0):
  Selects between two constant-sets; its fingerprint is dividing the CO RMV by
  7.1 (flag==0) vs not. exp(2.004)/7.1 ~= exp(0.0101), i.e. flag==0 ~= the
  classic Purser CO coefficient. Keep co_rmv_div_7_1=True (the default) unless a
  .SET shows otherwise.

================================================================================
WALKING SPEED IS NOT IN THIS MODEL  (removed — see Jin note at the bottom)
================================================================================
VB's movement loop advances each occupant at a FIXED deck velocity; there is NO
soot/extinction input to the position update anywhere in the binary. Soot enters
ONLY through the FED accumulators above. The Jin smoke-speed reduction that used
to live in this file (PART 2) had no binary basis and was the direct cause of
the normal-queue over-dosing. Those functions are now hard-disabled; calling
them raises, so they cannot be silently re-wired. See the bottom of the file.
"""
from __future__ import annotations
import numpy as np

# ============================================================================
# BINARY CONSTANTS  (decoded from FUN_004956E0 / FUN_00497950; do not edit)
# ============================================================================
# CO term
CO_CONC_POW   = 1.036       # exponent on CO ppm
CO_DOSE_DIV   = 36177.26    # CO dose divisor  (engine knob VB_FED_CO_DIV)
CO_RMV_SLOPE  = 0.1903      # RMV exponent slope on CO2
CO_RMV_ADD    = 2.004       # RMV exponent add const
CO_RMV_DIV    = 7.1         # divides RMV when flag DAT_004a6000 == 0

# Heat term
HEAT_SLOPE    = 0.0273
HEAT_SUB      = 5.1849
HEAT_GUARD_C  = 40.0        # `If Temp > 40 Then` (integer 0x28); see heat note

# Radiant term (Purser radiant form q^1.33 / 80, gated by tolerance threshold)
RAD_GATE_KW   = 2.5         # Purser radiant tolerance ~2.5 kW/m^2
RAD_DENOM     = 80.0

# CO2 hyperventilation term (binary; guard CO2 < 11)
CO2H_SLOPE    = 0.511
CO2H_REF      = 20.721
CO2H_SUB      = 8.55
CO2H_GUARD    = 11.0

# O2 depletion term (DORMANT — constants from binary, form/guard not validated)
O2_SLOPE      = 0.5189
O2_SUB        = 6.1623
O2_AMBIENT    = 20.72

# EQ_Fatal accumulation
FED_CAP       = 2.0         # per-occupant cap before the EQ_Fatal sum (VB lets
                            # FED run past 1.0; the cap only bounds runaway)

# .SET / FDB conventions confirmed from the files
SET_COL = {  # 0-based column indices in the .SET row
    "time_s": 7, "temp": 17, "soot": 18, "co": 19, "o2": 20,
    "vis": 21, "co2": 22, "co23": 23,
    "FED_total": 24, "FED_CO": 25, "FED_unused3": 26,
    "FED_heat": 27, "FED_unused5": 28, "FED_unused6": 29, "FED7": 30,
}
FDB_DT = 30.0  # FDB sampling interval (s); SET time col is in seconds


# ============================================================================
# THE VB-EXACT RATE  (mirror of EVCEngine._fed_rate_binary)
# ============================================================================
def fed_rate_binary(co_ppm, co2_pct, o2_pct, temp_c, radi_kw=None,
                    *,
                    co_dose_div: float = CO_DOSE_DIV,
                    co_rmv_div_7_1: bool = True,
                    heat_always: bool = True,
                    heat_threshold_c: float = HEAT_GUARD_C,
                    rad_gate_kw: float = RAD_GATE_KW,
                    rad_denom: float = RAD_DENOM,
                    include_o2: bool = False):
    """Per-minute, binary-exact FED rate, summed over all VB terms.

    Vectorised: every argument may be a scalar or an array; the result has the
    broadcast shape. Multiply by exposure minutes and accumulate (capping at
    FED_CAP) to integrate a trajectory — see ``accumulate_fed``.

    The defaults reproduce the validated engine configuration EXACTLY:
        co_dose_div=36177.26, co_rmv_div_7_1=True, heat_always=True,
        rad_gate_kw=2.5, rad_denom=80.0, include_o2=False.
    Pass radi_kw=None to omit the radiant term (no RADI column available).
    """
    co  = np.asarray(co_ppm,  dtype=float)
    co2 = np.asarray(co2_pct, dtype=float)
    T   = np.asarray(temp_c,  dtype=float)

    # CO (-> FED2)
    rmv = np.exp(CO_RMV_SLOPE * co2 + CO_RMV_ADD)
    if co_rmv_div_7_1:
        rmv = rmv / CO_RMV_DIV
    r_co = np.where(co > 0.0, (co ** CO_CONC_POW) / co_dose_div * rmv, 0.0)

    # HEAT (-> FED4)
    if heat_always:
        r_heat = np.exp(HEAT_SLOPE * T - HEAT_SUB)
    else:
        r_heat = np.where(T > heat_threshold_c,
                          np.exp(HEAT_SLOPE * T - HEAT_SUB), 0.0)

    # RADIANT (Purser radiant form q^1.33 / 80, gated)
    if radi_kw is not None:
        q = np.asarray(radi_kw, dtype=float)
        r_rad = np.where(q > rad_gate_kw,
                         np.power(np.maximum(q, 1e-9), 1.33) / rad_denom, 0.0)
    else:
        r_rad = 0.0

    rate = r_co + r_heat + r_rad

    # CO2 hyperventilation (small; guard CO2 < 11)
    r_co2 = np.where(co2 < CO2H_GUARD,
                     np.exp((co2 - CO2H_REF) * CO2H_SLOPE - CO2H_SUB), 0.0)
    rate = rate + r_co2

    # O2 depletion (dormant unless enabled)
    if include_o2:
        o2 = np.asarray(o2_pct, dtype=float)
        depl = np.maximum(O2_AMBIENT - o2, 0.0)
        rate = rate + np.exp(O2_SLOPE * depl - O2_SUB)

    return rate


def fed_rate_components(co_ppm, co2_pct, temp_c, o2_pct=None, radi_kw=None,
                        *,
                        co_dose_div: float = CO_DOSE_DIV,
                        co_rmv_div_7_1: bool = True,
                        heat_always: bool = True,
                        heat_threshold_c: float = HEAT_GUARD_C,
                        rad_gate_kw: float = RAD_GATE_KW,
                        rad_denom: float = RAD_DENOM,
                        include_o2: bool = False):
    """Same model as ``fed_rate_binary`` but returns the per-term breakdown
    (per minute) instead of the sum. Used by the .SET validation harness, which
    fits FED2 (CO) and FED4 (heat) against their own .SET columns.

    Returns dict with keys: FED_CO, FED_heat, FED_rad, FED_CO2hyp,
    and FED_O2 only when include_o2=True.
    """
    co  = np.asarray(co_ppm,  dtype=float)
    co2 = np.asarray(co2_pct, dtype=float)
    T   = np.asarray(temp_c,  dtype=float)

    rmv = np.exp(CO_RMV_SLOPE * co2 + CO_RMV_ADD)
    if co_rmv_div_7_1:
        rmv = rmv / CO_RMV_DIV
    r_co = np.where(co > 0.0, (co ** CO_CONC_POW) / co_dose_div * rmv, 0.0)

    if heat_always:
        r_heat = np.exp(HEAT_SLOPE * T - HEAT_SUB)
    else:
        r_heat = np.where(T > heat_threshold_c,
                          np.exp(HEAT_SLOPE * T - HEAT_SUB), 0.0)

    if radi_kw is not None:
        q = np.asarray(radi_kw, dtype=float)
        r_rad = np.where(q > rad_gate_kw,
                         np.power(np.maximum(q, 1e-9), 1.33) / rad_denom, 0.0)
    else:
        r_rad = np.zeros_like(r_co)

    r_co2 = np.where(co2 < CO2H_GUARD,
                     np.exp((co2 - CO2H_REF) * CO2H_SLOPE - CO2H_SUB), 0.0)

    out = {"FED_CO": r_co, "FED_heat": r_heat,
           "FED_rad": r_rad, "FED_CO2hyp": r_co2}
    if include_o2:
        if o2_pct is None:
            raise ValueError("include_o2=True requires o2_pct")
        o2 = np.asarray(o2_pct, dtype=float)
        depl = np.maximum(O2_AMBIENT - o2, 0.0)
        out["FED_O2"] = np.exp(O2_SLOPE * depl - O2_SUB)
    return out


# Backwards-compatible alias: the old name returned a {FED_CO, FED_heat} dict.
# It now returns the full component dict from the same VB-exact model.
def fed_rate(co_ppm, co2_pct, temp_c, o2_pct=None,
             co_rmv_div_7_1=True, include_o2=False):
    """DEPRECATED NAME — use ``fed_rate_components`` (full breakdown) or
    ``fed_rate_binary`` (summed). Kept so existing callers/harness keep working;
    forwards to ``fed_rate_components`` with the validated defaults."""
    return fed_rate_components(co_ppm, co2_pct, temp_c, o2_pct,
                              co_rmv_div_7_1=co_rmv_div_7_1,
                              include_o2=include_o2)


def accumulate_fed(exposure_timeseries, dt_seconds=FDB_DT,
                   *, co_rmv_div_7_1=True, heat_always=True,
                   include_o2=False, cap=FED_CAP):
    """Integrate FED over one occupant's exposure history, VB-style.

    exposure_timeseries: iterable of (co_ppm, co2_pct, temp_c[, o2_pct[, radi_kw]])
    per FDB frame. Accumulates rate * (dt/60) once per frame and caps the
    running total at ``cap`` (FED_CAP), exactly as the engine's per-frame loop.

    Returns (fed_total, components_summed).
    """
    dt_min = dt_seconds / 60.0
    comp = {"FED_CO": 0.0, "FED_heat": 0.0, "FED_rad": 0.0, "FED_CO2hyp": 0.0}
    if include_o2:
        comp["FED_O2"] = 0.0
    total = 0.0
    for step in exposure_timeseries:
        co, co2, temp = step[0], step[1], step[2]
        o2   = step[3] if len(step) > 3 else None
        radi = step[4] if len(step) > 4 else None
        r = fed_rate_components(co, co2, temp, o2, radi,
                               co_rmv_div_7_1=co_rmv_div_7_1,
                               heat_always=heat_always, include_o2=include_o2)
        for k in comp:
            comp[k] += float(r[k]) * dt_min
        total = min(total + float(sum(r[k] for k in comp)) * dt_min, cap)
    return total, comp


def eq_fatal(occupant_fed_totals, clip=True):
    """Scenario EQ_Fatal = expected-fatality sum over occupants. clip caps each
    occupant at 1.0 (the VB convention used by evc_history.snapshot). A
    zero-exposure scenario gives exactly 0.0."""
    fed = np.asarray(occupant_fed_totals, dtype=float)
    contrib = np.clip(fed, 0.0, 1.0) if clip else np.maximum(fed, 0.0)
    return float(contrib.sum())


def fatality_prob(fed_total):
    """Per-occupant incapacitation indicator at the VB threshold (FED >= 1.0).
    VB latches incapacitation at FED >= 1; this returns that step function."""
    return (np.asarray(fed_total, dtype=float) >= 1.0).astype(float)


def risk_index(frequency_per_yr, eq_fatal_value):
    """Per-scenario Risk Index = Frequency/yr * EQ_Fatal."""
    return frequency_per_yr * eq_fatal_value


# ============================================================================
# VALIDATION HARNESS (reproduces the fits used to confirm the model)
# ============================================================================
def validate_against_set(set_path, co_rmv_div_7_1=True, heat_always=True):
    """Fit confirmed rates against a real .SET file; prints per-term R^2.
    Run this whenever a new .SET arrives to re-check the bindings/flag."""
    rows = []
    for line in open(set_path, encoding="latin-1"):
        p = line.split()
        if len(p) >= 31:
            rows.append([float(x) for x in p[:31]])
    a = np.array(rows)
    if a.size == 0:
        print(f"{set_path}: no parseable rows"); return
    t = a[:, SET_COL["time_s"]] / 60.0
    m = a[:, SET_COL["FED_total"]] > 0
    if m.sum() == 0:
        print(f"{set_path}: no exposed occupants (control scenario)"); return

    def r2(rate, F):
        x = (rate * t)[m]; y = F[m]
        if np.dot(x, x) == 0:
            return float("nan"), float("nan")
        k = np.dot(x, y) / np.dot(x, x)
        return k, 1 - np.sum((y - k * x) ** 2) / np.sum((y - y.mean()) ** 2)

    rt = fed_rate_components(a[:, SET_COL["co"]], a[:, SET_COL["co2"]],
                            a[:, SET_COL["temp"]],
                            co_rmv_div_7_1=co_rmv_div_7_1,
                            heat_always=heat_always)
    k_co, r2_co = r2(rt["FED_CO"],   a[:, SET_COL["FED_CO"]])
    k_ht, r2_ht = r2(rt["FED_heat"], a[:, SET_COL["FED_heat"]])
    print(f"{set_path}: exposed={int(m.sum())}/{len(a)}")
    print(f"  CO   -> FED2: k={k_co:.4g}  R2={r2_co:+.3f}")
    print(f"  heat -> FED4: k={k_ht:.4g}  R2={r2_ht:+.3f}")


# ============================================================================
# REMOVED: Jin (1978) walking-speed-in-smoke  (NOT in the VB binary)
# ----------------------------------------------------------------------------
# VB advances occupant position with a FIXED deck velocity; no soot/extinction
# term touches the position update anywhere in the binary. Soot enters ONLY via
# the FED accumulators above. The former walking_speed()/soot_to_extinction()
# here were a pre-RE carry-over with no binary basis and were the direct cause
# of the normal-queue over-dosing (they slowed walkers in smoke, inflating
# dwell time and FED). They are hard-disabled so they cannot be silently
# re-wired. Walk speed lives in evc_engine ("SPEED DECOUPLED FROM SMOKE").
# ============================================================================
_JIN_REMOVED_MSG = (
    "Jin smoke-speed reduction is NOT part of the VB model. VB moves occupants "
    "at a fixed deck velocity; soot affects only FED, never walking speed. "
    "Re-enabling this reintroduces the normal-queue over-dose bug. If you need "
    "a non-VB physical-accuracy study, implement it explicitly in the engine "
    "behind its own flag — do not resurrect this function."
)


def walking_speed(*_args, **_kwargs):
    raise NotImplementedError(_JIN_REMOVED_MSG)


def soot_to_extinction(*_args, **_kwargs):
    raise NotImplementedError(_JIN_REMOVED_MSG)


# ============================================================================
# ENGINE WIRING (recommended — makes this module the single source of truth)
# ----------------------------------------------------------------------------
# Replace the body of EVCEngine._fed_rate_binary in evc_engine.py with a call
# into this module, so the engine and the standalone model can never drift:
#
#     from fed_eqfatal_model import fed_rate_binary   # (or: from .fed_eqfatal_model ...)
#
#     def _fed_rate_binary(self, co_arr, co2_arr, o2_arr, temp_arr, radi_arr=None):
#         return fed_rate_binary(
#             co_arr, co2_arr, o2_arr, temp_arr, radi_arr,
#             co_dose_div     = float(getattr(self, 'VB_FED_CO_DIV', 36177.26)),
#             co_rmv_div_7_1  = self._FED_CO_RMV_DIV_71,
#             heat_always     = bool(getattr(self, 'FED_HEAT_ALWAYS', True)),
#             heat_threshold_c= float(getattr(self, 'FED_HEAT_THRESHOLD_C', 40.0)),
#             rad_gate_kw     = float(getattr(self, 'RAD_FED_GATE_KW', 2.5)),
#             rad_denom       = float(getattr(self, 'RAD_FED_DENOM', 80.0)),
#             include_o2      = self._FED_INCLUDE_O2,
#         )
#
# The defaults above are the engine's current class defaults, so this is
# behaviour-preserving. The VB_NORMAL_FED_SCALE multiplier (engine default 1.0)
# stays in the engine — it is a traffic-mode scale applied AFTER the rate, not
# part of the binary rate itself.
# ============================================================================


if __name__ == "__main__":
    # ── 1. fed_rate_binary reproduces the engine's inline arithmetic exactly ──
    #    (the same identity-check pattern as l74_model.py)
    import random
    rng = random.Random(0)
    for _ in range(20000):
        co   = rng.uniform(0, 2000)
        co2  = rng.uniform(0, 15)
        o2   = rng.uniform(15, 21)
        T    = rng.uniform(10, 200)
        q    = rng.uniform(0, 40) if rng.random() < 0.5 else None
        div71      = rng.random() < 0.5
        heat_alw   = rng.random() < 0.5
        inc_o2     = rng.random() < 0.5

        # reference = the exact engine expression (evc_engine._fed_rate_binary)
        rmv = np.exp(0.1903 * co2 + 2.004)
        if div71:
            rmv = rmv / 7.1
        r_co = (co ** 1.036) / 36177.26 * rmv if co > 0.0 else 0.0
        if heat_alw:
            r_heat = np.exp(0.0273 * T - 5.1849)
        else:
            r_heat = np.exp(0.0273 * T - 5.1849) if T > 40.0 else 0.0
        if q is not None:
            r_rad = (max(q, 1e-9) ** 1.33) / 80.0 if q > 2.5 else 0.0
        else:
            r_rad = 0.0
        ref = r_co + r_heat + r_rad
        r_co2 = np.exp((co2 - 20.721) * 0.511 - 8.55) if co2 < 11.0 else 0.0
        ref = ref + r_co2
        if inc_o2:
            ref = ref + np.exp(0.5189 * max(20.72 - o2, 0.0) - 6.1623)

        got = float(fed_rate_binary(co, co2, o2, T, q,
                                    co_rmv_div_7_1=div71, heat_always=heat_alw,
                                    include_o2=inc_o2))
        assert abs(got - float(ref)) < 1e-9, (got, float(ref), co, co2, o2, T, q)

    # ── 2. components sum to the binary rate ──
    comp = fed_rate_components(800.0, 5.0, 90.0, 19.5, 7.0, include_o2=True)
    summed = float(fed_rate_binary(800.0, 5.0, 19.5, 90.0, 7.0, include_o2=True))
    assert abs(sum(float(v) for v in comp.values()) - summed) < 1e-9

    # ── 3. EQ_Fatal clip-sum and the FED>=1 latch ──
    assert eq_fatal([0.0, 0.5, 1.0, 2.0]) == 2.5      # clipped: 0+0.5+1+1
    assert list(fatality_prob([0.3, 1.0, 1.7])) == [0.0, 1.0, 1.0]
    assert eq_fatal([0.0, 0.0]) == 0.0                # zero-exposure -> 0

    # ── 4. Jin functions are hard-disabled ──
    for fn in (walking_speed, soot_to_extinction):
        try:
            fn(0.6, 1.0)
            raise SystemExit("Jin function was callable — neutralization failed")
        except NotImplementedError:
            pass

    # ── 5. demo trajectory ──
    demo = [  # co_ppm, co2_pct, temp_c, o2_pct, radi_kw  per 30 s
        (300.0, 0.3, 45.0, 20.6, 0.0),
        (500.0, 0.5, 60.0, 20.2, 3.0),
        (800.0, 0.68, 90.0, 19.8, 7.0),
    ]
    fed, comps = accumulate_fed(demo)
    print("Demo FED total:", round(fed, 4))
    print("Components:", {k: round(v, 4) for k, v in comps.items()})
    print("EQ_Fatal (1 occupant):", eq_fatal([fed]))
    print("fed_eqfatal_model: all checks passed")
