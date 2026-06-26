#!/usr/bin/env python3
"""
l74_check.py — diagnose L74 mismatches against VB ground-truth .evc files.

For each VB .evc it reads the inputs the L74 budget depends on (HRR=L68,
length=L63, fdb_time_ext=L73) and the VB L74 itself (L74), then BACK-SOLVES
the sim_n_occ the VB value implies. Because L74 is int()-truncated, the
implied sim_n_occ is an interval; we report its midpoint and width.

If you also feed it your port's computed values (a CSV), it shows, per file,
the port's predicted L74 and exactly which input is off (sim_n_occ, abs_ws,
L, or fdb) — so a batch run becomes a one-line diff.

The L74 formula and the (A,B,K) multiplier come from l74_model, so this
checker can never disagree with the writer about the formula itself.

USAGE
  # just show what sim_n_occ each VB file requires:
  python l74_check.py path/to/*.evc

  # compare against your port's numbers (CSV: file,sim_n_occ[,abs_ws][,L][,fdb]):
  python l74_check.py path/to/*.evc --port-values port_run.csv

  # single file, supply the port's sim_n_occ inline:
  python l74_check.py 100CFVP_P2.evc --sim-n-occ 341.4

CSV format for --port-values (header required; extra cols optional):
  file,sim_n_occ,abs_ws,L,fdb
  100CFVM_P2.evc,341.35,0.5,376,488.4
  100CFVP_P2.evc,341.35,0.5,376,488.4   # <- e.g. wrong: used Lower bore for both
"""
from __future__ import annotations
import argparse
import csv
import glob
import os
import re
import sys

# try:  # in-package
#     from .l74_model import l74_multiplier, l74_time_from_neff
# except ImportError:  # standalone
#     from l74_model import l74_multiplier, l74_time_from_neff

# Find l74_model whether it's in evc/ or alongside this script.
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.join(_here, "evc")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from l74_model import l74_multiplier, l74_time_from_neff

DEFAULT_WS = 0.5


def _num(s: str):
    m = re.findall(r'[-+]?\d*\.?\d+', s or "")
    return float(m[0]) if m else None


def parse_evc(path: str) -> dict:
    """Pull the L74-relevant fields out of a VB .evc deck."""
    txt = open(path, encoding="latin-1").read().replace("\r", "").split("\n")
    g = lambda n: txt[n - 1] if n - 1 < len(txt) else ""
    # L63 is "<fire_pos> , <L> , <L>" — length is the middle field.
    l63 = [p.strip() for p in g(63).split(",")]
    length = _num(l63[1]) if len(l63) > 1 else None
    return {
        "file": os.path.basename(path),
        "tunnel": g(1).strip(),
        "hrr": _num(g(68)),
        "L": length,
        "fdb": _num(g(73)),
        "vb_l74": _num(g(74)),
    }


def implied_sim_n_occ(vb_l74, hrr, L, fdb, abs_ws, A, B, K, ref):
    """Interval of sim_n_occ consistent with the int()-truncated VB L74.

    L74 = int(sim_n_occ * mult * L / (ws*200) + fdb) = V
      =>  sim_n_occ in [ (V - fdb)/k , (V+1 - fdb)/k )   with k = mult*L/(ws*200)
    Returns (lo, hi, mid) or None if k == 0.
    """
    mult = l74_multiplier(hrr, A, B, K, ref)
    ws = abs_ws if (abs_ws and abs_ws > 0) else DEFAULT_WS
    k = mult * L / (ws * 200.0)
    if k == 0:
        return None
    lo = (vb_l74 - fdb) / k
    hi = (vb_l74 + 1 - fdb) / k
    return lo, hi, 0.5 * (lo + hi)


