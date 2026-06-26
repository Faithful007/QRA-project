# -*- coding: utf-8 -*-
"""
tec_style_graphs.py
═══════════════════════════════════════════════════════════════════════════
Reproduce the VB-era Tecplot 4-panel scenario graphs (Soot / CO / Temp / CO2
vs tunnel position, one grey-shaded line per saved TIME step) and save them
as JPGs into  <project_dir>/graphs/.

Background
----------
The original VB EVC.exe (FUN_004956E0) wrote one <scenario>.OUT.TEC Tecplot
file per run (header written by FUN_0046fc60:
    Variables = Time, X, Dens, Temp, CO, Soot, co2, Oxyt, Radi, Visi, ...
with one ZONE per saved time step).  Those files were then plotted in
Tecplot using a fixed 2×2 layout:

    ┌──────────────┬──────────────┐
    │ Soot [mg/m3] │  CO  [ppm]   │     y-limits  0–5000 / 0–6000
    ├──────────────┼──────────────┤
    │ Temp [deg.]  │  CO2 [%]     │     y-limits  0–500  / 0–5
    └──────────────┴──────────────┘

Each line is one TIME zone, shaded on a black→white greyscale ramp
(t = 0 s → black, t = 1200 s → near-white), with a boxed vertical "TIME"
legend showing the levels 0 / 240 / 480 / 720 / 960 / 1200.

This module recreates that figure from a parsed FDB dataset
(evc_engine.FDBData) — the same hazard data the .OUT.TEC was built from.

Public API
----------
    plot_fdb_tec_style(fdb, out_path=None, ...)   -> matplotlib Figure
    generate_scenario_graph(fdb_path, project_dir) -> Path of saved JPG
    generate_all_graphs(project_dir, ...)          -> list[Path]

CLI
---
    python tec_style_graphs.py <project_dir> [--pattern "*.fdb"] [--dpi 150]
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg", force=False)          # headless-safe; Qt app may override
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

log = logging.getLogger("tec_style_graphs")

# ─────────────────────────────────────────────────────────────────────────────
# Panel configuration — mirrors the original Tecplot layout exactly
#   (attr on FDBData, axis label, fixed y-max, unit-conversion factor)
#   Soot uses AUTO unit detection (factor=None): FDB generators differ in
#   whether the SOOT column is kg/m³, g/m³, or already mg/m³. A hardcoded
#   ×1e6 sent mg/m³ data off-scale (vertical-line "curtain" artefact).
# ─────────────────────────────────────────────────────────────────────────────
PANELS = [
    ("soot", "Soot [mg/m3]", 5000.0, None),   # None → auto-detect units
    ("co",   "CO [ppm]",     6000.0, 1.0),
    ("temp", "Temp [deg.]",   500.0, 1.0),
    ("co2",  "CO2 [%]",         5.0, 1.0),
]


def _soot_to_mg_factor(arr: np.ndarray) -> float:
    """Infer the soot column's unit from its magnitude and return the
    multiplier that converts it to mg/m³ for plotting.

    Typical tunnel-fire soot peaks are O(100–2000) mg/m³, so:
      raw max ≤ 0.05   → kg/m³  → ×1e6
      raw max ≤ 50     → g/m³   → ×1e3
      otherwise        → mg/m³  → ×1
    """
    m = float(np.nanmax(arr)) if arr.size else 0.0
    if m <= 0.05:
        return 1.0e6
    if m <= 50.0:
        return 1.0e3
    return 1.0

# Default TIME legend levels (seconds) — matches the VB-era plots
DEFAULT_TIME_LEVELS = [0, 240, 480, 720, 960, 1200]

# Greyscale ramp: t=0 → black, t=t_max → light grey (not pure white,
# so the newest curve stays visible on the white background)
GREY_MIN, GREY_MAX = 0.0, 0.85


def _time_to_grey(t: float, t_max: float) -> str:
    """Map a time value to a greyscale colour string."""
    if t_max <= 0:
        frac = 0.0
    else:
        frac = float(np.clip(t / t_max, 0.0, 1.0))
    g = GREY_MIN + (GREY_MAX - GREY_MIN) * frac
    return (g, g, g)


def _draw_time_legend(ax, levels, t_max):
    """Draw the boxed vertical 'TIME' legend in the panel's top-right corner,
    replicating the Tecplot contour-legend style (white box, black border,
    grey swatches stacked from t_max at top to 0 at bottom)."""
    n = len(levels)
    # Geometry in axes-fraction coordinates
    box_w, row_h = 0.155, 0.082
    pad = 0.012
    box_h = row_h * (n + 1.35)          # +1 row for the TIME title
    x1 = 0.985
    x0 = x1 - box_w
    y1 = 0.975
    y0 = y1 - box_h

    # Outer white box
    ax.add_patch(Rectangle((x0, y0), box_w, box_h,
                           transform=ax.transAxes, facecolor="white",
                           edgecolor="black", linewidth=0.8, zorder=10))
    # Title
    ax.text(x0 + box_w / 2.0, y1 - row_h * 0.55, "TIME",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=8, zorder=12)

    sw_w = box_w * 0.30
    levels_desc = sorted(levels, reverse=True)   # 1200 at top … 0 at bottom
    for i, lv in enumerate(levels_desc):
        ry1 = y1 - row_h * (1.2 + i)             # top of this swatch row
        ax.add_patch(Rectangle((x0 + pad, ry1 - row_h * 0.9),
                               sw_w, row_h * 0.9,
                               transform=ax.transAxes,
                               facecolor=_time_to_grey(lv, t_max),
                               edgecolor="black", linewidth=0.5, zorder=11))
        ax.text(x0 + pad + sw_w + pad, ry1 - row_h * 0.45, f"{int(lv)}",
                transform=ax.transAxes, ha="left", va="center",
                fontsize=8, zorder=12)


def plot_fdb_tec_style(fdb, out_path: Path | str | None = None,
                       time_levels=None, dpi: int = 150,
                       title: str | None = None,
                       t_end: float | None = None):
    """Build the VB/Tecplot-style 2×2 figure from a parsed FDBData object.

    Parameters
    ----------
    fdb         : evc_engine.FDBData (or any object exposing
                  .times, .x_coords, .soot, .co, .temp, .co2 as 2-D
                  [time, x] arrays — soot in kg/m³)
    out_path    : if given, the figure is saved there (.jpg/.png by extension)
    time_levels : legend tick values in seconds (default 0…1200 step 240)
    dpi         : output resolution
    title       : optional suptitle (default: none, like the originals)

    Returns the matplotlib Figure (caller must plt.close() it if looping).
    """
    times = np.asarray(getattr(fdb, "times", []), dtype=float)
    xs    = np.asarray(getattr(fdb, "x_coords", []), dtype=float)
    if times.size == 0 or xs.size == 0:
        raise ValueError("FDB dataset has no time steps / x coordinates")

    # Clip to the EVC simulation end if requested. The VB-era figures were
    # plotted from the EVC .OUT.TEC, which only covers the evacuation
    # simulation duration (typically 1200 s) even when the FDB hazard data
    # extends further (e.g. 1590 s). Pass t_end=1200 for VB-identical framing.
    _tmask = None
    if t_end is not None and t_end > 0:
        _tmask = times <= float(t_end) + 1e-9
        if not np.any(_tmask):
            _tmask = None
        else:
            times = times[_tmask]

    if time_levels is None:
        # Use the classic 0–1200 legend when the data fits, otherwise
        # auto-build six evenly spaced levels up to the last time step.
        if times[-1] <= 1260.0:
            time_levels = DEFAULT_TIME_LEVELS
        else:
            time_levels = list(np.round(np.linspace(0, times[-1], 6)))
    t_max = max(float(max(time_levels)), float(times[-1]), 1.0)

    fig, axes = plt.subplots(2, 2, figsize=(9.6, 4.9))
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.062, right=0.992, top=0.985, bottom=0.03,
                        wspace=0.17, hspace=0.07)

    for (attr, ylabel, ymax, factor), ax in zip(PANELS, axes.flat):
        data = getattr(fdb, attr, None)
        ax.set_facecolor("white")
        ax.set_xlim(float(xs[0]), float(xs[-1]))
        ax.set_ylim(0.0, ymax)
        ax.set_ylabel(ylabel, fontsize=9)

        # Tecplot-like frame + grid: solid black gridlines, ~6 x-divisions
        for spine in ax.spines.values():
            spine.set_linewidth(1.0)
            spine.set_color("black")
        ax.grid(True, which="major", color="black", linewidth=0.5)
        ax.set_xticks(np.linspace(xs[0], xs[-1], 7))
        ax.tick_params(axis="x", labelbottom=False, length=3)
        ax.tick_params(axis="y", labelsize=8, length=3)

        if data is not None:
            arr = np.asarray(data, dtype=float)
            if _tmask is not None:
                arr = arr[_tmask]
            f = _soot_to_mg_factor(arr) if factor is None else factor
            arr = arr * f
            # Oldest (darkest) first so newer/lighter curves draw on top,
            # matching the original zone draw order.
            for ti, t in enumerate(times):
                ax.plot(xs, arr[ti, :], color=_time_to_grey(t, t_max),
                        linewidth=0.8, solid_capstyle="round", zorder=2)

        _draw_time_legend(ax, time_levels, t_max)

    if title:
        fig.suptitle(title, fontsize=10)

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=dpi, facecolor="white")
        log.info("TEC-style graph saved: %s", out_path)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Project-level helpers
# ─────────────────────────────────────────────────────────────────────────────
def _load_fdb(fdb_path: Path):
    """Parse an FDB file using the project's FDBData class."""
    FDBData = None
    try:
        # Works when evc/ is on sys.path (qra_main_app adds it) or when
        # running the CLI from inside the evc/ directory.
        from qra_system_v2.evc.evc_engine_old import FDBData
    except ImportError:
        try:
            # Works when running from the repo root with evc/ as a package.
            from qra_system_v2.evc.evc_engine_old import FDBData
        except ImportError:
            # Last resort: import evc_engine.py from this file's own folder.
            import importlib.util
            _here = Path(__file__).resolve().parent / "evc_engine.py"
            if _here.exists():
                spec = importlib.util.spec_from_file_location("evc_engine", _here)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                FDBData = mod.FDBData
    if FDBData is None:                              # pragma: no cover
        raise ImportError(
            "evc_engine.FDBData is required to parse FDB files "
            "(make sure tec_style_graphs.py sits next to evc_engine.py)")
    return FDBData(Path(fdb_path))


