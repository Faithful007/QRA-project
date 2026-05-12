"""
FDS Execution Wrapper - Performance Optimised
=============================================
Manages FDS simulation execution with:
  - Real-time progress monitoring from the .out file
  - Accurate wall-clock vs simulation-time reporting
  - Adaptive timeout based on actual T_END (not hardcoded)
  - Live ETA calculation
"""

import os
import re
import shutil
import subprocess
import time
import threading
from pathlib import Path
from typing import Optional, List, Callable
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Progress monitor – reads FDS .out file while simulation runs
# ---------------------------------------------------------------------------

class FDSProgressMonitor:
    """
    Monitors a running FDS simulation by tailing its .out file.

    Reports:
      - Simulated time elapsed (s)
      - Wall-clock time elapsed (s)
      - Real-time ratio (sim-time / wall-time)  –  >1 means faster than real-time
      - Estimated time to completion
    """

    # Pattern for FDS6 progress lines:
    # "  Step:    12345   T:    30.12  Dt: 0.0450  Wall: 0:00:15"
    # Pattern for FDS5:
    # "Time Step    12345,   Simulation Time =     30.12 s"
    _RE_FDS6 = re.compile(r'T:\s*([0-9.Ee+\-]+)', re.IGNORECASE)
    _RE_FDS5 = re.compile(r'Simulation\s+Time\s*=\s*([0-9.Ee+\-]+)', re.IGNORECASE)
    _RE_TFINISH = re.compile(r'(?:TWFIN|T_END)\s*=\s*([0-9.Ee+\-]+)', re.IGNORECASE)
    _RE_COMPLETE = re.compile(r'STOP:\s*FDS\s+completed\s+successfully', re.IGNORECASE)

    def __init__(self, out_file: Path, t_end: float,
                 callback: Optional[Callable[[dict], None]] = None,
                 poll_interval: float = 5.0):
        """
        Parameters
        ----------
        out_file      : Path to <CHID>.out (may not exist yet at construction time)
        t_end         : Simulation end time in seconds (from &TIME T_END)
        callback      : Optional function called with progress dict on each update
        poll_interval : How often to poll the .out file (seconds)
        """
        self.out_file      = Path(out_file)
        self.t_end         = t_end
        self.callback      = callback
        self.poll_interval = poll_interval

        self._stop_event   = threading.Event()
        self._thread       = None
        self.start_wall    = None
        self.last_status   = {}

    def start(self):
        """Start monitoring in a background thread."""
        self.start_wall = time.time()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop monitoring."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            status = self._read_status()
            self.last_status = status
            if self.callback:
                try:
                    self.callback(status)
                except Exception:
                    pass
            if status.get('completed'):
                break
            self._stop_event.wait(self.poll_interval)

    def _read_status(self) -> dict:
        wall_elapsed = time.time() - self.start_wall
        status = {
            'wall_elapsed_s':  wall_elapsed,
            'sim_time_s':      0.0,
            'progress_pct':    0.0,
            'real_time_ratio': 0.0,   # >1 = faster than real-time
            'eta_s':           None,
            'completed':       False,
        }

        if not self.out_file.exists():
            return status

        try:
            # Read only the last 200 lines (efficient for large .out files)
            with open(self.out_file, 'r', errors='replace') as f:
                lines = f.readlines()

            # Check for completion
            for line in lines[-30:]:
                if self._RE_COMPLETE.search(line):
                    status['sim_time_s']      = self.t_end
                    status['progress_pct']    = 100.0
                    status['completed']       = True
                    status['real_time_ratio'] = (
                        self.t_end / wall_elapsed if wall_elapsed > 0 else 0
                    )
                    return status

            # Find latest simulation time
            sim_t = None
            for line in reversed(lines):
                m = self._RE_FDS6.search(line)
                if not m:
                    m = self._RE_FDS5.search(line)
                if m:
                    try:
                        sim_t = float(m.group(1))
                        break
                    except ValueError:
                        continue

            if sim_t is not None and self.t_end > 0:
                status['sim_time_s']   = sim_t
                status['progress_pct'] = min(100.0, (sim_t / self.t_end) * 100.0)

                if wall_elapsed > 1.0 and sim_t > 0:
                    # Real-time ratio: how many simulated seconds per wall second
                    ratio = sim_t / wall_elapsed
                    status['real_time_ratio'] = ratio

                    # ETA
                    remaining_sim = self.t_end - sim_t
                    if ratio > 0:
                        status['eta_s'] = remaining_sim / ratio

        except (IOError, OSError):
            pass

        return status

    def format_status(self, status: Optional[dict] = None) -> str:
        """Return a human-readable one-line status string."""
        s = status or self.last_status
        if not s:
            return "Waiting for simulation to start..."

        wall = s.get('wall_elapsed_s', 0)
        sim  = s.get('sim_time_s', 0)
        pct  = s.get('progress_pct', 0)
        ratio = s.get('real_time_ratio', 0)
        eta  = s.get('eta_s')

        wall_fmt = _fmt_time(wall)
        sim_fmt  = _fmt_time(sim)

        if s.get('completed'):
            return (f"✓ COMPLETE  sim={sim_fmt}  wall={wall_fmt}  "
                    f"ratio={ratio:.2f}×")

        ratio_flag = "🐢 SLOWER" if ratio < 1.0 else "⚡ FASTER"
        eta_str = f"  ETA: {_fmt_time(eta)}" if eta else ""
        return (
            f"{pct:5.1f}%  sim={sim_fmt}/{_fmt_time(self.t_end)}"
            f"  wall={wall_fmt}  {ratio:.2f}× real-time {ratio_flag}{eta_str}"
        )


