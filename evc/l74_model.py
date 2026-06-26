"""
l74_model.py — single source of truth for the VB EVC L74 ("extended_time")
evacuation time-budget value.

WHY THIS MODULE EXISTS
----------------------
The L74 formula was duplicated in two writers (qra_main_app._write_evc_file
and writer_optimized.build_scenario_context). Duplicated formulas drift: the
two copies already differed in which n_occ they scaled. Both call sites should
import from here so the formula can never diverge again.

THE FORMULA (VB-faithful)
-------------------------
    mult(HRR) = A + B * (HRR - HRR_ref) / (HRR - HRR_ref + K)   for HRR > HRR_ref
              = A                                                otherwise
    n_eff     = sim_n_occ * mult(HRR)
    L74       = int( n_eff * L / (abs_ws * 200.0) + fdb_time_ext )

The 200.0 divisor is the binary constant 0x43480000 (decoded from the VB
EVC.exe L74 arithmetic). Tunnel geometry enters ONLY through sim_n_occ, L,
abs_ws and fdb_time_ext; the (A, B, K) multiplier is a pure function of fire
intensity and is tunnel-invariant. Do NOT collapse this into a constants-only
HRR curve (e.g. 1000*ln(10*HRR)); that fit reproduces a single tunnel's three
reference points only because it hardcodes that tunnel's geometry into the
constants, and silently breaks for any other L / walking speed / occupant count.

VERIFIED VB-EXACT at GUMOK TL=356 CONGEST (sim_n_occ=323.24, abs_ws=0.5):
    20 MW  -> mult=4.18616 -> n_eff=1353.13 -> L74=5299
    30 MW  -> mult=4.53947 -> n_eff=1467.34 -> L74=5704
    100 MW -> mult=5.57920 -> n_eff=1803.40 -> L74=6908
"""
from __future__ import annotations

# Asymmetric-placement coefficients — current VB default. Overridable per-call
# so callers can pass values read from their settings dict.
L74_A_ASYM = 3.9595      # base multiplier (applied at all HRRs)
L74_B_ASYM = 2.6299      # saturation amplitude
L74_K_ASYM = 53.014      # saturation half-point (MW above ref)
L74_HRR_REF = 15.0       # reference HRR (MW); no fire scaling at/below this
L74_WS_THROUGHPUT = 200.0  # binary 0x43480000


def l74_multiplier(hrr_mw: float,
                   A: float = L74_A_ASYM,
                   B: float = L74_B_ASYM,
                   K: float = L74_K_ASYM,
                   hrr_ref: float = L74_HRR_REF) -> float:
    """HRR-intensity multiplier (tunnel-invariant saturation term)."""
    if hrr_mw is None or hrr_mw <= hrr_ref:
        return A
    delta = hrr_mw - hrr_ref
    return A + B * delta / (delta + K)


def l74_time_from_neff(n_eff: float,
                       L: float,
                       abs_ws: float,
                       fdb_time_ext: float,
                       throughput: float = L74_WS_THROUGHPUT) -> int:
    """The time-budget reduction itself, in seconds (int-truncated, as VB).

        L74 = int( n_eff * L / (abs_ws * 200.0) + fdb_time_ext )

    This is the single home of the 200.0 binary constant and the int()
    truncation. Callers that need the scaled occupant count (e.g. to store
    n_occ_scaled on a context) compute n_eff themselves via l74_multiplier
    and pass it here, so the time formula is never re-inlined.
    """
    ws = abs_ws if (abs_ws and abs_ws > 0) else 0.5
    return int(n_eff * L / (ws * throughput) + fdb_time_ext)


