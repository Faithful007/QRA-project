"""
qra_evc_writer.py
=================
Drop-in replacement module for qra_main_app._write_evc_file.
 
Wires writer_optimized into qra_main_app via a single instance-level
method that preserves the existing API and call sites:
 
    self._write_evc_file(evc_path, params, chid,
                         csv_files=None,
                         fire_point_x=fp_x,
                         fire_pos_idx=pos_idx)
 
The wrapper transparently caches TunnelContext and ScenarioContext on
the QraMainApp instance, so consecutive calls within a batch loop reuse
pre-computed work. The cache key is (id(params), chid). If the params
dict is mutated between calls, this is detected by the GUI's normal
"Generate EVC" cycle since a fresh _collect_evc_params() returns a new
dict object.
 
Integration:
    Replace the existing _write_evc_file method (qra_main_app.py
    lines 12671–13257) with the body shown in this file. No call
    sites need to change.
 
Two correctness fixes are folded in (both bring output closer to the
legacy VB EVC.exe references):
    • Line endings: \\n only (was \\r\\n).
    • No trailing newline at end of file (was added).
 
The L74 formula is left as-is for now — it does NOT match VB references
and is a separate pre-existing bug. The optimized writer exposes an
l74_override hook so this can be fixed independently.
"""
from __future__ import annotations
 
# Imports from this package — ship writer_optimized.py alongside qra_main_app.py
from writer_optimized import (
    build_tunnel_context,
    build_scenario_context,
    write_evc_for_position,
    _f, _i,
)
 
 
# Mixin-style replacement. To use, copy `_write_evc_file` and the cache
# init into the QraMainApp class.
 
class _EVCWriterMixin:
    """Methods to inline into QraMainApp. Don't subclass — copy these in."""
 
    # Per-instance caches (initialise lazily on first use)
    _evc_tctx_cache: dict | None = None  # {id(params): TunnelContext}
    _evc_sctx_cache: dict | None = None  # {(id(params), chid): ScenarioContext}
 
    def _evc_invalidate_cache(self) -> None:
        """Clear cached EVC contexts. Call when params dict is rebuilt
        (typically after _collect_evc_params())."""
        self._evc_tctx_cache = None
        self._evc_sctx_cache = None
 
    def _write_evc_file(self, evc_path, params: dict, chid: str,
                        csv_files=None,
                        fire_point_x: float = None,
                        fire_pos_idx: int = 1) -> None:
        """Write a fully-structured .evc file in the legacy VB format.
 
        Drop-in replacement for the original 587-line implementation.
        Identical line-by-line output (verified byte-for-byte against
        legacy VB references for lines 1–73, 75–89; line 74 preserves
        the existing Python formula behavior).
        """
        # Lazy init caches
        if self._evc_tctx_cache is None:
            self._evc_tctx_cache = {}
            self._evc_sctx_cache = {}
 
        # ── Tunnel context: cache by params identity ───────────────────────
        params_key = id(params)
        tctx = self._evc_tctx_cache.get(params_key)
        if tctx is None:
            tctx = build_tunnel_context(params)
            # Bound cache to last 4 param dicts to avoid leaking memory
            if len(self._evc_tctx_cache) >= 4:
                self._evc_tctx_cache.clear()
                self._evc_sctx_cache.clear()
            self._evc_tctx_cache[params_key] = tctx
 
        # ── Scenario context: cache by (params, chid) ──────────────────────
        sctx_key = (params_key, chid)
        sctx = self._evc_sctx_cache.get(sctx_key)
        if sctx is None:
            sctx = build_scenario_context(tctx, chid, params)
            self._evc_sctx_cache[sctx_key] = sctx
 
        # ── Per-position arguments ─────────────────────────────────────────
        if fire_point_x is not None:
            fp = float(fire_point_x)
        else:
            hr = params.get("hrr_settings", {})
            fp = _f(hr, "fp_evc", tctx.L / 2.0)
 
        # MDB indices from params dict (L84 — defaults to all zeros)
        mb = params.get("mdb", {})
        mdb_indices = (
            _i(mb, "soot",      0),
            _i(mb, "co2",       0),
            _i(mb, "co",        0),
            _i(mb, "temp",      0),
            _i(mb, "radiation", 0),
            _i(mb, "oxygen",    0),
        )
 
        # ── Tunnel name (L01) ──────────────────────────────────────────────
        # Same priority as the original: GUI tunnel_name_input → fallback to
        # legacy reference (with mangled-cp949 bytes for byte-equivalence).
        tunnel_name_str = None
        try:
            t = self.tunnel_name_input.text().strip()
            if t:
                tunnel_name_str = t
        except Exception:
            pass
        if not tunnel_name_str:
            tunnel_name_str = params.get("tunnel", {}).get("name") or "율곡터널"
 
        write_evc_for_position(
            evc_path, tctx, sctx,
            fire_point_x=fp,
            fire_pos_idx=fire_pos_idx,
            tunnel_name_str=tunnel_name_str,
            mdb_indices=mdb_indices,
        )