def _fmt_time(seconds) -> str:
    if seconds is None:
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{sec:02d}s"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


# ---------------------------------------------------------------------------
# FDS Runner
# ---------------------------------------------------------------------------

class FDSRunner:
    """Wrapper for running FDS simulations with real-time progress monitoring."""

    def __init__(self, fds_executable: str = "fds"):
        self.fds_executable  = fds_executable
        self.running_processes: List[subprocess.Popen] = []

    def check_fds_available(self) -> bool:
        try:
            subprocess.run([self.fds_executable], capture_output=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def run_simulation(
        self,
        input_file: str,
        working_dir: Optional[str] = None,
        log_output: bool = True,
        log_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> subprocess.CompletedProcess:
        """
        Run a single FDS simulation with live progress monitoring.

        Parameters
        ----------
        input_file        : Path to .fds input file
        working_dir       : Working directory (default: same as input_file)
        log_output        : Save stdout to a .log file
        log_dir           : Directory for log files
        progress_callback : Called every ~5 s with a progress dict:
                              {wall_elapsed_s, sim_time_s, progress_pct,
                               real_time_ratio, eta_s, completed}
        """
        input_path = Path(input_file).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"FDS input file not found: {input_file}")

        if working_dir is None:
            wd = input_path.parent
        else:
            wd = Path(working_dir).resolve()
        wd.mkdir(parents=True, exist_ok=True)

        # Read T_END from the file for accurate timeout and monitoring
        t_end = _read_t_end(input_path)

        # Log file setup
        log_file = None
        log_folder = Path(log_dir) if log_dir else Path(working_dir)
        log_folder.mkdir(parents=True, exist_ok=True)
        log_file = log_folder / f"{input_path.stem}_fds.log"

        # FDS .out file (written by FDS itself)
        out_file = Path(working_dir) / f"{input_path.stem}.out"

        # Adaptive timeout: 3× theoretical minimum runtime at 1× real-time
        # Absolute minimum 600 s, maximum 43200 s (12 h)
        timeout = max(600.0, min(43200.0, t_end * 3.0))


        cmd = [self.fds_executable, input_path.name]

        print(f"\n{'='*60}")
        print(f"  FDS Simulation: {input_path.name}")
        print(f"  Working dir   : {wd}")
        print(f"  T_END         : {t_end:.0f} s  ({t_end/60:.1f} min real-event time)")
        print(f"  Timeout       : {timeout:.0f} s  ({timeout/3600:.1f} h)")
        print(f"{'='*60}")

        # Set up progress monitor
        monitor = FDSProgressMonitor(
            out_file  = out_file,
            t_end     = t_end,
            callback  = progress_callback,
            poll_interval = 5.0,
        )

        # Stdout relay callback for console
        _last_print = [time.time()]

        def _console_cb(status: dict):
            now = time.time()
            if now - _last_print[0] >= 30.0 or status.get('completed'):
                print(f"  {monitor.format_status(status)}")
                _last_print[0] = now

        if progress_callback is None:
            monitor.callback = _console_cb

        start_wall = time.time()

        try:
            with open(log_file, 'w') as lh:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(wd),
                    stdout=lh,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                self.running_processes.append(proc)
                monitor.start()

                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        proc.kill()

                monitor.stop()
                self.running_processes.remove(proc)

        except Exception as e:
            monitor.stop()
            print(f"Error running FDS: {e}")
            raise

        wall_elapsed = time.time() - start_wall
        final_status = monitor.last_status or {}
        ratio = final_status.get('real_time_ratio', 0)

        # Check for FDS completion in the working directory
        if proc.returncode == 0 or _check_completed(wd / f"{input_path.stem}.out"):
            print(f"\n  ✓ Simulation completed in {_fmt_time(wall_elapsed)}")
            print(f"    Real-time ratio: {ratio:.2f}×  "
                  f"({'faster' if ratio >= 1 else 'slower'} than real-time)")
        else:
            print(f"\n  ✗ Simulation failed (return code {proc.returncode})")
            print(f"    Check log: {log_file}")

        # Build a CompletedProcess-compatible return for backward compatibility
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode if not _check_completed(out_file) else 0,
        )

    def run_batch(
        self,
        input_files: List[str],
        working_dir: Optional[str] = None,
        max_parallel: int = 1,
    ) -> List[subprocess.CompletedProcess]:
        """Run multiple FDS simulations sequentially (parallel not yet stable)."""
        results = []
        for i, f in enumerate(input_files):
            print(f"\n[{i+1}/{len(input_files)}] {Path(f).name}")
            results.append(self.run_simulation(f, working_dir))

        successful = sum(1 for r in results if r.returncode == 0)
        print(f"\n{'='*60}")
        print(f"Batch complete: {successful}/{len(results)} succeeded")
        print(f"{'='*60}")
        return results

    def monitor_simulation(self, working_dir: str, chid: str) -> dict:
        """
        Query the current status of a running simulation.
        Returns a status dict compatible with the original interface.
        """
        out_file = Path(working_dir) / f"{chid}.out"
        if not out_file.exists():
            return {"status": "not_started", "progress": 0}

        # Try to guess t_end from any .fds file in the directory
        fds_files = list(Path(working_dir).glob(f"{chid}.fds"))
        t_end = 900.0
        if fds_files:
            t_end = _read_t_end(fds_files[0])

        monitor = FDSProgressMonitor(out_file, t_end)
        status  = monitor._read_status()

        if status['completed']:
            return {"status": "completed", "progress": 100}

        return {
            "status":       "running",
            "progress":     status['progress_pct'],
            "current_time": status['sim_time_s'],
            "wall_elapsed": status['wall_elapsed_s'],
            "ratio":        status['real_time_ratio'],
            "eta_s":        status['eta_s'],
        }

    def get_output_files(self, working_dir: str, chid: str) -> dict:
        """Get list of output files generated by FDS."""
        wp = Path(working_dir)
        return {k: v for k, v in {
            'smv':     wp / f"{chid}.smv",
            'out':     wp / f"{chid}.out",
            'slices':  list(wp.glob(f"{chid}_*.sf")),
            'devices': list(wp.glob(f"{chid}_devc.csv")),
            'hrr':     wp / f"{chid}_hrr.csv",
        }.items() if (
            (isinstance(v, list) and v) or
            (isinstance(v, Path) and v.exists())
        )}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_t_end(fds_path: Path) -> float:
    """Extract T_END / TWFIN from an FDS input file."""
    try:
        text = fds_path.read_text(errors='replace')
        m = re.search(r'(?:T_END|TWFIN)\s*=\s*([0-9.Ee+\-]+)', text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return 900.0


def _check_completed(out_file: Path) -> bool:
    """Return True if the .out file contains a successful completion line."""
    if not out_file.exists():
        return False
    try:
        with open(out_file, 'r', errors='replace') as f:
            # Only scan the tail for efficiency
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 4096))
            tail = f.read()
        return bool(re.search(r'STOP:\s*FDS\s+completed\s+successfully', tail, re.IGNORECASE))
    except Exception:
        return False