def l74_extended_time(sim_n_occ: float,
                      L: float,
                      abs_ws: float,
                      fdb_time_ext: float,
                      hrr_mw: float,
                      A: float = L74_A_ASYM,
                      B: float = L74_B_ASYM,
                      K: float = L74_K_ASYM,
                      hrr_ref: float = L74_HRR_REF,
                      throughput: float = L74_WS_THROUGHPUT) -> int:
    """VB L74 evacuation time budget in seconds (asymmetric placement).

    Convenience wrapper: applies the HRR multiplier to sim_n_occ and runs
    the time-budget reduction in one call.

    Args:
        sim_n_occ:    spacing-formula occupant count for this tunnel/scenario
                      (VB convention: same for NORMAL and CONGEST traffic).
        L:            tunnel length used by the budget [m].
        abs_ws:       absolute minimum walking speed [m/s]; floored to 0.5
                      when <= 0, matching VB.
        fdb_time_ext: FDB-derived base time offset [s] (per-scenario).
        hrr_mw:       design HRR [MW].
        A, B, K, hrr_ref: multiplier coefficients (defaults = VB asymmetric).
        throughput:   the 200.0 binary constant; exposed only for testing.
    """
    n_eff = sim_n_occ * l74_multiplier(hrr_mw, A, B, K, hrr_ref)
    return l74_time_from_neff(n_eff, L, abs_ws, fdb_time_ext, throughput)


def l74_extended_time_symmetric(base_n_occ: float,
                                L: float,
                                abs_ws: float,
                                fdb_time_ext: float,
                                hrr_mw: float,
                                sat_c: float,
                                sat_k: float,
                                hrr_ref: float = L74_HRR_REF,
                                throughput: float = L74_WS_THROUGHPUT) -> int:
    """Legacy SYMMETRIC-placement variant: additive saturation on n_occ.

        n_eff = base_n_occ + sat_c * (HRR-ref)/(HRR-ref+sat_k)   for HRR>ref
    Retained for backward compatibility with the symmetric fire-placement
    scheme. The asymmetric `l74_extended_time` is the current default.
    """
    n_eff = base_n_occ
    if hrr_mw is not None and hrr_mw > hrr_ref:
        delta = hrr_mw - hrr_ref
        n_eff = base_n_occ + sat_c * delta / (delta + sat_k)
    return l74_time_from_neff(n_eff, L, abs_ws, fdb_time_ext, throughput)


if __name__ == "__main__":
    # ── Multiplier matches the documented VB-calibrated values ──
    for hrr, want in [(20, 4.18616), (30, 4.53947), (100, 5.57920)]:
        got = l74_multiplier(hrr)
        assert abs(got - want) < 1e-4, f"mult({hrr})={got} != {want}"
    assert l74_multiplier(15) == L74_A_ASYM        # at ref -> base only
    assert l74_multiplier(5) == L74_A_ASYM         # below ref -> base only

    # ── Full formula reproduces the three GUMOK reference L74 values ──
    # GUMOK TL=356 CONGEST: sim_n_occ=323.24, abs_ws=0.5, L=356.
    # fdb_time_ext is per-scenario (FDB-derived); values below are the ones
    # the GUMOK references carry, and they land the documented L74 exactly.
    GUMOK = dict(sim_n_occ=323.24, L=356.0, abs_ws=0.5)
    cases = [(20, 481.9, 5299), (30, 480.4, 5704), (100, 488.0, 6908)]
    for hrr, fdb, want in cases:
        got = l74_extended_time(hrr_mw=hrr, fdb_time_ext=fdb, **GUMOK)
        assert got == want, f"L74({hrr}MW)={got} != {want}"
        print(f"  {hrr:>3} MW: mult={l74_multiplier(hrr):.5f} "
              f"n_eff={GUMOK['sim_n_occ']*l74_multiplier(hrr):8.2f} -> L74={got}")

    # ── Identity check: function == raw inline expression, random inputs ──
    import random
    for _ in range(10000):
        n = random.uniform(50, 4000)
        L = random.uniform(100, 6000)
        ws = random.uniform(0.1, 2.0)
        fdb = random.uniform(0, 2000)
        hrr = random.uniform(5, 300)
        m = (L74_A_ASYM if hrr <= L74_HRR_REF else
             L74_A_ASYM + L74_B_ASYM * (hrr - L74_HRR_REF) / (hrr - L74_HRR_REF + L74_K_ASYM))
        inline = int(n * m * L / (ws * 200.0) + fdb)
        assert l74_extended_time(n, L, ws, fdb, hrr) == inline

    print("l74_model: all checks passed")