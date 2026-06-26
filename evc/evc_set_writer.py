"""
evc_set_writer.py — VB-exact `.SET` per-occupant output writer.

The `.SET` file is VB's per-occupant evacuation-casualty record, emitted by the
decompiled orchestrator FUN_0049c8f0 (which opens it as file #5, runs the FED
routines FUN_004956e0/FUN_00497950, loops the occupant array DAT_004a60b4 at a
148-byte stride, and prints one fixed-width row per occupant per frame).

This module reproduces the FORMAT exactly. The column widths/decimals below were
reverse-engineered from real VB `.SET` files and verified by BYTE-EXACT
round-trip over 895 reference lines (see `round_trip_check` / __main__). So a row
emitted here is indistinguishable from VB's, given the same 31 values.

FILE STRUCTURE
--------------
Two frames per run, each a block of one row per occupant:
  * initial frame (col0 = 0.0)      — start state; concentrations/FED zero,
                                       col6 carries the -999.0 "not-computed"
                                       sentinel, col8 = start position.
  * final frame   (col0 = run_end_s) — end state; endpoint concentrations and
                                       accumulated FED, col10 = 99 (escaped).

COLUMN MAP (0-based) — name, decimals, and DATA SOURCE.
  Source legend:  [engine] available now · [engine+]= needs per-occupant
  recording added to evc_engine · [obs]= observed constant/sentinel ·
  [decode] = exact VB meaning still to be decoded from the row-writer.
   0  TIME       .1f  frame time (0 or run-end)                       [engine]
   1  ID         int  occupant id (1-based)                           [engine]
   2  VTYPE      int  vehicle type (1..7)                             [engine]
   3  X0         .1f  start position [m] (EVC frame)                  [engine]
   4  C4         .1f  always 0.0 (lane/flag)                          [obs]
   5  C5         .1f  changes; per-occupant evac param                [decode]
   6  C6         .1f  -999.0 init -> value final (escape metric)      [decode]
   7  TEXP       .1f  final = exposure time [s]; init = time budget   [engine]
   8  XEND       .1f  end position [m] (exit-relative; <0 = exited)   [engine]
   9  C9         .1f  changes; speed/dist-related                     [decode]
  10  STATUS     int  0 init -> 99 final (escaped)                    [engine]
  11  DIST       .1f  distance walked [m]                             [engine]
  12  SPEED      .2f  walking speed [m/s]                             [engine]
  13  C13        .2f  const 1.40 (speed/width param)                  [obs]
  14  C14        .2f  const 1.06                                      [obs]
  15  C15        .2f  const 1.40                                      [obs]
  16  C16        .2f  0 init -> 1.06 final (speed-related)            [decode]
  17  TEMP       .2f  endpoint temperature [degC]                     [engine+]
  18  SOOT       .2f  endpoint soot                                   [engine+]
  19  CO         .2f  endpoint CO [ppm]                               [engine+]
  20  O2         .2f  endpoint O2 [%]                                 [engine+]
  21  VIS        .2f  endpoint visibility [m]                         [engine+]
  22  CO2        .2f  endpoint CO2 [%]                                [engine+]
  23  CO23       .2f  CO-derived (dose ppm or COHb)                   [decode]
  24  FED_TOTAL  .4f  = FED_CO + FED_HEAT + FED7                      [engine+]
  25  FED_CO     .4f  CO FED component                                [engine+]
  26  C26        .4f  0 (unused)                                      [obs]
  27  FED_HEAT   .4f  heat FED component                              [engine+]
  28  C28        .4f  0 (unused)                                      [obs]
  29  C29        .4f  0 (unused)                                      [obs]
  30  FED7       .4f  trajectory FED term (dominant for normal FVM;   [decode]
                      currently UNRESOLVED in fed_eqfatal_model)

INTEGRITY: VB satisfies col24 == col25 + col27 + col30 exactly.

HONEST STATUS (do not overclaim):
  * The FORMAT is exact (round-trip proven).
  * Filling it from the engine needs (a) per-occupant recording of the FED
    components and endpoint concentrations (cols 17-23, 25/27/30), and
    (b) the FED7 (col30) decode — without which the dose columns won't match
    VB for normal-FVM cells even though the format is perfect.
  * Cols 5,6,9,13-16,23 are evac-state internals not yet decoded; they are
    emitted from whatever the caller supplies (observed constants by default).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Sequence
import re

# ── Proven fixed-width format (verified byte-exact vs real VB .SET) ──────────
SET_WIDTHS  = [7, 6, 3, 9, 8, 8, 9, 9, 8, 8, 4, 9, 8, 7, 7, 7, 7,
               8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8]
SET_DECIMALS = [1, None, None, 1, 1, 1, 1, 1, 1, 1, None, 1, 2, 2, 2, 2, 2,
                2, 2, 2, 2, 2, 2, 2, 4, 4, 4, 4, 4, 4, 4]
N_COLS = 31
assert len(SET_WIDTHS) == len(SET_DECIMALS) == N_COLS

# Integer columns (decimals is None): id, vtype, status
_INT_COLS = {i for i, d in enumerate(SET_DECIMALS) if d is None}

SENTINEL_NOT_COMPUTED = -999.0   # col6 init value
STATUS_ESCAPED = 99              # col10 final value
LINE_TERM = "\n"                 # VB writes LF here (matches references)


def format_set_row(values: Sequence[float]) -> str:
    """Format 31 values into one VB-exact fixed-width .SET row (no newline)."""
    if len(values) != N_COLS:
        raise ValueError(f".SET row needs {N_COLS} values, got {len(values)}")
    out = []
    for v, w, d in zip(values, SET_WIDTHS, SET_DECIMALS):
        if d is None:
            out.append(f"{int(round(float(v))):{w}d}")
        else:
            out.append(f"{float(v):{w}.{d}f}")
    return "".join(out)


@dataclass
class OccupantSetRecord:
    """One occupant's full row data (final-frame oriented). The engine fills
    what it has; unfilled evac-internal columns keep their observed defaults.

    To emit the initial frame, the writer zeros the dynamic columns and applies
    the documented sentinels (col6=-999, col10=0, concentrations/FED=0), keeping
    the static columns (id, vtype, x0).
    """
    occ_id: int
    veh_type: int
    x0: float                 # col3 start position
    texp: float = 0.0         # col7 exposure time (final)
    x_end: float = 0.0        # col8 end position
    status: int = STATUS_ESCAPED  # col10
    dist: float = 0.0         # col11
    speed: float = 0.0        # col12
    temp: float = 0.0         # col17
    soot: float = 0.0         # col18
    co: float = 0.0           # col19
    o2: float = 0.0           # col20
    vis: float = 0.0          # col21
    co2: float = 0.0          # col22
    co23: float = 0.0         # col23
    fed_co: float = 0.0       # col25
    fed_heat: float = 0.0     # col27
    fed7: float = 0.0         # col30
    # evac-internal columns not yet decoded — caller may override; defaults are
    # the observed constants so output stays well-formed.
    c4: float = 0.0
    c5: float = 0.0
    c6: float = 0.0
    c9: float = 0.0
    c13: float = 1.40
    c14: float = 1.06
    c15: float = 1.40
    c16: float = 0.0

    @property
    def fed_total(self) -> float:           # col24 (enforce VB's identity)
        return self.fed_co + self.fed_heat + self.fed7

    def row(self, frame_time: float, initial: bool) -> List[float]:
        if initial:
            # start state: static cols kept; dynamics zeroed; sentinels applied
            return [0.0, self.occ_id, self.veh_type, self.x0, self.c4,
                    self.c5, SENTINEL_NOT_COMPUTED, self.texp, self.x0, self.c9,
                    0, 0.0, self.speed, self.c13, self.c14, self.c15, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        return [frame_time, self.occ_id, self.veh_type, self.x0, self.c4,
                self.c5, self.c6, self.texp, self.x_end, self.c9,
                self.status, self.dist, self.speed, self.c13, self.c14,
                self.c15, self.c16, self.temp, self.soot, self.co, self.o2,
                self.vis, self.co2, self.co23, self.fed_total, self.fed_co,
                0.0, self.fed_heat, 0.0, 0.0, self.fed7]


def write_set(path: str,
              records: Sequence[OccupantSetRecord],
              run_end_s: float,
              initial_records: Sequence[OccupantSetRecord] | None = None) -> str:
    """Write a VB-format .SET: an initial frame (t=0) then a final frame.

    records          — final-frame occupant records.
    run_end_s        — final frame time (col0).
    initial_records  — optional explicit initial-frame records; defaults to
                       `records` (which the .row(initial=True) path zeroes).
    """
    init = initial_records if initial_records is not None else records
    lines: List[str] = []
    for r in init:
        lines.append(format_set_row(r.row(0.0, initial=True)))
    for r in records:
        lines.append(format_set_row(r.row(run_end_s, initial=False)))
    with open(path, "w", encoding="latin-1", newline="") as fh:
        fh.write(LINE_TERM.join(lines) + LINE_TERM)
    return path


# ── Verification: round-trip a real VB .SET byte-for-byte ────────────────────
def round_trip_check(set_path: str) -> bool:
    """Read a VB .SET and re-emit each row from its own values; assert the
    bytes are identical. This proves the format constants above are exact."""
    ok = True
    n = 0
    for line in open(set_path, encoding="latin-1").read().split("\n"):
        if not line.strip():
            continue
        vals = [float(x) for x in line.split()]
        if len(vals) != N_COLS:
            continue
        n += 1
        if format_set_row(vals) != line.rstrip("\r"):
            ok = False
            break
    return ok and n > 0


if __name__ == "__main__":
    import glob, sys
    # 1) format self-consistency
    demo = OccupantSetRecord(occ_id=1, veh_type=2, x0=243.3, texp=358.0,
                             x_end=-1.3, dist=246.3, speed=1.01,
                             temp=26.07, soot=0.03, co=29.36, o2=20.72,
                             vis=32.11, co2=0.01, co23=26.85, fed7=0.03)
    assert len(format_set_row(demo.row(628.0, False))) == sum(SET_WIDTHS)
    assert abs(demo.fed_total - 0.03) < 1e-9
    print("format self-test OK; row width =", sum(SET_WIDTHS))

    # 2) byte-exact round-trip against any real .SET passed or found nearby
    paths = sys.argv[1:] or glob.glob("*.SET") or glob.glob("**/*.SET", recursive=True)
    if not paths:
        print("(no .SET file found to round-trip; pass one as an argument)")
    else:
        allok = True
        for p in paths[:5]:
            r = round_trip_check(p)
            allok &= r
            print(f"  round-trip {p}: {'BYTE-EXACT' if r else 'MISMATCH'}")
        print("evc_set_writer:", "all round-trips byte-exact" if allok else "MISMATCH")
        