#!/usr/bin/env python3
"""
set_compare.py — diagnose EQ_Fatal mismatches against VB ground-truth .SET files.

This is the fatality-side analogue of l74_check.py. It reads VB's actual
evacuation casualty output (the per-occupant .SET), summarises what VB really
did — how many occupants, where they were placed, which side of the fire got
dosed, the FED distribution, and the EQ_Fatal sum — and (optionally) runs the
Python engine on the same .evc + .FDB and reports the same summary side by side,
so a divergence is attributed to a specific mechanism rather than guessed.

THE KEY DISTINCTION THIS TOOL ENFORCES
--------------------------------------
VB exposes TWO different "fatality" numbers and they disagree by ~50-75x:

  * the .SET casualty output  — the real evacuation-sim result, O(1) fatalities.
    THIS is what the consequence engine must reproduce.
  * the Raw_FNC / FN-curve number (e.g. the "68.8" in the Results screenshots)
    — a frequency-RE-WEIGHTED post-processing figure, NOT a sim output.

A 236-occupant scenario whose worst occupant reaches FED~0.04 cannot physically
sum to 68 fatalities; that number is a post-processing re-weight and belongs in
the frequency layer, never in the dose. This tool reports the .SET EQ_Fatal so
the engine is measured against the right target.

.SET COLUMN MAP (0-based; confirmed on the Gopo decks)
------------------------------------------------------
  col0  frame marker (0 = initial, max = final-accumulated)
  col1  occupant id        col2  vehicle type
  col3  EVC position [m]    col7  exposure time [s]
  col17 temp  col18 soot  col19 co  col20 o2  col21 vis  col22 co2
  col24 FED_total  col25 FED_CO  col27 FED_heat  col30 FED7
  (identity: col24 == col25 + col27 + col30)

USAGE
  # VB-only summary for a cell (all runs):
  python set_compare.py 030NFVM_P5_*.SET --fire-x 263.2

  # compare VB vs the Python engine (needs the .evc and .FDB):
  python set_compare.py 030NFVM_P5_*.SET --fire-x 263.2 \
      --evc 030NFVM_P5.evc --fdb 030NFVM.FDB [--mirror] [--cnv 1.0] [--iters 10]
"""
from __future__ import annotations
import argparse, glob, os, sys
import numpy as np

C_FRAME, C_POS, C_TEXP = 0, 3, 7
C_FED, C_FED_CO, C_FED_HEAT, C_FED7 = 24, 25, 27, 30
BANDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 1.0, np.inf]


def read_set(path):
    rows = []
    for line in open(path, encoding="latin-1"):
        p = line.split()
        if len(p) >= 31:
            try:
                rows.append([float(x) for x in p[:31]])
            except ValueError:
                continue
    a = np.array(rows)
    if a.size == 0:
        return None
    return a[a[:, C_FRAME] == a[:, C_FRAME].max()]   # final-accumulated frame


def summarise(fr, fire_x=None):
    pos = fr[:, C_POS]; fed = fr[:, C_FED]
    out = {
        "n": len(fr),
        "eq_fatal": float(np.clip(fed, 0, 1).sum()),
        "n_exposed": int((fed > 0).sum()),
        "n_fatal": int((fed >= 1.0).sum()),
        "fed_max": float(fed.max()),
        "pos": pos, "fed": fed, "fire_x": fire_x,
    }
    if fire_x is not None:
        out["n_below"] = int((pos < fire_x).sum())
        out["n_above"] = int((pos >= fire_x).sum())
        dosed = pos[fed > 0]
        out["dosed_side"] = ("below" if dosed.size and dosed.mean() < fire_x
                             else "above" if dosed.size else "none")
    return out


def band_counts(fed):
    return [int(((fed >= BANDS[i]) & (fed < BANDS[i + 1])).sum())
            for i in range(len(BANDS) - 1)]


def print_summary(tag, s):
    print(f"  {tag:16} EQ_Fatal={s['eq_fatal']:7.2f}  occ={s['n']:4d}  "
          f"exposed={s['n_exposed']:4d}  FED>=1={s['n_fatal']:3d}  "
          f"FED_max={s['fed_max']:.3f}")
    if s.get("fire_x") is not None:
        print(f"  {'':16} placement: {s['n_below']} below / {s['n_above']} above fire"
              f" (x={s['fire_x']})   dosed side: {s['dosed_side']}")