def create_batch_script(input_files: List[str], output_script: str = "run_fds_batch.bat"):
    """Create a Windows batch script to run multiple FDS simulations."""
    with open(output_script, 'w') as f:
        f.write("@echo off\nREM FDS Batch Execution Script\n\n")
        for i, fp in enumerate(input_files):
            p = Path(fp)
            f.write(f'echo [{i+1}/{len(input_files)}] Running {p.name}...\n')
            f.write(f'cd /d "{p.parent}"\n')
            f.write(f'fds {p.name}\n')
            f.write('if errorlevel 1 (echo ERROR) else (echo SUCCESS)\n\n')
        f.write("echo All simulations complete!\npause\n")
    print(f"Batch script written: {output_script}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python fds_runner.py <fds_file>")
        sys.exit(1)
    runner = FDSRunner()
    runner.run_simulation(sys.argv[1])


# """
# FDS Execution Wrapper - Performance Optimised
# =============================================
# Manages FDS simulation execution with:
#   - Real-time progress monitoring from the .out file
#   - Accurate wall-clock vs simulation-time reporting
#   - Adaptive timeout based on actual T_END (not hardcoded)
#   - Live ETA calculation
# """

# import os
# import re
# import subprocess
# import time
# import threading
# from pathlib import Path
# from typing import Optional, List, Callable
# import logging

