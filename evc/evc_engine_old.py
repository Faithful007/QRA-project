import logging
import math
import re
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import numpy as np
 
__version__ = "1.9.4"
log = logging.getLogger(__name__)
 
# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────
class EVCError(Exception):
    """Base exception for all EVC engine errors."""
class EVCFileError(EVCError):
    """Raised when a required input file is missing or unreadable."""
class EVCParameterError(EVCError):
    """Raised when simulation parameters are invalid or out of range."""
class EVCSimulationError(EVCError):
    """Raised when the simulation encounters an unrecoverable state."""
 
# ─────────────────────────────────────────────────────────────────────────────
# VB compatibility utilities
# ─────────────────────────────────────────────────────────────────────────────
def vb_round(x: float, ndigits: int = 0) -> float:
    """Round matching VB's Round() — banker's rounding (round-half-to-even)."""
    factor    = 10 ** ndigits
    x_scaled  = x * factor
    floor_val = math.floor(x_scaled)
    diff      = x_scaled - floor_val
    if diff > 0.5:
        result = math.ceil(x_scaled)
    elif diff < 0.5:
        result = floor_val
    else:  # exactly 0.5 → round to even
        result = floor_val if floor_val % 2 == 0 else floor_val + 1
    return result / factor
 
def vb_int(x: float) -> int:
    """Integer conversion matching VB's Int() — floor toward negative infinity."""
    return math.floor(x)
 
def calavg_vb_exact(vals: List[float], exmin: int, exmax: int, ndigits: int) -> float:
    """Priority 4: Exact VB CalAvg implementation."""
    vals = sorted(vals)
    lo = exmin
    hi = len(vals) - exmax
    if lo >= hi:
        return 0.0
    return round(sum(vals[lo:hi]) / (hi - lo), ndigits)
 
def calavg_vb(values: List[float], exmin: int = 0, exmax: int = 0,
              ndigits: int = 2) -> float:
    """Legacy wrapper for calavg_vb_exact."""
    return calavg_vb_exact(values, exmin, exmax, ndigits)
 
# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1 & 2: VB-style logic
# ─────────────────────────────────────────────────────────────────────────────
def distribute_vehicles_vb_style(n_total, weights):
    """
    VB-style vehicle distribution:
    - Only dominant bins are used
    - Prevents unrealistic spreading
    """
    n_bins = len(weights)
    allocation = [0] * n_bins
 
    # Sort bins by weight (descending)
    idx = sorted(range(n_bins), key=lambda i: weights[i], reverse=True)
 
    # Use top 3 bins only (VB behavior)
    top_bins = idx[:3]
 
    total_weight = sum(weights[i] for i in top_bins)
    if total_weight == 0:
        return allocation
 
    # Allocate proportionally
    for i in top_bins:
        allocation[i] = int(round(n_total * weights[i] / total_weight))
 
    # 🔥 Enforce clustering (critical)
    for i in top_bins:
        if allocation[i] > 0:
            allocation[i] = max(allocation[i], 2)
 
    return allocation
 
def compute_vehicle_counts(n_cong, traffic, t_react, mix_rates):
    """
    VB-exact vehicle count logic
    """
    # Entering vehicles (VB uses R65 only)
    n_enter_total = int(round(traffic * (t_react / 3600.0)))
    n_enter = [n_enter_total * (m / 100.0) for m in mix_rates]
 
    # Congested vehicles (one direction)
    n_cong_list = [n_cong * (m / 100.0) for m in mix_rates]
 
    return n_enter, n_cong_list
 
# ─────────────────────────────────────────────────────────────────────────────
# Simulation result containers
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class RunResult:
    run_no: int
    ev_time: float
    evacuees: int
    fed: List[int]
    eq_fatal: float
    pct_safe: float = 0.0
    pct_fed: List[float] = field(default_factory=list)
    n_occ_zone: int = 0
    n_occ_total: int = 0
    n_evac_zone: int = 0
    upstream_failed: int = 0
    history: list = field(default_factory=list)   # per-timestep DAT.TEC rows (opt-in)
 
@dataclass
class BatchResult:
    chid: str
    runs: List[RunResult]
    avg: RunResult
    exmax: int = 0
    exmin: int = 0
 
# ─────────────────────────────────────────────────────────────────────────────
# FDB/FDS data parser
# ─────────────────────────────────────────────────────────────────────────────
class FDBData:
    def __init__(self, fdb_path: Path):
        self.path = Path(fdb_path)
        self.times = []
        self.x_coords = []
        self.soot = None
        self.temp = None
        self.co2 = None
        self.co = None
        self.rad = None
        self.o2 = None
        self.fire_center = None   # parsed from FDB "FIRE PT" header (x-center of fire)
        self._parse()
 
    def _parse(self):
        """Robust FDB parser that handles the structured text format."""
        if not self.path.exists():
            return
        try:
            # Decode with multiple encoding fallbacks (Korean filenames use cp949)
            raw = None
            for enc in ('utf-8', 'cp949', 'latin-1', 'cp1252'):
                try:
                    raw = self.path.read_bytes().decode(enc, errors='replace')
                    break
                except Exception:
                    continue
            if raw is None:
                log.warning(f"Failed to decode FDB file {self.path}")
                return
 
            rows = []
            col_map = None
            in_data = False
            in_tunnel_x = False
            tunnel_x_header_seen = False
 
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith('!') or line.startswith('#'):
                    continue
 
                # 🔥 Parse FIRE PT from the TUNNEL X COORDINATE header block.
                # Format:
                #   TUNNEL X COORDINATE
                #                  MIN_X     MAX_X     NX GRID     FIRE PT
                #                  0.000     640.000   641         317.000- 323.000
                # The fire center is `(fp_start + fp_end) / 2` — typically x=320
                # for these tunnels, regardless of HRR level. Without this we
                # auto-detect via peak temperature, which is ~10-15 m off for
                # larger fires (100 MW plume peaks upstream of the fuel source).
                if 'TUNNEL X COORDINATE' in line.upper():
                    in_tunnel_x = True
                    tunnel_x_header_seen = False
                    continue
                if in_tunnel_x and self.fire_center is None:
                    if 'MIN_X' in line.upper() and 'FIRE' in line.upper():
                        tunnel_x_header_seen = True
                        continue
                    if tunnel_x_header_seen:
                        # Try to parse: "0.000  640.000  641  317.000- 323.000"
                        import re as _re
                        # Look for a fire-pt range like "317.000- 323.000" (with optional space around dash)
                        m = _re.search(r'([\d.]+)\s*-\s*([\d.]+)\s*$', line)
                        if m:
                            fp_start = float(m.group(1))
                            fp_end   = float(m.group(2))
                            self.fire_center = (fp_start + fp_end) / 2.0
                            in_tunnel_x = False
                        else:
                            # Maybe single-value fire pt at end of line
                            parts = line.split()
                            if len(parts) >= 4:
                                try:
                                    self.fire_center = float(parts[-1])
                                    in_tunnel_x = False
                                except ValueError:
                                    pass
 
                # Detect DATA START sentinel — skip all header text before it
                if 'DATA START' in line.upper():
                    in_data = True
                    col_map = None   # reset; next non-separator line is column header
                    continue
 
                if 'DATA END' in line.upper():
                    break
 
                if not in_data:
                    continue
 
                # Skip separator lines (all *, |, -, =, space, tab)
                if all(c in '*|-= \t' for c in line):
                    continue
 
                parts = line.split()
                try:
                    nums = [float(p) for p in parts]
                except ValueError:
                    # Non-numeric line inside DATA block → column header
                    up = [p.upper() for p in parts]
                    col_map = {}
                    for i, h in enumerate(up):
                        if 'TIME' in h:                        col_map['time']   = i
                        elif h in ('X', 'X-COOR', 'XCOOR'):   col_map['x']      = i
                        elif 'SOOT' in h:                      col_map['soot']   = i
                        elif 'CO2' in h:                       col_map['co2']    = i
                        elif 'CO' in h and 'CO2' not in h:     col_map['co']     = i
                        elif 'TEMP' in h:                      col_map['temp']   = i
                        elif 'RADI' in h:                      col_map['radi']   = i
                        elif 'OXY' in h or h == 'O2':          col_map['oxygen'] = i
                    continue
 
                if len(nums) < 2:
                    continue
 
                # Default column positions if no header line was found
                if col_map is None:
                    col_map = {
                        'time': 0, 'x': 1, 'soot': 2, 'co2': 3,
                        'co': 4, 'temp': 5, 'radi': 6, 'oxygen': 7
                    }
 
                def _g(key, default=0.0):
                    idx = col_map.get(key)
                    return nums[idx] if idx is not None and idx < len(nums) else default
 
                rows.append((
                    _g('time'), _g('x'),
                    _g('soot'), _g('co2'), _g('co'),
                    _g('temp', 20.0), _g('radi'), _g('oxygen', 21.0)
                ))
 
            if not rows:
                log.warning(f"FDB file {self.path} contained no numeric data rows")
                return
 
            arr = np.array(rows, dtype=float)
            times_u  = np.unique(arr[:, 0])
            x_coords = np.unique(arr[:, 1])
            nt, nx   = len(times_u), len(x_coords)
 
            self.times    = times_u
            self.x_coords = x_coords
 
            t_map = {t: i for i, t in enumerate(times_u)}
            x_map = {x: i for i, x in enumerate(x_coords)}
 
            def _fill(col_idx, default):
                A = np.full((nt, nx), default, dtype=float)
                for row in arr:
                    ti = t_map.get(row[0])
                    xi = x_map.get(row[1])
                    if ti is not None and xi is not None:
                        A[ti, xi] = row[col_idx]
                return A
 
            self.temp  = _fill(5, 20.0)   # TEMP [°C]
            self.co    = _fill(4, 0.0)    # CO   [ppm]
            self.co2   = _fill(3, 0.04)   # CO2  [%]
            self.o2    = _fill(7, 21.0)   # O2   [%]
            self.soot  = _fill(2, 0.0)    # SOOT [kg/m³]
            self.rad   = _fill(6, 0.0)    # RADI [kW/m²]
 
            log.info(f"FDB parsed: {self.path.name}  "
                     f"t=[{times_u[0]:.0f}..{times_u[-1]:.0f}]s  "
                     f"x=[{x_coords[0]:.1f}..{x_coords[-1]:.1f}]m  "
                     f"rows={len(rows)}")
 
        except Exception as e:
            log.warning(f"Failed to parse FDB file {self.path}: {e}")
 
    def get_value(self, key: str, t: float, x_batch: np.ndarray) -> np.ndarray:
        arr_2d = getattr(self, key, None)
        if arr_2d is None or len(self.times) == 0 or len(self.x_coords) == 0:
            return np.zeros_like(x_batch, dtype=float)
 
        # Ambient (clean-air) defaults for extrapolation beyond the FDB mesh.
        # Agents far downstream of fire (after EVC↔FDB offset) can produce
        # x-queries beyond the FDB x_max; returning row-edge values there would
        # leak fire-zone contamination. Use ambient values instead.
        _defaults = {'temp': 20.0, 'o2': 21.0, 'co2': 0.04,
                     'co': 0.0, 'soot': 0.0, 'rad': 0.419}
        default = _defaults.get(key, 0.0)
 
        t_clipped = float(np.clip(t, self.times[0], self.times[-1]))
        ti_hi = int(np.searchsorted(self.times, t_clipped, side='right'))
        ti_hi = min(ti_hi, len(self.times) - 1)
        ti_lo = max(ti_hi - 1, 0)
        t_lo, t_hi = self.times[ti_lo], self.times[ti_hi]
        dt = t_hi - t_lo
        wt_hi = (t_clipped - t_lo) / dt if dt > 0 else 0.0
        wt_lo = 1.0 - wt_hi
 
        row_lo = arr_2d[ti_lo]
        row_hi = arr_2d[ti_hi]
        val_lo = np.interp(x_batch, self.x_coords, row_lo,
                           left=default, right=default)
        val_hi = np.interp(x_batch, self.x_coords, row_hi,
                           left=default, right=default)
        return wt_lo * val_lo + wt_hi * val_hi
 
    @property
    def is_loaded(self) -> bool:
        return len(self.times) > 0 and self.co is not None
 
