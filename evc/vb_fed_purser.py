"""
vb_fed_purser.py — faithful port of the VB6 per-occupant FED accumulation.

Source of truth: the decompiled exposure loop FUN at 0x004956E0 (== MOV.txt),
which walks every occupant (record stride 0x94 bytes in DAT_004a60b4) and, per
timestep, accumulates five Purser dose components into per-occupant fields.

Every constant below was recovered directly from the IEEE-754 dwords in the
decompile (not fitted). Provenance is given per line as  ⟨MOV.txt:line⟩  and the
raw dword pair where applicable.

    field  +0x6c   HEAT      exp(0.0273*T - 5.1849)              gate T > 40C      ⟨436,445-463⟩
    field  +0x74   CO        CO^1.036 / 36177.26 * VCO2          gate CO > 0       ⟨360,368-384⟩
    field  +0x70   CO2(dir)  exp(0.5189*CO2 - 6.1623)            gate CO2 > 1.0    ⟨405,414-432⟩
    field  +0x78   O2        exp(0.54*(20.721 - O2) - 8.13)      gate O2 < 11      ⟨309,318-339,579-600⟩
    field  +0x80   SOOT      local_dc * 80 / 1.33^soot                            ⟨255-268,554-566⟩
    VCO2 (multiplier on CO)  exp(0.1903*CO2 + 2.004)                              ⟨341-356,386-401⟩

Decoded dwords (verified with struct.unpack):
    0x40000831 26e978d5 -> 2.004      (CO2 hyperventilation intercept)
    0x4014bd56 6cf41f21 -> 5.1849     (heat intercept)
    0x40e1aa28 51eb851f -> 36177.26   (CO divisor; 1/36177.26 = 2.7642e-5 = Purser CO coeff)
    0x4018a631 f8a0902e -> 6.1623     (direct-CO2 intercept)
    0x3fe147ae 147ae148 -> 0.54       (O2 slope, pass A)
    0x3fe05a1c ac083127 -> 0.511      (O2 slope, pass B / two-way bore)

TWO UNKNOWNS that are NOT in MOV.txt and must come from the caller / .SET:
  1. STEP_NORM (= local_dc, set at MOV.txt:47 as 5 / DAT_004a66e8).  This is the
     per-timestep normaliser. Heat/CO2/O2 divide by it; CO and soot multiply by
     it. Its numeric value lives in DAT_004a66e8 (a .SET / DAT dump), so it is a
     PARAMETER here, not a literal. With a dt-seconds timestep and per-minute
     Purser rates the expected value is dt/60, but confirm against a VB run.
  2. Concentration UNITS. Purser identities imply CO in ppm, CO2 and O2 in
     percent, T in degC. The caller (0x004956E0 setup / FDB read) fixes the
     actual units; if the FDB stores CO2/O2 as fractions, scale before calling.

This module reproduces the *algorithm*; the two scalars above set the absolute
magnitude and are the only things that should ever need calibration.
"""
import math
import numpy as np

# ── Literal constants recovered from the decompile ──────────────────────────
HEAT_SLOPE      = 0.0273      # ⟨MOV.txt:448⟩
HEAT_INTERCEPT  = 5.1849      # ⟨MOV.txt:445-446⟩  0x4014bd56_6cf41f21
HEAT_GATE_C     = 40.0        # ⟨MOV.txt:434⟩  local_160 = 0x28 = 40

VCO2_SLOPE      = 0.1903      # ⟨MOV.txt:341⟩
VCO2_INTERCEPT  = 2.004       # ⟨MOV.txt:343-344⟩ 0x40000831_26e978d5

CO_EXPONENT     = 1.036       # ⟨MOV.txt:368⟩
CO_DIVISOR      = 36177.26    # ⟨MOV.txt:370-371⟩ 0x40e1aa28_51eb851f

CO2_DIR_SLOPE   = 0.5189      # ⟨MOV.txt:417⟩
CO2_DIR_INTER   = 6.1623      # ⟨MOV.txt:414-415⟩ 0x4018a631_f8a0902e
CO2_DIR_GATE    = 1.0         # ⟨MOV.txt:403/405⟩ local_160 = 1.0

O2_AMBIENT      = 20.721      # ⟨MOV.txt:323/584⟩
O2_SLOPE_A      = 0.54        # ⟨MOV.txt:581-582⟩ 0x3fe147ae_147ae148  (one-way bore)
O2_INTER_A      = 8.13        # ⟨MOV.txt:584⟩
O2_SLOPE_B      = 0.511       # ⟨MOV.txt:320-321⟩ 0x3fe05a1c_ac083127 (two-way bore)
O2_INTER_B      = 8.55        # ⟨MOV.txt:318⟩
O2_GATE_PCT     = 11.0        # ⟨MOV.txt:307/309⟩ local_160 = 0xb = 11

SOOT_BASE       = 1.33        # ⟨MOV.txt:255/554⟩
SOOT_NUM        = 80.0        # ⟨MOV.txt:257/556⟩ local_170 = 0x50 = 80


def vco2(co2_pct):
    """CO2 hyperventilation multiplier — Purser. ⟨MOV.txt:341-349⟩."""
    return np.exp(VCO2_SLOPE * co2_pct + VCO2_INTERCEPT)