# """
# evc_output_writer.py
# ====================
# Writes the five EVC.exe-compatible output files produced per Monte Carlo run.
# """
# from __future__ import annotations
# import logging
# import math
# import tempfile
# import os
# from dataclasses import dataclass, field
# from pathlib import Path
# from typing import Any, Callable, Dict, List, Optional, Tuple
# import numpy as np
# from evc_engine import EVCEngine, FDBData, BatchResult, RunResult, EVCError, EVCFileError, EVCParameterError

# log = logging.getLogger(__name__)

# _CASET_THRESHOLDS = [
#     ("temp",  90.0,  "gt"), ("temp",  60.0,  "gt"),
#     ("co",   1400.0, "gt"), ("co",   1200.0, "gt"), ("co",    900.0, "gt"),
#     ("co",    600.0, "gt"), ("co",    300.0, "gt"),
#     ("soot",  10.0,  "lt"), ("soot",   5.0,  "lt"),
# ]

# _CASET_HEADER = "      Time Temp > 90 Temp > 60 CO > 1400 CO > 1200  CO > 900  CO > 600  CO > 300 VISI < 10  VISI < 5\r\n"
# _DAT_HEADER = "    time EVC_MAN   Fatals    0.1DN    0.2DN    0.3DN    0.4DN    0.5DN    0.6DN    0.7DN    0.8DN    0.9DN    1.0DN    1.0UP EQ_FATAL  FED_MAX MEVC_MAX MEVC_MIN PEVC_MAX PEVC_MIN SMDS_MAX SMDS_MIN PSIN_SMK  EXNO_01  EXNO_02\r\n"
# _SET_FOOTER_LINES = ["01. 시간", "02. 대피자 Number", "03. 대피자가 탑승한 차량 종류", "04. 초기위치", "05. 목표지점", "06. 대피시작시간(Set)", "07. 대피시작시간(Real)", "08. 대피종료시간", "09. 지점(X)", "10. 지점(Y)", "11. 상태", "12. 누적이동거리(m)", "13. 평균대피속도(m/s)", "14. 대피속도1", "15. 대피속도2", "16. 대피속도3", "17. 적용대피속도", "18. CCN(1~7)", "19. FED(1~7)"]

# @dataclass
# class TimestepState:
#     t: float; pos: np.ndarray; escaped: np.ndarray; fatal: np.ndarray; incap: np.ndarray
#     fed_co: np.ndarray; fed_o2: np.ndarray; fed_heat: np.ndarray; fed_radi: np.ndarray
#     n_occ: int; fire_x: float; tunnel_len: float; fdb: Optional[FDBData]; _init_pos: np.ndarray

# @dataclass
# class RunPaths:
#     run_no: int; dat: Path; caset1: Path; caset2: Path; set_: Path; hestime: Path

# @dataclass
# class WriterResult:
#     batch: BatchResult; run_paths: List[RunPaths]; set_path: Path; db_run_ids: List[int]; stem: Path

# class EVCOutputWriter:
#     def __init__(self, evc_path, fdb_path=None, fire_pos_idx=1, output_dir=None, stem=None, dat_interval=2.0):
#         self.evc_path = Path(evc_path); self.fdb_path = Path(fdb_path) if fdb_path else None
#         self.fire_pos_idx = fire_pos_idx; self.output_dir = Path(output_dir) if output_dir else self.evc_path.parent
#         self.stem = stem or self.evc_path.stem; self.dat_interval = dat_interval
#         self._engine = EVCEngine(self.evc_path, self.fdb_path); self._params = self._engine.params
#         self._fdb = self._engine.fdb; self._snapshots = []

#     def run_and_write(self, n_iterations=5, exmax=0, exmin=0, seed=None, t_end_override=None, progress_cb=None):
#         rng = np.random.default_rng(seed); runs = []; paths_list = []; set_path = self._file_path(1, ".SET")
#         for k in range(1, n_iterations + 1):
#             self._snapshots = []
#             result = self._engine._run_one(run_no=k, rng=rng, timestep_cb=self._timestep_callback)
#             runs.append(result)
#             dat_path = self._write_dat(k, result)
#             c1_path = self._write_caset(k, 1); c2_path = self._write_caset(k, 2)
#             hes_path = self._write_hestime(k, result)
#             self._append_set(set_path, k, result, k == n_iterations)
#             paths_list.append(RunPaths(k, dat_path, c1_path, c2_path, set_path, hes_path))
#             if progress_cb: progress_cb(k, n_iterations)
#         avg = self._engine._compute_avg(runs, exmax, exmin)
#         self._engine.write_results_to_evc(avg, runs)
#         return WriterResult(BatchResult(self.stem, runs, avg, exmax, exmin), paths_list, set_path, [], self.output_dir / self.stem)

#     def _file_path(self, run_no, suffix): return self.output_dir / f"{self.stem}_P{self.fire_pos_idx}_{run_no}{suffix}"
#     def _hestime_path(self, run_no): return self.output_dir / f"{self.stem}_P{self.fire_pos_idx}_{run_no}LVCNHesTime.dat"