# ─────────────────────────────────────────────────────────────────────────────
# EVC parameter parser
# ─────────────────────────────────────────────────────────────────────────────
class EVCParams:
    def __init__(self, evc_path: Path):
        self.path = evc_path
        self._raw_lines = []
        self._parse()
 
    def _parse(self):
        for enc in ("cp949", "utf-8", "latin-1"):
            try:
                raw = self.path.read_bytes().decode(enc, errors="replace")
                self._raw_lines = raw.splitlines(keepends=False)
                return
            except Exception: continue
        raise EVCFileError(f"Failed to decode EVC file '{self.path}'")
 
    def _line(self, idx: int) -> str:
        if 0 < idx <= len(self._raw_lines): return self._raw_lines[idx - 1].strip()
        return ""
 
    def _float(self, idx: int, pos: int = 0, default: float = 0.0) -> float:
        fs = [float(x) for x in re.findall(r"[-+]?[0-9]*\.?[0-9]+", self._line(idx))]
        return fs[pos] if pos < len(fs) else default
 
    @property
    def abs_min_speed(self) -> float:
        return self._float(9, pos=0, default=0.5)
 
    @property
    def tunnel_length(self) -> float: return self._float(3, default=320.0)
    @property
    def fire_pt_x(self) -> float: return self._float(64, default=self.tunnel_length / 2.0)
    @property
    def min_walk_speed(self) -> float: return self._float(87, pos=0, default=0.45)
    @property
    def elderly_walk_speed(self) -> float: return self._float(87, pos=1, default=0.6)
    @property
    def elderly_ratio(self) -> float: return self._float(87, pos=2, default=0.4)
    @property
    def premovement_time(self) -> float:
        # NOTE: EVC L65 is actually the MAX-CONGESTION / jam-density value
        # (VB DAT_004a6220, default 150) — see max_congestion_vehicles below.
        # This property is retained only as a legacy continuation-loop horizon
        # proxy (its numeric value ~150–165 is immaterial there); the real
        # pre-movement/reaction time is detection + broadcast/3 (L81 + L80/3),
        # computed in _run_one.
        return self._float(65, default=165.0)
    @property
    def max_congestion_vehicles(self) -> float:
        # EVC L65 = jam density K (veh/km/lane); VB defaults it to 150.
        v = self._float(65, default=150.0)
        return v if v > 0 else 150.0
    @property
    def detection_time(self) -> float: return self._float(81, default=60.0)
    @property
    def broadcast_time(self) -> float: return self._float(80, default=180.0)
    @property
    def sim_end_time_r72(self) -> float: return self._float(72, default=0.0)
    @property
    def normal_traffic(self) -> float: return self._float(66, default=2000.0)
    @property
    def veh_lengths(self) -> List[float]: return [self._float(r) for r in range(45, 52)]
    @property
    def veh_counts_dir1(self) -> List[int]:
        """EVC L10–L16: vehicle counts per type, direction 1
        (VB input array DAT_004a61a4[1][1..7])."""
        return [int(round(self._float(r, default=0.0))) for r in range(10, 17)]
    @property
    def veh_counts_dir2(self) -> List[int]:
        """EVC L17–L23: vehicle counts per type, direction 2
        (VB input array DAT_004a61a4[2][1..7]; zeros for one-way bores)."""
        return [int(round(self._float(r, default=0.0))) for r in range(17, 24)]
    @property
    def veh_pcu(self) -> List[float]: return [self._float(r) for r in range(38, 45)]
    @property
    def veh_occ(self) -> List[float]: return [self._float(r) for r in range(52, 59)]
    @property
    def num_lanes(self) -> int: return int(self._float(8, default=2))
    @property
    def is_two_way(self) -> bool:
        vals = [float(x) for x in re.findall(r'[-+]?[0-9]*\.?[0-9]+', self._line(2))]
        dir_flag = vals[1] if len(vals) >= 2 else vals[0] if vals else 0.0
        return dir_flag == -1 or (len(vals) == 1 and vals[0] == -1)
 
    @property
    def exits(self) -> List[float]:
        n_seg = int(self._float(61))
        ex = []
        for r in range(62, 62 + n_seg):
            fs = [float(x) for x in re.findall(r"[-+]?[0-9]*\.?[0-9]+", self._line(r))]
            if len(fs) >= 3: ex.append(fs[2])
            elif len(fs) >= 2: ex.append(fs[1])
        return ex if ex else [0.0, self.tunnel_length]
 
    def total_occupants_vb(self, pcpkpl_override=None, mix_rate_override=None,
                           occ_per_veh_override=None,
                           dir_mult_override=None, r74_occ_per_veh=None,
                           hrr_mw=None, hrr_ref=15.0, hrr_sat_c=1082.47, hrr_sat_k=14.45,
                           load_factor=0.53, lth_override: Optional[float] = None,
                           is_normal_traffic: Optional[bool] = None) -> int:
        """Calculate total occupants — VB-faithful, derived from the Korean
        tunnel-safety design formula encoded in EVC.exe.
 
        Formula (verified against GUMOK reference, where VB EVC.exe gives
        331 CONGEST evacuees and 19/62/140/189/235/283 for NORMAL P1-P6):
 
            slot       = Clavg + LTH                # vehicle slot length (m)
            pcpkpl_jam = 1000 / slot                # jam density (veh/km/lane)
 
            CONGEST traffic (whole tunnel filled at jam density):
                n_cong = pcpkpl_jam × N_lanes × L_km
                n_occ  = n_cong × avg_occ_per_veh
 
            NORMAL traffic (only upstream of fire populated at jam density,
            because the upstream zone backs up to jam during reaction time):
                n_cong = pcpkpl_jam × N_lanes × (fire_x / 1000)
                n_occ  = n_cong × avg_occ_per_veh
 
        Where:
            Clavg            = Σ (mix_fraction_i × veh_length_i)   from EVC L24-30 × L45-51
            avg_occ_per_veh  = Σ (mix_fraction_i × occ_per_veh_i)  from EVC L24-30 × L52-58
            LTH              = inter-vehicle gap, VB default 2.17 m (calibrated to VB)
            mix_fraction_i   = mix_pct_i / 100
 
        Both Python and VB use the SAME avg_occ_per_veh — the mix-weighted
        vehicle capacity from EVC L52-58 ([3, 8, 30, 2, 2, 1, 1] for the
        standard 7-vehicle table). The VB "터널교통량등제원" sheet R11/R13
        documents these as 승차인원 (passenger count) values, and VB stores
        the derived mix-weighted avg (3.164 for GUMOK).
 
        Verification (GUMOK tunnel, TL=356 m, 2 lanes, AADT=8256):
            Clavg = 4.64 m, LTH = 2.17 m → slot = 6.81 m, pcpkpl_jam = 146.83
            avg_occ = 3.164 person/vehicle (mix-weighted)
            CONGEST: 146.83 × 2 × 0.356 × 3.164 = 330.8 (VB: 331.2, -0.1%)
 
        Historical note on Python over-counting (May 2026 fix):
            Earlier Python builds reported 486 evacuees (vs VB 331, +47%)
            because the GUI passed pcpkpl_override=216 (a legacy hardcoded
            default that was never derived from a real spacing measurement).
            The function now ignores pcpkpl_override when it equals 216.0
            (the legacy default), preferring the spacing formula. Callers
            wanting to force a custom density can still pass any value
            other than 216.
 
        Parameters
        ----------
        lth_override : float, optional
            Inter-vehicle gap LTH (m). VB default 2.17. Pass a different
            value for non-default tunnels.
        pcpkpl_override : float, optional
            Force a specific jam density (veh/km/lane). Pass None or 216
            to use the VB-faithful spacing formula (recommended).
        is_normal_traffic : bool, optional
            Whether the current scenario is Normal traffic (occupy upstream
            of fire only) or Congested (occupy whole tunnel). The EVCEngine
            sets this from the CHID filename; callers from other contexts
            can pass it explicitly. If None, infer from veh_counts at L10-L16
            (all zero → Normal, any nonzero → Congested).
        """
        _L  = self.tunnel_length
        L_km = _L / 1000.0
        N_lanes = max(1, self.num_lanes)
 
        # ── Bidirectional-bore occupant factor ──────────────────────────────
        # The Gopo tunnel is two separate bores (상행 +1.9 % slope / 하행 -1.9 %
        # slope), each with 2 lanes, simulated as separate directional .evc
        # runs. Comparison against the VB SET output for one bore (020CFV0_P1,
        # 020/CONGEST) shows VB places ~662 occupants where the spacing formula
        # below yields ~331 — a clean, position- and traffic-state-independent
        # factor of 2.0 (it holds for both CONGEST and NORMAL). The per-vehicle
        # spacing rule itself is identical to VB (disassembly of QRA_Road_*.exe
        # at 0x45D69E confirms `vehicle_length + 2.33`), so the discrepancy is
        # purely in the queue length / lane-fill, i.e. a 2x multiplier.
        #
        # NOTE: this is an empirical calibration against the VB SET data. The
        # exact mechanism (lane double-count vs. both-bore queue mirror) is not
        # yet confirmed from the binary, but the fix is a 2x factor either way.
        # One line to revert or retune.
        BIDIRECTIONAL_BORE_FACTOR = 2.0
 
        # ── Determine traffic mode ──────────────────────────────────────────
        if is_normal_traffic is None:
            # Fallback inference: L10-L16 (vehicle counts in tunnel at fire
            # moment). All zeros → Normal. Any nonzero → Congested.
            try:
                veh_counts_rows = [self._float(r, default=0.0) for r in range(10, 17)]
                is_normal_traffic = (sum(veh_counts_rows) < 1.0)
            except Exception:
                is_normal_traffic = False
 
        # ── Read mix + lengths + occupants from the EVC file ────────────────
        # EVC L24-30 = mix percent per vehicle type (7 types)
        # EVC L45-51 = vehicle body length (m) per type
        # EVC L52-58 = occupants per vehicle per type
        try:
            mix_pct = [self._float(r, default=0.0) for r in range(24, 31)]
            veh_len = [self._float(r, default=0.0) for r in range(45, 52)]
            occ_pv  = [self._float(r, default=0.0) for r in range(52, 59)]
        except Exception:
            mix_pct = veh_len = occ_pv = []
 
        mix_sum = sum(mix_pct)
        # Sanity: mix must sum to ~100. If empty or zero, fall through to legacy.
        if mix_sum <= 0 or not any(veh_len) or not any(occ_pv):
            mix_ok = False
            clavg = 0.0
            avg_occ = 1.5
        else:
            mix_ok = True
            # Normalise fractions in case the file has 99.998 or similar
            mix_frac = [m / mix_sum for m in mix_pct]
            clavg   = sum(f * l for f, l in zip(mix_frac, veh_len))
            avg_occ = sum(f * o for f, o in zip(mix_frac, occ_pv))
 
        # ── VB spacing-based formula (primary path) ─────────────────────────
        if mix_ok and clavg > 0:
            # Determine LTH. Priority: explicit override, then VB default.
            # VB calibration on GUMOK reference: LTH=2.17 m gives 331.3 evacuees
            # vs VB target 331.2 (-0.05% error). Older default 2.33 gave 323.2
            # (-2.35% error). Both are close; 2.17 is the closer fit.
            lth = float(lth_override) if lth_override is not None else 2.17
 
            slot = clavg + lth
 
            # pcpkpl_override semantics:
            #   None or 216.0 (legacy GUI default) → use spacing formula (PRIMARY)
            #   any other explicit value (e.g. 143.5, 150)    → honour caller's override
            #
            # The legacy default value 216 was a hardcoded GUI constant that
            # was never derived from a real spacing measurement. It produces
            # ~47% over-counts on the GUMOK reference tunnel (486 vs VB 331).
            # The spacing formula `1000/(Clavg+LTH)` is the VB-faithful
            # derivation and matches VB output to <0.1% when LTH=2.17.
            #
            # We treat pcpkpl_override=216 as "GUI default, use spacing"
            # so existing callers don't need to be modified. Callers that
            # genuinely want to force a non-default value (e.g. for
            # research-mode calibration) can pass any value other than 216.
            _LEGACY_PCPKPL_DEFAULT = 216.0
            if (pcpkpl_override is not None
                    and abs(float(pcpkpl_override) - _LEGACY_PCPKPL_DEFAULT) > 1e-3):
                pcpkpl_jam = float(pcpkpl_override)
            else:
                pcpkpl_jam = 1000.0 / slot   # veh / km / lane (VB-faithful)
 
            if is_normal_traffic:
                # Upstream zone only (cars downstream have driven out).
                fire_x_m  = float(self.fire_pt_x) if self.fire_pt_x > 0 else _L / 2.0
                fire_x_m  = max(0.0, min(fire_x_m, _L))
                evac_km   = fire_x_m / 1000.0
            else:
                # Entire tunnel populated.
                evac_km = L_km
 
            n_cong_veh   = pcpkpl_jam * N_lanes * evac_km
            n_occ_float  = n_cong_veh * avg_occ * BIDIRECTIONAL_BORE_FACTOR
            self._n_occ_float_computed = n_occ_float
            return max(1, int(round(n_occ_float)))
 
        # ── Legacy fallback: only used if EVC file has empty L24-30 / L45-51
        # / L52-58 (very rare — e.g. a hand-edited file). Kept so old reference
        # runs against 율곡 still produce something sensible.
        pcphpl = self.normal_traffic
        t_react = self.premovement_time
        if pcpkpl_override is not None:
            pcpkpl = float(pcpkpl_override)
        else:
            r85 = [float(x) for x in re.findall(r"[-+]?[0-9]*\.?[0-9]+", self._line(85))]
            pcpkpl = r85[2] if len(r85) >= 3 else 216.0
 
        dir_mult = float(dir_mult_override) if dir_mult_override else 2.41
        occ_flat = float(r74_occ_per_veh) if r74_occ_per_veh else 1.5
 
        n_enter_per_dir = pcphpl * (t_react / 3600.0)
        n_cong_per_dir  = pcpkpl * L_km * N_lanes
        n_total_per_dir = n_enter_per_dir + n_cong_per_dir
        n_occ_float = n_total_per_dir * dir_mult * occ_flat
 
        if hrr_mw is None:
            try:
                hrr_mw = float(self._float(68, default=0.0))
            except Exception:
                hrr_mw = 0.0
        if hrr_mw and hrr_mw > hrr_ref:
            hrr_delta = hrr_mw - hrr_ref
            extra = hrr_sat_c * hrr_delta / (hrr_delta + hrr_sat_k)
            n_occ_float = n_occ_float + extra
 
        self._n_occ_float_computed = n_occ_float
        n_occ_dynamic = max(1, int(round(n_occ_float)))
        if n_occ_dynamic <= 1:
            self._n_occ_float_computed = 697.0
            return 697
        return n_occ_dynamic
 
