# -*- coding: utf-8 -*-
"""fn_basis_align.py — FN-curve frequency-basis alignment, sourced ENTIRELY
from the Python program (no .xlsm required).

Why this module exists
----------------------
The Python and VB F-N curves are offset *vertically* (the frequency axis)
while the fatality axis matches (r ≈ 0.95).  The offset factorises as a
constant fire-occurrence ratio (~16.6×) times a conditional scenario-split
residual (1.1–4.2×).  Both factors live in the ECAR table — the annual
frequency per (HRR × Traffic × Wind) scenario — not in the consequence
engine.

VB itself never computes those numbers at FN time.  Module1.CalnFillFreq
loads them verbatim from the workbook:

    Set DataRange = Range("SenarioTable")
    ...
    ECAR(nHrr, nTRC, nWDC) = .Cells(i, 3)

The Python program already CONTAINS that table, twice over:

1. **Scenario Detail Table** — ``standard_scenario_widget.
   _build_standard_scenario_data()`` constructs the default event tree whose
   SubScenario ``freq_per_yr`` values are direct transcriptions of the
   reference workbook's per-scenario annual frequencies (e.g. 020N/NNVC
   = 2.010e-4, 020N/NNV0 = 1.608e-3, …).  Accumulating its non-alias
   leaves reproduces the SenarioTable exactly — this is the same walk
   that was verified to reproduce every workbook Q value and the FNCurve2
   PLL (6.9985e-05) to 5 significant digits.

2. **Tunnel Traffic Volume sheet** — ``tunnel_traffic_sheet.json``'s
   ``named_values`` block carries the workbook's named ranges (BASE,
   VK.*, LFR.*, NNVC/NNV0/NFF, CNVC/CNV0/CFF, CongRate, …), which lets
   the loaded basis be cross-checked against a second independent
   in-program source.

So the alignment needs nothing outside the codebase:

* ``ecar_from_workbook_defaults()`` — the VB basis, rebuilt from source 1.
* ``vb_named_values()`` / ``verify_basis()`` — cross-check via source 2.
* ``ecar_from_scenario_details(data)`` — the same accumulation applied to
  a LIVE widget dataset (i.e. the current Python/Gopo basis), so the two
  bases can be diffed scenario-by-scenario.
* ``rescale_ecar()`` — frequency-level-only alignment that preserves the
  current split.

Alias rule (critical): GV "20MW" → BUS-20 and ST "30MW" → GV-30 fire types
are DISPLAY mirrors of downgrade terms the parent class node already
contains; accumulating them double-counts the 020 class by 1.751× and the
030 class by 1.079×.  They are skipped here, identically to the verified
fix in qra_main_app._t6_load_ecar_from_standard_scenario.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HRR_LIST = ["PC1", "PC2", "020", "030", "100"]
TRC_LIST = ["NORMAL", "CONGEST"]
WDC_LIST = ["NVC", "NV0", "FV0", "FVM", "FVP"]

Key = Tuple[str, str, str]          # (hrr, traffic, wind)
EcarMap = Dict[Key, float]


# ──────────────────────────────────────────────────────────────────────────
# Source 1 — Scenario Detail Table (event-tree leaves)
# ──────────────────────────────────────────────────────────────────────────
def decode_leaf(scenario_id: str, smoke_control: str) -> Optional[Key]:
    """Decode a SubScenario's (scenario_id, smoke_control) → ECAR key.

    Identical grammar to qra_main_app._t6_load_ecar_from_standard_scenario:
        scenario_id  = HRR + traffic letter      e.g. "020C", "PC1N"
        smoke_control = traffic letter + wind     e.g. "CFVP" → wind "FVP"
    """
    sid = (scenario_id or "").upper().strip()
    smk = (smoke_control or "").upper().strip()
    if sid.startswith(("PC1", "PC2")) or sid[:3] in ("020", "030", "100"):
        hrr = sid[:3]
        trc_letter = sid[3:4]
    else:
        return None
    if len(smk) < 4:
        return None
    wind = smk[1:4]
    trc = "NORMAL" if trc_letter == "N" else (
        "CONGEST" if trc_letter == "C" else None)
    if hrr not in HRR_LIST or trc not in TRC_LIST or wind not in WDC_LIST:
        return None
    return (hrr, trc, wind)


def ecar_from_scenario_details(data) -> EcarMap:
    """Accumulate {(hrr, traffic, wind): Σ freq_per_yr} from an event-tree
    dataset (a list of VehicleType objects, default or live).

    Duck-typed: any objects exposing .fire_types / .alias_to / .normal /
    .congest / .sub_scenarios / .scenario_id / .smoke_control /
    .freq_per_yr work.  Alias fire types are skipped (see module docstring).
    """
    ecar: EcarMap = {}
    for vt in data or []:
        for ft in getattr(vt, "fire_types", []) or []:
            if getattr(ft, "alias_to", None) is not None:
                continue  # display mirror of a downgrade term — never count
            for branch in (getattr(ft, "normal", None),
                           getattr(ft, "congest", None)):
                if branch is None:
                    continue
                for ss in getattr(branch, "sub_scenarios", []) or []:
                    key = decode_leaf(getattr(ss, "scenario_id", ""),
                                      getattr(ss, "smoke_control", ""))
                    freq = getattr(ss, "freq_per_yr", None)
                    if key is None or freq is None or freq < 0:
                        continue
                    ecar[key] = ecar.get(key, 0.0) + float(freq)
    return ecar


def ecar_from_workbook_defaults() -> EcarMap:
    """The VB frequency basis, rebuilt from the Python program itself.

    Constructs a FRESH default event tree via
    standard_scenario_widget._build_standard_scenario_data() — whose leaf
    frequencies are the reference workbook's SenarioTable transcriptions,
    untouched by any tunnel-sheet recalculation — and accumulates it.

    Note: building the defaults does not instantiate any widget, so no
    QApplication is required.
    """
    try:
        from standard_scenario_widget import _build_standard_scenario_data
    except ImportError:
        from evc.standard_scenario_widget import _build_standard_scenario_data
    return ecar_from_scenario_details(_build_standard_scenario_data())


# ──────────────────────────────────────────────────────────────────────────
# Source 2 — Tunnel Traffic Volume sheet (named values) for cross-checking
# ──────────────────────────────────────────────────────────────────────────
def vb_named_values(json_path: Optional[str] = None) -> Dict[str, float]:
    """Workbook named ranges as carried by tunnel_traffic_sheet.json.

    These are the reference workbook's values (BASE, VK.*, LFR.*, vent
    splits NNVC/NNV0/NFF + CNVC/CNV0/CFF, CongRate, …), independent of any
    cell edits made for the current tunnel.
    """
    if json_path is None:
        here = Path(__file__).resolve().parent
        for cand in (here / "tunnel_traffic_sheet.json",
                     here / "evc" / "tunnel_traffic_sheet.json",
                     here.parent / "tunnel_traffic_sheet.json"):
            if cand.exists():
                json_path = str(cand)
                break
    if json_path is None or not Path(json_path).exists():
        return {}
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except Exception:
        return {}
    out: Dict[str, float] = {}
    for k, v in (doc.get("named_values") or {}).items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def verify_basis(ecar_map: EcarMap,
                 named: Optional[Dict[str, float]] = None,
                 tol: float = 0.02) -> str:
    """Cross-check the loaded basis against the Tunnel Traffic named values.

    Two structural invariants of the workbook event tree are checked,
    because they depend ONLY on the conditional split (not on rates/AADT):

      * vent split within each traffic state:
            NVC : NV0 : (FV0+FVM+FVP)  ==  NNVC : NNV0 : NFF   (normal)
                                       ==  CNVC : CNV0 : CFF   (congested)
      * congested share of total      ==  CongRate

    Returns a human-readable PASS/FAIL report.  A FAIL means the loaded
    map is NOT on the workbook's conditional split (e.g. it came from a
    live tree already recalculated with tunnel-specific factors).
    """
    if named is None:
        named = vb_named_values()
    lines: List[str] = []

    def _sum(trc: str, winds) -> float:
        return sum(v for (h, t, w), v in ecar_map.items()
                   if t == trc and w in winds)

    total = total_fire_frequency(ecar_map)
    lines.append(f"Total fire frequency: {total:.6E}/yr "
                 f"(return {1.0/total:,.1f} yr)" if total > 0 else
                 "Total fire frequency: 0 — empty map")
    if total <= 0:
        return "\n".join(lines)

    checks = []
    for trc, (k_nvc, k_nv0, k_ff) in (
            ("NORMAL",   ("NNVC", "NNV0", "NFF")),
            ("CONGEST",  ("CNVC", "CNV0", "CFF"))):
        sub = (_sum(trc, {"NVC"}), _sum(trc, {"NV0"}),
               _sum(trc, {"FV0", "FVM", "FVP"}))
        sub_tot = sum(sub)
        if sub_tot <= 0:
            continue
        got = tuple(s / sub_tot for s in sub)
        want = tuple(named.get(k, float("nan"))
                     for k in (k_nvc, k_nv0, k_ff))
        if all(w == w for w in want):  # no NaNs
            ok = all(abs(g - w) <= tol for g, w in zip(got, want))
            checks.append(ok)
            lines.append(
                f"{trc:8} vent split NVC/NV0/FF: "
                f"got {got[0]:.3f}/{got[1]:.3f}/{got[2]:.3f}  "
                f"named {want[0]:.3f}/{want[1]:.3f}/{want[2]:.3f}  "
                f"{'PASS' if ok else 'FAIL'}")

    cong = sum(v for (h, t, w), v in ecar_map.items() if t == "CONGEST")
    cong_share = cong / total
    cong_named = named.get("CongRate")
    if cong_named is not None:
        ok = abs(cong_share - cong_named) <= tol
        checks.append(ok)
        lines.append(f"Congested share: got {cong_share:.4f}  "
                     f"named CongRate {cong_named:.4f}  "
                     f"{'PASS' if ok else 'FAIL'}")

    lines.append("BASIS CHECK: " + ("PASS — matches the workbook split"
                 if checks and all(checks) else
                 "FAIL — split differs from the workbook named values"))
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# Totals / rescale / diff
# ──────────────────────────────────────────────────────────────────────────
def total_fire_frequency(ecar_map: EcarMap) -> float:
    """Σ over all scenarios — the tunnel-wide annual fire frequency."""
    return float(sum(v for v in ecar_map.values() if v and v > 0.0))


def rescale_ecar(ecar_map: EcarMap, target_total: float) -> EcarMap:
    """Uniformly rescale so Σ frequencies == target_total.

    Preserves the conditional scenario split exactly; only the
    fire-occurrence level changes.  Returns a NEW dict.
    """
    cur = total_fire_frequency(ecar_map)
    if cur <= 0.0:
        raise ValueError("Current total fire frequency is zero — nothing to scale.")
    if target_total <= 0.0:
        raise ValueError("Target total fire frequency must be positive.")
    k = target_total / cur
    return {key: v * k for key, v in ecar_map.items()}


def diff_report(py_map: EcarMap, vb_map: EcarMap) -> str:
    """Per-scenario ratio table (VB ÷ Python) — shows exactly WHERE the
    fire-occurrence factor and the conditional-split residual live."""
    keys = sorted(set(py_map) | set(vb_map))
    lines = [f"{'HRR':5} {'Traffic':8} {'Wind':4} "
             f"{'Python/yr':>12} {'VB/yr':>12} {'VB÷Py':>8}"]
    for k in keys:
        p = py_map.get(k, 0.0)
        v = vb_map.get(k, 0.0)
        ratio = (v / p) if p > 0 else (float("inf") if v > 0 else 1.0)
        lines.append(f"{k[0]:5} {k[1]:8} {k[2]:4} "
                     f"{p:12.4E} {v:12.4E} {ratio:8.2f}")
    tp, tv = total_fire_frequency(py_map), total_fire_frequency(vb_map)
    lines.append("-" * 56)
    lines.append(f"TOTAL fire freq:  Python {tp:.4E}/yr   VB {tv:.4E}/yr"
                 f"   ratio {tv / max(tp, 1e-300):.2f}×")
    return "\n".join(lines)


if __name__ == "__main__":
    # Self-test / report when run directly inside the project.
    vb = ecar_from_workbook_defaults()
    print(f"VB basis from Scenario Detail defaults: {len(vb)} scenarios, "
          f"total {total_fire_frequency(vb):.6E}/yr")
    print(verify_basis(vb))