def generate_scenario_graph(fdb_path: Path | str,
                            project_dir: Path | str,
                            dpi: int = 150,
                            t_end: float | None = None) -> Path | None:
    """Parse one FDB file and write <project_dir>/graphs/<scenario>.jpg.

    The scenario name is the FDB file stem (e.g. 020CFV0.fdb → 020CFV0.jpg),
    matching the VB-era naming convention.
    Returns the saved Path, or None if the FDB held no usable data.
    """
    fdb_path = Path(fdb_path)
    out_dir = Path(project_dir) / "graphs"
    out_dir.mkdir(parents=True, exist_ok=True)

    fdb = _load_fdb(fdb_path)
    if len(getattr(fdb, "times", [])) == 0:
        log.warning("Skipping %s — no data rows parsed", fdb_path.name)
        return None

    out_path = out_dir / f"{fdb_path.stem}.jpg"
    fig = plot_fdb_tec_style(fdb, out_path=out_path, dpi=dpi, t_end=t_end)
    plt.close(fig)
    return out_path


def generate_from_loaded_fdb(fdb,
                            fdb_stem: str,
                            project_dir: Path | str,
                            dpi: int = 150,
                            t_end: float | None = None) -> "Path | None":
    """Render a TEC-style JPG from an already-parsed FDBData object.

    Equivalent to generate_scenario_graph but skips the file-parse step,
    reusing the FDB that EVCEngine already holds in memory.

    Parameters
    ----------
    fdb         : evc_engine.FDBData — the loaded dataset (may be None)
    fdb_stem    : filename stem used for the output JPG (e.g. '020CFV0')
    project_dir : project root; the JPG is written to <project_dir>/graphs/
    dpi         : output resolution (default 150)

    Returns the saved Path, or None if the FDB held no usable data.
    """
    if fdb is None or len(getattr(fdb, "times", [])) == 0:
        log.warning("Skipping %s — no data rows in loaded FDB", fdb_stem)
        return None
    out_dir = Path(project_dir) / "graphs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{fdb_stem}.jpg"
    fig = plot_fdb_tec_style(fdb, out_path=out_path, dpi=dpi, t_end=t_end)
    plt.close(fig)
    return out_path