def fed_rate_components(co_ppm, co2_pct, o2_pct, temp_c, soot=None,
                        two_way=False):
    """Per-timestep, PRE-normalisation FED increments for each component.

    Returns a dict of numpy arrays. Each is the value the decompile adds to the
    occupant field *before* the local_dc (STEP_NORM) division/multiplication —
    i.e. the bracketed rate. Gating exactly mirrors MOV.txt.

    Inputs are element-wise numpy arrays (one entry per occupant) or scalars.
    co_ppm  : CO concentration, ppm
    co2_pct : CO2, percent
    o2_pct  : O2, percent
    temp_c  : temperature, degC
    soot    : extinction/soot proxy used by the +0x80 term (optional)
    two_way : select the O2 slope/intercept of the second bore (DAT_004a623c==2)
    """
    co_ppm  = np.asarray(co_ppm,  dtype=float)
    co2_pct = np.asarray(co2_pct, dtype=float)
    o2_pct  = np.asarray(o2_pct,  dtype=float)
    temp_c  = np.asarray(temp_c,  dtype=float)

    # HEAT — exp(0.0273*T - 5.1849), only when T > 40C   ⟨MOV.txt:434-463⟩
    heat = np.where(temp_c > HEAT_GATE_C,
                    np.exp(HEAT_SLOPE * temp_c - HEAT_INTERCEPT), 0.0)

    # CO — CO^1.036 / 36177.26, multiplied by the CO2 hyperventilation factor.
    #      ⟨MOV.txt:360-384⟩ ; local_a0 = VCO2 computed at 341-356.
    co_safe = np.maximum(co_ppm, 0.0)
    co = np.where(co_safe > 0.0,
                  (co_safe ** CO_EXPONENT) / CO_DIVISOR * vco2(co2_pct), 0.0)

    # CO2 direct incapacitation — exp(0.5189*CO2 - 6.1623), only CO2 > 1.0%
    #      ⟨MOV.txt:403-432⟩
    co2 = np.where(co2_pct > CO2_DIR_GATE,
                   np.exp(CO2_DIR_SLOPE * co2_pct - CO2_DIR_INTER), 0.0)

    # O2 hypoxia — exp(slope*(20.721 - O2) - inter), only when O2 < 11%
    #      ⟨MOV.txt:307-339 (pass A: 8.13/0.54), 569-600 (pass B: 8.55/0.511)⟩
    if two_way:
        o2_slope, o2_inter = O2_SLOPE_B, O2_INTER_B
    else:
        o2_slope, o2_inter = O2_SLOPE_A, O2_INTER_A
    o2 = np.where(o2_pct < O2_GATE_PCT,
                  np.exp(o2_slope * (O2_AMBIENT - o2_pct) - o2_inter), 0.0)

    out = {"heat": heat, "co": co, "co2": co2, "o2": o2}

    # SOOT / visibility term — local_dc * 80 / 1.33^soot   ⟨MOV.txt:255-268,554-566⟩
    if soot is not None:
        soot = np.asarray(soot, dtype=float)
        out["soot"] = SOOT_NUM / np.power(SOOT_BASE, soot)
    return out


def accumulate_fed(co_ppm, co2_pct, o2_pct, temp_c, *, dt_min,
                   soot=False, two_way=False, prev=None, vb_local_dc=None):
    """One timestep of FED accumulation.

    The five bracketed rates (`fed_rate_components`) are *fully* decompile-
    grounded — every constant is a literal recovered from MOV.txt. What is NOT
    determinable from MOV.txt is the single normaliser `local_dc = 5/DAT_004a66e8`
    (set at ⟨MOV.txt:47⟩, value lives in a .SET/DAT dump), and MOV.txt applies it
    ASYMMETRICALLY: heat/CO2/O2 are divided by it ⟨429,460,336⟩ while CO/soot are
    multiplied by it ⟨264,379,564⟩.

    Two modes:
      * DEFAULT (vb_local_dc=None): treat all components as per-minute Purser
        rates and accumulate rate*dt_min. This is the standard egress-tool
        convention and is dimensionally consistent; use it until DAT_004a66e8 is
        known, then validate the absolute magnitude against a VB Raw_Senario row.
      * EXACT (vb_local_dc=<float>): reproduce the literal MOV.txt divide/multiply
        structure with local_dc = vb_local_dc. Switch to this ONLY once
        DAT_004a66e8 has been read from the reference .SET, because the
        asymmetric scaling makes the result extremely sensitive to its value.

    `prev` is the running FED vector (None => start at 0). Heat/CO2/O2/CO are
    always included; the soot/visibility term is opt-in via `soot=<array>`.
    """
    c = fed_rate_components(co_ppm, co2_pct, o2_pct, temp_c,
                            soot=(soot if soot is not False else None),
                            two_way=two_way)
    if vb_local_dc is None:
        inc = (c["heat"] + c["co"] + c["co2"] + c["o2"]) * dt_min
        if "soot" in c:
            inc = inc + c["soot"] * dt_min
    else:
        ld = float(vb_local_dc)
        inc = c["heat"] / ld + c["co"] * ld + c["co2"] / ld + c["o2"] / ld
        if "soot" in c:
            inc = inc + c["soot"] * ld
    if prev is None:
        return inc
    return np.asarray(prev, dtype=float) + inc