#!/usr/bin/env python3
"""
FDS to FDB Converter - Version 3
Converts FDS (Fire Dynamics Simulator) slice output files to FDB format.
Output matches the exact FIRE ANALYSIS DB format used by the QRA system.

Unit conversions applied:
  SOOT  : kg/m³     (FDS raw, no conversion)
  CO2   : %         (FDS volume fraction × 100)
  CO    : PPM       (FDS volume fraction × 1,000,000)
  TEMP  : °C        (FDS raw, no conversion)
  RADI  : kW/m²     (FDS raw, no conversion)
  OXYGEN: %         (FDS volume fraction × 100)
"""

import logging
import re
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
try:
    import fdsreader as fds
except ImportError:
    fds = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class ConversionConfig:
    """Configuration for FDS to FDB conversion"""

    def __init__(self):
        # Breathing height (metres) – auto-detected from slices if None
        self.breathing_height: Optional[float] = None

        # Output time interval (seconds) – auto-detected from slice times if None
        self.time_interval: Optional[float] = None

        # Ambient conditions (auto-read from FDS file if not set)
        self.ambient_temp: float = 20.0       # °C
        self.ambient_radi: float = 0.0        # kW/m²  (will be estimated from data)

        # Tunnel main axis ('X' or 'Y')
        self.tunnel_axis: str = 'X'

        # Fire location along tunnel axis (min, max) in metres
        # Set to None to attempt auto-detection from FDS file
        self.fire_pt_min: Optional[float] = None
        self.fire_pt_max: Optional[float] = None

        # Mesh number (for MESH header line)
        self.mesh_number: int = 1