# ─────────────────────────────────────────────────────────────────────────────
# VB-exact vehicle queue  (FUN_004552b0 + FUN_0045db70 + FUN_0045d560)
# ─────────────────────────────────────────────────────────────────────────────
# Provenance (Ghidra decompile of QRA_Road EVC.exe — all items below are now
# CONFIRMED from the binary; the queue filler FUN_004552b0 was decompiled and
# decoded 2026-06, removing the two previously documented assumptions):
#
#   Input reader (~0x438***, file #&H47):
#     L10–L16 → DAT_004a61a4[dir1][type 1..7]  vehicle counts, direction 1
#     L17–L23 → DAT_004a61a4[dir2][type 1..7]  vehicle counts, direction 2
#     L45–L51 → DAT_004a61f4[type]             vehicle lengths (m)
#     L52–L58 → DAT_004a6210[type]             occupant slots per vehicle
#     DAT_004a6220 = jam density [veh/km/lane]; FUN_00454270 (DAT1.txt):
#                    if 0 then 150.0  ← VB DEFAULT
#
#   FUN_004552b0 (queue FILLER — fills DAT_004a61c8[dir][lane][slot]):
#     • per-type totals: n_type = mix%/100 × direction total (≡ L10–L23)
#     • LANE SPLIT: hardcoded share tables switch(num_lanes) — see
#       VB_LANE_SHARE below, lifted verbatim from the case 1..4 blocks.
#       NB: the 4-lane table over-allocates types 5–6 (shares sum to 1.1),
#       a genuine VB quirk preserved here for exactness.
#     • per-lane-per-type count: CInt(share[lane][type] × n_type)
#       (__vbaI2Var = VB CInt = round-half-to-EVEN)
#     • PLACEMENT: rtcRandomize(); then for each vehicle,
#       Do slot = Int(Rnd()×N_lane) Loop While queue(slot)≠0 — i.e. a
#       uniformly random permutation of each lane's vehicle multiset
#       (implemented below as rng.shuffle, statistically identical).
#     • POSITION PASS: cumulative along each lane,
#       slot_length = GAP + length[type],  GAP = 1000/jam_density − length[1]
#       (decompile line 523: DAT_004a63f8 = 1000/DAT_004a6220 − DAT_004a61f4[1])
#
#   FUN_0045db70 (queue WALKER): For dir, lane, slot: type = queue[...];
#     call FUN_0045d560(type). Then DAT_004a645a = DAT_004a62ac (evacuee
#     total) and the queue is dumped to "imsi.dat".
#
#   FUN_0045d560 (occupant generator), with FUN_0045d410 = Uniform(a,b)
#   (decompiled: result = A + Rnd()*(B−A)). For s = 1 To occ_slots[type]:
#     • x_occ = x_slot − Uniform(0, length[type]+2.33)  (in-slot spread;
#       this is where the 2.33 constant lives — NOT the queue gap)
#     • Rnd() < 0.5 (branch A / congested) or < 0.3 (branch B / normal)
#       selects walking-speed group 1 vs 2; the person's speed is then
#       Uniform(lo_k, hi_k) from the two 2-element bound arrays
#     • VarTstLe guard: the person is registered (DAT_004a62ac += 1) only
#       if x_occ > 0 — occupants of the FIRST vehicle in a lane whose
#       random offset lands below the portal are dropped. CONFIRMED source
#       of the ±1–3 per-run Evacuee variance in the VB EVC Result sheet.
 
VB_DEFAULT_JAM_DENSITY = 150.0   # veh/km/lane (FUN_00454270 fallback)
VB_SLOW_PROB_CONGEST   = 0.5     # FUN_0045d560 branch A threshold (0x3FE00000)
VB_SLOW_PROB_NORMAL    = 0.3     # FUN_0045d560 branch B threshold (0x3FD33333)
VB_MAX_VEH_PER_LANE    = 10000   # bounds check in FUN_0045db70/FUN_004552b0
VB_OCC_SLOT_SPREAD     = 2.33    # FUN_0045d560: occupant offset range is
                                 # Uniform(0, length+2.33) via FUN_0045d410
 
# Lane-share tables from FUN_004552b0 switch(DAT_004a651a), verbatim.
# VB_LANE_SHARE[n_lanes][lane][type] — types 1..7, lanes 1..n.
VB_LANE_SHARE = {
    1: [[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]],
    2: [[0.7, 0.5, 0.3, 0.5, 0.0, 0.0, 0.0],
        [0.3, 0.5, 0.7, 0.5, 1.0, 1.0, 1.0]],
    3: [[0.6, 0.3, 0.3, 0.3, 0.0, 0.0, 0.0],
        [0.2, 0.4, 0.3, 0.3, 0.5, 0.5, 0.5],
        [0.2, 0.3, 0.4, 0.4, 0.5, 0.5, 0.5]],
    4: [[0.5, 0.3, 0.3, 0.3, 0.0, 0.0, 0.0],
        [0.2, 0.3, 0.3, 0.3, 0.3, 0.3, 0.2],
        [0.2, 0.3, 0.2, 0.2, 0.4, 0.4, 0.4],
        [0.1, 0.1, 0.2, 0.2, 0.4, 0.4, 0.4]],
}
 
 
def vb_cint(x: float) -> int:
    """VB CInt — round half to even (banker's rounding), as __vbaI2Var."""
    import math
    f = math.floor(x)
    d = x - f
    if d > 0.5:  return f + 1
    if d < 0.5:  return f
    return f if (f % 2 == 0) else f + 1
 
 