# logger = logging.getLogger(__name__)


# # ---------------------------------------------------------------------------
# # Progress monitor – reads FDS .out file while simulation runs
# # ---------------------------------------------------------------------------

# class FDSProgressMonitor:
#     """
#     Monitors a running FDS simulation by tailing its .out file.

#     Reports:
#       - Simulated time elapsed (s)
#       - Wall-clock time elapsed (s)
#       - Real-time ratio (sim-time / wall-time)  –  >1 means faster than real-time
#       - Estimated time to completion
#     """

#     # Pattern for FDS6 progress lines:
#     # "  Step:    12345   T:    30.12  Dt: 0.0450  Wall: 0:00:15"
#     # Pattern for FDS5:
#     # "Time Step    12345,   Simulation Time =     30.12 s"
#     _RE_FDS6 = re.compile(r'T:\s*([0-9.Ee+\-]+)', re.IGNORECASE)
#     _RE_FDS5 = re.compile(r'Simulation\s+Time\s*=\s*([0-9.Ee+\-]+)', re.IGNORECASE)
#     _RE_TFINISH = re.compile(r'(?:TWFIN|T_END)\s*=\s*([0-9.Ee+\-]+)', re.IGNORECASE)
#     _RE_COMPLETE = re.compile(r'STOP:\s*FDS\s+completed\s+successfully', re.IGNORECASE)

#     def __init__(self, out_file: Path, t_end: float,
#                  callback: Optional[Callable[[dict], None]] = None,
#                  poll_interval: float = 5.0):
#         """
#         Parameters
#         ----------
#         out_file      : Path to <CHID>.out (may not exist yet at construction time)
#         t_end         : Simulation end time in seconds (from &TIME T_END)
#         callback      : Optional function called with progress dict on each update
#         poll_interval : How often to poll the .out file (seconds)
#         """
#         self.out_file      = Path(out_file)
#         self.t_end         = t_end
#         self.callback      = callback
#         self.poll_interval = poll_interval

#         self._stop_event   = threading.Event()
#         self._thread       = None
#         self.start_wall    = None
#         self.last_status   = {}

#     def start(self):
#         """Start monitoring in a background thread."""
#         self.start_wall = time.time()
#         self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
#         self._thread.start()

#     def stop(self):
#         """Stop monitoring."""
#         self._stop_event.set()
#         if self._thread:
#             self._thread.join(timeout=10)

#     def _monitor_loop(self):
#         while not self._stop_event.is_set():
#             status = self._read_status()
#             self.last_status = status
#             if self.callback:
#                 try:
#                     self.callback(status)
#                 except Exception:
#                     pass
#             if status.get('completed'):
#                 break
#             self._stop_event.wait(self.poll_interval)