def load_port_values(path: str) -> dict:
    """CSV -> {filename: {sim_n_occ, abs_ws?, L?, fdb?}} (floats)."""
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            key = (row.get("file") or row.get("filename") or "").strip()
            if not key:
                continue
            rec = {}
            for col in ("sim_n_occ", "abs_ws", "L", "fdb"):
                v = (row.get(col) or "").strip()
                if v != "":
                    rec[col] = float(v)
            out[key] = rec
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diagnose L74 vs VB .evc references.")
    ap.add_argument("evc", nargs="+", help="VB .evc files (globs ok).")
    ap.add_argument("--abs-ws", type=float, default=DEFAULT_WS,
                    help=f"walking speed for back-solve (default {DEFAULT_WS}).")
    ap.add_argument("--sim-n-occ", type=float, default=None,
                    help="port's sim_n_occ to test against ALL files (single-bore use).")
    ap.add_argument("--port-values", default=None,
                    help="CSV of the port's per-file values (file,sim_n_occ[,abs_ws][,L][,fdb]).")
    ap.add_argument("--A", type=float, default=3.9595)
    ap.add_argument("--B", type=float, default=2.6299)
    ap.add_argument("--K", type=float, default=53.014)
    ap.add_argument("--ref", type=float, default=15.0)
    args = ap.parse_args(argv)

    paths = []
    for pat in args.evc:
        paths.extend(sorted(glob.glob(pat)) or ([pat] if os.path.exists(pat) else []))
    if not paths:
        ap.error("no .evc files matched.")

    port = load_port_values(args.port_values) if args.port_values else {}

    header = (f"{'file':18} {'tunnel':14} {'HRR':>4} {'L':>4} {'fdb':>6} "
              f"{'VB L74':>6} {'needs n_occ':>18}")
    if port or args.sim_n_occ is not None:
        header += f" {'port n_occ':>10} {'port L74':>8} {'ΔL74':>5} {'verdict':>8}"
    print(header)
    print("-" * len(header))

    n_mismatch = 0
    by_tunnel: dict = {}   # tunnel name -> list of (file, hrr, lo, hi)
    for p in paths:
        d = parse_evc(p)
        if None in (d["hrr"], d["L"], d["fdb"], d["vb_l74"]):
            print(f"{d['file']:18} <could not parse L68/L63/L73/L74>")
            continue
        iv = implied_sim_n_occ(d["vb_l74"], d["hrr"], d["L"], d["fdb"],
                               args.abs_ws, args.A, args.B, args.K, args.ref)
        lo, hi, mid = iv
        by_tunnel.setdefault(d["tunnel"], []).append((d["file"], d["hrr"], lo, hi))
        line = (f"{d['file']:18} {d['tunnel'][:14]:14} {d['hrr']:4.0f} {d['L']:4.0f} "
                f"{d['fdb']:6.1f} {d['vb_l74']:6.0f} {mid:9.2f} [{lo:.1f},{hi:.1f})")

        rec = port.get(d["file"], {})
        port_n = rec.get("sim_n_occ", args.sim_n_occ)
        if port_n is not None:
            ws = rec.get("abs_ws", args.abs_ws)
            L = rec.get("L", d["L"])
            fdb = rec.get("fdb", d["fdb"])
            mult = l74_multiplier(d["hrr"], args.A, args.B, args.K, args.ref)
            port_l74 = l74_time_from_neff(port_n * mult, L, ws, fdb)
            delta = port_l74 - int(d["vb_l74"])
            ok = (delta == 0)
            if not ok:
                n_mismatch += 1
            # name the likely culprit
            why = ""
            if not ok:
                bits = []
                if not (lo <= port_n < hi):
                    bits.append(f"n_occ {port_n:.2f}≠{mid:.2f}")
                if abs(L - d["L"]) > 1e-6:
                    bits.append(f"L {L:g}≠{d['L']:g}")
                if abs(fdb - d["fdb"]) > 1e-6:
                    bits.append(f"fdb {fdb:g}≠{d['fdb']:g}")
                if rec.get("abs_ws", args.abs_ws) != args.abs_ws:
                    bits.append(f"ws {ws:g}")
                why = "  <- " + ("; ".join(bits) if bits else "rounding")
            line += (f" {port_n:10.2f} {port_l74:8d} {delta:+5d} "
                     f"{'OK' if ok else 'MISS':>8}{why}")
        print(line)

    # ── Per-bore feasible sim_n_occ: intersect the per-file intervals ──
    # The same bore must use ONE sim_n_occ across all its HRR scenarios, so the
    # true value is the intersection of every file's interval for that tunnel.
    if by_tunnel:
        print()
        print("Per-bore feasible sim_n_occ (must satisfy all HRRs for that bore):")
        for tunnel, rows in by_tunnel.items():
            lo = max(r[2] for r in rows)
            hi = min(r[3] for r in rows)
            if lo < hi:
                tag = f"sim_n_occ in [{lo:.2f}, {hi:.2f})  -> use ~{0.5*(lo+hi):.2f}"
            else:
                tag = (f"NO single sim_n_occ fits all {len(rows)} files "
                       f"(intervals disjoint) — check abs_ws / fdb / coefficients")
            print(f"  {tunnel[:24]:24} ({len(rows)} files): {tag}")

    if port or args.sim_n_occ is not None:
        print("-" * len(header))
        print(f"{n_mismatch} mismatch(es)." if n_mismatch else "All files match VB L74.")
    return 1 if n_mismatch else 0


if __name__ == "__main__":
    sys.exit(main())