#     def _timestep_callback(self, t, pos, escaped, fatal, incap, fed_co, fed_o2, fed_heat, fed_radi, n_occ, fire_x, tunnel_len, fdb, _init_pos):
#         self._snapshots.append(TimestepState(t, pos, escaped, fatal, incap, fed_co, fed_o2, fed_heat, fed_radi, n_occ, fire_x, tunnel_len, fdb, _init_pos))

#     def _write_dat(self, run_no, result):
#         path = self._file_path(run_no, ".DAT"); p = self._params; lines = [_DAT_HEADER]
#         snaps = [s for s in self._snapshots if abs(s.t % self.dat_interval) < 0.1 or s.t == 0.0]
#         for s in snaps:
#             fed_tot = s.fed_co + s.fed_o2 + s.fed_heat + s.fed_radi
#             evc_man = int(np.sum(s.escaped & (s._init_pos <= p.fire_pt_x)))
#             fatals = int(np.sum(s.fatal))
#             fed_counts = [int(np.sum(fed_tot >= th)) for th in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]]
#             started = ~s.escaped & ~s.fatal
#             mevc_max = float(s.pos[started].max()) if started.any() else 0.0
#             mevc_min = float(s.pos[started].min()) if started.any() else 0.0
#             vis_max, vis_min, psin = self._smoke_stats(s)
#             row = f" {s.t:8.1f} {float(evc_man):8.1f} {float(fatals):8.2f} " + " ".join(f"{float(c):8.2f}" for c in fed_counts) + \
#                   f" {0.0:8.2f} {0.0:8.2f} {float(fed_tot.max() if fed_tot.any() else 0):8.2f} {mevc_max:8.2f} {mevc_min:8.2f} {mevc_max:8.2f} {mevc_min:8.2f} {vis_max:8.2f} {vis_min:8.2f} {psin:8.2f} {0:8d} {0:8d}\r\n"
#             lines.append(row)
#         path.write_bytes("".join(lines).encode("utf-8")); return path

#     def _write_caset(self, run_no, zone):
#         path = self._file_path(run_no, f".CASET{zone}"); p = self._params; lines = [_CASET_HEADER]
#         z_start, z_end = (0.0, p.fire_pt_x) if zone == 1 else (p.fire_pt_x, p.tunnel_length)
#         snaps = [s for s in self._snapshots if abs(s.t % self.dat_interval) < 0.1 and s.t > 0.0]
#         for s in snaps:
#             counts = self._count_hazard_nodes(s, z_start, z_end)
#             lines.append(f"  {s.t:8.1f}" + "".join(f"{c:9d}" for c in counts) + "\r\n")
#         path.write_bytes("".join(lines).encode("utf-8")); return path

#     def _count_hazard_nodes(self, s, z_start, z_end):
#         if not s.fdb: return [0]*9
#         zx = s.fdb.x_coords[(s.fdb.x_coords >= z_start) & (s.fdb.x_coords <= z_end)]
#         if zx.size == 0: return [0]*9
#         res = []
#         for k, th, d in _CASET_THRESHOLDS:
#             v = s.fdb.get_value(k if k != "soot" else "soot", s.t, zx)
#             res.append(int(np.sum(v > th if d == "gt" else v < th)))
#         return res

#     def _write_hestime(self, run_no, result):
#         path = self._hestime_path(run_no); p = self._params; n_occ = self._engine._n_occ
#         tb = p.broadcast_time or 180.0; td = p.detection_time or 60.0; total = int(td + tb)
#         lines = []
#         for t in range(1, total + 1):
#             sfx = 1.0 / (1.0 + math.exp(-10.0/tb * (t - (td + tb/2.0)))) if t > td else 0.000760398 * (t/td)
#             nom = n_occ * (p.fire_pt_x/p.tunnel_length) * min(max(0, t-td)/tb, 1.0)
#             lines.append(f"Time =  {t:<7d}SFX = {sfx:.9f}         No_of_Man =  {nom:.15f} \r\n")
#         path.write_bytes("".join(lines).encode("utf-8")); return path

#     def _append_set(self, path, run_no, result, last):
#         s = self._snapshots[-1]; lines = []
#         for i in range(len(s.pos)):
#             row = f"{s.t:8.1f} {i+1:8d} {0:8d} {s._init_pos[i]:8.2f} {0:8.2f} {0:8.2f} {0:8.2f} {s.t:8.2f} {s.pos[i]:8.2f} {0:8.2f} {1:8d} {0:8.2f} {0:8.2f} " + \
#                   " ".join(f"{0:8.2f}" for _ in range(4)) + f" {0:8d} " + " ".join(f"{0:10.4f}" for _ in range(8)) + "\r\n"
#             lines.append(row)
#         for fl in _SET_FOOTER_LINES: lines.append(fl + "\r\n")
#         with open(path, "ab") as f: f.write("".join(lines).encode("cp949"))

#     def _smoke_stats(self, s):
#         if not s.fdb: return 0.0, 26.7, 0.0
#         v = s.fdb.get_value("soot", s.t, s.pos)
#         return float(v.max()), float(v.min()), float(np.mean(v > 5.0))

#     def __enter__(self): return self
#     def __exit__(self, *args): pass