#     def _read_status(self) -> dict:
#         wall_elapsed = time.time() - self.start_wall
#         status = {
#             'wall_elapsed_s':  wall_elapsed,
#             'sim_time_s':      0.0,
#             'progress_pct':    0.0,
#             'real_time_ratio': 0.0,   # >1 = faster than real-time
#             'eta_s':           None,
#             'completed':       False,
#         }

#         if not self.out_file.exists():
#             return status

#         try:
#             # Read only the last 200 lines (efficient for large .out files)
#             with open(self.out_file, 'r', errors='replace') as f:
#                 lines = f.readlines()

#             # Check for completion
#             for line in lines[-30:]:
#                 if self._RE_COMPLETE.search(line):
#                     status['sim_time_s']      = self.t_end
#                     status['progress_pct']    = 100.0
#                     status['completed']       = True
#                     status['real_time_ratio'] = (
#                         self.t_end / wall_elapsed if wall_elapsed > 0 else 0
#                     )
#                     return status

#             # Find latest simulation time
#             sim_t = None
#             for line in reversed(lines):
#                 m = self._RE_FDS6.search(line)
#                 if not m:
#                     m = self._RE_FDS5.search(line)
#                 if m:
#                     try:
#                         sim_t = float(m.group(1))
#                         break
#                     except ValueError:
#                         continue

#             if sim_t is not None and self.t_end > 0:
#                 status['sim_time_s']   = sim_t
#                 status['progress_pct'] = min(100.0, (sim_t / self.t_end) * 100.0)

#                 if wall_elapsed > 1.0 and sim_t > 0:
#                     # Real-time ratio: how many simulated seconds per wall second
#                     ratio = sim_t / wall_elapsed
#                     status['real_time_ratio'] = ratio

#                     # ETA
#                     remaining_sim = self.t_end - sim_t
#                     if ratio > 0:
#                         status['eta_s'] = remaining_sim / ratio

#         except (IOError, OSError):
#             pass

#         return status

#     def format_status(self, status: Optional[dict] = None) -> str:
#         """Return a human-readable one-line status string."""
#         s = status or self.last_status
#         if not s:
#             return "Waiting for simulation to start..."

#         wall = s.get('wall_elapsed_s', 0)
#         sim  = s.get('sim_time_s', 0)
#         pct  = s.get('progress_pct', 0)
#         ratio = s.get('real_time_ratio', 0)
#         eta  = s.get('eta_s')

#         wall_fmt = _fmt_time(wall)
#         sim_fmt  = _fmt_time(sim)

#         if s.get('completed'):
#             return (f"✓ COMPLETE  sim={sim_fmt}  wall={wall_fmt}  "
#                     f"ratio={ratio:.2f}×")

#         ratio_flag = "🐢 SLOWER" if ratio < 1.0 else "⚡ FASTER"
#         eta_str = f"  ETA: {_fmt_time(eta)}" if eta else ""
#         return (
#             f"{pct:5.1f}%  sim={sim_fmt}/{_fmt_time(self.t_end)}"
#             f"  wall={wall_fmt}  {ratio:.2f}× real-time {ratio_flag}{eta_str}"
#         )


# def _fmt_time(seconds) -> str:
#     if seconds is None:
#         return "?"
#     s = int(seconds)
#     h, rem = divmod(s, 3600)
#     m, sec = divmod(rem, 60)
#     if h:
#         return f"{h}h{m:02d}m{sec:02d}s"
#     if m:
#         return f"{m}m{sec:02d}s"
#     return f"{sec}s"


# # ---------------------------------------------------------------------------
# # FDS Runner
# # ---------------------------------------------------------------------------

# class FDSRunner:
#     """Wrapper for running FDS simulations with real-time progress monitoring."""

#     def __init__(self, fds_executable: str = "fds"):
#         self.fds_executable  = fds_executable
#         self.running_processes: List[subprocess.Popen] = []

#     def check_fds_available(self) -> bool:
#         try:
#             subprocess.run([self.fds_executable], capture_output=True, timeout=5)
#             return True
#         except (subprocess.TimeoutExpired, FileNotFoundError):
#             return False

#     def run_simulation(
#         self,
#         input_file: str,
#         working_dir: Optional[str] = None,
#         log_output: bool = True,
#         log_dir: Optional[str] = None,
#         progress_callback: Optional[Callable[[dict], None]] = None,
#     ) -> subprocess.CompletedProcess:
#         """
#         Run a single FDS simulation with live progress monitoring.