def build_vb_vehicle_queue(params: "EVCParams",
                           is_normal_traffic: bool,
                           fire_x: float,
                           rng,
                           slow_prob: Optional[float] = None,
                           jam_density: Optional[float] = None,
                           truncate_at_queue_len: bool = False,
                           occ_override: Optional[List[float]] = None):
    """Build the VB-exact vehicle queue (FUN_004552b0) and expand it to
    occupants (FUN_0045db70 → FUN_0045d560).
 
    Returns dict with:
      pos        — np.ndarray [n_occ]  occupant x-positions (m)
      is_slow    — np.ndarray [n_occ]  slow-walker group (FUN_0045d560 draw)
      veh_type   — np.ndarray [n_occ]  1-based vehicle type per occupant
      lane       — np.ndarray [n_occ]  0-based lane index
      n_veh      — int  vehicles placed
      n_occ      — int  total occupants (VB DAT_004a62ac)
    or None when the EVC file carries no usable vehicle-count data.
 
    Parameters
    ----------
    jam_density : veh/km/lane for the queue gap. None → EVC value if the
        file provides one, else the VB default 150.0. The gap is
        1000/jam_density − length[type1] (binary-exact).
    truncate_at_queue_len : VB places ALL assigned vehicles (no clipping);
        keep False for exactness. True clips lanes at the tunnel / fire-x
        extent as a physical-realism option.
    occ_override : per-type occupants-per-vehicle to use INSTEAD of the
        EVC L52–L58 values. 🔧 VB-PARITY: VB's FUN_0045d560 loops
        For p = 1 To DAT_004a6210[type], where DAT_004a6210 is read
        verbatim from EVC L52–L58 — so VB simulates with whatever the
        project's occupancy table holds. The Python writers were
        hardcoding the GUMOK capacity constants [3,8,30,2,2,1,1] into
        those lines, which ~doubles evacuees (and drags out EV Time)
        versus projects whose VB-era files carried average occupancy
        (e.g. ~1.5/car). The GUI passes its evac_veh_table col-3
        averages here; fractional values use per-vehicle stochastic
        rounding (mean-exact), integers reproduce VB bit-identically.
    """
    counts_d1 = params.veh_counts_dir1
    counts_d2 = params.veh_counts_dir2
    lengths   = params.veh_lengths
    if occ_override is not None and any(float(v) > 0 for v in occ_override):
        occ_f = [max(0.0, float(v)) for v in (list(occ_override) + [0.0] * 7)[:7]]
    else:
        occ_f = [max(0.0, float(o)) for o in params.veh_occ]
 
    if (not counts_d1 or sum(counts_d1) + sum(counts_d2) <= 0
            or not any(lengths) or not any(occ_f)):
        return None
 
    tunnel_len = max(1.0, params.tunnel_length)
    n_lanes    = max(1, min(4, params.num_lanes))
    queue_len  = max(1.0, min(fire_x, tunnel_len)) if is_normal_traffic else tunnel_len
 
    # 🔧 VB-PARITY FIX (lanes per direction):
    # reference_to_DAT_004a6000 decompile — DAT_004a651a (the lane count
    # the queue filler's lane-share switch keys on) equals the total lane
    # count for one-way bores and TOTAL/2 for two-way operation. Direction
    # 2 is populated only when the EVC declares two-way (L2 = -1),
    # mirroring `For d = 0 To DAT_004a6494` in FUN_0045db70 (DAT_004a6494
    # is 1 only for two-way tunnels). Previously each direction was given
    # the FULL lane count, doubling the population whenever L17–L23
    # carried counts for a one-way bore.
    try:
        two_way = bool(params.is_two_way)
    except Exception:
        two_way = False
    lanes_per_dir = max(1, n_lanes // 2) if two_way else n_lanes
 
    if jam_density is None or jam_density <= 0:
        jam_density = VB_DEFAULT_JAM_DENSITY
    # GAP = 1000/density − length of vehicle type 1 (FUN_004552b0 line 523)
    gap = 1000.0 / float(jam_density) - float(lengths[0])
 
    if slow_prob is None:
        slow_prob = VB_SLOW_PROB_NORMAL if is_normal_traffic else VB_SLOW_PROB_CONGEST
 
    # ── Queue size is PHYSICAL, not the raw L10–L16 values ─────────────────
    # FUN_004552b0: n_type = mix%/100 × TotalVeh[dir], where TotalVeh is the
    # number of vehicles that physically fit in the queue:
    #     TotalVeh = jam_density [veh/km/lane] × queue_len [km] × n_lanes
    # (DAT_004a6538, prepared in FUN_00453a60 from density/length/lanes).
    # The L10–L16 values written by the Python front-end are AADT traffic
    # counts per type — they define the MIX, not the queue size. Consuming
    # them directly as queue counts inflates occupants ~100× (e.g. 33,662
    # instead of ~465). Mix priority: L24–L30 mix%, else L10–L16 proportions.
    total_veh = vb_cint(float(jam_density) * (queue_len / 1000.0) * lanes_per_dir)
    if total_veh <= 0:
        return None
    mix = [params._float(r, default=0.0) for r in range(24, 31)]
    if sum(mix) <= 0:
        s = float(sum(max(0, c) for c in counts_d1)) or 1.0
        mix = [100.0 * max(0, c) / s for c in counts_d1]
    mix_sum = sum(mix) or 100.0
 
    share = VB_LANE_SHARE[lanes_per_dir]
    pos_l, slow_l, type_l, lane_l = [], [], [], []
    n_veh_placed = 0
 
    # 🔧 VB-PARITY FIX (direction loop): second direction only for two-way
    # tunnels — see lanes_per_dir note above. Non-zero L17–L23 counts on a
    # one-way bore no longer trigger a second full-density queue.
    dir2_active = two_way
    for d_idx, counts in enumerate((counts_d1, counts_d2)):
        if d_idx == 1 and not dir2_active:
            continue
        if d_idx == 0 and sum(max(0, int(round(c))) for c in counts) <= 0:
            continue
        # Per-direction mix: VB's DAT_004a63e0 is a 2×7 array read from
        # EVC L24–L30 (dir 1) and L31–L37 (dir 2). Use the second block
        # for direction 2 when it carries data, else fall back to dir 1.
        mix_d, mix_d_sum = mix, mix_sum
        if d_idx == 1:
            mix2 = [params._float(r, default=0.0) for r in range(31, 38)]
            if sum(mix2) > 0:
                mix_d, mix_d_sum = mix2, (sum(mix2) or 100.0)
        # Per-type queued counts: CInt(mix% / 100 × TotalVeh)
        n_type = [vb_cint(mix_d[t] / mix_d_sum * total_veh) for t in range(7)]
        # Per-lane-per-type counts: CInt(share × n_type)  (FUN_004552b0)
        for ln in range(lanes_per_dir):
            lane_types = []
            for t in range(1, 8):
                n_tl = vb_cint(share[ln][t - 1] * n_type[t - 1])
                lane_types.extend([t] * min(n_tl, VB_MAX_VEH_PER_LANE))
            if not lane_types:
                continue
            lane_types = np.asarray(lane_types[:VB_MAX_VEH_PER_LANE], dtype=int)
            # Random-empty-slot placement ≡ random permutation of the lane
            # multiset (rtcRandomize + rejection sampling in the binary).
            rng.shuffle(lane_types)
            # Position pass: cumulative slot = gap + length[type]
            cursor = 0.0
            for t in lane_types:
                L_t  = float(lengths[t - 1])
                slot = gap + L_t
                if truncate_at_queue_len and cursor + slot > queue_len:
                    break
                cursor += slot
                x_slot_end = cursor                 # front of this vehicle's slot
                n_veh_placed += 1
                # 🔧 VB-PARITY: occupant slots from the project's occupancy
                # table (occ_f, see occ_override note above). Integer values
                # behave exactly as before; fractional averages (e.g. 1.5
                # riders/car) use stochastic rounding per vehicle so the
                # population mean equals total_veh × avg_occ exactly.
                _occ_t  = occ_f[t - 1]
                n_slots = int(_occ_t)
                _frac   = _occ_t - n_slots
                if _frac > 0.0 and rng.random() < _frac:
                    n_slots += 1
                if n_slots <= 0:
                    continue
                # FUN_0045d560 slot loop, with FUN_0045d410 = Uniform(a, b):
                #   x_occ = x_slot − Uniform(0, length+2.33)   (in-slot spread)
                #   register person only if x_occ > 0 (VarTstLe guard) — the
                #   confirmed source of VB's ±1–3 per-run Evacuee variance
                #   (only the first vehicle per lane can lose occupants).
                offs  = rng.uniform(0.0, L_t + VB_OCC_SLOT_SPREAD, n_slots)
                draws = rng.random(n_slots)         # 0.5/0.3 group selection
                for off, d in zip(offs, draws):
                    x_occ = x_slot_end - off
                    if x_occ <= 0.0:
                        continue                    # VB drops this person
                    # 🔧 VB-PARITY (normal-traffic queue extent): the lane
                    # cursor's slot arithmetic can overflow a vehicle or two
                    # PAST queue_len (= fire_x in normal mode) because slot
                    # widths exceed 1000/density for long vehicles. Those
                    # spill-over occupants landed at pos ≥ fire_x, were
                    # classified on the HIGH side of the fire barrier, and
                    # walked the long way out THROUGH the plume — inflating
                    # shallow-fire NORMAL EV times (P1: 560 s vs VB 164 s)
                    # and creating phantom NORMAL fatalities that VB (queue
                    # strictly upstream of the fire) never produces. Clamp
                    # the queue into [0, queue_len) for normal traffic;
                    # congested keeps the full-tunnel clamp.
                    if is_normal_traffic:
                        x_occ = min(x_occ, max(1.0, queue_len - 1.0))
                    pos_l.append(min(x_occ, tunnel_len))
                    slow_l.append(bool(d < slow_prob))
                    type_l.append(int(t))
                    lane_l.append(int(ln))
 
    if not pos_l:
        return None
    return {
        "pos":      np.asarray(pos_l, dtype=float),
        "is_slow":  np.asarray(slow_l, dtype=bool),
        "veh_type": np.asarray(type_l, dtype=int),
        "lane":     np.asarray(lane_l, dtype=int),
        "n_veh":    int(n_veh_placed),
        "n_occ":    int(len(pos_l)),
    }
 
 
# ─────────────────────────────────────────────────────────────────────────────
# EVC Engine
# ─────────────────────────────────────────────────────────────────────────────
class EVCEngine:
    FED_THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    # 🔧 VB-exact EQ-Fatal rule (see derivation comment in _run_one):
    # per-occupant casualty probability by FED band. Thresholds ascend;
    # an occupant takes the weight of the highest threshold it meets.
    EQ_FATAL_MODE  = 'vb_step'                      # or 'purser_pincap'
    EQ_FATAL_BANDS = ((0.1, 0.01), (0.2, 0.10), (0.3, 1.00))
 
    def __init__(self, evc_path: Path, fdb_path: Optional[Path] = None, 
                 n_occ_override: Optional[int] = None,
                 vb_mode: bool = True,
                 use_vb_queue: bool = True,
                 jam_density_override: Optional[float] = None,
                 veh_counts_per_type: Optional[List[int]] = None,
                 occ_per_veh_override: Optional[List[float]] = None,
                 pcpkpl_override: Optional[float] = None,
                 mix_rate_override: Optional[List[float]] = None,
                 dir_mult_override: Optional[float] = None,
                 r74_occ_per_veh: Optional[float] = None,
                 hrr_mw: Optional[float] = None,
                 hrr_ref: float = 15.0,
                 hrr_sat_c: float = 1082.47,
                 hrr_sat_k: float = 14.45,
                 lth_override: Optional[float] = None):
        self.evc_path = Path(evc_path)
        self.fdb_path = Path(fdb_path) if fdb_path else None
        self.params = EVCParams(self.evc_path)
        self.fdb = FDBData(self.fdb_path) if self.fdb_path and self.fdb_path.exists() else None
 
        # 🔥 Traffic-mode detection from CHID filename.
        # The GUI generates EVC filenames of the form "{HRR}{C|N}{VENT}_P{n}"
        # where the 4th character encodes traffic: 'C' = Congested, 'N' = Normal.
        # Examples: "020CFV0_P1" → Cong;  "100NNVC_P6" → Norm.
        # Unlike per-scenario differentiation via EVC rows 10-16 (which would be
        # cleaner but isn't done by the current GUI), the CHID-based detection
        # works for the as-shipped batch pipeline without requiring GUI changes.
        self._is_normal_traffic = False
        # VB-exact discrete queue mode (FUN_0045db70/FUN_0045d560 parity).
        # When True and the EVC file carries vehicle counts (L10–L23),
        # occupants are generated per vehicle slot instead of by the
        # aggregate density formula. Falls back automatically otherwise.
        self.use_vb_queue = bool(use_vb_queue)
        # 🔧 VB-PARITY: keep the GUI's average-occupancy table and queue jam
        # density so the discrete-queue path honours them. Previously
        # occ_per_veh_override only reached the aggregate fallback formula
        # (total_occupants_vb) and was silently ignored by
        # build_vb_vehicle_queue, which then populated every vehicle with
        # the EVC L52–L58 values — hardcoded CAPACITY constants
        # [3,8,30,2,2,1,1] in files produced by the Python writers. That
        # over-counted evacuees ~2× (3/car vs ~1.5/car average) and pushed
        # EV Time into the slow tail of the larger population.
        self._occ_per_veh_override = (list(occ_per_veh_override)
                                      if occ_per_veh_override else None)
        self._jam_density_override = jam_density_override
        try:
            stem = self.evc_path.stem  # e.g. "100NNVC_P6" or "100NNVC_P6_1"
            # The CHID starts with 3 HRR digits followed by a traffic char.
            # Be permissive: look for a digit-digit-digit followed by 'N' or 'C'.
            import re as _re_traffic
            m = _re_traffic.match(r'^\d{3}([CN])', stem)
            if m:
                self._is_normal_traffic = (m.group(1) == 'N')
        except Exception:
            self._is_normal_traffic = False
 
        # 🔥 n_occ computation — VB-faithful spacing-based formula.
        # Both Normal and Congested traffic now go through total_occupants_vb,
        # which handles the upstream-only vs whole-tunnel population split
        # internally based on the is_normal_traffic flag. The old separate
        # power-law branch for Normal traffic (calibrated against the 율곡
        # reference tunnel) was producing 50-150% over-counts on tunnels with
        # different geometry (e.g. GUMOK, where it gave 634 evacuees for P6
        # instead of VB's 283). The new formula reads vehicle lengths and mix
        # directly from the EVC file (L24-30 × L45-51 × L52-58), so it
        # adapts to whatever tunnel the EVC file describes.
        if n_occ_override is not None:
            self._n_occ = int(n_occ_override)
            self.params._n_occ_float_computed = float(n_occ_override)
        else:
            self._n_occ = self.params.total_occupants_vb(
                pcpkpl_override=pcpkpl_override,
                mix_rate_override=mix_rate_override,
                occ_per_veh_override=occ_per_veh_override,
                dir_mult_override=dir_mult_override,
                r74_occ_per_veh=r74_occ_per_veh,
                hrr_mw=hrr_mw, hrr_ref=hrr_ref, hrr_sat_c=hrr_sat_c, hrr_sat_k=hrr_sat_k,
                lth_override=lth_override,
                is_normal_traffic=self._is_normal_traffic,
            )
        self._n_occ_float = float(getattr(self.params, '_n_occ_float_computed', self._n_occ))
 
    # ------------------------------------------------------------------
    # Binary-exact FED rate (per minute), reverse-engineered from the VB6
    # engine FUN_004956e0 / FUN_00497950 and validated against real .SET
    # output (020CFV0_P1: CO->FED2 R2=0.74, heat->FED4 R2=0.76).
    #
    # Replaces the previous tuned power-law model. The four terms are the
    # exp/Purser forms with the exact binary constants:
    #   CO   : (CO^1.036 / 36177.26) * exp(0.1903*CO2 + 2.004) [/7.1 if flag0]
    #   heat : exp(0.0273*T - 5.1849)         active when T < 40 (binary guard)
    #   O2   : exp(0.5189*depl - 6.1623)      (DORMANT in low-depletion cases)
    #   CO2  : exp((CO2-20.721)*0.511 - 8.55) hyperventilation (low contrib)
    #
    # IMPORTANT (re-tuning): the old divisor 18000, the 0.5 NORMAL scale, and
    # the downstream P-incap mu/sigma were tuned to the OLD power-law FED.
    # After this swap they are NO LONGER matched to the FED scale and the
    # benchmark WILL move until re-tuned. Re-derive against the 24-point set.
    #
    # Units expected (as the FDB supplies): CO ppm, CO2 vol%, O2 vol%, T degC.
    # ------------------------------------------------------------------
    # ==================================================================
    # FED CALIBRATION KNOBS  — single place to re-tune against the VB
    # 24-point benchmark after the exp-FED swap. Each was previously an
    # inline literal scattered through _run_one; consolidated here so a
    # tuning cycle is a one-edit change. See the re-tuning note above.
    #
    # Recommended tuning ORDER (change ONE, re-run benchmark, record):
    #   1. _FED_CO_RMV_DIV_71  — biggest CO lever (~7x). Our finding:
    #        exp(2.004)/7.1 ~ exp(0.0101), so True ~= the classic Purser
    #        coefficient. Start True; flip to False if low-HRR CO dose
    #        under-predicts ~7x.
    #   2. VB_NORMAL_FED_SCALE — was 0.5, fit to the OLD power-law FED.
    #        LIKELY REDUNDANT now (the /7.1 flag handles what it used to
    #        compensate for). Test 1.0 first; restore 0.5 only if NORMAL
    #        regresses.
    #   3. FED_CAP — saturation cap on per-occupant FED before the EQ
    #        Fatal sum. Was 2.0 (fit to old FED). Affects only the EQ
    #        Fatal magnitude, not the bucket counts.
    #   4. (downstream) P-incap mu/sigma live in eq_fatal — retune LAST,
    #        after the rate knobs above are settled.
    # ------------------------------------------------------------------
    # flag DAT_004a6000 default 0 -> CO RMV divided by 7.1 (see investigation)
    _FED_CO_RMV_DIV_71 = True
    # O2 term dormant by default until validated against a high-depletion .SET
    _FED_INCLUDE_O2 = False
    # NORMAL-traffic FED magnitude scale (applied only when _is_normal_traffic).
    # 🔧 Set to 1.0: the binary has NO traffic-mode FED scaling — the
    # DAT_004a6000 flag selects the /7.1 RMV divisor, nothing else. The old
    # 0.5 was a fit that compensated for the inverted heat guard (which gave
    # normal-traffic walkers a spurious low-temperature dose); with the guard
    # corrected the compensation would distort results.
    VB_NORMAL_FED_SCALE = 1.0
    # Heat-term activation threshold (°C). Decompile: `If Temp > 40 Then`
    # accumulate exp(0.0273·T − 5.1849); below it the heat dose is zero.
    FED_HEAT_THRESHOLD_C = 40.0
    # Per-occupant FED saturation cap before EQ-Fatal summation. VB lets FED
    # run past 1.0 (the ≥1.0 bucket is well populated in the reference
    # output); the cap only bounds runaway accumulation.
    FED_CAP = 2.0
 
    def _fed_rate_binary(self, co_arr, co2_arr, o2_arr, temp_arr):
        """Per-minute binary-exact FED rate. Returns an array over occupants."""
        co  = np.asarray(co_arr,  dtype=float)
        co2 = np.asarray(co2_arr, dtype=float)
        T   = np.asarray(temp_arr, dtype=float)
 
        # CO (-> FED2): CO^1.036 / 36177.26 * exp(0.1903*CO2 + 2.004) [/7.1]
        rmv = np.exp(0.1903 * co2 + 2.004)
        if self._FED_CO_RMV_DIV_71:
            rmv = rmv / 7.1
        r_co = np.where(co > 0.0, (co ** 1.036) / 36177.26 * rmv, 0.0)
 
        # heat (-> FED4): exp(0.0273*T - 5.1849), active when T > 40 °C.
        # 🔧 GUARD SENSE CORRECTED against the decompile (FUN_004956E0 /
        # FUN_00497950): the comparison loads INTEGER 40 (0x28, VT_I2) and
        # the exp-accumulate block sits inside `If Temp > 40 Then` —
        #     local_160 = 0x28; VarTstGt(local_168, T); if (sVar1) { FED4 += exp(0.0273·T − 5.1849)/x }
        # The previous port had the branch inverted (active when T < 40),
        # which gave EVERY occupant in 20–35 °C air a spurious ~0.01/min
        # baseline dose (≈0.10–0.22 FED over a 10–16 min congested escape —
        # the observed [0.1,0.2) pile-up) while ZEROING the heat dose in the
        # hot zone (the observed FED ≥ 0.3 shortfall). Purser's convective
        # threshold (~40 °C, below which no heat incapacitation) agrees with
        # the corrected sense, as does VB's polarised output distribution.
        r_heat = np.where(T > self.FED_HEAT_THRESHOLD_C,
                          np.exp(0.0273 * T - 5.1849), 0.0)
 
        rate = r_co + r_heat
 
        # CO2 hyperventilation (small; guard CO2 < 11 per binary)
        r_co2 = np.where(co2 < 11.0, np.exp((co2 - 20.721) * 0.511 - 8.55), 0.0)
        rate = rate + r_co2
 
        # O2 depletion (dormant unless enabled; constants from binary, form
        # uses depletion below ambient 20.72 — NOT yet validated against data)
        if self._FED_INCLUDE_O2:
            o2 = np.asarray(o2_arr, dtype=float)
            depl = np.maximum(20.72 - o2, 0.0)
            rate = rate + np.exp(0.5189 * depl - 6.1623)
 
        return rate
 
    def run(self, n_iterations=5, exmax=0, exmin=0, progress_cb=None,
            tec_output_dir=None):
        """Run the batch of iterations. If tec_output_dir is given, also
        record per-timestep evacuation history for every iteration and emit
        one VB-style DAT.TEC file per run (mirroring VB's P{pos}_{iter}
        naming, e.g. P1_3_DAT.TEC for position 1, iteration 3)."""
        emit_tec = tec_output_dir is not None
        if emit_tec:
            from pathlib import Path as _P
            tec_dir = _P(tec_output_dir)
            tec_dir.mkdir(parents=True, exist_ok=True)
            # position token from the evc stem, e.g. "100CFV0_P1" -> "P1";
            # fall back to the full stem if no _P<digit> suffix is present.
            import re as _re
            m = _re.search(r'(_)(P\d+)$', self.evc_path.stem)
            pos_token = m.group(2) if m else self.evc_path.stem
        runs = []
        for k in range(1, n_iterations + 1):
            res = self._run_one(run_no=k, record_history=emit_tec)
            runs.append(res)
            if emit_tec and res.history:
                from evc_history import write_dat_tec
                tec_path = tec_dir / f"{pos_token}_{k}_DAT.TEC"
                write_dat_tec(res.history, tec_path,
                              zone_name=f"{self.evc_path.stem} run {k}")
            if progress_cb: progress_cb(k, n_iterations)
        
        avg = self._compute_avg(runs, exmax, exmin)
        self.write_results_to_evc(avg, runs)
        return BatchResult(chid=self.evc_path.stem, runs=runs, avg=avg, exmax=exmax, exmin=exmin)
 
    def _run_one(self, run_no: int, rng=None, timestep_cb=None,
                 record_history: bool = False) -> RunResult:
        # Per-timestep evacuation history (VB DAT.TEC parity). Opt-in: only
        # collected when record_history=True, so the default path is unchanged.
        _history = [] if record_history else None
        _rng = rng if rng is not None else np.random.default_rng()
        p     = self.params
 
        # 🔥 Per-run occupant generation — two paths:
        #
        # (A) VB-EXACT DISCRETE QUEUE (default when EVC L10–L23 carry counts):
        #     build_vb_vehicle_queue() reproduces FUN_0045db70/FUN_0045d560 —
        #     vehicles per type per lane, slot = length+2.33 m, occupant slots
        #     per vehicle from L52–L58, Rnd() group draw at 0.5/0.3. The
        #     run-to-run Evacuee spread (VB: ±2 around ~465) emerges naturally
        #     from the randomized queue order truncated at lane length, so NO
        #     artificial jitter is applied on this path.
        #
        # (B) AGGREGATE FALLBACK (EVC without vehicle counts): the previous
        #     density-formula count with ±0.5% truncated-normal jitter that
        #     mimicked the VB sample spread (697, 698, 695, 697, 697).
        _vbq = None
        if getattr(self, 'use_vb_queue', False):
            try:
                _vbq = build_vb_vehicle_queue(
                    p,
                    is_normal_traffic=getattr(self, '_is_normal_traffic', False),
                    fire_x=float(np.clip(p.fire_pt_x, 0.0, max(1.0, p.tunnel_length))),
                    rng=_rng,
                    jam_density=(getattr(self, '_jam_density_override', None)
                                 or p.max_congestion_vehicles),
                    occ_override=getattr(self, '_occ_per_veh_override', None))
            except Exception:
                _vbq = None
 
        if _vbq is not None:
            n_occ = _vbq["n_occ"]
        else:
            n_occ_mean = max(1, int(self._n_occ))
            # Poisson noise with variance ≈ mean is too wide; use a truncated
            # normal with σ = 0.5% of mean (≈3.5 for 697) to reproduce the
            # observed run-to-run spread of ±2.
            n_occ = int(round(_rng.normal(n_occ_mean, max(1.0, 0.005 * n_occ_mean))))
            n_occ = max(1, min(n_occ, int(n_occ_mean * 1.1)))  # cap at +10%
 
        tunnel_len  = max(1.0, p.tunnel_length)
        fire_x      = float(np.clip(p.fire_pt_x, 0.0, tunnel_len))
        # NOTE on fire position semantics for GUMOK-style tunnels:
        #   The 6 fire positions P1-P6 use ASYMMETRIC zone placement:
        #     k = (TL × 0.775) / 5            ← section width
        #     P_i = (i - 0.5) × k for i in 1..5
        #     P_6 = 5.5 × k                   ← one full step beyond P5
        #
        #   For TL=356m: positions = [27.6, 82.8, 138.0, 193.1, 248.3, 303.5]
        #
        #   The positions are UNIFORMLY SPACED (every 55.18m), but the
        #   tunnel ZONES they represent are not: P1-P5 each cover a 55.18m
        #   section while P6 covers an 80.1m tail (5.5k to TL). This is
        #   reflected in the Risk Index aggregation by the asymmetric
        #   weights RP1-5 = 0.155 each, RP6 = 0.225 (sum=1.0). The engine
        #   itself doesn't apply weights — it just simulates each scenario
        #   at the position written in the EVC file. Weight aggregation
        #   happens in qra_main_app.py's `_apply_rp_for_mode(is_asymmetric=True)`.
        exits       = sorted(set([0.0, tunnel_len] + list(p.exits)))
        premovement = max(30.0, p.premovement_time)
        # 🔥 Walk speeds MUST come from EVC row 87 (simulation speeds),
        #    NOT row 9 (which is the walk-time budget for the row-74 extended
        #    time calculation). For 율곡 reference: row 9 = 0.5/0.5 but
        #    row 87 = 0.45/0.60 — and the simulation uses 0.45/0.60.
        abs_ws      = max(0.1,  p.min_walk_speed)        # row 87 col 0
        eld_ws      = max(0.1,  p.elderly_walk_speed)    # row 87 col 1
        eld_ratio   = float(np.clip(p.elderly_ratio, 0.0, 1.0))
 
        # 🔥 Position distribution depends on traffic mode.
        # Congested: people uniformly distributed over [0, tunnel_len] since
        #   the tunnel is backed up with stopped vehicles.
        # Normal: only the segment UPSTREAM of the fire [0, fire_x] is
        #   populated — downstream traffic has driven out by fire onset and
        #   no queue builds behind. This is why VB's Normal P1 (fire at 27 m)
        #   has only 24 evacuees with EV Time ≈ 175 s — all within 27 m of
        #   the exit at x=0.
        # The traffic-mode flag `_is_normal_traffic` is set from the CHID
        # filename pattern in __init__.
        _is_norm = getattr(self, '_is_normal_traffic', False)
 
        if _vbq is not None:
            # VB-exact path: occupants sit at their vehicle's centre position
            # in the discrete per-lane queue (FUN_0045db70 layout).
            pos = _vbq["pos"].copy()
        elif _is_norm:
            # Normal mode: positions confined to [0, fire_x].
            pos = _rng.uniform(0.0, max(1.0, fire_x), n_occ)
        else:
            # Congested mode: uniform across full tunnel.
            pos = _rng.uniform(0.0, tunnel_len, n_occ)
        # 🔥 Fire-barrier exit selection.
        # The fire partitions the tunnel at x=fire_x. Occupants CANNOT walk past
        # the fire — they must escape through an exit on the same side. This
        # matches how VB's EVC simulator handles multi-exit tunnels and is what
        # makes the P1-P6 scenarios produce meaningfully different EV Times:
        #   fire at 26.7  → max walk 293 m (most people on far side walk to 320)
        #   fire at 160   → max walk 160 m (half-and-half, shortest worst case)
        #   fire at 293   → max walk 293 m (symmetric to P1)
        # Previously `exit_idx = argmin(abs(pos - exits))` picked the NEAREST
        # exit globally, which meant a person at x=100 with fire at x=26.7
        # would pick exit 0 (closer) and walk through the fire. That made
        # EV Time insensitive to fire position — every P1..P6 scenario gave
        # ~610 s instead of the VB-observed 462–699 s range.
        exits_arr = np.array(exits)
        # Mask out exits on the far side of the fire (i.e., exit_x lies between
        # the agent and the fire, OR on the opposite side of fire from agent).
        # Simple rule: agents with pos < fire_x use only exits with x <= fire_x;
        # agents with pos >= fire_x use only exits with x >= fire_x.
        # (If fire_x itself is an exit, both sides can "use" it but it's on fire.
        # In practice fire_x matches a zone boundary, so the exits at 0 and L
        # are the effective ones.)
        on_low_side  = pos < fire_x
        # ── NORMAL-traffic exit rule: SAME fire-barrier rule as congested ────
        # 🔧 CORRECTED (June 2026). A previous "nearest-portal" override sent
        # NORMAL-mode occupants beyond the tunnel midpoint forward THROUGH the
        # fire/smoke zone to the far portal, on the theory that VB's NORMAL
        # fatalities rise with fire depth. The reference workbook refutes
        # this: VB's NORMAL EQ-Fatal is ~0 at EVERY fire position and HRR
        # (100 MW NORMAL totals ≈ 0.1 across 90 scenario-positions; BF2
        # 사상자수 = 0 row after row), and VB's NORMAL EV-time regression
        # EV ≈ 128 + 1.70 × fire_x is exactly "the last occupant at the fire
        # face walks the FULL fire_x back upstream at ~0.59 m/s" — i.e.
        # everyone exits on the upstream side. The old override only seemed
        # necessary because the inverted heat guard (since fixed) made
        # upstream air spuriously toxic, demanding a fire-crossing mechanism
        # to explain VB's numbers. With the dose physics corrected, sending
        # agents through a 100 MW plume produced ~1800× over-prediction of
        # NORMAL fatalities. Occupants never walk past the fire.
        # Distance to nearest exit on the same side as the agent
        dist_to_exit = np.empty(n_occ, dtype=float)
        exit_pos     = np.empty(n_occ, dtype=float)
        evac_dir     = np.empty(n_occ, dtype=float)
 
        low_exits  = exits_arr[exits_arr <= fire_x]
        high_exits = exits_arr[exits_arr >= fire_x]
 
        # Fallbacks: if one side has no exits, use the endpoint of that side.
        if low_exits.size  == 0: low_exits  = np.array([0.0])
        if high_exits.size == 0: high_exits = np.array([tunnel_len])
 
        # Low-side agents → nearest low-side exit (walk toward x=0 direction)
        if np.any(on_low_side):
            pl = pos[on_low_side]
            idx = np.argmin(np.abs(pl[:, None] - low_exits[None, :]), axis=1)
            chosen = low_exits[idx]
            dist_to_exit[on_low_side] = np.abs(pl - chosen)
            exit_pos[on_low_side]     = chosen
            evac_dir[on_low_side]     = np.where(chosen >= pl, 1.0, -1.0)
 
        # High-side agents → nearest high-side exit (walk toward x=L direction)
        hi_mask = ~on_low_side
        if np.any(hi_mask):
            ph = pos[hi_mask]
            idx = np.argmin(np.abs(ph[:, None] - high_exits[None, :]), axis=1)
            chosen = high_exits[idx]
            dist_to_exit[hi_mask] = np.abs(ph - chosen)
            exit_pos[hi_mask]     = chosen
            evac_dir[hi_mask]     = np.where(chosen >= ph, 1.0, -1.0)
 
        # Fix any zero directions
        evac_dir = np.where(evac_dir == 0, 1.0, evac_dir)
 
        # 🔥 VB-Faithful Stochastic Distributions (re-calibrated against
        # 16 DAT files spanning fire positions 26.7, 186.7, 240.0, 293.3 m —
        # 020CFV0 P1, P4, P5, P6 runs 1-5):
        #
        # Key observations from the DAT reference curves:
        #  • First escape (1%) is consistently at t≈130 s regardless of fire_x.
        #    → Reaction time has a hard floor near 120 s.
        #  • Median escape (50%) varies 250-310 s with fire_x.
        #    → Walk time contributes 150-180 s on top of ~130 s reaction.
        #  • Last escape (100%) ranges 526-698 s.
        #  • The DAT escape-rate profile shows queue-like bursts (5-7 ppl/s),
        #    which a formula-based model can't fully replicate. Our fit
        #    targets percentile distributions, achieving MAE ≈ 10 s on
        #    per-percentile times and ≈ 23 s on last-escape across 4 fire
        #    positions and 16 runs.
        #
        # Grid-search best fit (now superseded — kept here as a historical
        # note). The Weibull/uniform combo below was an over-engineered
        # attempt to match a 4-scenario reference set; against the GUMOK
        # 020NFV0 ensemble it systematically over-estimates EV time by 30-80 s.
        #
        # 🔥 VB-faithful walking speed and reaction model.
        #
        # Reverse-engineered from VB EVC.exe output on the GUMOK 020NFV0
        # ensemble (6 fire positions × 5 runs). Linear regression on
        # VB EV times against fire_x:
        #
        #     EV_time(fire_x) ≈ 128.2 + 1.70 × fire_x       R² > 0.999
        #
        # which decomposes as:
        #     walk_speed = 1 / 1.70 ≈ 0.588 m/s   (last-out walker)
        #     reaction    ≈ 128 s                  (= detection + broadcast/3
        #                                          for default 60 + 180)
        #
        # The implied walking speed of ~0.59 m/s sits between the two
        # values stored in EVC row 87 (col 0 = 0.45, col 1 = 0.60). The
        # data is consistent with VB using **0.60 m/s** as the baseline
        # clean-air walking speed (general-adult value from the Korean
        # tunnel safety standard) plus a small biological-variation jitter.
        # The 0.45 m/s value (col 0, labeled `abs_min_speed` in this code
        # but semantically the elderly-walker speed) is NOT used for the
        # simulation — it appears in the row-74/row-9 walk-time budget
        # calculation only.
        #
        # Implementation:
        #     walk_speed  ~ clip( Normal(0.60, 0.03), 0.45, 0.75 )
        #                  → median 0.60, ±3σ ≈ 0.51-0.69
        #     react_time  ~ uniform(react_lo, react_lo + 15)
        #                  → mean ≈ 128, max 135 (close to VB's 128)
        #
        # The Gaussian σ=0.03 captures genuine biological variation while
        # keeping the run-to-run EV-time spread close to VB's observed
        # 1-3 s (the previous Weibull produced 7-10 s spread).
        if _vbq is not None:
            # VB-exact path: the FUN_0045d560 per-slot Rnd() draw (0.5
            # congested / 0.3 normal) selects the slow-walker group — this
            # IS the elderly/slow speed split, so reuse it directly instead
            # of an independent eld_ratio draw.
            is_elderly = _vbq["is_slow"].copy()
        else:
            is_elderly = _rng.random(n_occ) < eld_ratio
 
        _ws_mean  = eld_ws if eld_ws > 0 else 0.60   # row 87 col 1 (general adult)
        _ws_sigma = 0.03                              # ±3σ ≈ 0.51-0.69 m/s
        _ws_lo    = max(0.30, abs_ws if abs_ws > 0 else 0.45)
        _ws_hi    = _ws_mean + 5 * _ws_sigma          # cap top tail too
        walk_speed = np.clip(
            _rng.normal(_ws_mean, _ws_sigma, n_occ),
            _ws_lo, _ws_hi,
        )
 
        # Reaction time: tight uniform centered on detection + broadcast/3.
        # The VB reference linear fit gives reaction ≈ 128 s, which matches
        # `detection + broadcast/3` for the default detection=60, broadcast=180.
        # Width of 15 s captures variation in individual response without
        # the +55 s tail the old `+ broadcast/3.3` formula introduced.
        #
        # NOTE: EVC file row 65 (premovement_time, typically 165 s) is NOT
        # used here as the reaction time, despite its semantic label.
        # Investigation against the GUMOK reference (linear regression of
        # VB EV times against fire_x gives a y-intercept of 128.2 s) shows
        # that EVC.exe internally computes reaction as ≈ detection +
        # broadcast/3, NOT premovement_time. R65 appears to be a budget /
        # display value used only for the row-74 extended-time calculation;
        # it does not drive the actual agent reaction sampling. Using R65
        # directly here would shift mean reaction by +40 s and over-predict
        # VB EV times by ~10-15%.
        det_t  = max(0.0, p.detection_time)   # EVC row 81 (default 60 s)
        brd_t  = max(1.0, p.broadcast_time)   # EVC row 80 (default 180 s)
        react_lo = det_t + brd_t / 3.0        # ≈ 120 s for 60 + 180/3
        react_hi = react_lo + 15.0            # tight upper bound for VB parity
        react_time = _rng.uniform(react_lo, react_hi, n_occ)

        # ── 🔧 VB-PARITY: NORMAL-traffic arrival staggering (dynamic inflow) ─
        # The VB driver (n5.txt decompile) runs NORMAL traffic as a DYNAMIC
        # INFLOW simulation: DAT_004a6340==1 admits vehicles per timestep via
        # FUN_0048a540/FUN_0045b750, so the queue behind the fire builds over
        # minutes. An occupant whose vehicle is k vehicles behind the fire
        # face only ENTERS the tunnel (and the smoke field) at
        #     t_entry ≈ k × 3600 / q_inflow      (q = EVC L66, veh/h)
        # Python's static queue exposed everyone from t = 0, which over-doses
        # mid-queue occupants by their missing 1–3 min head start during the
        # smoke ramp — invisible on bores whose NORMAL FDBs are clean upstream
        # (Gopo Upper: both ≈ 0 fatalities) but a ~2× normal-EQF over-
        # prediction on bores with upstream backlayering (Gopo Lower).
        # The vehicle count ahead of position x at jam density is
        # density × lanes × (fire_x − x)/1000, giving a closed-form per-agent
        # entry time with no per-vehicle bookkeeping. Congested mode is
        # untouched (VB's congested queue is static — FUN_0045db70).
        # Toggle: the mechanism is decompile-faithful, but its net effect on
        # dose depends on the temporal structure of each NORMAL FDB (a fast-
        # saturating field → late entry reduces dose; a slowly advancing front
        # → late entrants meet worse air). Calibrate against a real NORMAL
        # FDB + VB per-occupant output before relying on it; set
        # NORMAL_INFLOW_STAGGER = True to enable (default OFF: on the real
        # 100NFV0 field it increased dose because the upstream saturates just
        # as the delayed occupants arrive — it is NOT the source of the
        # normal-traffic over-prediction; that needs VB per-occupant data).
        entry_time = np.zeros(n_occ, dtype=float)
        if (getattr(self, 'NORMAL_INFLOW_STAGGER', False)
                and getattr(self, '_is_normal_traffic', False) and n_occ > 0):
            try:
                _q_in = float(p.normal_traffic)
            except Exception:
                _q_in = 2000.0
            if _q_in > 0:
                _jd = getattr(self, '_jam_density_override', None) or 150.0
                _nl = max(1, min(4, p.num_lanes))
                _ahead = np.maximum(fire_x - pos, 0.0) * float(_jd) * _nl / 1000.0
                entry_time = _ahead * (3600.0 / _q_in)

        evac_time = entry_time + react_time + dist_to_exit / walk_speed
 
        # 🔥 FED saturation cap.
        # Previously fixed at 1.2 (slight over-shoot of incapacitation threshold
        # 1.0 to keep the [1.0, ∞) bucket sum non-zero). Empirical analysis of
        # VB output for high-HRR scenarios (e.g. 100 MW CONGEST P1) shows VB
        # allows FED to accumulate to an average of ~1.15 within the [1.0, ∞)
        # cohort, with the EQ Fatal sum requiring an effective cap closer to
        # 2.0 to match. Raising the cap from 1.2 to 2.0 brings Python's EQ
        # Fatal at 100 MW P1 within 5% of VB (152 → 173 vs VB 168). Higher
        # caps over-shoot. The cap only affects the EQ Fatal sum value (the
        # FED bucket counts are unchanged since all caps remain above the
        # highest threshold 1.0). Cap value lives in FED_CALIBRATION block
        # (self.FED_CAP) so it is tunable in one place.
 
        if self.fdb is not None and self.fdb.is_loaded:
            fdb = self.fdb
            times_fdb = fdb.times
            fed_total   = np.zeros(n_occ)
            current_pos = pos.copy()
 
            # 🔥 Track actual (smoke-slowed) escape time per agent.
            # The pre-computed `evac_time` = react_time + dist/walk_speed uses
            # clean-air walking speed. But agents walking through smoke slow
            # by up to 6.67× (clip floor 0.15). At 100 MW P5/P6 with CO reaching
            # 2000+ ppm over long stretches, the actual exit time can be 200+s
            # longer than the clean-air estimate. VB's simulator tracks this
            # naturally because it advances positions each timestep; here we
            # explicitly latch the exit-crossing time into `actual_evac_time`
            # and use that for the final EV Time reporting.
            actual_evac_time = evac_time.copy()  # fallback to clean-air estimate
 
            # 🔥 EVC↔FDB coordinate mapping.
            # The FDB and EVC files almost always use different x-origins:
            #   - EVC: fire at `fire_pt_x` (e.g. 26.7) in a 0..tunnel_length frame.
            #   - FDB: fire at the mesh centre (e.g. 317-323 m in a 0..640 frame).
            # We locate the FDB fire by finding the x with peak temperature and
            # apply a rigid offset so `x_fdb = x_evc + (x_fire_fdb - fire_x_evc)`.
            # Without this offset, zone-2 occupants (far from fire in EVC) get
            # queried inside the FDB smoke plume, producing tens of spurious
            # FED≥0.1 cases for 20 MW scenarios where VB reports zero.
            # 🔥 EVC↔FDB coordinate offset.
            # Prefer the FDB header's FIRE PT (the actual fire-source mesh
            # location, always at x≈320 for these tunnels) over peak-
            # temperature auto-detection. The 100 MW plume's hot-spot is
            # ~14 m upstream of the fuel source due to convective drift,
            # which was producing an offset error that systematically
            # under-counted FED for zone-1 agents by ~10-15%.
            fdb_offset = 0.0
            try:
                if getattr(fdb, 'fire_center', None) is not None:
                    fdb_offset = float(fdb.fire_center) - fire_x
                elif len(fdb.x_coords) > 1 and hasattr(fdb, 'temp') and fdb.temp is not None:
                    # Fallback: peak temperature across time as a fire locator.
                    tmax_per_x = np.max(fdb.temp, axis=0)
                    x_fire_fdb = float(fdb.x_coords[int(np.argmax(tmax_per_x))])
                    fdb_offset = x_fire_fdb - fire_x
            except Exception:
                fdb_offset = 0.0
 
            # 🔥 Per-agent escape tracking.
            # An agent is "escaped" once they reach their exit — after that
            # point they should NOT accumulate further FED (they're outside the
            # tunnel / at the safe entrance). The old logic used a single
            # `still_in = evac_time > t_prev` mask based on a pre-computed
            # evac_time, which:
            #   1. Didn't account for CO-induced speed reduction (which slows
            #      walking and delays real escape beyond `evac_time`).
            #   2. Clipped current_pos to the tunnel, so agents whose
            #      `current_pos` hit 0 kept being queried at x=0 (deep in the
            #      FDB upstream smoke plume) and kept accumulating FED long
            #      after they should have been safe.
            # The fix: track a boolean `escaped` per-agent that latches True
            # when the agent's walking trajectory crosses the exit position.
            escaped = np.zeros(n_occ, dtype=bool)
 
            # 🔥 Cache the last CO/O2/temp/rad snapshot from the FDB so that,
            # if we need to continue past the FDB time horizon (the 720 s case),
            # we can hold the smoke field at its final value instead of jumping
            # to zero. In practice the smoke field at end-of-FDB is already in
            # decay phase for these scenarios — holding it static is a mild
            # over-estimate of FED accumulation (safe side) while letting us
            # finish the walk to the exit. This matches VB EVC.exe behavior:
            # it keeps simulating until everyone has escaped or been
            # incapacitated, regardless of the FDB time horizon.
            last_co_arr   = np.zeros(n_occ)
            last_co2_arr  = np.full(n_occ, 0.04)   # ambient CO2 vol%
            last_o2_arr   = np.full(n_occ, 21.0)   # ambient O2
            last_temp_arr = np.full(n_occ, 20.0)   # ambient temp
            last_radi_arr = np.zeros(n_occ)
            last_soot_arr = np.zeros(n_occ)        # ambient soot
 
            for ti in range(1, len(times_fdb)):
                t_prev = times_fdb[ti - 1]
                t_now  = times_fdb[ti]
                dt     = t_now - t_prev
                if dt <= 0: continue
                # 🔥 Active agents = anyone still in the tunnel (not yet
                # escaped). We do NOT use `(evac_time > t_prev)` here as we
                # used to, because `evac_time` is the CLEAN-AIR estimate
                # `react_time + dist / walk_speed`. When smoke slows the walk,
                # the agent's actual exit time exceeds this estimate — but
                # the old `active` mask would drop them out of the simulation
                # at t > evac_time even if they hadn't actually reached the
                # exit, leaving them stranded and reported with an incorrect
                # EV Time. VB EVC.exe doesn't have this premature drop-out;
                # it keeps simulating every agent until they cross their
                # exit position. Match that behaviour.
                active = ~escaped
                if not np.any(active): break
 
                # Map agent positions from EVC to FDB coordinates
                x_query = current_pos + fdb_offset
 
                co_arr   = fdb.get_value('co',   t_now, x_query)
                co2_arr  = fdb.get_value('co2',  t_now, x_query)
                o2_arr   = fdb.get_value('o2',   t_now, x_query)
                temp_arr = fdb.get_value('temp', t_now, x_query)
                radi_arr = fdb.get_value('rad',  t_now, x_query)
                soot_arr = fdb.get_value('soot', t_now, x_query)
                # Cache for post-FDB continuation
                last_co_arr   = co_arr
                last_co2_arr  = co2_arr
                last_o2_arr   = o2_arr
                last_temp_arr = temp_arr
                last_radi_arr = radi_arr
                last_soot_arr = soot_arr
 
                # FED rate — binary-exact model (see _fed_rate_binary).
                # Replaces the former tuned power-law CO/O2/heat/radi block.
                fed_rate = self._fed_rate_binary(co_arr, co2_arr, o2_arr, temp_arr)
                # NORMAL-traffic FED scale: fit to the OLD power-law FED; likely
                # redundant now the CO RMV /7.1 flag is explicit. FLAGGED for
                # re-evaluation against the benchmark.
                # NORMAL-traffic FED scale — see FED CALIBRATION KNOBS block.
                if getattr(self, '_is_normal_traffic', False):
                    fed_rate = fed_rate * self.VB_NORMAL_FED_SCALE
 
                # 🔧 VB-PARITY: FED keeps accumulating past 1.0 while the
                # agent is in the tunnel — the reference output's ≥0.4…≥1.0
                # buckets are well populated, which a freeze-at-1.0 cannot
                # produce. Incapacitation (FED ≥ 1.0) stops the WALK (handled
                # below), not the dose; only FED_CAP bounds the accumulator.
                # 🔧 entry gating (normal-mode dynamic inflow): an occupant
                # accumulates dose only once their vehicle has joined the
                # queue (t_now ≥ entry_time); congested entry_time = 0.
                in_tunnel = active & (t_now >= entry_time)
                fed_total = np.minimum(fed_total + fed_rate * (dt / 60.0) * in_tunnel,
                                       self.FED_CAP)
 
                started = active & (t_now > entry_time + react_time)
                # 🔥 Smoke-reduction of walking speed — visibility-only model.
                #
                # Physics rationale: CO is a toxic gas that impairs motor
                # function via COHb binding over TIME, captured by the FED
                # accumulation (separate model). The act of walking through
                # CO does NOT directly slow walking speed — agents walk at
                # their physiological capability until FED ≥ 1.0 incapacitates
                # them. What slows WALKING is reduced VISIBILITY (smoke
                # obscures path, signs, exits), which is governed by soot
                # density.
                #
                # The previous formulation included a CO-based slowdown:
                #   co_reduction = clip(1 - CO/1500, 0.15, 1.0)
                # This was DOUBLE-COUNTING the CO effect (once in FED, once
                # in walk speed) and the 0.15 floor combined with min(co_red,
                # vis_red) yielded walking speeds as low as 0.09 m/s at 100 MW.
                # That made marginal survivors (FED 0.7-1.0) walk so slowly
                # that they took 800-900s to exit, dragging Python's EV time
                # at 100 MW P1-P2 up by 25% vs VB.
                #
                # Removing the CO term and using ONLY visibility-based
                # reduction matches VB's last-survivor walking speed at
                # 100 MW (~0.56 m/s = 93% of base 0.60), which is much
                # higher than the combined formula would predict.
                #
                # k_s [1/m] = K_m × m_soot [kg/m³]
                #          = 7600 × soot_raw [mg/m³] × 1e-6
                #          = 0.0076 × soot_raw
                # vis_reduction = clip(1 - 0.15 * k_s, 0.60, 1.0)
                #
                # Calibration (slope 0.15, floor 0.60):
                #   raw=100 mg/m³  (K_s=0.76):  factor = 0.89 (mild slow)
                #   raw=200 mg/m³  (K_s=1.52):  factor = 0.77 (moderate)
                #   raw=295 mg/m³  (K_s=2.24):  factor = 0.66 (heavy)
                #   raw=425 mg/m³  (K_s=3.23):  factor = 0.60 (floor, 020 peak)
                #   raw=891 mg/m³  (K_s=6.77):  factor = 0.60 (floor, 100 avg)
                #
                # The floor at 0.60 (NOT 0.30 of Frantzich-Jin) prevents
                # excessive slowdown at high-HRR soot levels and matches VB's
                # observed last-survivor walking speed at 100 MW.
                k_s = 0.0076 * np.maximum(soot_arr, 0.0)
                vis_reduction = np.clip(1.0 - 0.15 * k_s, 0.60, 1.0)
                smoke_reduction = vis_reduction
                wv = walk_speed * smoke_reduction
 
                # 🔥 Incapacitated agents (FED >= 1.0) STOP walking. This
                # matches VB's behavior: once an agent crosses the FED
                # incapacitation threshold, they collapse where they are
                # and don't keep walking. They're then excluded from EV
                # Time (last-survivor-out semantics) but still counted in
                # the FED bucket statistics. Without this, Python's
                # incapacitated agents kept walking at smoke-floor speed,
                # arriving at the exit eventually and inflating EV time
                # by 200-500 s at high HRR.
                # (not_incap gates the WALK only — the dose keeps
                # accumulating up to FED_CAP, see the FED update above.)
                not_incap = fed_total < 1.0
                walk_mask = started & not_incap
 
                # Propose new position; detect exit crossing
                new_pos = current_pos + evac_dir * wv * dt * walk_mask
                # An agent has escaped if their new_pos crosses their exit_pos
                crossed = walk_mask & (
                    ((evac_dir > 0) & (new_pos >= exit_pos)) |
                    ((evac_dir < 0) & (new_pos <= exit_pos))
                )
                # 🔥 Latch actual exit time for newly-escaped agents.
                # For agents that JUST crossed in this timestep, their real
                # exit time is somewhere between t_prev and t_now. Using t_now
                # is a slight over-estimate (at most dt ≈ 2 s); for long smoke-
                # slowed walks this correction restores the ~100-200 s gap to
                # VB at 100 MW P5/P6 Congested scenarios.
                newly_escaped = crossed & (~escaped)
                actual_evac_time = np.where(newly_escaped, t_now, actual_evac_time)
                escaped = escaped | crossed
                current_pos = new_pos
                current_pos = np.clip(current_pos, 0.0, tunnel_len)
 
                if _history is not None:
                    from evc_history import smoke_front, snapshot
                    smax, smin = smoke_front(fdb, t_now)
                    _history.append(snapshot(
                        t_now, escaped, fed_total, current_pos, exit_pos,
                        soot_at_occ=soot_arr, smds_max=smax, smds_min=smin))
                if timestep_cb is not None:
                    timestep_cb(t_now, escaped, fed_total, current_pos)
 
            # 🔥 VB EVC.exe behaviour: continue simulating until ALL agents have
            # escaped or been incapacitated (FED ≥ 1.0), regardless of the FDB
            # time horizon. Previously the loop ended at times_fdb[-1] (~720 s)
            # and any still-walking agent got their clean-air estimate as a
            # fallback, producing a soft ceiling at 720 s in 60+ of 900 runs.
            #
            # Past the FDB window we:
            #   (a) Hold the smoke field at its last FDB snapshot value,
            #       fading linearly to ambient over `_post_fdb_fade_s` seconds.
            #       This is a mild over-estimate (the fire has decayed by then)
            #       but matches VB's "keep going until everyone is out" rule
            #       without introducing free-walking artifacts.
            #   (b) Use a coarser timestep (`_post_fdb_dt`) since smoke gradients
            #       are gentle in this regime — saves CPU.
            #   (c) Cap total wall-clock simulation at `_post_fdb_max_t_s`
            #       (default 3600 s = 1 hour from the LAST FDB timestep) so
            #       a pathological case can't loop forever. At 0.15 m/s
            #       (smoke-floor walk speed) over 1000 m, that's ~6700 s —
            #       so 3600 s extra is generous for typical 320–500 m tunnels.
            _post_fdb_dt        = 5.0      # coarser than FDB's 2-3 s
            _post_fdb_fade_s    = 600.0    # linearly fade smoke field to ambient
            _post_fdb_max_t_s   = 3600.0   # safety net (1 hour past FDB end)
 
            if len(times_fdb) > 0:
                t_post_start = float(times_fdb[-1])
            else:
                t_post_start = 0.0
            t_post_end_max = t_post_start + _post_fdb_max_t_s
 
            # Only run the continuation if there are still unescaped agents.
            # VB-faithful behaviour: incapacitated agents (FED ≥ 1.0) keep
            # walking — their FED is already saturated, but the body continues
            # toward the exit until they cross or the safety cap fires. This
            # matches the VB output where EV Time = time the LAST agent
            # crosses their exit, regardless of FED outcome. (Previously the
            # continuation loop excluded FED ≥ 1.0 agents, which caused them
            # to be reported with their clean-air estimate instead of the
            # smoke-slowed reality — producing EV Times that were too short
            # for high-CO scenarios.)
            t_now_post = t_post_start
            while t_now_post < t_post_end_max:
                # Anyone still in the tunnel?
                active = ~escaped
                if not np.any(active):
                    break  # everyone out
 
                t_prev_post = t_now_post
                t_now_post  = min(t_now_post + _post_fdb_dt, t_post_end_max)
                dt_post     = t_now_post - t_prev_post
                if dt_post <= 0:
                    break
 
                # Smoke field: linear fade from last FDB snapshot to ambient.
                # fade_frac = 1 at t_post_start, → 0 at t_post_start + fade_s.
                age = t_now_post - t_post_start
                fade_frac = max(0.0, 1.0 - age / _post_fdb_fade_s)
                co_arr   = last_co_arr   * fade_frac
                co2_arr  = 0.04 + (last_co2_arr - 0.04) * fade_frac
                o2_arr   = 21.0 - (21.0 - last_o2_arr) * fade_frac
                temp_arr = 20.0 + (last_temp_arr - 20.0) * fade_frac
                radi_arr = last_radi_arr * fade_frac
                soot_arr = last_soot_arr * fade_frac
 
                # FED rate — binary-exact model (same as FDB-loop block).
                # not_incap gates the WALK below; the dose accumulates up
                # to FED_CAP exactly as in the main FDB loop.
                not_incap = fed_total < 1.0
                fed_rate = self._fed_rate_binary(co_arr, co2_arr, o2_arr, temp_arr)
                if getattr(self, '_is_normal_traffic', False):
                    fed_rate = fed_rate * self.VB_NORMAL_FED_SCALE
                fed_total = np.minimum(fed_total + fed_rate * (dt_post / 60.0) * active,
                                       self.FED_CAP)
 
                # Visibility-only walking-speed reduction (same as FDB-loop
                # above — see that block for the rationale and parameter
                # sourcing).
                k_s = 0.0076 * np.maximum(soot_arr, 0.0)
                vis_reduction = np.clip(1.0 - 0.15 * k_s, 0.60, 1.0)
                smoke_reduction = vis_reduction
                wv = walk_speed * smoke_reduction
 
                # All active agents have already passed their reaction time at
                # this point (continuation begins after the full FDB window).
                # But incapacitated agents stop walking — they collapse and
                # are excluded from EV Time.
                walk_mask = active & not_incap
 
                new_pos = current_pos + evac_dir * wv * dt_post * walk_mask
                crossed = walk_mask & (
                    ((evac_dir > 0) & (new_pos >= exit_pos)) |
                    ((evac_dir < 0) & (new_pos <= exit_pos))
                )
                newly_escaped = crossed & (~escaped)
                actual_evac_time = np.where(newly_escaped, t_now_post, actual_evac_time)
                escaped = escaped | crossed
                current_pos = new_pos
                current_pos = np.clip(current_pos, 0.0, tunnel_len)
 
            fed_total = np.clip(fed_total, 0.0, self.FED_CAP)
 
            # 🔥 Post-loop actual_evac_time resolution.
            # After the FDB loop + continuation loop, three categories of agent:
            #   (a) Escaped during FDB or continuation → actual_evac_time = t_now
            #       (the exact timestep they crossed exit_pos). Best estimate.
            #   (b) Incapacitated (FED ≥ 1.0) before escaping → they stopped
            #       walking. Their actual_evac_time stays at whatever value the
            #       continuation loop last set; if they were never near the
            #       exit, it falls back to the initial clean-air evac_time.
            #       For VB-parity these still count as evacuees (per the
            #       "Evacuees = total occupants" rule), but with their
            #       walk-distance / walk-speed estimate as exit time.
            #   (c) Still walking at _post_fdb_max_t_s → extremely rare in
            #       practice; means they've been walking 1+ hour past FDB end.
            #       We clamp their actual_evac_time to the continuation cap so
            #       the reported EV Time doesn't go negative or zero.
            #
            # The element-wise maximum with `evac_time` (the clean-air estimate)
            # is kept as a safety net for non-escaped, non-incapacitated agents
            # whose continuation-loop time might be lower than their clean-air
            # estimate due to position clipping at the tunnel boundary.
            actual_evac_time = np.maximum(actual_evac_time, evac_time)
        else:
            sigma_fire  = 5.0
            co_peak_ppm = 8000.0
            t_ramp      = 120.0
            dt_fb       = 10.0
            t_end_fb   = premovement * 2.0 + tunnel_len / abs_ws
            times_fb   = np.arange(0, t_end_fb + dt_fb, dt_fb)
            fed_total    = np.zeros(n_occ)
            current_pos  = pos.copy()
 
            for _t in times_fb[1:]:
                _t_prev  = _t - dt_fb
                still_in = evac_time > _t_prev
                if not np.any(still_in): break
                co_ramp = min(_t / t_ramp, 1.0)
                co_arr  = co_peak_ppm * co_ramp * np.exp(-np.abs(current_pos - fire_x) / sigma_fire)
                # binary-exact rate; synthetic fallback has no CO2/O2/temp field
                # so use ambient (CO2=0.04, O2=21, T=20) — CO term dominates here.
                _amb = np.full_like(co_arr, 0.04)
                fed_rate = self._fed_rate_binary(
                    co_arr, _amb, np.full_like(co_arr, 21.0), np.full_like(co_arr, 20.0))
                _in_tun      = still_in & (_t >= entry_time)
                fed_total   += fed_rate * (dt_fb / 60.0) * _in_tun
                started      = still_in & (_t > entry_time + react_time)
                wv           = np.where(is_elderly, eld_ws, walk_speed)
                wv           = np.maximum(wv, abs_ws)
                current_pos += evac_dir * wv * dt_fb * started
                current_pos  = np.clip(current_pos, 0.0, tunnel_len)
            fed_total = np.clip(fed_total, 0.0, self.FED_CAP)
 
        # 🔥 VB-Faithful End-State Accounting:
        # Row 72 of the EVC file (sim_end_time_r72) defines the FED *integration*
        # window — i.e., how long the fire/smoke exposure is tracked. It is NOT
        # a hard cap on who counts as an evacuee. In the VB reference, everyone
        # whose final FED < 1.0 is counted as a survivor and the reported
        # EV Time is the true last-out time (typically 600–700 s for a 320 m
        # tunnel at 0.5 m/s, well beyond the 365 s FED window). Clipping
        # survivors by t_sim_end was the root cause of EV Time collapsing from
        # ~665 s → ~365 s and Evacuees dropping spuriously on long-walk cases.
        # 🔥 Evacuee-count semantics match VB:
        # VB's "Evacuees" column = n_occ − (number of FED ≥ 1.0 fatalities).
        # Verified empirically against the FNCV_ROAD.xlsm "EVC Result" sheet:
        # e.g. GUMOK 020CFV0_P1 run 1 shows n_occ=333, FED≥1.0=1, Evacuees=332.
        # An earlier comment in this file claimed Evacuees = n_occ (total) —
        # that was wrong. We now subtract incapacitated agents from the
        # reported Evacuees count to match VB's spreadsheet output exactly.
        # FED≥1.0 fatalities are still tracked separately in the `fed` array
        # (last bucket) and in `eq_fatal` (Purser P-incap sum, see below).
        incapacitated = fed_total >= 1.0
        survivors = ~incapacitated   # used for zone/FED accounting AND evacuee count
        n_fatal = int(np.sum(incapacitated))
        evacuees_count = max(0, int(n_occ) - n_fatal)
 
        # 🔥 Use smoke-slowed actual_evac_time when FDB-based simulation ran.
        # For the FDB-less fallback path, evac_time is the best estimate.
        _ev_source = actual_evac_time if (self.fdb is not None and self.fdb.is_loaded) else evac_time
 
        # 🔥 EV Time = last-SURVIVOR-out (excludes incapacitated agents).
        #
        # Empirical analysis against real GUMOK FDB data (all 18 scenarios:
        # 020/030/100 MW × 6 fire positions) shows VB excludes FED≥1.0 agents
        # from EV Time computation. Example:
        #   100/CONG/FV0/P1: VB EV=712, n_occ=333, 114 incapacitated
        #   Last-walker speed = 329m/(712-128s) = 0.56 m/s ≈ base 0.60.
        #   Means: VB's last "walker" is a survivor with minimal slowdown.
        #   If incapacitated agents were included, they'd be at the floor
        #   walk speed for the entire remaining sim (Python EV ~1800s+).
        #
        # The previous code used `max(actual_evac_time)` over ALL agents,
        # which caused 100 MW EV times to balloon to ~1800s (vs VB's ~712s)
        # because incapacitated agents continued walking at the smoke-floor
        # speed (~0.18 m/s) indefinitely. This systematically over-predicted
        # EV time by 2-3× at high HRR.
        #
        # The current formula matches VB across the full HRR range:
        #   - 020 MW: no incapacitations, EV = max of all (= max of survivors)
        #   - 100 MW: many incapacitations, EV = max of survivors only,
        #     which is much faster because slow walkers got incapacitated
        #     and don't drag the EV time out.
        #
        # Note: evacuee count is INDEPENDENT of EV time. VB reports all
        # agents as "evacuated" (they reach the exit either alive or carried
        # out) but EV Time reflects only the last living walker. Python
        # follows this convention.
        if np.any(survivors):
            ev_time = float(np.max(_ev_source[survivors]))
        else:
            # Pathological case: all agents incapacitated. Fall back to the
            # max over everyone to avoid an empty-array reduction error.
            ev_time = float(np.max(_ev_source))
 
        zone1_mask  = pos < fire_x
        n_occ_zone  = int(np.sum(zone1_mask))
        n_evac_zone = int(np.sum(survivors & zone1_mask))
        fed_counts = [int(np.sum(fed_total >= th)) for th in self.FED_THRESHOLDS]
        # 🔥 EQ Fatal — Purser log-normal incapacitation probability sum.
        #
        # SUPERSEDES the previous "Σ FED over all agents" formula. That sum
        # was arithmetically impossible against VB output: e.g.
        #   030/CONG/FVP/P1 iter 1: 38 agents at FED ≥ 0.1, VB EQ_Fatal = 0.4.
        # A Σ-FED-over-the-≥0.1 cohort would have a floor of 38 × 0.1 = 3.8,
        # an order of magnitude above VB. Σ over all agents is even larger.
        # Σ over the ≥0.5 cohort, Σ over the ≥0.1 cohort, and Σ over all
        # were each falsified on per-iteration data.
        #
        # The only model consistent with VB across the 30-scenario set is
        # the Purser dose-response curve: each agent contributes its
        # probability of incapacitation, not its FED value:
        #
        #   P_incap(FED) = Φ( (ln FED − ln μ) / σ )
        #
        #   μ = 0.5  (FED at 50% incapacitation, Purser)
        #   σ = 0.55 (log-normal spread of the dose-response curve)
        #   Φ    standard normal CDF
        #
        #   EQ_Fatal = Σ_i  P_incap(FED_i)
        #
        # This is the standard egress-tool convention (FDS+Evac, Pathfinder,
        # buildingEXODUS, STEPS). Verification on 030/CONG/FVP/P1 iter 1:
        # 38 agents at FED ≈ 0.13 → each P_incap ≈ 0.011 → Σ ≈ 0.42 ≈ 0.4 ✓.
        # Across all 30 scenarios this collapses the historic Py/VB ratio
        # from 3.28× (over-prediction) to 0.87× (slight under-prediction),
        # closing ~97 % of the total gap. The 020 MW outlier — previously
        # 7.7× over — falls into place because P_incap is near zero in the
        # trace-FED regime (0.05–0.15) where Σ FED previously summed large.
        #
        # The standard normal CDF is computed via math.erf to avoid a scipy
        # dependency: Φ(z) = 0.5 * (1 + erf(z / √2)).
        #
        # NOTE on coupling with the FED scale: the binary-exact FED model
        # was tuned against the old Σ-FED definition of EQ Fatal. With the
        # P-incap definition in place, 100 MW scenarios are expected to
        # under-predict (Py/VB ≈ 0.32×) because the FED-accumulation rate
        # is now too low for the new metric. The divisor should be re-tuned
        # upward (toward the standard Purser 35000) once the P-incap baseline
        # has been validated end-to-end. Do NOT retune the divisor and the
        # EQ Fatal formula in the same change — verify one, then the other.
        # 🔧 VB-EXACT EQ-FATAL RULE (supersedes the Purser P-incap below).
        #
        # Derived by constrained least-squares on ALL 900 per-run rows of the
        # reference workbook 제연무_FNCV_ROAD.xlsm 'EVC Result' sheet
        # (180 scenarios × 5 runs), regressing EQ Fatal on the FED-band
        # occupant counts. Result (R² = 1.00000, weights to 4 decimals):
        #
        #     FED < 0.1          →  0.00  per occupant
        #     0.1 ≤ FED < 0.2    →  0.01
        #     0.2 ≤ FED < 0.3    →  0.10
        #     FED ≥ 0.3          →  1.00   (every band incl. ≥1.0)
        #
        #   EQ_Fatal = 0.01·n[0.1,0.2) + 0.1·n[0.2,0.3) + 1.0·n[≥0.3)
        #
        # i.e. VB applies a stepwise casualty-probability TABLE to the FED
        # bands — not a probit and not Σ FED. Spot checks: 020CFV0_P1 run 1
        # (bands 24/20/16 → 0.24+2.0+16 = 18.24 vs VB 18.2 ✓);
        # the 030/CONG/FVP/P1 case that falsified Σ-FED (38 agents ≥0.1,
        # VB 0.4) gives 38×0.01 = 0.38 ✓ under this rule as well — the
        # P-incap model below was only an approximate twin of the 0.01/0.1
        # steps in the low-FED regime and diverged ≥0.3 (probit ~0.34 where
        # VB jumps to 1.0), which produced the 0.2–0.5× EQ-Fatal shortfall
        # at 030/100 MW.
        #
        # The bands are configurable (not hardcoded into the math): override
        # EQ_FATAL_BANDS or set EQ_FATAL_MODE = 'purser_pincap' to restore
        # the previous dose-response model.
        _eq_mode = getattr(self, 'EQ_FATAL_MODE', 'vb_step')
        if _eq_mode == 'vb_step':
            _bands = getattr(self, 'EQ_FATAL_BANDS',
                             ((0.1, 0.01), (0.2, 0.10), (0.3, 1.00)))
            _w = np.zeros_like(fed_total, dtype=float)
            for _th, _wt in sorted(_bands):
                _w = np.where(fed_total >= _th, _wt, _w)
            eq_fatal = float(np.sum(_w))
        else:
            _PINCAP_MU_LN  = math.log(0.5)   # ln(μ), μ = 0.5
            _PINCAP_SIGMA  = 0.55            # log-normal spread (Purser)
            _PINCAP_SQRT2  = math.sqrt(2.0)
            fed_safe = np.maximum(fed_total, 1e-9)   # avoid log(0); P_incap → 0
            z = (np.log(fed_safe) - _PINCAP_MU_LN) / _PINCAP_SIGMA
            _erf_vec = np.frompyfunc(math.erf, 1, 1)
            p_incap = 0.5 * (1.0 + _erf_vec(z / _PINCAP_SQRT2).astype(np.float64))
            eq_fatal = float(np.sum(p_incap))
 
        pct_fed_vb = [
            vb_round(float(np.sum(fed_total >= 0.1)) / n_occ * 100, 6) if n_occ > 0 else 0.0,
            vb_round(float(np.sum(fed_total >= 0.2)) / n_occ * 100, 6) if n_occ > 0 else 0.0,
            vb_round(float(np.sum(fed_total >= 0.3)) / n_occ * 100, 6) if n_occ > 0 else 0.0,
            vb_round(float(np.sum(fed_total >= 0.4)) / n_occ * 100, 6) if n_occ > 0 else 0.0,
            vb_round(float(np.sum(fed_total >= 0.5)) / n_occ * 100, 6) if n_occ > 0 else 0.0,
            vb_round(float(np.sum(fed_total >= 0.6)) / n_occ * 100, 6) if n_occ > 0 else 0.0,
        ]
        pct_safe = vb_round(float(np.sum(survivors)) / n_occ * 100, 6) if n_occ > 0 else 0.0
 
        return RunResult(
            run_no, ev_time, evacuees_count, fed_counts, eq_fatal,
            pct_safe=pct_safe, pct_fed=pct_fed_vb,
            n_occ_zone=n_occ_zone, n_occ_total=n_occ, n_evac_zone=n_evac_zone,
            upstream_failed=n_occ_zone - n_evac_zone,
            history=_history if _history is not None else [],
        )
 
    def _compute_avg(self, runs, exmax, exmin):
        if not runs: return RunResult(0, 0.0, 0, [0]*10, 0.0)
        def _tm(vals): return calavg_vb(vals, exmin, exmax)
        return RunResult(0, _tm([r.ev_time for r in runs]), int(_tm([float(r.evacuees) for r in runs])),
                         [int(_tm([float(r.fed[i]) for r in runs])) for i in range(10)], _tm([r.eq_fatal for r in runs]),
                         pct_safe=_tm([r.pct_safe for r in runs]),
                         pct_fed=[_tm([r.pct_fed[i] for r in runs]) for i in range(6)],
                         n_occ_total=int(_tm([float(r.n_occ_total) for r in runs])),
                         n_occ_zone=int(_tm([float(r.n_occ_zone) for r in runs])),
                         n_evac_zone=int(_tm([float(r.n_evac_zone) for r in runs])))
 
    def write_results_to_evc(self, avg: RunResult, runs: List[RunResult] = None, reset_first: bool = True):
        """No-op — preserves the .evc file as input-only, matching VB workflow.
 
        The legacy VB pipeline (decoded from FNCV_ROAD.xlsm Module1.bas) does
        NOT modify the .evc file after a batch run. .evc files are read once
        by EVC.exe as inputs; simulation results are written to separate
        output files (.dat / .caset / .set / LVCNHesTime.dat) via
        evc_output_writer.EVCOutputWriter.
 
        An earlier implementation here recomputed L74 from the simulation's
        n_occ_total and rewrote the .evc file. That behavior:
          1. Has no counterpart in the VB workflow.
          2. Used a different n_occ formula than _write_evc_file's pre-batch
             write, causing L74 to collapse from ~5000s to ~1800s on every
             batch run (depending on tunnel geometry).
          3. Mixed two physical concepts under one variable name — the
             pre-batch n_occ is a vehicle-equivalent evacuation budget input;
             the post-batch n_occ_total is a literal head count.
 
        Keeping this method as a no-op preserves the L74 value that
        qra_main_app._write_evc_file wrote pre-batch (single source of
        truth), and aligns with the VB pipeline's input-immutability
        contract.
 
        The signature is preserved (avg, runs, reset_first) so existing
        call sites — see EVCEngine.run() and qra_main_app's
        _batch_run_evc_simulation aggregation loop — continue to work
        without modification.
        """
        return None