class FDSToFDBConverter:
    """Converter: FDS slice output → FIRE ANALYSIS DB (.fdb) format"""

    # Map FDS quantity names → internal variable keys
    QUANTITY_MAP = {
        'TEMPERATURE':                    'TEMP',
        'SOOT VISIBILITY':                'SOOT',
        'SOOT DENSITY':                   'SOOT',
        'CARBON MONOXIDE VOLUME FRACTION':'CO',
        'CARBON DIOXIDE VOLUME FRACTION': 'CO2',
        'OXYGEN VOLUME FRACTION':         'OXYGEN',
        'RADIATION INTENSITY':            'RADI',
        'RADIANT HEAT FLUX':              'RADI',
        'RADIATIVE HEAT FLUX':            'RADI',
        'RADIATION':                      'RADI',
    }

    # Unit conversion factors from FDS native → FDB units
    UNIT_CONV = {
        'SOOT':   1.0,          # kg/m³  → kg/m³
        'CO2':    100.0,        # frac   → %
        'CO':     1.0e6,        # frac   → PPM
        'TEMP':   1.0,          # °C     → °C
        'RADI':   1.0,          # kW/m²  → kW/m²
        'OXYGEN': 100.0,        # frac   → %
    }

    def __init__(self, simulation_dir, config: Optional[ConversionConfig] = None):
        if isinstance(simulation_dir, (str, Path)):
            self.simulation_dir = Path(simulation_dir)
        else:
            self.simulation_dir = Path(str(simulation_dir))

        self.config = config or ConversionConfig()
        self.logger = logging.getLogger(__name__)
        self.sim = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def convert(self, output_file: Optional[Path] = None) -> Path:
        """Convert FDS output to FDB format. Returns path to written file."""
        self.logger.info("Starting FDS → FDB conversion")
        self.logger.info(f"Simulation directory: {self.simulation_dir}")

        # Load simulation
        self.sim = fds.Simulation(str(self.simulation_dir))
        self.logger.info(f"Loaded: CHID={self.sim.chid}  FDS version={self.sim.fds_version}")
        self.logger.info(f"Slices available: {len(self.sim.slices)}")

        # Determine output path
        if output_file is None:
            base = (self.simulation_dir.parent
                    if self.simulation_dir.is_file()
                    else self.simulation_dir)
            output_file = base / f"{self.sim.chid}.fdb"
        output_file = Path(output_file)

        # Find horizontal breathing-height slices
        breathing_slices = self._find_breathing_height_slices()
        if not breathing_slices:
            raise ValueError("No slices found at breathing height. "
                             "Check that your FDS file outputs horizontal slices.")

        # Extract data arrays
        data_dict, times, mesh_info = self._extract_data(breathing_slices)

        # Parse FDS input file for extra metadata (fire location, ambient)
        fds_meta = self._parse_fds_file()

        # Write output
        self._write_fdb(output_file, data_dict, times, mesh_info, fds_meta)

        self.logger.info(f"Conversion complete: {output_file}")
        return output_file

    # ------------------------------------------------------------------
    # Slice detection
    # ------------------------------------------------------------------

    def _find_breathing_height_slices(self) -> Dict[str, object]:
        """Return mapping variable_key → slice object for breathing-height slices."""
        # Collect all quasi-horizontal slices (Z nearly constant)
        candidates: List[Tuple[float, object]] = []
        for slc in self.sim.slices:
            ext = slc.extent
            dz = abs(ext.z_end - ext.z_start)
            if dz < 0.1:                          # horizontal (constant-Z) slice
                z_val = (ext.z_start + ext.z_end) / 2.0
                if 1.4 <= z_val <= 2.2:           # plausible breathing height
                    candidates.append((z_val, slc))

        if not candidates:
            self.logger.warning("No horizontal slices in 1.4–2.2 m range.")
            self.logger.info("All slices:")
            for slc in self.sim.slices:
                self.logger.info(f"  {slc.quantity.name}  extent={slc.extent}")
            return {}

        # Choose breathing height: override from config or pick most-populated Z
        from collections import defaultdict
        by_z: Dict[float, list] = defaultdict(list)
        for z, slc in candidates:
            by_z[round(z, 3)].append(slc)

        if self.config.breathing_height is not None:
            target_z = min(by_z.keys(),
                           key=lambda z: abs(z - self.config.breathing_height))
        else:
            target_z = max(by_z.keys(), key=lambda z: len(by_z[z]))

        self.logger.info(f"Breathing height selected: Z = {target_z:.3f} m "
                         f"({len(by_z[target_z])} slices)")

        result: Dict[str, object] = {}
        for slc in by_z[target_z]:
            key = self.QUANTITY_MAP.get(slc.quantity.name.upper())
            if key and key not in result:
                result[key] = slc
                self.logger.info(f"  {slc.quantity.name!r}  →  {key}")

        return result

    # ------------------------------------------------------------------
    # Data extraction
    # ------------------------------------------------------------------

    def _extract_data(self, breathing_slices: Dict[str, object]):
        """Extract numpy arrays for all variables. Returns (data_dict, times, mesh_info)."""
        data_dict: Dict[str, np.ndarray] = {}
        times = None
        mesh_info = None

        for var_key, slc in breathing_slices.items():
            self.logger.info(f"Loading {var_key} …")
            try:
                raw = slc.to_global()          # shape: (n_times, nx, ny[, nz])
                conv = self.UNIT_CONV.get(var_key, 1.0)
                data_dict[var_key] = raw * conv

                if times is None:
                    times = slc.times
                    self.logger.info(f"  Time: {times[0]:.1f}–{times[-1]:.1f} s  "
                                     f"({len(times)} steps)")

                if mesh_info is None:
                    ext = slc.extent
                    mesh_info = {
                        'extent': ext,
                        'breathing_z': (ext.z_start + ext.z_end) / 2.0,
                    }
                    self.logger.info(f"  Mesh: X=[{ext.x_start:.2f}, {ext.x_end:.2f}]  "
                                     f"Y=[{ext.y_start:.2f}, {ext.y_end:.2f}]  "
                                     f"Z={mesh_info['breathing_z']:.3f}")

                self.logger.info(f"  Shape={raw.shape}  "
                                 f"range=[{raw.min():.4g}, {raw.max():.4g}]")
            except Exception as exc:
                self.logger.error(f"  Failed to load {var_key}: {exc}")

        if times is None or mesh_info is None:
            raise ValueError("Could not extract any data from slices.")

        return data_dict, times, mesh_info

    # ------------------------------------------------------------------
    # FDS file parsing for metadata
    # ------------------------------------------------------------------

    def _parse_fds_file(self) -> dict:
        """Read the .fds input file and extract ambient conditions + fire location."""
        meta = {
            'ambient_temp': self.config.ambient_temp,
            'fire_pt_min':  self.config.fire_pt_min,
            'fire_pt_max':  self.config.fire_pt_max,
        }

        # Locate the .fds file
        base = (self.simulation_dir.parent
                if self.simulation_dir.is_file()
                else self.simulation_dir)
        fds_files = list(base.glob("*.fds")) + list(base.glob("*.FDS"))
        if not fds_files:
            self.logger.warning("No .fds input file found; using default ambient values.")
            return meta

        fds_text = fds_files[0].read_text(errors='ignore')

        # Ambient temperature from &MISC TMPA=...
        m = re.search(r'TMPA\s*=\s*([0-9.]+)', fds_text, re.IGNORECASE)
        if m:
            meta['ambient_temp'] = float(m.group(1))

        # Fire location: look for VENT lines with SURF_ID containing 'BURNER' or 'FIRE'
        if meta['fire_pt_min'] is None:
            axis = self.config.tunnel_axis.upper()
            idx = {'X': 0, 'Y': 2}.get(axis, 0)   # XB pair index for axis
            fire_coords = []
            for line in fds_text.splitlines():
                if re.search(r'SURF_ID\s*=\s*[\'"].*(?:BURNER|FIRE)', line, re.IGNORECASE):
                    xb = re.search(r'XB\s*=\s*([0-9.,\s-]+)', line)
                    if xb:
                        nums = [float(x) for x in re.findall(r'-?[0-9]+\.?[0-9]*', xb.group(1))]
                        if len(nums) >= idx + 2:
                            fire_coords.extend([nums[idx], nums[idx + 1]])
            if fire_coords:
                meta['fire_pt_min'] = min(fire_coords)
                meta['fire_pt_max'] = max(fire_coords)

        return meta

    # ------------------------------------------------------------------
    # FDB writer – exact FIRE ANALYSIS DB format
    # ------------------------------------------------------------------

    def _write_fdb(self, output_file: Path, data_dict: Dict[str, np.ndarray],
                   times: np.ndarray, mesh_info: dict, fds_meta: dict):
        """Write the FDB file in the exact FIRE ANALYSIS DB format (CRLF line endings)."""

        ext = mesh_info['extent']
        breathing_z = mesh_info['breathing_z']

        # Determine grid dimensions from first data array
        first = next(iter(data_dict.values()))
        if first.ndim == 4:        # (t, nx, ny, nz)
            n_times, nx, ny, _ = first.shape
        elif first.ndim == 3:      # (t, nx, ny)
            n_times, nx, ny = first.shape
        else:
            raise ValueError(f"Unexpected data shape: {first.shape}")

        # X coordinates along tunnel axis
        x_coords = np.linspace(ext.x_start, ext.x_end, nx)

        # Y: use middle slice for single-axis output
        mid_y = ny // 2 if ny > 1 else 0

        # ---- Time interval ----
        if len(times) > 1:
            dt = float(times[1] - times[0])
        else:
            dt = self.config.time_interval or 30.0

        # ---- Ambient RADI: use median of RADI data at t=0 (background) ----
        ambient_radi = self.config.ambient_radi
        if 'RADI' in data_dict and ambient_radi == 0.0:
            radi_t0 = data_dict['RADI'][0]
            ambient_radi = float(np.median(radi_t0[radi_t0 > 0])) if np.any(radi_t0 > 0) else 0.0

        # ---- Mesh indices (cell-based, 0-indexed) ----
        # I corresponds to X, J to Y, K to Z
        # The 020CFV0.FDB uses cell-face indices: I1=0, I2=nx_cells, etc.
        nx_cells = nx - 1   # number of cells
        ny_cells = ny - 1
        # K index for breathing height
        z_total = ext.z_end if hasattr(ext, 'z_end') else breathing_z
        # Infer total mesh Z from FDS (not directly available from slice; use breathing_z/nk)
        # Approximate K from proportion — this will be read from FDS mesh if available
        k_idx = self._estimate_k_index(breathing_z)

        # Fire location
        fire_min = fds_meta.get('fire_pt_min')
        fire_max = fds_meta.get('fire_pt_max')
        if fire_min is not None:
            fire_str = f"{fire_min:10.3f}-{fire_max:9.3f}"
        else:
            fire_str = "        N/A-       N/A"

        # Simulation time (last time step)
        sim_time = int(round(times[-1]))

        self.logger.info(f"Writing FDB: {nx} X-points × {n_times} time steps …")

        lines = []

        # ---- Header block ----
        lines.append("******************** FIRE ANALYSIS DB ********************")
        lines.append(f"TUNNEL MAIN AXIS : {self.config.tunnel_axis}")
        lines.append(f"TUNNEL HEIGHT AXIS : Z AT  {breathing_z:9.3f}")
        lines.append(f"SIMULATION TIME :   {sim_time}")
        lines.append(f"FDB TIME INTERVAL :  {dt:.1f}")
        lines.append(f"MESH :  {self.config.mesh_number}")
        lines.append(
            f"I1 :       0   I2 :     {nx_cells}   "
            f"J1 :       0   J2 :      {ny_cells}   "
            f"K1 :  {k_idx:5d}   K2 :  {k_idx:5d}"
        )
        lines.append(
            f"X1 : {ext.x_start:6.2f}   X2 : {ext.x_end:6.2f}   "
            f"Y1 : {ext.y_start:6.2f}   Y2 : {ext.y_end:6.2f}   "
            f"Z1 : {breathing_z:6.2f}   Z2 : {breathing_z:6.2f}"
        )

        # ---- TIME TABLE ----
        lines.append("TIME TABLE")
        lines.append(f"  {n_times}")
        # Rows of 11: first column is row-index prefix (0, 10, 20, …)
        for row_start in range(0, n_times, 11):
            chunk = times[row_start: row_start + 11]
            prefix = f"{row_start:4d}" if row_start > 0 else "   0"
            time_str = "".join(f"  {t:6.1f}" for t in chunk)
            lines.append(f"{prefix}{time_str}")

        # ---- AMBIENT CONDITION ----
        lines.append("AMBIENT CONDITION")
        lines.append("         TEMPERATURE   RADIATE INTENSITY")
        lines.append(f"         {fds_meta['ambient_temp']:12.3f}   {ambient_radi:14.3f}")

        # ---- TUNNEL X COORDINATE ----
        lines.append("TUNNEL X COORDINATE")
        lines.append(
            f"{'':>15}MIN_X{'':>15}MAX_X{'':>13}NX GRID{'':>13}FIRE PT"
        )
        lines.append(
            f"{'':>15}{ext.x_start:.3f}{'':>13}{ext.x_end:.3f}"
            f"{'':>16}{nx:d}        {fire_str}"
        )

        # ---- Column headers ----
        lines.append("*" * 90)
        lines.append(
            "  TIME    X-COOR      SOOT        CO2         CO         "
            "TEMP        RADI       OXYGEN"
        )
        lines.append(
            "  [SEC]    [M]      [KG/M^3]      [%]        [PPM]       "
            "[DEG.]     [KW/M^2]      [%]"
        )
        lines.append(
            "*" * 7 + "|" + "*" * 9 + "|" + ("|" + "*" * 11) * 6 + "|"
        )
        lines.append("DATA START")

        # ---- Data rows ----
        soot_d   = data_dict.get('SOOT')
        co2_d    = data_dict.get('CO2')
        co_d     = data_dict.get('CO')
        temp_d   = data_dict.get('TEMP')
        radi_d   = data_dict.get('RADI')
        oxygen_d = data_dict.get('OXYGEN')

        for t_idx, t_val in enumerate(times):
            for x_idx, x_val in enumerate(x_coords):
                sv  = self._get(soot_d,   t_idx, x_idx, mid_y)
                cv2 = self._get(co2_d,    t_idx, x_idx, mid_y)
                cv  = self._get(co_d,     t_idx, x_idx, mid_y)
                tv  = self._get(temp_d,   t_idx, x_idx, mid_y)
                rv  = self._get(radi_d,   t_idx, x_idx, mid_y)
                ov  = self._get(oxygen_d, t_idx, x_idx, mid_y)

                lines.append(
                    f"{t_val:7.1f}  {x_val:7.1f}  "
                    f"{sv:11.5E}  {cv2:11.5E}  {cv:11.5E}  "
                    f"{tv:11.5E}  {rv:11.5E}  {ov:11.5E}"
                )

        # Write with CRLF line endings (Windows format, as in original)
        output_file.write_bytes(("\r\n".join(lines) + "\r\n").encode('ascii', errors='replace'))
        self.logger.info(f"Wrote {len(lines)} lines to {output_file}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get(arr: Optional[np.ndarray], t_idx: int, x_idx: int, y_idx: int) -> float:
        """Safe array element access."""
        if arr is None:
            return 0.0
        try:
            if arr.ndim == 4:
                return float(arr[t_idx, x_idx, y_idx, 0])
            elif arr.ndim == 3:
                return float(arr[t_idx, x_idx, y_idx])
            elif arr.ndim == 2:
                return float(arr[t_idx, x_idx])
            return 0.0
        except (IndexError, ValueError, TypeError):
            return 0.0

    def _estimate_k_index(self, breathing_z: float) -> int:
        """Estimate the K (Z-cell) index for the breathing height slice."""
        # Try to get Z bounds from the full simulation mesh
        try:
            for mesh in self.sim.meshes:
                zcc = mesh.coordinates['z']  # cell-centre Z coordinates
                if zcc is not None and len(zcc) > 0:
                    z_min = float(zcc[0])
                    z_max = float(zcc[-1])
                    nz = len(zcc)
                    frac = (breathing_z - z_min) / (z_max - z_min) if z_max > z_min else 0
                    return max(0, round(frac * nz))
        except Exception:
            pass
        # Fallback: return 4 (most common for 1.8m breathing height in 6.77m tunnel)
        return 4


# ---------------------------------------------------------------------------
# Convenience wrapper (maintains backward-compatible signature)
# ---------------------------------------------------------------------------

def convert_fds_to_fdb(simulation_dir: str,
                       output_file: Optional[str] = None,
                       config: Optional[ConversionConfig] = None,
                       config_file: Optional[str] = None) -> str:
    """
    Convert FDS output directory to FDB format.

    Args:
        simulation_dir : Directory containing FDS output (.smv + slice files)
        output_file    : Destination .fdb path (auto-generated if None)
        config         : ConversionConfig instance (optional)
        config_file    : Legacy parameter – accepted but not used

    Returns:
        Absolute path to the generated .fdb file (str)
    """
    converter = FDSToFDBConverter(simulation_dir, config)
    out_path = converter.convert(Path(output_file) if output_file else None)
    return str(out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fds_to_fdb_converter.py <simulation_directory> [output.fdb]")
        sys.exit(1)

    result = convert_fds_to_fdb(
        simulation_dir=sys.argv[1],
        output_file=sys.argv[2] if len(sys.argv) > 2 else None,
    )
    print(f"Done: {result}")


# #!/usr/bin/env python3
# """
# FDS to FDB Converter - Version 3
# Converts FDS (Fire Dynamics Simulator) slice output files to FDB format.
# Output matches the exact FIRE ANALYSIS DB format used by the QRA system.

# Unit conversions applied:
#   SOOT  : kg/m³     (FDS raw, no conversion)
#   CO2   : %         (FDS volume fraction × 100)
#   CO    : PPM       (FDS volume fraction × 1,000,000)
#   TEMP  : °C        (FDS raw, no conversion)
#   RADI  : kW/m²     (FDS raw, no conversion)
#   OXYGEN: %         (FDS volume fraction × 100)
# """

# import logging
# import re
# import numpy as np
# from pathlib import Path
# from typing import Dict, List, Optional, Tuple
# import fdsreader as fds

# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )


# class ConversionConfig:
#     """Configuration for FDS to FDB conversion"""

#     def __init__(self):
#         # Breathing height (metres) – auto-detected from slices if None
#         self.breathing_height: Optional[float] = None

#         # Output time interval (seconds) – auto-detected from slice times if None
#         self.time_interval: Optional[float] = None

#         # Ambient conditions (auto-read from FDS file if not set)
#         self.ambient_temp: float = 20.0       # °C
#         self.ambient_radi: float = 0.0        # kW/m²  (will be estimated from data)

#         # Tunnel main axis ('X' or 'Y')
#         self.tunnel_axis: str = 'X'

#         # Fire location along tunnel axis (min, max) in metres
#         # Set to None to attempt auto-detection from FDS file
#         self.fire_pt_min: Optional[float] = None
#         self.fire_pt_max: Optional[float] = None

#         # Mesh number (for MESH header line)
#         self.mesh_number: int = 1


# class FDSToFDBConverter:
#     """Converter: FDS slice output → FIRE ANALYSIS DB (.fdb) format"""

#     # Map FDS quantity names → internal variable keys
#     QUANTITY_MAP = {
#         'TEMPERATURE':                    'TEMP',
#         'SOOT VISIBILITY':                'SOOT',
#         'SOOT DENSITY':                   'SOOT',
#         'CARBON MONOXIDE VOLUME FRACTION':'CO',
#         'CARBON DIOXIDE VOLUME FRACTION': 'CO2',
#         'OXYGEN VOLUME FRACTION':         'OXYGEN',
#         'RADIATION INTENSITY':            'RADI',
#         'RADIANT HEAT FLUX':              'RADI',
#         'RADIATIVE HEAT FLUX':            'RADI',
#         'RADIATION':                      'RADI',
#     }

#     # Unit conversion factors from FDS native → FDB units
#     UNIT_CONV = {
#         'SOOT':   1.0,          # kg/m³  → kg/m³
#         'CO2':    100.0,        # frac   → %
#         'CO':     1.0e6,        # frac   → PPM
#         'TEMP':   1.0,          # °C     → °C
#         'RADI':   1.0,          # kW/m²  → kW/m²
#         'OXYGEN': 100.0,        # frac   → %
#     }

#     def __init__(self, simulation_dir, config: Optional[ConversionConfig] = None):
#         if isinstance(simulation_dir, (str, Path)):
#             self.simulation_dir = Path(simulation_dir)
#         else:
#             self.simulation_dir = Path(str(simulation_dir))

#         self.config = config or ConversionConfig()
#         self.logger = logging.getLogger(__name__)
#         self.sim = None

#     # ------------------------------------------------------------------
#     # Public entry point
#     # ------------------------------------------------------------------

#     def convert(self, output_file: Optional[Path] = None) -> Path:
#         """Convert FDS output to FDB format. Returns path to written file."""
#         self.logger.info("Starting FDS → FDB conversion")
#         self.logger.info(f"Simulation directory: {self.simulation_dir}")

#         # Load simulation
#         self.sim = fds.Simulation(str(self.simulation_dir))
#         self.logger.info(f"Loaded: CHID={self.sim.chid}  FDS version={self.sim.fds_version}")
#         self.logger.info(f"Slices available: {len(self.sim.slices)}")

#         # Determine output path
#         if output_file is None:
#             base = (self.simulation_dir.parent
#                     if self.simulation_dir.is_file()
#                     else self.simulation_dir)
#             output_file = base / f"{self.sim.chid}.fdb"
#         output_file = Path(output_file)

#         # Find horizontal breathing-height slices
#         breathing_slices = self._find_breathing_height_slices()
#         if not breathing_slices:
#             raise ValueError("No slices found at breathing height. "
#                              "Check that your FDS file outputs horizontal slices.")

#         # Extract data arrays
#         data_dict, times, mesh_info = self._extract_data(breathing_slices)

#         # Parse FDS input file for extra metadata (fire location, ambient)
#         fds_meta = self._parse_fds_file()

#         # Write output
#         self._write_fdb(output_file, data_dict, times, mesh_info, fds_meta)

#         self.logger.info(f"Conversion complete: {output_file}")
#         return output_file

#     # ------------------------------------------------------------------
#     # Slice detection
#     # ------------------------------------------------------------------

#     def _find_breathing_height_slices(self) -> Dict[str, object]:
#         """Return mapping variable_key → slice object for breathing-height slices."""
#         # Collect all quasi-horizontal slices (Z nearly constant)
#         candidates: List[Tuple[float, object]] = []
#         for slc in self.sim.slices:
#             ext = slc.extent
#             dz = abs(ext.z_end - ext.z_start)
#             if dz < 0.1:                          # horizontal (constant-Z) slice
#                 z_val = (ext.z_start + ext.z_end) / 2.0
#                 if 1.4 <= z_val <= 2.2:           # plausible breathing height
#                     candidates.append((z_val, slc))

#         if not candidates:
#             self.logger.warning("No horizontal slices in 1.4–2.2 m range.")
#             self.logger.info("All slices:")
#             for slc in self.sim.slices:
#                 self.logger.info(f"  {slc.quantity.name}  extent={slc.extent}")
#             return {}

#         # Choose breathing height: override from config or pick most-populated Z
#         from collections import defaultdict
#         by_z: Dict[float, list] = defaultdict(list)
#         for z, slc in candidates:
#             by_z[round(z, 3)].append(slc)

#         if self.config.breathing_height is not None:
#             target_z = min(by_z.keys(),
#                            key=lambda z: abs(z - self.config.breathing_height))
#         else:
#             target_z = max(by_z.keys(), key=lambda z: len(by_z[z]))

#         self.logger.info(f"Breathing height selected: Z = {target_z:.3f} m "
#                          f"({len(by_z[target_z])} slices)")

#         result: Dict[str, object] = {}
#         for slc in by_z[target_z]:
#             key = self.QUANTITY_MAP.get(slc.quantity.name.upper())
#             if key and key not in result:
#                 result[key] = slc
#                 self.logger.info(f"  {slc.quantity.name!r}  →  {key}")

#         return result

#     # ------------------------------------------------------------------
#     # Data extraction
#     # ------------------------------------------------------------------

#     def _extract_data(self, breathing_slices: Dict[str, object]):
#         """Extract numpy arrays for all variables. Returns (data_dict, times, mesh_info)."""
#         data_dict: Dict[str, np.ndarray] = {}
#         times = None
#         mesh_info = None

#         for var_key, slc in breathing_slices.items():
#             self.logger.info(f"Loading {var_key} …")
#             try:
#                 raw = slc.to_global()          # shape: (n_times, nx, ny[, nz])
#                 conv = self.UNIT_CONV.get(var_key, 1.0)
#                 data_dict[var_key] = raw * conv

#                 if times is None:
#                     times = slc.times
#                     self.logger.info(f"  Time: {times[0]:.1f}–{times[-1]:.1f} s  "
#                                      f"({len(times)} steps)")

#                 if mesh_info is None:
#                     ext = slc.extent
#                     mesh_info = {
#                         'extent': ext,
#                         'breathing_z': (ext.z_start + ext.z_end) / 2.0,
#                     }
#                     self.logger.info(f"  Mesh: X=[{ext.x_start:.2f}, {ext.x_end:.2f}]  "
#                                      f"Y=[{ext.y_start:.2f}, {ext.y_end:.2f}]  "
#                                      f"Z={mesh_info['breathing_z']:.3f}")

#                 self.logger.info(f"  Shape={raw.shape}  "
#                                  f"range=[{raw.min():.4g}, {raw.max():.4g}]")
#             except Exception as exc:
#                 self.logger.error(f"  Failed to load {var_key}: {exc}")

#         if times is None or mesh_info is None:
#             raise ValueError("Could not extract any data from slices.")

#         return data_dict, times, mesh_info

#     # ------------------------------------------------------------------
#     # FDS file parsing for metadata
#     # ------------------------------------------------------------------

#     def _parse_fds_file(self) -> dict:
#         """Read the .fds input file and extract ambient conditions + fire location."""
#         meta = {
#             'ambient_temp': self.config.ambient_temp,
#             'fire_pt_min':  self.config.fire_pt_min,
#             'fire_pt_max':  self.config.fire_pt_max,
#         }

#         # Locate the .fds file
#         base = (self.simulation_dir.parent
#                 if self.simulation_dir.is_file()
#                 else self.simulation_dir)
#         fds_files = list(base.glob("*.fds")) + list(base.glob("*.FDS"))
#         if not fds_files:
#             self.logger.warning("No .fds input file found; using default ambient values.")
#             return meta

#         fds_text = fds_files[0].read_text(errors='ignore')

#         # Ambient temperature from &MISC TMPA=...
#         m = re.search(r'TMPA\s*=\s*([0-9.]+)', fds_text, re.IGNORECASE)
#         if m:
#             meta['ambient_temp'] = float(m.group(1))

#         # Fire location: look for VENT lines with SURF_ID containing 'BURNER' or 'FIRE'
#         if meta['fire_pt_min'] is None:
#             axis = self.config.tunnel_axis.upper()
#             idx = {'X': 0, 'Y': 2}.get(axis, 0)   # XB pair index for axis
#             fire_coords = []
#             for line in fds_text.splitlines():
#                 if re.search(r'SURF_ID\s*=\s*[\'"].*(?:BURNER|FIRE)', line, re.IGNORECASE):
#                     xb = re.search(r'XB\s*=\s*([0-9.,\s-]+)', line)
#                     if xb:
#                         nums = [float(x) for x in re.findall(r'-?[0-9]+\.?[0-9]*', xb.group(1))]
#                         if len(nums) >= idx + 2:
#                             fire_coords.extend([nums[idx], nums[idx + 1]])
#             if fire_coords:
#                 meta['fire_pt_min'] = min(fire_coords)
#                 meta['fire_pt_max'] = max(fire_coords)

#         return meta

#     # ------------------------------------------------------------------
#     # FDB writer – exact FIRE ANALYSIS DB format
#     # ------------------------------------------------------------------

#     def _write_fdb(self, output_file: Path, data_dict: Dict[str, np.ndarray],
#                    times: np.ndarray, mesh_info: dict, fds_meta: dict):
#         """Write the FDB file in the exact FIRE ANALYSIS DB format (CRLF line endings)."""

#         ext = mesh_info['extent']
#         breathing_z = mesh_info['breathing_z']

#         # Determine grid dimensions from first data array
#         first = next(iter(data_dict.values()))
#         if first.ndim == 4:        # (t, nx, ny, nz)
#             n_times, nx, ny, _ = first.shape
#         elif first.ndim == 3:      # (t, nx, ny)
#             n_times, nx, ny = first.shape
#         else:
#             raise ValueError(f"Unexpected data shape: {first.shape}")

#         # X coordinates along tunnel axis
#         x_coords = np.linspace(ext.x_start, ext.x_end, nx)

#         # Y: use middle slice for single-axis output
#         mid_y = ny // 2 if ny > 1 else 0

#         # ---- Time interval ----
#         if len(times) > 1:
#             dt = float(times[1] - times[0])
#         else:
#             dt = self.config.time_interval or 30.0

#         # ---- Ambient RADI: use median of RADI data at t=0 (background) ----
#         ambient_radi = self.config.ambient_radi
#         if 'RADI' in data_dict and ambient_radi == 0.0:
#             radi_t0 = data_dict['RADI'][0]
#             ambient_radi = float(np.median(radi_t0[radi_t0 > 0])) if np.any(radi_t0 > 0) else 0.0

#         # ---- Mesh indices (cell-based, 0-indexed) ----
#         # I corresponds to X, J to Y, K to Z
#         # The 020CFV0.FDB uses cell-face indices: I1=0, I2=nx_cells, etc.
#         nx_cells = nx - 1   # number of cells
#         ny_cells = ny - 1
#         # K index for breathing height
#         z_total = ext.z_end if hasattr(ext, 'z_end') else breathing_z
#         # Infer total mesh Z from FDS (not directly available from slice; use breathing_z/nk)
#         # Approximate K from proportion — this will be read from FDS mesh if available
#         k_idx = self._estimate_k_index(breathing_z)

#         # Fire location
#         fire_min = fds_meta.get('fire_pt_min')
#         fire_max = fds_meta.get('fire_pt_max')
#         if fire_min is not None:
#             fire_str = f"{fire_min:10.3f}-{fire_max:9.3f}"
#         else:
#             fire_str = "        N/A-       N/A"

#         # Simulation time (last time step)
#         sim_time = int(round(times[-1]))

#         self.logger.info(f"Writing FDB: {nx} X-points × {n_times} time steps …")

#         lines = []

#         # ---- Header block ----
#         lines.append("******************** FIRE ANALYSIS DB ********************")
#         lines.append(f"TUNNEL MAIN AXIS : {self.config.tunnel_axis}")
#         lines.append(f"TUNNEL HEIGHT AXIS : Z AT  {breathing_z:9.3f}")
#         lines.append(f"SIMULATION TIME :   {sim_time}")
#         lines.append(f"FDB TIME INTERVAL :  {dt:.1f}")
#         lines.append(f"MESH :  {self.config.mesh_number}")
#         lines.append(
#             f"I1 :       0   I2 :     {nx_cells}   "
#             f"J1 :       0   J2 :      {ny_cells}   "
#             f"K1 :  {k_idx:5d}   K2 :  {k_idx:5d}"
#         )
#         lines.append(
#             f"X1 : {ext.x_start:6.2f}   X2 : {ext.x_end:6.2f}   "
#             f"Y1 : {ext.y_start:6.2f}   Y2 : {ext.y_end:6.2f}   "
#             f"Z1 : {breathing_z:6.2f}   Z2 : {breathing_z:6.2f}"
#         )

#         # ---- TIME TABLE ----
#         lines.append("TIME TABLE")
#         lines.append(f"  {n_times}")
#         # Rows of 11: first column is row-index prefix (0, 10, 20, …)
#         for row_start in range(0, n_times, 11):
#             chunk = times[row_start: row_start + 11]
#             prefix = f"{row_start:4d}" if row_start > 0 else "   0"
#             time_str = "".join(f"  {t:6.1f}" for t in chunk)
#             lines.append(f"{prefix}{time_str}")

#         # ---- AMBIENT CONDITION ----
#         lines.append("AMBIENT CONDITION")
#         lines.append("         TEMPERATURE   RADIATE INTENSITY")
#         lines.append(f"         {fds_meta['ambient_temp']:12.3f}   {ambient_radi:14.3f}")

#         # ---- TUNNEL X COORDINATE ----
#         lines.append("TUNNEL X COORDINATE")
#         lines.append(
#             f"{'':>15}MIN_X{'':>15}MAX_X{'':>13}NX GRID{'':>13}FIRE PT"
#         )
#         lines.append(
#             f"{'':>15}{ext.x_start:.3f}{'':>13}{ext.x_end:.3f}"
#             f"{'':>16}{nx:d}        {fire_str}"
#         )

#         # ---- Column headers ----
#         lines.append("*" * 90)
#         lines.append(
#             "  TIME    X-COOR      SOOT        CO2         CO         "
#             "TEMP        RADI       OXYGEN"
#         )
#         lines.append(
#             "  [SEC]    [M]      [KG/M^3]      [%]        [PPM]       "
#             "[DEG.]     [KW/M^2]      [%]"
#         )
#         lines.append(
#             "*" * 7 + "|" + "*" * 9 + "|" + ("|" + "*" * 11) * 6 + "|"
#         )
#         lines.append("DATA START")

#         # ---- Data rows ----
#         soot_d   = data_dict.get('SOOT')
#         co2_d    = data_dict.get('CO2')
#         co_d     = data_dict.get('CO')
#         temp_d   = data_dict.get('TEMP')
#         radi_d   = data_dict.get('RADI')
#         oxygen_d = data_dict.get('OXYGEN')

#         for t_idx, t_val in enumerate(times):
#             for x_idx, x_val in enumerate(x_coords):
#                 sv  = self._get(soot_d,   t_idx, x_idx, mid_y)
#                 cv2 = self._get(co2_d,    t_idx, x_idx, mid_y)
#                 cv  = self._get(co_d,     t_idx, x_idx, mid_y)
#                 tv  = self._get(temp_d,   t_idx, x_idx, mid_y)
#                 rv  = self._get(radi_d,   t_idx, x_idx, mid_y)
#                 ov  = self._get(oxygen_d, t_idx, x_idx, mid_y)

#                 lines.append(
#                     f"{t_val:7.1f}  {x_val:7.1f}  "
#                     f"{sv:11.5E}  {cv2:11.5E}  {cv:11.5E}  "
#                     f"{tv:11.5E}  {rv:11.5E}  {ov:11.5E}"
#                 )

#         # Write with CRLF line endings (Windows format, as in original)
#         output_file.write_bytes(("\r\n".join(lines) + "\r\n").encode('ascii', errors='replace'))
#         self.logger.info(f"Wrote {len(lines)} lines to {output_file}")

#     # ------------------------------------------------------------------
#     # Helpers
#     # ------------------------------------------------------------------

#     @staticmethod
#     def _get(arr: Optional[np.ndarray], t_idx: int, x_idx: int, y_idx: int) -> float:
#         """Safe array element access."""
#         if arr is None:
#             return 0.0
#         try:
#             if arr.ndim == 4:
#                 return float(arr[t_idx, x_idx, y_idx, 0])
#             elif arr.ndim == 3:
#                 return float(arr[t_idx, x_idx, y_idx])
#             elif arr.ndim == 2:
#                 return float(arr[t_idx, x_idx])
#             return 0.0
#         except (IndexError, ValueError, TypeError):
#             return 0.0

#     def _estimate_k_index(self, breathing_z: float) -> int:
#         """Estimate the K (Z-cell) index for the breathing height slice."""
#         # Try to get Z bounds from the full simulation mesh
#         try:
#             for mesh in self.sim.meshes:
#                 zcc = mesh.coordinates['z']  # cell-centre Z coordinates
#                 if zcc is not None and len(zcc) > 0:
#                     z_min = float(zcc[0])
#                     z_max = float(zcc[-1])
#                     nz = len(zcc)
#                     frac = (breathing_z - z_min) / (z_max - z_min) if z_max > z_min else 0
#                     return max(0, round(frac * nz))
#         except Exception:
#             pass
#         # Fallback: return 4 (most common for 1.8m breathing height in 6.77m tunnel)
#         return 4


# # ---------------------------------------------------------------------------
# # Convenience wrapper (maintains backward-compatible signature)
# # ---------------------------------------------------------------------------

# def convert_fds_to_fdb(simulation_dir: str,
#                        output_file: Optional[str] = None,
#                        config: Optional[ConversionConfig] = None,
#                        config_file: Optional[str] = None) -> str:
#     """
#     Convert FDS output directory to FDB format.

#     Args:
#         simulation_dir : Directory containing FDS output (.smv + slice files)
#         output_file    : Destination .fdb path (auto-generated if None)
#         config         : ConversionConfig instance (optional)
#         config_file    : Legacy parameter – accepted but not used

#     Returns:
#         Absolute path to the generated .fdb file (str)
#     """
#     converter = FDSToFDBConverter(simulation_dir, config)
#     out_path = converter.convert(Path(output_file) if output_file else None)
#     return str(out_path)


# # ---------------------------------------------------------------------------
# # CLI
# # ---------------------------------------------------------------------------

# if __name__ == "__main__":
#     import sys

#     if len(sys.argv) < 2:
#         print("Usage: python fds_to_fdb_converter.py <simulation_directory> [output.fdb]")
#         sys.exit(1)

#     result = convert_fds_to_fdb(
#         simulation_dir=sys.argv[1],
#         output_file=sys.argv[2] if len(sys.argv) > 2 else None,
#     )
#     print(f"Done: {result}")