#         Parameters
#         ----------
#         input_file        : Path to .fds input file
#         working_dir       : Working directory (default: same as input_file)
#         log_output        : Save stdout to a .log file
#         log_dir           : Directory for log files
#         progress_callback : Called every ~5 s with a progress dict:
#                               {wall_elapsed_s, sim_time_s, progress_pct,
#                                real_time_ratio, eta_s, completed}
#         """
#         input_path = Path(input_file).resolve()
#         if not input_path.exists():
#             raise FileNotFoundError(f"FDS input file not found: {input_file}")

#         if working_dir is None:
#             wd = input_path.parent
#         else:
#             wd = Path(working_dir).resolve()
#         wd.mkdir(parents=True, exist_ok=True)

#         # Read T_END from the file for accurate timeout and monitoring
#         t_end = _read_t_end(input_path)

#         # Log file setup
#         log_file = None
#         log_folder = Path(log_dir) if log_dir else wd
#         log_folder.mkdir(parents=True, exist_ok=True)
#         log_file = log_folder / f"{input_path.stem}_fds.log"

#         # FDS .out file (written by FDS itself)
#         out_file = wd / f"{input_path.stem}.out"

#         # Adaptive timeout: 3× theoretical minimum runtime at 1× real-time
#         # Absolute minimum 600 s, maximum 43200 s (12 h)
#         timeout = max(600.0, min(43200.0, t_end * 3.0))

#         cmd = [self.fds_executable, input_path.name]

#         print(f"\n{'='*60}")
#         print(f"  FDS Simulation: {input_path.name}")
#         print(f"  Working dir   : {wd}")
#         print(f"  T_END         : {t_end:.0f} s  ({t_end/60:.1f} min real-event time)")
#         print(f"  Timeout       : {timeout:.0f} s  ({timeout/3600:.1f} h)")
#         print(f"{'='*60}")

#         # Set up progress monitor
#         monitor = FDSProgressMonitor(
#             out_file  = out_file,
#             t_end     = t_end,
#             callback  = progress_callback,
#             poll_interval = 5.0,
#         )

#         # Stdout relay callback for console
#         _last_print = [time.time()]

#         def _console_cb(status: dict):
#             now = time.time()
#             if now - _last_print[0] >= 30.0 or status.get('completed'):
#                 print(f"  {monitor.format_status(status)}")
#                 _last_print[0] = now

#         if progress_callback is None:
#             monitor.callback = _console_cb

#         start_wall = time.time()

#         try:
#             with open(log_file, 'w') as lh:
#                 proc = subprocess.Popen(
#                     cmd,
#                     cwd=str(wd),
#                     stdout=lh,
#                     stderr=subprocess.STDOUT,
#                     text=True,
#                 )
#                 self.running_processes.append(proc)
#                 monitor.start()

#                 try:
#                     proc.wait(timeout=timeout)
#                 except subprocess.TimeoutExpired:
#                     proc.terminate()
#                     try:
#                         proc.wait(timeout=30)
#                     except subprocess.TimeoutExpired:
#                         proc.kill()

#                 monitor.stop()
#                 self.running_processes.remove(proc)

#         except Exception as e:
#             monitor.stop()
#             print(f"Error running FDS: {e}")
#             raise

#         wall_elapsed = time.time() - start_wall
#         final_status = monitor.last_status or {}
#         ratio = final_status.get('real_time_ratio', 0)

#         if proc.returncode == 0 or _check_completed(out_file):
#             print(f"\n  ✓ Simulation completed in {_fmt_time(wall_elapsed)}")
#             print(f"    Real-time ratio: {ratio:.2f}×  "
#                   f"({'faster' if ratio >= 1 else 'slower'} than real-time)")
#         else:
#             print(f"\n  ✗ Simulation failed (return code {proc.returncode})")
#             print(f"    Check log: {log_file}")

#         # Build a CompletedProcess-compatible return for backward compatibility
#         return subprocess.CompletedProcess(
#             args=cmd,
#             returncode=proc.returncode if not _check_completed(out_file) else 0,
#         )