def dose_by_band(label, pos, fed, fire_x, width=40.0):
    print(f"\n  {label} — mean FED by position band (fire at {fire_x}):")
    xmax = max(pos.max(), fire_x) + width
    lo = 0.0
    while lo < xmax:
        m = (pos >= lo) & (pos < lo + width)
        if m.sum():
            star = "  <-- fire" if lo <= fire_x < lo + width else ""
            print(f"      x[{lo:5.0f},{lo+width:5.0f}): n={int(m.sum()):3d}  "
                  f"meanFED={fed[m].mean():.3f}  #>0={int((fed[m] > 0).sum())}{star}")
        lo += width


def run_engine(evc, fdb, mirror, cnv, iters):
    from pathlib import Path
    sys.path.insert(0, os.path.dirname(os.path.abspath(evc)) or ".")
    from evc_engine import EVCEngine
    e = EVCEngine(Path(evc), Path(fdb))
    if not (e.fdb and e.fdb.is_loaded):
        raise RuntimeError(f"engine could not load FDB {fdb}")
    e.smoke_mirrored = mirror
    e.FIELD_CNV_FAC = cnv
    res = e.run(n_iterations=iters)
    return float(res.avg.eq_fatal)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diagnose EQ_Fatal vs VB .SET ground truth.")
    ap.add_argument("sets", nargs="+", help="VB .SET files (globs ok).")
    ap.add_argument("--fire-x", type=float, default=None, help="EVC fire position [m].")
    ap.add_argument("--evc", default=None, help="matching .evc deck (to run the engine).")
    ap.add_argument("--fdb", default=None, help="matching .FDB field (to run the engine).")
    ap.add_argument("--mirror", action="store_true", help="run engine with smoke_mirrored=True.")
    ap.add_argument("--cnv", type=float, default=1.0, help="FIELD_CNV_FAC for the engine run.")
    ap.add_argument("--iters", type=int, default=10, help="engine iterations.")
    args = ap.parse_args(argv)

    paths = []
    for pat in args.sets:
        paths.extend(sorted(glob.glob(pat)) or ([pat] if os.path.exists(pat) else []))
    if not paths:
        ap.error("no .SET files matched.")

    eqs, pooled_pos, pooled_fed = [], [], []
    last = None
    for p in paths:
        fr = read_set(p)
        if fr is None:
            print(f"{os.path.basename(p)}: unparseable"); continue
        s = summarise(fr, args.fire_x)
        eqs.append(s["eq_fatal"])
        pooled_pos.append(s["pos"]); pooled_fed.append(s["fed"]); last = s
        print(f"{os.path.basename(p)}:")
        print_summary("VB .SET", s)

    if eqs:
        print(f"\nVB .SET EQ_Fatal across {len(eqs)} run(s): "
              f"mean={np.mean(eqs):.2f}  range=[{min(eqs):.2f}, {max(eqs):.2f}]")
        if args.fire_x is not None:
            pos = np.concatenate(pooled_pos); fed = np.concatenate(pooled_fed)
            dose_by_band("VB (pooled)", pos, fed, args.fire_x)
            print(f"\n  VB FED bands {BANDS[:-1]}:\n    {band_counts(fed)}")

    if args.evc and args.fdb:
        print("\n=== Python engine on the same .evc + real .FDB ===")
        try:
            nat = run_engine(args.evc, args.fdb, False, args.cnv, args.iters)
            print(f"  native (mirror=False, cnv={args.cnv}):  EQ_Fatal = {nat:.2f}")
            if args.mirror:
                mir = run_engine(args.evc, args.fdb, True, args.cnv, args.iters)
                print(f"  mirror (mirror=True,  cnv={args.cnv}):  EQ_Fatal = {mir:.2f}")
            vb = np.mean(eqs) if eqs else float("nan")
            print(f"\n  VB .SET mean = {vb:.2f}   "
                  f"native/VB = {nat/vb:.2f}x" if vb else "")
        except Exception as e:
            print(f"  [engine run failed: {e}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
    