def generate_all_graphs(project_dir: Path | str,
                        pattern: str = "*.fdb",
                        dpi: int = 150,
                        t_end: float | None = None) -> list[Path]:
    """Find every FDB file under the project directory (recursively) and
    render one TEC-style JPG per scenario into <project_dir>/graphs/.

    Returns the list of files written.
    """
    project_dir = Path(project_dir)
    written: list[Path] = []
    fdb_files = sorted(project_dir.rglob(pattern))
    if not fdb_files:
        log.warning("No %s files found under %s", pattern, project_dir)
        return written

    for fdb_path in fdb_files:
        # Don't re-plot anything that already lives inside graphs/
        if "graphs" in fdb_path.parts:
            continue
        try:
            p = generate_scenario_graph(fdb_path, project_dir, dpi=dpi, t_end=t_end)
            if p is not None:
                written.append(p)
        except Exception:
            log.exception("Failed to plot %s", fdb_path)
    return written


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s  %(message)s")
    ap = argparse.ArgumentParser(
        description="Render VB/Tecplot-style 4-panel scenario graphs "
                    "(Soot/CO/Temp/CO2 vs X, grey-shaded by TIME) into "
                    "<project_dir>/graphs/")
    ap.add_argument("project_dir", help="QRA project directory")
    ap.add_argument("--pattern", default="*.fdb",
                    help="glob for scenario data files (default *.fdb)")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--t-end", type=float, default=None,
                    help="clip plotted time steps at this simulation end "
                         "(e.g. 1200 to match the VB .OUT.TEC framing)")
    args = ap.parse_args()

    files = generate_all_graphs(args.project_dir, args.pattern, args.dpi,
                                t_end=args.t_end)
    print(f"{len(files)} graph(s) written to "
          f"{Path(args.project_dir) / 'graphs'}")
    for f in files:
        print("  ", f.name)
    sys.exit(0 if files else 1)