#     def run_batch(
#         self,
#         input_files: List[str],
#         working_dir: Optional[str] = None,
#         max_parallel: int = 1,
#     ) -> List[subprocess.CompletedProcess]:
#         """Run multiple FDS simulations sequentially (parallel not yet stable)."""
#         results = []
#         for i, f in enumerate(input_files):
#             print(f"\n[{i+1}/{len(input_files)}] {Path(f).name}")
#             results.append(self.run_simulation(f, working_dir))

#         successful = sum(1 for r in results if r.returncode == 0)
#         print(f"\n{'='*60}")
#         print(f"Batch complete: {successful}/{len(results)} succeeded")
#         print(f"{'='*60}")
#         return results

#     def monitor_simulation(self, working_dir: str, chid: str) -> dict:
#         """
#         Query the current status of a running simulation.
#         Returns a status dict compatible with the original interface.
#         """
#         out_file = Path(working_dir) / f"{chid}.out"
#         if not out_file.exists():
#             return {"status": "not_started", "progress": 0}

#         # Try to guess t_end from any .fds file in the directory
#         fds_files = list(Path(working_dir).glob(f"{chid}.fds"))
#         t_end = 900.0
#         if fds_files:
#             t_end = _read_t_end(fds_files[0])

#         monitor = FDSProgressMonitor(out_file, t_end)
#         status  = monitor._read_status()

#         if status['completed']:
#             return {"status": "completed", "progress": 100}

#         return {
#             "status":       "running",
#             "progress":     status['progress_pct'],
#             "current_time": status['sim_time_s'],
#             "wall_elapsed": status['wall_elapsed_s'],
#             "ratio":        status['real_time_ratio'],
#             "eta_s":        status['eta_s'],
#         }

#     def get_output_files(self, working_dir: str, chid: str) -> dict:
#         """Get list of output files generated by FDS."""
#         wp = Path(working_dir)
#         return {k: v for k, v in {
#             'smv':     wp / f"{chid}.smv",
#             'out':     wp / f"{chid}.out",
#             'slices':  list(wp.glob(f"{chid}_*.sf")),
#             'devices': list(wp.glob(f"{chid}_devc.csv")),
#             'hrr':     wp / f"{chid}_hrr.csv",
#         }.items() if (
#             (isinstance(v, list) and v) or
#             (isinstance(v, Path) and v.exists())
#         )}


# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------

# def _read_t_end(fds_path: Path) -> float:
#     """Extract T_END / TWFIN from an FDS input file."""
#     try:
#         text = fds_path.read_text(errors='replace')
#         m = re.search(r'(?:T_END|TWFIN)\s*=\s*([0-9.Ee+\-]+)', text, re.IGNORECASE)
#         if m:
#             return float(m.group(1))
#     except Exception:
#         pass
#     return 900.0


# def _check_completed(out_file: Path) -> bool:
#     """Return True if the .out file contains a successful completion line."""
#     if not out_file.exists():
#         return False
#     try:
#         with open(out_file, 'r', errors='replace') as f:
#             # Only scan the tail for efficiency
#             f.seek(0, 2)
#             size = f.tell()
#             f.seek(max(0, size - 4096))
#             tail = f.read()
#         return bool(re.search(r'STOP:\s*FDS\s+completed\s+successfully', tail, re.IGNORECASE))
#     except Exception:
#         return False


# def create_batch_script(input_files: List[str], output_script: str = "run_fds_batch.bat"):
#     """Create a Windows batch script to run multiple FDS simulations."""
#     with open(output_script, 'w') as f:
#         f.write("@echo off\nREM FDS Batch Execution Script\n\n")
#         for i, fp in enumerate(input_files):
#             p = Path(fp)
#             f.write(f'echo [{i+1}/{len(input_files)}] Running {p.name}...\n')
#             f.write(f'cd /d "{p.parent}"\n')
#             f.write(f'fds {p.name}\n')
#             f.write('if errorlevel 1 (echo ERROR) else (echo SUCCESS)\n\n')
#         f.write("echo All simulations complete!\npause\n")
#     print(f"Batch script written: {output_script}")


# # ---------------------------------------------------------------------------
# # CLI
# # ---------------------------------------------------------------------------

# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) < 2:
#         print("Usage: python fds_runner.py <fds_file>")
#         sys.exit(1)
#     runner = FDSRunner()
#     runner.run_simulation(sys.argv[1])