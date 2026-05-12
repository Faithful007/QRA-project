"""
Quantitative Risk Assessment System - Version 2.0
Complete tunnel fire risk assessment workflow with 7-tab interface
"""

import os
import sys
import subprocess
import shutil
import warnings
from pathlib import Path
from dataclasses import dataclass

# Suppress known harmless matplotlib warnings
warnings.filterwarnings("ignore", message=".*tight_layout.*")
warnings.filterwarnings("ignore", message=".*Glyph.*missing from font.*")

# Add paths for module imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "qra_app"))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QFileDialog,
    QTextEdit, QGroupBox, QMessageBox, QProgressBar, QTreeWidget,
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QListWidget, QListWidgetItem,
    QGridLayout, QScrollArea, QFrame, QRadioButton, QButtonGroup,
    QSlider, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

# Import modules
import sys
import os
from pathlib import Path

# Ensure database module is importable
app_dir = Path(__file__).parent.absolute()
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

# Import QRADatabase from qra_database.py (root level module)
try:
    from qra_database import QRADatabase
except ImportError:
    QRADatabase = None

try:
    # Try importing from the package first
    try:
        from fds_workflow import FDSWorkflow
    except ImportError:
        # Fallback to local import if not in a package
        try:
            import fds_workflow
            FDSWorkflow = getattr(fds_workflow, 'FDSWorkflow', None)
        except ImportError:
            # Try importing from fds_generator if that's the actual module name
            try:
                import fds_generator
                FDSWorkflow = getattr(fds_generator, 'FDSWorkflow', None)
            except ImportError:
                FDSWorkflow = None
    
    if not FDSWorkflow:
        FDSWorkflow = None
except Exception:
    FDSWorkflow = None

# Import FDS to FDB converter modules
try:
    convert_fds_to_fdb = None
    get_fdb_conversion_db = None
    
    # Try various import paths for converter
    try:
        from fds_workflow.fds_to_fdb_converter import convert_fds_to_fdb
    except ImportError:
        try:
            from fds_to_fdb_converter import convert_fds_to_fdb
        except ImportError:
            pass
            
    # Try various import paths for DB
    try:
        from database.fdb_conversion_db import get_fdb_conversion_db
    except ImportError:
        try:
            from fdb_conversion_db import get_fdb_conversion_db
        except ImportError:
            pass
            
except Exception:
    convert_fds_to_fdb = None
    get_fdb_conversion_db = None

# EVC generator - Avoid self-import circularity
# These classes are defined in this file, so we don't need to import them from elsewhere.
# We'll define them below.
EVCGenerator = None
EVCParams = None
params_from_qra_dict = None


@dataclass
class TunnelGeometry:
    """Tunnel geometry parameters for FDS simulation"""
    name: str = "GUMOK"
    length: float = 2000.0
    radius: float = 7.2
    width: float = None
    height: float = None
    ix: int = 2500
    iy: int = 36
    iz: int = 26

    def __post_init__(self):
        if self.width is None:
            self.width = self.radius * 2
        if self.height is None:
            self.height = self.radius * 2


@dataclass
class FireScenario:
    """Fire scenario parameters for FDS simulation"""
    hrr_type: str = "020"
    hrr_value: float = 20000
    fire_position: float = 1000.0
    flashover_time: int = 450
    traffic_condition: str = "Normal"
    ventilation_condition: str = "NVC"
    t_end: float = 900.0
    bus_length: float = 12.0
    bus_width: float = 2.4
    bus_height: float = 3.42
    # Fuel properties (for FDS6)
    fuel_type: str = None
    fuel_id: str = None
    fuel: str = None
    soot_yield: float = 0.10
    co_yield: float = 0.042
    heat_of_combustion: float = None
    # FDS version
    fds_version: str = "FDS5"


class FDSInputGenerator:
    """Generates FDS input files for tunnel fire simulations"""

    def __init__(self, tunnel: TunnelGeometry):
        self.tunnel = tunnel

    def generate_fds_input(self, scenario: FireScenario, output_path: str):
        """Generate an FDS input file for the given fire scenario"""
        lines = []
        t = self.tunnel
        s = scenario

        # Compute mesh dimensions
        y_max = t.width
        cell_y = y_max / t.iy
        z_max = t.height + cell_y  # One cell of headroom above tunnel

        # CHID and TITLE
        traffic_code = s.traffic_condition[0]  # N or C
        chid = f"{s.hrr_type}_{traffic_code}_{s.ventilation_condition}"
        hrr_mw = int(s.hrr_value / 1000)
        title = f"{hrr_mw}MW {s.traffic_condition} {s.ventilation_condition}"

        lines.append(f"&HEAD CHID='{chid}', TITLE='{title}' /\n")
        lines.append(f"\n&TIME T_END={s.t_end:.1f} /\n")
        lines.append(f"\n&MISC TMPA=20.0 /\n")

        # Mesh
        lines.append(f"\n&MESH IJK={t.ix},{t.iy},{t.iz}, "
                     f"XB=0.0,{t.length:.1f}, 0.0,{y_max:.1f}, 0.0,{z_max:.1f} /\n")

        # Reaction
        if s.fds_version == "FDS6" and s.fuel_id and s.fuel:
            lines.append(f"\n&REAC ID='{s.fuel_id}',\n")
            lines.append(f"      FUEL='{s.fuel}',\n")
            lines.append(f"      SOOT_YIELD={s.soot_yield:.3f},\n")
            lines.append(f"      CO_YIELD={s.co_yield:.3f},\n")
            if s.heat_of_combustion is not None:
                lines.append(f"      HEAT_OF_COMBUSTION={s.heat_of_combustion:.1E} /\n")
            else:
                lines[-1] = f"      CO_YIELD={s.co_yield:.3f} /\n"
        else:
            # FDS5 default reaction
            lines.append(f"\n&REAC ID='POLYURETHANE',\n")
            lines.append(f"      FYI='Polyurethane, GM27',\n")
            lines.append(f"      FUEL='PROPANE',\n")
            lines.append(f"      SOOT_YIELD=0.10,\n")
            lines.append(f"      CO_YIELD=0.042 /\n")

        # Species
        lines.append(f"\n&SPEC ID='CARBON MONOXIDE', FORMULA='CO' /\n")
        lines.append(f"&SPEC ID='CARBON DIOXIDE', FORMULA='CO2' /\n")
        lines.append(f"&SPEC ID='OXYGEN', FORMULA='O2' /\n")

        # Material
        lines.append(f"\n&MATL ID='CONCRETE',\n")
        lines.append(f"      SPECIFIC_HEAT=0.88,\n")
        lines.append(f"      CONDUCTIVITY=1.8,\n")
        lines.append(f"      DENSITY=2400.0 /\n")

        # Surfaces
        lines.append(f"\n&SURF ID='WALL',\n")
        lines.append(f"      MATL_ID='CONCRETE',\n")
        lines.append(f"      THICKNESS=0.30,\n")
        lines.append(f"      COLOR='GRAY 80' /\n")

        # Fire surface
        hrrpua = s.hrr_value / (s.bus_length * s.bus_width)
        lines.append(f"\n&SURF ID='FIRE',\n")
        lines.append(f"      HRRPUA={hrrpua:.1f},\n")
        lines.append(f"      RAMP_Q='Fire_Ramp',\n")
        lines.append(f"      COLOR='RED' /\n")

        # Fire growth ramp (t-squared)
        lines.append(f"\n")
        n_steps = int(s.flashover_time / 10)
        for i in range(n_steps + 1):
            t_val = i * 10.0
            f_val = (t_val / s.flashover_time) ** 2
            lines.append(f"&RAMP ID='Fire_Ramp', T={t_val:.1f},   F={f_val:.4f} /\n")
        # Maintain peak until end
        lines.append(f"&RAMP ID='Fire_Ramp', T={s.t_end:.1f}, F=1.0000 /\n")

        # Fire obstruction (bus)
        center_y = y_max / 2
        x1 = s.fire_position - s.bus_length / 2
        x2 = s.fire_position + s.bus_length / 2
        y1 = center_y - s.bus_width / 2
        y2 = center_y + s.bus_width / 2
        z2 = s.bus_height
        lines.append(f"\n&OBST XB={x1:.1f},{x2:.1f}, {y1:.1f},{y2:.1f}, 0.0,{z2:.2f}, "
                     f"SURF_ID='FIRE', COLOR='RED' /\n")

        # Ventilation
        lines.append(f"\n&VENT MB='XMIN', SURF_ID='OPEN' /\n")
        lines.append(f"&VENT MB='XMAX', SURF_ID='OPEN' /\n")

        # Slice files
        pby = y_max / 2
        cell_z = z_max / t.iz
        pbz = round(3 * cell_z, 2)

        lines.append(f"\n&SLCF PBY={pby:.2f}, QUANTITY='TEMPERATURE' /\n")
        lines.append(f"&SLCF PBY={pby:.2f}, QUANTITY='VISIBILITY' /\n")
        lines.append(f"\n&SLCF PBZ={pbz:.2f}, QUANTITY='TEMPERATURE' /\n")
        lines.append(f"&SLCF PBZ={pbz:.2f}, QUANTITY='VOLUME FRACTION', SPEC_ID='CARBON MONOXIDE' /\n")
        lines.append(f"&SLCF PBZ={pbz:.2f}, QUANTITY='VOLUME FRACTION', SPEC_ID='CARBON DIOXIDE' /\n")
        lines.append(f"&SLCF PBZ={pbz:.2f}, QUANTITY='VOLUME FRACTION', SPEC_ID='OXYGEN' /\n")

        # Devices at tunnel center
        dev_x = t.length / 2
        dev_y = y_max / 2
        dev_z = 1.7
        lines.append(f"\n&DEVC ID='temp_dev', QUANTITY='TEMPERATURE', "
                     f"XYZ={dev_x:.1f},{dev_y:.1f},{dev_z:.1f} /\n")
        lines.append(f"&DEVC ID='co_dev', QUANTITY='VOLUME FRACTION', "
                     f"SPEC_ID='CARBON MONOXIDE', XYZ={dev_x:.1f},{dev_y:.1f},{dev_z:.1f} /\n")

        # End
        lines.append(f"\n&TAIL /\n")

        # Write to file
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.writelines(lines)


class FDSSimulationThread(QThread):
    """Background thread for running FDS simulations without blocking GUI"""
    progress_signal = pyqtSignal(int)  # Progress percentage
    status_signal = pyqtSignal(str)    # Status messages
    finished_signal = pyqtSignal(int, int, int)  # completed, failed, total
    
    def __init__(self, fds_exe, fds_files, output_dir, num_cores=4, timeout_per_file=10800, parallel_jobs=1):
        super().__init__()
        self.fds_exe = fds_exe
        self.fds_files = fds_files
        self.output_dir = output_dir
        self.num_cores = num_cores  # Total cores available
        self.timeout_per_file = timeout_per_file
        self.parallel_jobs = parallel_jobs  # Number of parallel simulations
        self.should_stop = False
        self.active_processes = []  # Track active subprocesses
    
    def stop(self):
        """Request thread to stop and terminate active processes"""
        self.should_stop = True
        # Terminate all active processes
        for proc in self.active_processes:
            try:
                if proc.poll() is None:  # Process still running
                    proc.terminate()
            except:
                pass
    
    def run_single_simulation(self, fds_file, cores_per_job):
        """Run a single FDS simulation (helper method for parallel execution)"""
        import subprocess
        import shutil
        import os
        from pathlib import Path
        
        try:
            # Copy FDS file to output directory
            fds_filename = fds_file.name
            fds_copy = self.output_dir / fds_filename
            shutil.copy2(fds_file, fds_copy)
            
            # Set up FDS environment variables
            fds_env = os.environ.copy()
            
            # Detect FDS bin directory from executable path
            fds_bin_dir = Path(self.fds_exe).parent
            fds_mpi_dir = fds_bin_dir / 'mpi'
            
            # Set Intel MPI environment variables
            fds_env['I_MPI_ROOT'] = str(fds_mpi_dir)
            fds_env['OMP_NUM_THREADS'] = str(cores_per_job)  # Cores for this specific job
            fds_env['IN_CMDFDS'] = '1'
            
            # Add MPI directory to PATH if it exists
            if fds_mpi_dir.exists():
                fds_env['PATH'] = str(fds_mpi_dir) + os.pathsep + fds_env.get('PATH', '')
            
            # Run FDS (support both batch files and direct executables)
            # Use absolute paths and proper quoting for Windows compatibility
            fds_exe_path = Path(self.fds_exe)
            fds_input_path = self.output_dir / fds_filename
            
            if self.fds_exe.lower().endswith('.bat'):
                # Batch file execution - pass FDS input file as parameter to batch file
                # The batch file will set up PATH and call the appropriate FDS executable
                
                # Windows specific: Ensure we switch to the correct drive if necessary
                # and use /d flag with cd command.
                drive = fds_input_path.drive
                if drive:
                    # Construct a command that switches drive and directory before running the batch file
                    cmd = f'{drive} && cd /d "{fds_input_path.parent}" && "{fds_exe_path}" "{fds_input_path}"'
                else:
                    cmd = f'cd /d "{fds_input_path.parent}" && "{fds_exe_path}" "{fds_input_path}"'
                
                result = subprocess.run(
                    cmd,
                    cwd=str(self.output_dir),
                    env=fds_env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_per_file,
                    shell=True
                )
            else:
                # Direct executable execution
                result = subprocess.run(
                    [str(fds_exe_path), fds_filename],
                    cwd=str(self.output_dir),
                    env=fds_env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_per_file
                )
            
            # Get basename
            fds_basename = fds_filename.replace('.fds', '')
            
            # Save FDS output to log file
            log_file = self.output_dir / f"{fds_basename}_run.log"
            with open(log_file, 'w') as f:
                f.write("=== FDS STDOUT ===\n")
                f.write(result.stdout if result.stdout else "(no output)\n")
                f.write("\n=== FDS STDERR ===\n")
                f.write(result.stderr if result.stderr else "(no errors)\n")
            
            # Check result
            if result.returncode == 0:
                expected_smv = self.output_dir / f"{fds_basename}.smv"
                if expected_smv.exists():
                    return ('success', fds_file.name, None)
                else:
                    return ('warning', fds_file.name, f"No .smv file found. Check {log_file.name}")
            else:
                error_msg = result.stderr[:200] if result.stderr else f"Return code {result.returncode}"
                return ('failed', fds_file.name, error_msg)
                
        except subprocess.TimeoutExpired:
            # Check if actually completed
            fds_basename = fds_filename.replace('.fds', '')
            expected_smv = self.output_dir / f"{fds_basename}.smv"
            expected_out = self.output_dir / f"{fds_basename}.out"
            
            completed_successfully = False
            if expected_out.exists():
                try:
                    with open(expected_out, 'r') as f:
                        last_lines = f.readlines()[-50:]
                        for line in last_lines:
                            if 'STOP: FDS completed successfully' in line or 'completed successfully' in line.lower():
                                completed_successfully = True
                                break
                except:
                    pass
            
            if completed_successfully and expected_smv.exists():
                return ('success', fds_file.name, 'Completed after timeout')
            else:
                return ('timeout', fds_file.name, f"Exceeded {self.timeout_per_file/60:.1f} minutes")
                
        except Exception as e:
            return ('error', fds_file.name, str(e))
    
    def run(self):
        """Run FDS simulations in background with parallel processing"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        completed = 0
        failed = 0
        total = len(self.fds_files)
        
        # Calculate cores per job
        cores_per_job = max(1, self.num_cores // self.parallel_jobs)
        
        self.status_signal.emit(f"\n🚀 Starting parallel processing:")
        self.status_signal.emit(f"  • Total simulations: {total}")
        self.status_signal.emit(f"  • Parallel jobs: {self.parallel_jobs}")
        self.status_signal.emit(f"  • Cores per job: {cores_per_job}")
        self.status_signal.emit(f"  • Total cores used: {self.num_cores}")
        
        # Use ThreadPoolExecutor for parallel execution
        completed_count = 0
        lock = threading.Lock()
        
        with ThreadPoolExecutor(max_workers=self.parallel_jobs) as executor:
            # Submit all jobs
            future_to_file = {executor.submit(self.run_single_simulation, fds_file, cores_per_job): fds_file 
                             for fds_file in self.fds_files}
            
            # Process completed jobs as they finish
            for future in as_completed(future_to_file):
                if self.should_stop:
                    self.status_signal.emit("\n⚠️ Simulations stopped by user")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                fds_file = future_to_file[future]
                
                try:
                    status, filename, message = future.result()
                    
                    with lock:
                        completed_count += 1
                        
                        self.status_signal.emit(f"\n[{completed_count}/{total}] {filename}")
                        
                        if status == 'success':
                            self.status_signal.emit(f"  ✓ Completed successfully")
                            if message:
                                self.status_signal.emit(f"    Note: {message}")
                            completed += 1
                        elif status == 'warning':
                            self.status_signal.emit(f"  ⚠️ Warning: {message}")
                            failed += 1
                        elif status == 'timeout':
                            self.status_signal.emit(f"  ⏱️ Timeout: {message}")
                            failed += 1
                        elif status == 'failed':
                            self.status_signal.emit(f"  ✗ Failed: {message}")
                            failed += 1
                        elif status == 'error':
                            self.status_signal.emit(f"  ❌ Error: {message}")
                            failed += 1
                        
                        # Update progress
                        progress = int((completed_count / total) * 100)
                        self.progress_signal.emit(progress)
                        
                except Exception as e:
                    with lock:
                        self.status_signal.emit(f"\n[{completed_count}/{total}] {fds_file.name}")
                        self.status_signal.emit(f"  ❌ Exception: {str(e)}")
                        failed += 1
                        completed_count += 1
                        progress = int((completed_count / total) * 100)
                        self.progress_signal.emit(progress)
        
        # Emit finished signal
        self.finished_signal.emit(completed, failed, total)


# QRAMainWindow is defined in qra_main_app.py.
# This file should only contain EVC related logic.
# If you need to run this as a standalone app, consider a separate launcher.

class EVCMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_dir = None
        self.db = None
        self.fds_workflow = None
        self.current_project_id = None
        self.custom_hrr_list = []  # Store custom HRR values
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("Quantitative Risk Assessment System v2.9.0")
        self.setGeometry(50, 50, 1600, 1000)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title
        title_label = QLabel("Quantitative Risk Assessment System")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50; margin: 10px;")
        main_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Tunnel Fire Risk Assessment: FDS Simulation → EVC/FED Analysis → Risk Calculation")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #7f8c8d; margin-bottom: 15px; font-size: 12px;")
        main_layout.addWidget(subtitle_label)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
            }
            QTabBar::tab {
                background: #ecf0f1;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
                font-weight: bold;
            }
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #bdc3c7;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #95a5a6;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        main_layout.addWidget(self.tabs)
        
        # Create all tabs
        self.create_tab1_directory_setup()
        self.create_tab2_fds_generation()
        self.create_tab3_fds_simulation()
        self.create_tab4_evc_fed_analysis()
        self.create_tab5_statistics()
        self.create_tab6_risk_calculation()
        self.create_tab7_results()

        # Ensure required directories exist whenever Tab 4 (EVC/FED) is activated
        self.tabs.currentChanged.connect(self._on_main_tab_changed)
        
        # Status bar
        self.statusBar().showMessage("Ready - Start by creating a project in Tab 1")
        self.statusBar().setStyleSheet("background-color: #ecf0f1; padding: 5px;")
    
    def _on_main_tab_changed(self, index: int):
        """Called whenever the user switches main tabs.

        Tab 4 (index 3) = EVC/FED Analysis.
        Ensures ascii_files/, evc_files/, and fed_results/ exist so buttons
        never fail with a 'directory not found' error, even for legacy projects
        that were created before these folders were part of the template.
        """
        if index == 3 and self.project_dir:   # Tab 4 is index 3 (0-based)
            for _subdir in ("ascii_files", "evc_files", "fed_results"):
                _p = Path(self.project_dir) / _subdir
                if not _p.exists():
                    _p.mkdir(parents=True, exist_ok=True)
                    # Show a subtle status-bar hint (not a popup)
                    self.statusBar().showMessage(
                        f"Created missing directory: {_subdir}", 3000)

    def create_tab1_directory_setup(self):
        """Tab 1: FDS Project Directory Structure Setup"""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Header
        header_label = QLabel("📁 FDS Project Directory Structure Setup")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 10px;")
        layout.addWidget(header_label)
        
        # Project configuration
        config_group = QGroupBox("Project Configuration")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        config_layout = QVBoxLayout()
        config_group.setLayout(config_layout)
        
        # Project name
        name_layout = QHBoxLayout()
        name_label = QLabel("Project Name:")
        name_label.setMinimumWidth(150)
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("e.g., Highway_Tunnel_2026")
        self.project_name_input.textChanged.connect(self.update_directory_preview)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.project_name_input)
        config_layout.addLayout(name_layout)
        
        # Home directory
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Home Directory:")
        dir_label.setMinimumWidth(150)
        self.home_dir_input = QLineEdit()
        self.home_dir_input.setPlaceholderText("Select home directory location")
        self.home_dir_input.textChanged.connect(self.update_directory_preview)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_home_directory)
        browse_btn.setStyleSheet("QPushButton { background-color: #95a5a6; color: white; padding: 5px 15px; }")
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.home_dir_input)
        dir_layout.addWidget(browse_btn)
        config_layout.addLayout(dir_layout)
        
        # Full path display
        path_layout = QHBoxLayout()
        path_label = QLabel("Full Project Path:")
        path_label.setMinimumWidth(150)
        self.full_path_display = QLineEdit()
        self.full_path_display.setReadOnly(True)
        self.full_path_display.setStyleSheet("background-color: #ecf0f1; font-weight: bold;")
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.full_path_display)
        config_layout.addLayout(path_layout)
        
        layout.addWidget(config_group)
        
        # Directory structure preview
        preview_group = QGroupBox("Directory Structure Preview")
        preview_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        preview_layout = QVBoxLayout()
        preview_group.setLayout(preview_layout)
        
        self.dir_tree = QTreeWidget()
        self.dir_tree.setHeaderLabel("Folder Structure")
        self.dir_tree.setStyleSheet("QTreeWidget { font-family: 'Courier New'; }")
        preview_layout.addWidget(self.dir_tree)
        
        layout.addWidget(preview_group)
        
        # Progress section
        progress_group = QGroupBox("Setup Progress")
        progress_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        progress_layout = QVBoxLayout()
        progress_group.setLayout(progress_layout)
        
        self.dir_progress_bar = QProgressBar()
        self.dir_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
            }
        """)
        progress_layout.addWidget(self.dir_progress_bar)
        
        self.dir_status_text = QTextEdit()
        self.dir_status_text.setReadOnly(True)
        self.dir_status_text.setMaximumHeight(100)
        self.dir_status_text.setStyleSheet("background-color: #f8f9fa; font-family: 'Courier New';")
        progress_layout.addWidget(self.dir_status_text)
        
        layout.addWidget(progress_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.create_project_btn = QPushButton("✓ Create Project")
        self.create_project_btn.setMinimumHeight(45)
        self.create_project_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.create_project_btn.clicked.connect(self.create_project)
        self.create_project_btn.setEnabled(False)
        
        self.open_project_btn = QPushButton("📂 Open Existing Project")
        self.open_project_btn.setMinimumHeight(45)
        self.open_project_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.open_project_btn.clicked.connect(self.open_existing_project)
        
        button_layout.addWidget(self.create_project_btn)
        button_layout.addWidget(self.open_project_btn)
        layout.addLayout(button_layout)
        
        self.tabs.addTab(scroll, "1. Directory Setup")
    
    def create_tab2_fds_generation(self):
        """Tab 2: Generate FDS Files with Tunnel Specifications"""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Header
        header_label = QLabel("🔥 Generate FDS Input Files")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 10px;")
        layout.addWidget(header_label)
        
        # Tunnel Specifications
        tunnel_group = QGroupBox("Tunnel Specifications")
        tunnel_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        tunnel_layout = QGridLayout()
        tunnel_group.setLayout(tunnel_layout)
        
        row = 0
        
        # Tunnel Name
        tunnel_layout.addWidget(QLabel("Tunnel Name:"), row, 0)
        self.tunnel_name_input = QLineEdit()
        self.tunnel_name_input.setPlaceholderText("e.g., GUMOK")
        tunnel_layout.addWidget(self.tunnel_name_input, row, 1)
        
        # Tunnel Length
        tunnel_layout.addWidget(QLabel("Tunnel Length (m):"), row, 2)
        self.tunnel_length_input = QDoubleSpinBox()
        self.tunnel_length_input.setRange(100, 10000)
        self.tunnel_length_input.setValue(2000)
        self.tunnel_length_input.setDecimals(1)
        tunnel_layout.addWidget(self.tunnel_length_input, row, 3)
        
        row += 1
        
        # Tunnel Radius
        tunnel_layout.addWidget(QLabel("Tunnel Radius (m):"), row, 0)
        self.tunnel_radius_input = QDoubleSpinBox()
        self.tunnel_radius_input.setRange(3, 15)
        self.tunnel_radius_input.setValue(7.2)
        self.tunnel_radius_input.setDecimals(2)
        tunnel_layout.addWidget(self.tunnel_radius_input, row, 1)
        
        # Tunnel Width
        tunnel_layout.addWidget(QLabel("Tunnel Width (m):"), row, 2)
        self.tunnel_width_input = QDoubleSpinBox()
        self.tunnel_width_input.setRange(5, 30)
        self.tunnel_width_input.setValue(14.4)
        self.tunnel_width_input.setDecimals(2)
        self.tunnel_width_input.setReadOnly(True)
        self.tunnel_width_input.setStyleSheet("background-color: #ecf0f1;")
        tunnel_layout.addWidget(self.tunnel_width_input, row, 3)
        
        row += 1
        
        # Tunnel Height
        tunnel_layout.addWidget(QLabel("Tunnel Height (m):"), row, 0)
        self.tunnel_height_input = QDoubleSpinBox()
        self.tunnel_height_input.setRange(5, 20)
        self.tunnel_height_input.setValue(14.8)
        self.tunnel_height_input.setDecimals(2)
        self.tunnel_height_input.setReadOnly(True)
        self.tunnel_height_input.setStyleSheet("background-color: #ecf0f1;")
        tunnel_layout.addWidget(self.tunnel_height_input, row, 1)
        
        # Calculate dimensions button
        calc_btn = QPushButton("Calculate Width/Height from Radius")
        calc_btn.clicked.connect(self.calculate_tunnel_dimensions)
        calc_btn.setStyleSheet("QPushButton { background-color: #95a5a6; color: white; padding: 5px; }")
        tunnel_layout.addWidget(calc_btn, row, 2, 1, 2)
        
        row += 1
        
        # Mesh Configuration
        tunnel_layout.addWidget(QLabel("Mesh IX:"), row, 0)
        self.mesh_ix_input = QSpinBox()
        self.mesh_ix_input.setRange(100, 5000)
        self.mesh_ix_input.setValue(2500)
        tunnel_layout.addWidget(self.mesh_ix_input, row, 1)
        
        tunnel_layout.addWidget(QLabel("Mesh IY:"), row, 2)
        self.mesh_iy_input = QSpinBox()
        self.mesh_iy_input.setRange(10, 100)
        self.mesh_iy_input.setValue(36)
        tunnel_layout.addWidget(self.mesh_iy_input, row, 3)
        
        row += 1
        
        tunnel_layout.addWidget(QLabel("Mesh IZ:"), row, 0)
        self.mesh_iz_input = QSpinBox()
        self.mesh_iz_input.setRange(10, 100)
        self.mesh_iz_input.setValue(26)
        tunnel_layout.addWidget(self.mesh_iz_input, row, 1)
        
        layout.addWidget(tunnel_group)
        
        # FDS Version Selection
        fds_version_group = QGroupBox("FDS Version Selection")
        fds_version_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        fds_version_layout = QHBoxLayout()
        fds_version_group.setLayout(fds_version_layout)
        
        fds_version_layout.addWidget(QLabel("FDS Version:"))
        self.fds_version_group = QButtonGroup()
        self.fds6_radio = QRadioButton("FDS 6")
        self.fds6_radio.setChecked(True)  # Default to FDS6
        self.fds5_radio = QRadioButton("FDS 5")
        self.fds_version_group.addButton(self.fds6_radio)
        self.fds_version_group.addButton(self.fds5_radio)
        fds_version_layout.addWidget(self.fds6_radio)
        fds_version_layout.addWidget(self.fds5_radio)
        fds_version_layout.addStretch()
        
        # Connect FDS version change to update batch file fields in Tab 3
        self.fds6_radio.toggled.connect(self.on_fds_version_changed)
        self.fds5_radio.toggled.connect(self.on_fds_version_changed)
        
        layout.addWidget(fds_version_group)
        
        # Fire Specifications
        fire_group = QGroupBox("Fire Specifications")
        fire_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        fire_layout = QVBoxLayout()
        fire_group.setLayout(fire_layout)
        
        # Bus dimensions
        bus_layout = QGridLayout()
        bus_layout.addWidget(QLabel("Bus Length (m):"), 0, 0)
        self.bus_length_input = QDoubleSpinBox()
        self.bus_length_input.setRange(5, 20)
        self.bus_length_input.setValue(12.0)
        self.bus_length_input.setDecimals(1)
        bus_layout.addWidget(self.bus_length_input, 0, 1)
        
        bus_layout.addWidget(QLabel("Bus Width (m):"), 0, 2)
        self.bus_width_input = QDoubleSpinBox()
        self.bus_width_input.setRange(1, 5)
        self.bus_width_input.setValue(2.4)
        self.bus_width_input.setDecimals(1)
        bus_layout.addWidget(self.bus_width_input, 0, 3)
        
        bus_layout.addWidget(QLabel("Bus Height (m):"), 1, 0)
        self.bus_height_input = QDoubleSpinBox()
        self.bus_height_input.setRange(2, 5)
        self.bus_height_input.setValue(3.42)
        self.bus_height_input.setDecimals(2)
        bus_layout.addWidget(self.bus_height_input, 1, 1)
        
        fire_layout.addLayout(bus_layout)
        
        # Fuel Type Selection
        fuel_type_layout = QGridLayout()
        fuel_type_layout.addWidget(QLabel("Fuel Type:"), 0, 0)
        self.fuel_type_combo = QComboBox()
        self.fuel_type_combo.addItems(["Petrol", "Diesel", "CNG", "LPG", "EVC"])
        self.fuel_type_combo.setCurrentText("Diesel")  # Default
        self.fuel_type_combo.currentTextChanged.connect(self.on_fuel_type_changed)
        fuel_type_layout.addWidget(self.fuel_type_combo, 0, 1)
        fire_layout.addLayout(fuel_type_layout)
        
        # Fuel Properties (Editable for Petrol/Diesel)
        fuel_props_layout = QGridLayout()
        
        # SOOT_YIELD
        fuel_props_layout.addWidget(QLabel("SOOT_YIELD:"), 0, 0)
        self.soot_yield_input = QDoubleSpinBox()
        self.soot_yield_input.setRange(0.0, 1.0)
        self.soot_yield_input.setDecimals(3)
        self.soot_yield_input.setSingleStep(0.001)
        self.soot_yield_input.setValue(0.133)  # Default for Diesel
        fuel_props_layout.addWidget(self.soot_yield_input, 0, 1)
        
        # CO_YIELD
        fuel_props_layout.addWidget(QLabel("CO_YIELD:"), 0, 2)
        self.co_yield_input = QDoubleSpinBox()
        self.co_yield_input.setRange(0.0, 1.0)
        self.co_yield_input.setDecimals(3)
        self.co_yield_input.setSingleStep(0.001)
        self.co_yield_input.setValue(0.168)  # Default for Diesel
        fuel_props_layout.addWidget(self.co_yield_input, 0, 3)
        
        # HEAT_OF_COMBUSTION
        fuel_props_layout.addWidget(QLabel("HEAT_OF_COMBUSTION:"), 1, 0)
        self.heat_of_combustion_input = QDoubleSpinBox()
        self.heat_of_combustion_input.setRange(1.0e7, 1.0e8)
        self.heat_of_combustion_input.setDecimals(1)
        self.heat_of_combustion_input.setSingleStep(1.0e6)
        self.heat_of_combustion_input.setValue(4.3e7)  # Default for Diesel
        self.heat_of_combustion_input.setEnabled(True)
        fuel_props_layout.addWidget(self.heat_of_combustion_input, 1, 1, 1, 3)
        
        fire_layout.addLayout(fuel_props_layout)
        
        # Note about editable properties
        fuel_note = QLabel("Note: Fuel properties are editable for Petrol and Diesel only")
        fuel_note.setStyleSheet("color: #7f8c8d; font-style: italic; font-size: 10px;")
        fire_layout.addWidget(fuel_note)
        
        layout.addWidget(fire_group)
        
        # HRR Selection
        hrr_group = QGroupBox("Heat Release Rate (HRR) Selection")
        hrr_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        hrr_layout = QVBoxLayout()
        hrr_group.setLayout(hrr_layout)
        
        # Standard HRR checkboxes
        hrr_check_layout = QHBoxLayout()
        hrr_check_layout.addWidget(QLabel("Standard HRR Values:"))
        
        self.hrr_005_check = QCheckBox("5 MW")
        self.hrr_010_check = QCheckBox("10 MW")
        self.hrr_020_check = QCheckBox("20 MW")
        self.hrr_020_check.setChecked(True)
        self.hrr_030_check = QCheckBox("30 MW")
        self.hrr_030_check.setChecked(True)
        self.hrr_050_check = QCheckBox("50 MW")
        self.hrr_100_check = QCheckBox("100 MW")
        self.hrr_100_check.setChecked(True)
        
        # Connect checkboxes to auto-selection logic
        self.hrr_005_check.stateChanged.connect(self.on_hrr_selection_changed)
        self.hrr_010_check.stateChanged.connect(self.on_hrr_selection_changed)
        self.hrr_020_check.stateChanged.connect(self.on_hrr_selection_changed)
        self.hrr_030_check.stateChanged.connect(self.on_hrr_selection_changed)
        self.hrr_050_check.stateChanged.connect(self.on_hrr_selection_changed)
        self.hrr_100_check.stateChanged.connect(self.on_hrr_selection_changed)
        
        hrr_check_layout.addWidget(self.hrr_005_check)
        hrr_check_layout.addWidget(self.hrr_010_check)
        hrr_check_layout.addWidget(self.hrr_020_check)
        hrr_check_layout.addWidget(self.hrr_030_check)
        hrr_check_layout.addWidget(self.hrr_050_check)
        hrr_check_layout.addWidget(self.hrr_100_check)
        hrr_check_layout.addStretch()
        
        hrr_layout.addLayout(hrr_check_layout)
        
        # Custom HRR section
        custom_hrr_layout = QHBoxLayout()
        custom_hrr_layout.addWidget(QLabel("Custom HRR (MW):"))
        self.custom_hrr_input = QDoubleSpinBox()
        self.custom_hrr_input.setRange(1, 500)
        self.custom_hrr_input.setValue(15)
        self.custom_hrr_input.setDecimals(1)
        custom_hrr_layout.addWidget(self.custom_hrr_input)
        
        add_custom_btn = QPushButton("Add Custom HRR")
        add_custom_btn.clicked.connect(self.add_custom_hrr)
        add_custom_btn.setStyleSheet("QPushButton { background-color: #f39c12; color: white; padding: 5px 15px; }")
        custom_hrr_layout.addWidget(add_custom_btn)
        
        custom_hrr_layout.addWidget(QLabel("Custom HRR List:"))
        self.custom_hrr_list_widget = QListWidget()
        self.custom_hrr_list_widget.setMaximumHeight(60)
        custom_hrr_layout.addWidget(self.custom_hrr_list_widget)
        
        remove_custom_btn = QPushButton("Remove Selected")
        remove_custom_btn.clicked.connect(self.remove_custom_hrr)
        remove_custom_btn.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; padding: 5px 15px; }")
        custom_hrr_layout.addWidget(remove_custom_btn)
        
        custom_hrr_layout.addStretch()
        hrr_layout.addLayout(custom_hrr_layout)
        
        layout.addWidget(hrr_group)
        
        # Scenario Configuration
        scenario_group = QGroupBox("Scenario Configuration")
        scenario_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        scenario_layout = QVBoxLayout()
        scenario_group.setLayout(scenario_layout)

        # ── Fire position mode selector ───────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Fire Position Mode:"))
        self.fp_mode_auto  = QRadioButton("Auto (from tunnel length + N)")
        self.fp_mode_manual = QRadioButton("Manual (enter positions)")
        self.fp_mode_auto.setChecked(True)
        fp_mode_group = QButtonGroup(self)
        fp_mode_group.addButton(self.fp_mode_auto)
        fp_mode_group.addButton(self.fp_mode_manual)
        mode_row.addWidget(self.fp_mode_auto)
        mode_row.addWidget(self.fp_mode_manual)
        mode_row.addStretch()
        scenario_layout.addLayout(mode_row)

        # ── Auto mode: N spinner + preview ────────────────────────────────────
        self.fp_auto_widget = QWidget()
        auto_layout = QVBoxLayout(self.fp_auto_widget)
        auto_layout.setContentsMargins(0, 0, 0, 0)

        n_row = QHBoxLayout()
        n_row.addWidget(QLabel("Number of Fire Positions:"))
        self.num_fire_positions_spin = QSpinBox()
        self.num_fire_positions_spin.setRange(1, 50)
        self.num_fire_positions_spin.setValue(6)
        self.num_fire_positions_spin.setFixedWidth(70)
        self.num_fire_positions_spin.setToolTip(
            "How many evenly-spaced fire positions to generate along the tunnel.\n"
            "Positions are placed as midpoints of equal segments covering ~93% of tunnel length.")
        n_row.addWidget(self.num_fire_positions_spin)
        n_row.addSpacing(20)

        recalc_btn = QPushButton("↻  Recalculate Positions")
        recalc_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "padding: 4px 14px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #219a52; }")
        recalc_btn.clicked.connect(self.recalculate_fire_positions)
        n_row.addWidget(recalc_btn)
        n_row.addStretch()
        auto_layout.addLayout(n_row)

        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("Computed Positions (m):"))
        self.fp_preview_label = QLabel("")
        self.fp_preview_label.setStyleSheet(
            "color: #2980b9; font-family: monospace; font-size: 11px;")
        self.fp_preview_label.setWordWrap(True)
        preview_row.addWidget(self.fp_preview_label, 1)
        auto_layout.addLayout(preview_row)

        scenario_layout.addWidget(self.fp_auto_widget)

        # ── Manual mode: free-text entry ──────────────────────────────────────
        self.fp_manual_widget = QWidget()
        manual_layout = QHBoxLayout(self.fp_manual_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.addWidget(QLabel("Fire Positions (m):"))
        self.fire_positions_input = QLineEdit()
        self.fire_positions_input.setText("500, 750, 1000, 1250, 1500, 1750")
        self.fire_positions_input.setPlaceholderText("Comma-separated positions, e.g. 300, 600, 900")
        manual_layout.addWidget(self.fire_positions_input)
        self.fp_manual_widget.setVisible(False)
        scenario_layout.addWidget(self.fp_manual_widget)

        # Wire mode toggle
        self.fp_mode_auto.toggled.connect(self._on_fp_mode_changed)
        self.fp_mode_manual.toggled.connect(self._on_fp_mode_changed)

        # Wire N-spinner and tunnel length to live-preview
        self.num_fire_positions_spin.valueChanged.connect(self.recalculate_fire_positions)
        self.tunnel_length_input.valueChanged.connect(self.recalculate_fire_positions)

        # Initial preview
        self.recalculate_fire_positions()
        
        # Traffic conditions
        traffic_layout = QHBoxLayout()
        traffic_layout.addWidget(QLabel("Traffic Conditions:"))
        self.traffic_normal_check = QCheckBox("Normal")
        self.traffic_normal_check.setChecked(True)
        self.traffic_congested_check = QCheckBox("Congested")
        self.traffic_congested_check.setChecked(True)
        traffic_layout.addWidget(self.traffic_normal_check)
        traffic_layout.addWidget(self.traffic_congested_check)
        traffic_layout.addStretch()
        scenario_layout.addLayout(traffic_layout)
        
        # Ventilation conditions
        vent_layout = QHBoxLayout()
        vent_layout.addWidget(QLabel("Ventilation:"))
        self.vent_nvc_check = QCheckBox("NVC")
        self.vent_nvc_check.setChecked(True)
        self.vent_nv0_check = QCheckBox("NV0")
        self.vent_nv0_check.setChecked(True)
        self.vent_fvp_check = QCheckBox("FVP")
        self.vent_fvp_check.setChecked(True)
        self.vent_fv0_check = QCheckBox("FV0")
        self.vent_fv0_check.setChecked(True)
        self.vent_fvm_check = QCheckBox("FVM")
        self.vent_fvm_check.setChecked(True)
        vent_layout.addWidget(self.vent_nvc_check)
        vent_layout.addWidget(self.vent_nv0_check)
        vent_layout.addWidget(self.vent_fvp_check)
        vent_layout.addWidget(self.vent_fv0_check)
        vent_layout.addWidget(self.vent_fvm_check)
        vent_layout.addStretch()
        scenario_layout.addLayout(vent_layout)
        
        # Flashover time
        flash_layout = QHBoxLayout()
        flash_layout.addWidget(QLabel("Flashover Time (s):"))
        self.flashover_input = QSpinBox()
        self.flashover_input.setRange(300, 600)
        self.flashover_input.setValue(450)
        self.flashover_input.setSingleStep(10)
        flash_layout.addWidget(self.flashover_input)
        flash_layout.addStretch()
        scenario_layout.addLayout(flash_layout)
        
        # Simulation end time (T_END)
        tend_layout = QHBoxLayout()
        tend_layout.addWidget(QLabel("Simulation Time T_END (s):"))
        self.tend_input = QDoubleSpinBox()
        self.tend_input.setRange(60, 7200)  # 1 min to 2 hours
        self.tend_input.setValue(900.0)  # Default 15 minutes
        self.tend_input.setDecimals(1)
        self.tend_input.setSingleStep(60)  # 1 minute increments
        self.tend_input.setToolTip("Total simulation time in seconds (default: 900s = 15 minutes)\nLonger times = more accurate but slower simulations")
        tend_layout.addWidget(self.tend_input)
        tend_layout.addStretch()
        scenario_layout.addLayout(tend_layout)
        
        # Scenario count
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Total Scenarios:"))
        self.scenario_count_label = QLabel("0")
        self.scenario_count_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #e74c3c;")
        count_layout.addWidget(self.scenario_count_label)
        
        calc_count_btn = QPushButton("Calculate Scenario Count")
        calc_count_btn.clicked.connect(self.calculate_scenario_count)
        calc_count_btn.setStyleSheet("QPushButton { background-color: #9b59b6; color: white; padding: 5px 15px; }")
        count_layout.addWidget(calc_count_btn)
        count_layout.addStretch()
        scenario_layout.addLayout(count_layout)
        
        layout.addWidget(scenario_group)
        
        # Generation progress
        progress_group = QGroupBox("Generation Progress")
        progress_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        progress_layout = QVBoxLayout()
        progress_group.setLayout(progress_layout)
        
        self.fds_progress_bar = QProgressBar()
        self.fds_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
            }
        """)
        progress_layout.addWidget(self.fds_progress_bar)
        
        self.fds_status_text = QTextEdit()
        self.fds_status_text.setReadOnly(True)
        self.fds_status_text.setMaximumHeight(120)
        self.fds_status_text.setStyleSheet("background-color: #f8f9fa; font-family: 'Courier New';")
        progress_layout.addWidget(self.fds_status_text)
        
        layout.addWidget(progress_group)
        
        # Generate button
        button_layout = QHBoxLayout()
        self.generate_fds_btn = QPushButton("🚀 Generate FDS Input Files")
        self.generate_fds_btn.setMinimumHeight(45)
        self.generate_fds_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.generate_fds_btn.clicked.connect(self.generate_fds_files)
        self.generate_fds_btn.setEnabled(False)
        button_layout.addWidget(self.generate_fds_btn)
        layout.addLayout(button_layout)
        
        layout.addStretch()
        
        self.tabs.addTab(scroll, "2. Generate FDS")
    
    def create_tab3_fds_simulation(self):
        """Tab 3: FDS Simulation Management"""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        header_label = QLabel("⚙️ FDS Simulation Management")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 10px;")
        layout.addWidget(header_label)
        
        # Mode Selection
        mode_group = QGroupBox("🎯 Workflow Mode")
        mode_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        mode_layout = QVBoxLayout()
        mode_group.setLayout(mode_layout)
        
        mode_desc = QLabel("Choose workflow mode:")
        mode_desc.setStyleSheet("font-size: 12px; color: #7f8c8d; padding: 5px;")
        mode_layout.addWidget(mode_desc)
        
        mode_radio_layout = QHBoxLayout()
        
        self.batch_mode_radio = QRadioButton("Batch Mode (Multiple Scenarios)")
        self.batch_mode_radio.setChecked(True)
        self.batch_mode_radio.setToolTip("Run all generated FDS files from Tab 2")
        self.batch_mode_radio.toggled.connect(self.on_mode_changed)
        mode_radio_layout.addWidget(self.batch_mode_radio)
        
        self.simple_mode_radio = QRadioButton("Simple Mode (Single File)")
        self.simple_mode_radio.setToolTip("Select and run a single FDS file for quick testing")
        self.simple_mode_radio.toggled.connect(self.on_mode_changed)
        mode_radio_layout.addWidget(self.simple_mode_radio)
        
        mode_radio_layout.addStretch()
        mode_layout.addLayout(mode_radio_layout)
        
        # Simple mode file selection
        self.simple_mode_widget = QWidget()
        simple_mode_layout = QHBoxLayout()
        simple_mode_layout.setContentsMargins(20, 5, 0, 5)
        self.simple_mode_widget.setLayout(simple_mode_layout)
        
        simple_mode_layout.addWidget(QLabel("FDS File:"))
        self.simple_fds_file_input = QLineEdit()
        self.simple_fds_file_input.setPlaceholderText("Select a single .fds file to simulate...")
        self.simple_fds_file_input.setReadOnly(True)
        simple_mode_layout.addWidget(self.simple_fds_file_input)
        
        browse_single_btn = QPushButton("Browse...")
        browse_single_btn.clicked.connect(self.browse_single_fds_file)
        browse_single_btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; padding: 5px 15px; }")
        simple_mode_layout.addWidget(browse_single_btn)
        
        self.simple_mode_widget.setVisible(False)
        mode_layout.addWidget(self.simple_mode_widget)
        
        layout.addWidget(mode_group)
        
        info_label = QLabel(
            "This tab manages FDS simulation execution. You can run simulations manually using "
            "the generated batch script, or integrate with FDS.exe if installed on your system."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #e8f4f8; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # CPU Configuration Panel
        cpu_config_group = QGroupBox("💻 CPU Configuration")
        cpu_config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        cpu_config_layout = QVBoxLayout()
        cpu_config_group.setLayout(cpu_config_layout)
        
        # Auto-detect CPU cores
        self.system_cpu_count = os.cpu_count() or 4
        self.recommended_cores = max(4, int(self.system_cpu_count * 0.8))
        
        # CPU info display
        cpu_info_layout = QGridLayout()
        
        cpu_info_layout.addWidget(QLabel("System CPU Cores:"), 0, 0)
        self.cpu_count_label = QLabel(f"{self.system_cpu_count}")
        self.cpu_count_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        cpu_info_layout.addWidget(self.cpu_count_label, 0, 1)
        
        cpu_info_layout.addWidget(QLabel("Recommended Cores:"), 1, 0)
        self.recommended_cores_label = QLabel(f"{self.recommended_cores} (80% of total)")
        self.recommended_cores_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        cpu_info_layout.addWidget(self.recommended_cores_label, 1, 1)
        
        cpu_config_layout.addLayout(cpu_info_layout)
        
        # User input for cores
        cores_input_layout = QHBoxLayout()
        cores_input_layout.addWidget(QLabel("Cores to Use:"))
        self.cores_spinbox = QSpinBox()
        self.cores_spinbox.setMinimum(1)
        self.cores_spinbox.setMaximum(self.system_cpu_count)
        self.cores_spinbox.setValue(self.recommended_cores)
        self.cores_spinbox.setToolTip(f"Enter number of CPU cores to use (1-{self.system_cpu_count})")
        self.cores_spinbox.valueChanged.connect(self.update_time_estimates)
        cores_input_layout.addWidget(self.cores_spinbox)
        cores_input_layout.addStretch()
        cpu_config_layout.addLayout(cores_input_layout)
        
        layout.addWidget(cpu_config_group)
        
        # RAM Configuration Panel
        ram_config_group = QGroupBox("🧠 RAM & Parallel Processing Configuration")
        ram_config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        ram_config_layout = QVBoxLayout()
        ram_config_group.setLayout(ram_config_layout)
        
        # Auto-detect system RAM
        try:
            import psutil
            self.system_ram_gb = psutil.virtual_memory().total / (1024**3)
            self.available_ram_gb = psutil.virtual_memory().available / (1024**3)
        except:
            self.system_ram_gb = 16.0  # Default fallback
            self.available_ram_gb = 12.0
        
        # RAM info display
        ram_info_layout = QGridLayout()
        
        ram_info_layout.addWidget(QLabel("Total System RAM:"), 0, 0)
        self.ram_total_label = QLabel(f"{self.system_ram_gb:.1f} GB")
        self.ram_total_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        ram_info_layout.addWidget(self.ram_total_label, 0, 1)
        
        ram_info_layout.addWidget(QLabel("Currently Available:"), 1, 0)
        self.ram_available_label = QLabel(f"{self.available_ram_gb:.1f} GB")
        self.ram_available_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        ram_info_layout.addWidget(self.ram_available_label, 1, 1)
        
        ram_config_layout.addLayout(ram_info_layout)
        
        # RAM usage percentage selection
        ram_usage_layout = QHBoxLayout()
        ram_usage_layout.addWidget(QLabel("RAM Usage Limit:"))
        self.ram_usage_combo = QComboBox()
        self.ram_usage_combo.addItems(["50%", "75%", "90%"])  # RAM usage options
        self.ram_usage_combo.setCurrentText("75%")  # Default 75%
        self.ram_usage_combo.setToolTip("Maximum percentage of system RAM to use for parallel simulations\nSystem automatically detects available RAM")
        self.ram_usage_combo.currentTextChanged.connect(self.update_parallel_config)
        self.ram_usage_combo.currentTextChanged.connect(self.update_time_estimates)  # Dynamic time update
        ram_usage_layout.addWidget(self.ram_usage_combo)
        ram_usage_layout.addStretch()
        ram_config_layout.addLayout(ram_usage_layout)
        
        # Parallel jobs configuration
        parallel_layout = QHBoxLayout()
        parallel_layout.addWidget(QLabel("Parallel Simulations:"))
        self.parallel_jobs_spinbox = QSpinBox()
        self.parallel_jobs_spinbox.setMinimum(1)
        self.parallel_jobs_spinbox.setMaximum(8)
        self.parallel_jobs_spinbox.setValue(1)
        self.parallel_jobs_spinbox.setToolTip("Number of FDS simulations to run simultaneously")
        self.parallel_jobs_spinbox.valueChanged.connect(self.update_time_estimates)
        parallel_layout.addWidget(self.parallel_jobs_spinbox)
        
        auto_parallel_btn = QPushButton("Auto-Calculate")
        auto_parallel_btn.setToolTip("Automatically calculate optimal parallel jobs based on RAM and CPU")
        auto_parallel_btn.clicked.connect(self.auto_calculate_parallel)
        auto_parallel_btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; padding: 5px; }")
        parallel_layout.addWidget(auto_parallel_btn)
        parallel_layout.addStretch()
        ram_config_layout.addLayout(parallel_layout)
        
        # Resource allocation display
        self.resource_info_label = QLabel("")
        self.resource_info_label.setStyleSheet("padding: 8px; background-color: #e8f4f8; border-radius: 5px; font-size: 11px;")
        self.resource_info_label.setWordWrap(True)
        ram_config_layout.addWidget(self.resource_info_label)
        
        layout.addWidget(ram_config_group)
        
        # Initialize parallel configuration
        self.update_parallel_config()
        
        # Simulation Time Estimate Panel
        time_estimate_group = QGroupBox("⏱️ Simulation Time Estimate")
        time_estimate_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        time_estimate_layout = QVBoxLayout()
        time_estimate_group.setLayout(time_estimate_layout)
        
        self.time_estimate_text = QTextEdit()
        self.time_estimate_text.setReadOnly(True)
        self.time_estimate_text.setMaximumHeight(150)
        self.time_estimate_text.setStyleSheet("background-color: #f8f9fa; font-family: 'Courier New'; font-size: 11px;")
        self.time_estimate_text.setPlaceholderText("Time estimates will appear here after generating FDS files...")
        time_estimate_layout.addWidget(self.time_estimate_text)
        
        layout.addWidget(time_estimate_group)
        
        # Simulation status
        status_group = QGroupBox("Simulation Status")
        status_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)
        
        self.sim_status_text = QTextEdit()
        self.sim_status_text.setReadOnly(True)
        self.sim_status_text.setPlaceholderText("Simulation status and progress will appear here...")
        self.sim_status_text.setStyleSheet("background-color: #f8f9fa; font-family: 'Courier New';")
        status_layout.addWidget(self.sim_status_text)
        
        layout.addWidget(status_group)
        
        # FDS and fds2ascii configuration
        fds_config_group = QGroupBox("🔧 FDS Tools Configuration")
        fds_config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        fds_config_layout = QVBoxLayout()
        fds_config_group.setLayout(fds_config_layout)
        
        # FDS6 Batch File
        fds6_batch_layout = QHBoxLayout()
        self.fds6_batch_label = QLabel("FDS6 Batch File:")
        fds6_batch_layout.addWidget(self.fds6_batch_label)
        self.fds6_batch_path = QLineEdit()
        self.fds6_batch_path.setPlaceholderText("Path to run_fds6.bat (e.g., C:/FDS6/run_fds6.bat)")
        fds6_batch_layout.addWidget(self.fds6_batch_path)
        
        self.browse_fds6_batch_btn = QPushButton("Browse...")
        self.browse_fds6_batch_btn.clicked.connect(self.browse_fds6_batch)
        fds6_batch_layout.addWidget(self.browse_fds6_batch_btn)
        fds_config_layout.addLayout(fds6_batch_layout)
        
        # FDS5 Batch File
        fds5_batch_layout = QHBoxLayout()
        self.fds5_batch_label = QLabel("FDS5 Batch File:")
        fds5_batch_layout.addWidget(self.fds5_batch_label)
        self.fds5_batch_path = QLineEdit()
        self.fds5_batch_path.setPlaceholderText("Path to run_fds5.bat (e.g., C:/FDS5/run_fds5.bat)")
        fds5_batch_layout.addWidget(self.fds5_batch_path)
        
        self.browse_fds5_batch_btn = QPushButton("Browse...")
        self.browse_fds5_batch_btn.clicked.connect(self.browse_fds5_batch)
        fds5_batch_layout.addWidget(self.browse_fds5_batch_btn)
        fds_config_layout.addLayout(fds5_batch_layout)
        
        # FDS Executable (Legacy - kept for backward compatibility)
        fds_exe_layout = QHBoxLayout()
        fds_exe_layout.addWidget(QLabel("FDS Executable (Direct):"))
        self.fds_exe_path = QLineEdit()
        self.fds_exe_path.setPlaceholderText("Path to fds_openmp.exe (optional if using batch files)")
        fds_exe_layout.addWidget(self.fds_exe_path)
        
        browse_fds_btn = QPushButton("Browse...")
        browse_fds_btn.clicked.connect(self.browse_fds_exe)
        fds_exe_layout.addWidget(browse_fds_btn)
        fds_config_layout.addLayout(fds_exe_layout)
        
        # fds2ascii Executable
        fds2ascii_layout = QHBoxLayout()
        fds2ascii_layout.addWidget(QLabel("fds2ascii Tool:"))
        self.fds2ascii_path = QLineEdit()
        self.fds2ascii_path.setPlaceholderText("Path to fds2ascii.exe (e.g., C:/FDS6/FDS6/bin/fds2ascii.exe)")
        fds2ascii_layout.addWidget(self.fds2ascii_path)
        
        browse_fds2ascii_btn = QPushButton("Browse...")
        browse_fds2ascii_btn.clicked.connect(self.browse_fds2ascii)
        fds2ascii_layout.addWidget(browse_fds2ascii_btn)
        fds_config_layout.addLayout(fds2ascii_layout)
        
        # Info label
        info_label = QLabel("ℹ️ fds2ascii converts SMV files to ASCII/CSV format for analysis")
        info_label.setStyleSheet("color: #7f8c8d; font-size: 11px; font-style: italic;")
        info_label.setWordWrap(True)
        fds_config_layout.addWidget(info_label)

        # ── FDS2FDB Executable ──────────────────────────────────────────────
        fds2fdb_exe_layout = QHBoxLayout()
        fds2fdb_exe_layout.addWidget(QLabel("FDS2FDB Executable:"))
        self.fds2fdb_exe_path = QLineEdit()
        self.fds2fdb_exe_path.setPlaceholderText("Path to FDS2FDB.exe  (converts FDS slice files → .fdb via CONVERT.DES)")
        fds2fdb_exe_layout.addWidget(self.fds2fdb_exe_path)
        browse_fds2fdb_exe_btn = QPushButton("Browse...")
        browse_fds2fdb_exe_btn.clicked.connect(self.browse_fds2fdb_exe)
        fds2fdb_exe_layout.addWidget(browse_fds2fdb_exe_btn)
        fds_config_layout.addLayout(fds2fdb_exe_layout)

        # ── CONVERT.DES path ────────────────────────────────────────────────
        convert_des_layout = QHBoxLayout()
        convert_des_layout.addWidget(QLabel("CONVERT.DES File:"))
        self.convert_des_path = QLineEdit()
        self.convert_des_path.setPlaceholderText("Path to CONVERT.DES  (FDS_ID, axis direction, slice file numbers, unit conversion factors)")
        convert_des_layout.addWidget(self.convert_des_path)
        browse_convert_des_btn = QPushButton("Browse...")
        browse_convert_des_btn.clicked.connect(self.browse_convert_des)
        convert_des_layout.addWidget(browse_convert_des_btn)
        fds_config_layout.addLayout(convert_des_layout)

        # ── CONVERT.DES live preview ─────────────────────────────────────────
        self.convert_des_preview = QLabel("ℹ️  CONVERT.DES not loaded — browse to set FDS_ID, axis, slice numbers and unit factors")
        self.convert_des_preview.setWordWrap(True)
        self.convert_des_preview.setStyleSheet(
            "color: #7f8c8d; font-size: 11px; font-style: italic; "
            "margin-left: 4px; padding: 3px; background: #f8f9fa; border-radius: 3px;")
        fds_config_layout.addWidget(self.convert_des_preview)

        layout.addWidget(fds_config_group)
        
        # Simulation control
        sim_control_group = QGroupBox("Simulation Control")
        sim_control_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        sim_control_layout = QVBoxLayout()
        sim_control_group.setLayout(sim_control_layout)
        
        # Progress bar
        self.sim_progress_bar = QProgressBar()
        self.sim_progress_bar.setValue(0)
        sim_control_layout.addWidget(self.sim_progress_bar)
        
        # Control buttons
        control_btn_layout = QHBoxLayout()
        
        self.run_sim_btn = QPushButton("▶️ Run FDS Simulations")
        self.run_sim_btn.clicked.connect(self.run_fds_simulations)
        self.run_sim_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; padding: 12px; font-weight: bold; font-size: 14px; }")
        control_btn_layout.addWidget(self.run_sim_btn)
        
        self.stop_sim_btn = QPushButton("⏹️ Stop Simulations")
        self.stop_sim_btn.clicked.connect(self.stop_fds_simulations)
        self.stop_sim_btn.setEnabled(False)
        self.stop_sim_btn.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; padding: 12px; }")
        control_btn_layout.addWidget(self.stop_sim_btn)
        
        sim_control_layout.addLayout(control_btn_layout)
        layout.addWidget(sim_control_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.open_batch_btn = QPushButton("📄 Open Batch Script Location")
        self.open_batch_btn.clicked.connect(self.open_batch_script)
        self.open_batch_btn.setStyleSheet("QPushButton { background-color: #95a5a6; color: white; padding: 10px; }")
        
        self.check_outputs_btn = QPushButton("🔍 Check Simulation Outputs")
        self.check_outputs_btn.clicked.connect(self.check_simulation_outputs)
        self.check_outputs_btn.setStyleSheet("QPushButton { background-color: #16a085; color: white; padding: 10px; }")
        
        self.convert_to_fdb_btn = QPushButton("🗄️ Run FDS2FDB → .fdb")
        self.convert_to_fdb_btn.clicked.connect(self.convert_smv_to_fdb_with_exe)
        self.convert_to_fdb_btn.setStyleSheet("QPushButton { background-color: #2980b9; color: white; padding: 10px; }")

        self.run_fds2ascii_btn = QPushButton("📄 Run fds2ascii → ASCII/CSV")
        self.run_fds2ascii_btn.clicked.connect(self.run_fds2ascii_conversion)
        self.run_fds2ascii_btn.setStyleSheet("QPushButton { background-color: #8e44ad; color: white; padding: 10px; }")

        button_layout.addWidget(self.open_batch_btn)
        button_layout.addWidget(self.check_outputs_btn)
        button_layout.addWidget(self.convert_to_fdb_btn)
        button_layout.addWidget(self.run_fds2ascii_btn)
        layout.addLayout(button_layout)
        
        layout.addStretch()
        
        self.tabs.addTab(scroll, "3. FDS Simulation")
    
    def create_tab4_evc_fed_analysis(self):
        """Tab 4: EVC/FED Analysis — Calculation of FED
        Layout:
          ┌─ File Loader bar (FDS + FDB, auto-scan + manual browse) ──────────┐
          │  [Auto-Scan Output Folder]  FDS: [path...]  [Browse]              │
          │                             FDB: [path...]  [Browse]              │
          └────────────────────────────────────────────────────────────────────┘
          ┌─ Inner sub-tabs ───────────────────────────────────────────────────┐
          │  1.터널기본정보  2.Traffic_Man  3.HRR_EVAC  4.시뮬레이션  5.MDB  │
          └────────────────────────────────────────────────────────────────────┘
          (no bottom action panel — Generate EVC / Run Analysis live in sub-tab)
        """
        # ── style constants ───────────────────────────────────────────────────
        GS  = ("QGroupBox { font-weight: bold; font-size: 12px; "
               "border: 1px solid #bdc3c7; border-radius: 5px; "
               "margin-top: 10px; padding-top: 8px; }"
               "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; "
               "padding: 0 6px; left: 10px; }")
        HDR = "font-size: 15px; font-weight: bold; color: #1a252f;"
        LBL = ("QLabel { font-size: 12px; font-weight: bold; color: #1a252f; "
               "padding-right: 4px; }")
        # Spin-box: large enough to show ▲▼ buttons clearly
        SB_H = 32          # fixed height for all spin widgets
        SB_W = 160         # fixed width
        FONT_SZ = "12px"
        DSB_RO_SS = (f"QDoubleSpinBox {{ background:#eaf4fb; border:1px solid #aed6f1; "
                     f"border-radius:3px; font-size:{FONT_SZ}; padding:2px 4px; }}")
        DSB_RW_SS = (f"QDoubleSpinBox {{ background:white; border:1px solid #95a5a6; "
                     f"border-radius:3px; font-size:{FONT_SZ}; padding:2px 4px; }}")
        SB_RW_SS  = (f"QSpinBox {{ background:white; border:1px solid #95a5a6; "
                     f"border-radius:3px; font-size:{FONT_SZ}; padding:2px 4px; }}")
        LE_SS = (f"QLineEdit {{ background:white; border:1px solid #95a5a6; "
                 f"border-radius:3px; font-size:{FONT_SZ}; padding:3px 4px; }}")
        LE_RO_SS = (f"QLineEdit {{ background:#ecf0f1; border:1px solid #bdc3c7; "
                    f"border-radius:3px; font-size:11px; padding:3px 4px; color:#555; }}")

        # ── widget factories ──────────────────────────────────────────────────
        def _lbl(txt):
            w = QLabel(txt); w.setStyleSheet(LBL)
            w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            w.setMinimumWidth(120)
            return w

        def _dsb(vmin, vmax, val, dec=2, ro=False, unit="", step=None):
            w = QDoubleSpinBox()
            w.setRange(vmin, vmax); w.setValue(val); w.setDecimals(dec)
            if unit: w.setSuffix(f" {unit}")
            if step is not None: w.setSingleStep(step)
            w.setFixedHeight(SB_H); w.setMinimumWidth(SB_W)
            if ro:
                w.setReadOnly(True); w.setStyleSheet(DSB_RO_SS)
                w.setButtonSymbols(QDoubleSpinBox.NoButtons)
            else:
                w.setStyleSheet(DSB_RW_SS)
            return w

        def _sb(vmin, vmax, val, unit="", step=1):
            w = QSpinBox(); w.setRange(vmin, vmax); w.setValue(val)
            w.setSingleStep(step)
            if unit: w.setSuffix(f" {unit}")
            w.setFixedHeight(SB_H); w.setMinimumWidth(SB_W)
            w.setStyleSheet(SB_RW_SS)
            return w

        def _le(txt="", ph="", ro=False):
            w = QLineEdit(txt); w.setPlaceholderText(ph)
            w.setFixedHeight(SB_H)
            if ro: w.setReadOnly(True); w.setStyleSheet(LE_RO_SS)
            else:  w.setStyleSheet(LE_SS)
            return w

        def _row_pair(gl, row, lbl1, w1, lbl2=None, w2=None):
            """Add a label+widget pair (and optional second pair) to a QGridLayout row."""
            gl.addWidget(_lbl(lbl1), row, 0)
            gl.addWidget(w1,         row, 1)
            if lbl2 and w2:
                gl.addWidget(_lbl(lbl2), row, 2)
                gl.addWidget(w2,         row, 3)

        # ── outer container (no scroll — inner tabs handle their own scroll) ──
        outer_tab = QWidget()
        outer_scroll = QScrollArea()
        outer_scroll.setWidgetResizable(True)
        outer_scroll.setWidget(outer_tab)
        outer_layout = QVBoxLayout(outer_tab)
        outer_layout.setContentsMargins(10, 8, 10, 8)
        outer_layout.setSpacing(6)

        # ── Title ─────────────────────────────────────────────────────────────
        title_lbl = QLabel("📊  Calculation of FED  —  EVC / FED Analysis")
        title_lbl.setStyleSheet(HDR)
        outer_layout.addWidget(title_lbl)

        # ══════════════════════════════════════════════════════════════════════
        # FILE LOADER PANEL  (replaces the old bottom action group)
        # ══════════════════════════════════════════════════════════════════════
        file_grp = QGroupBox("📂  Input Files  —  Auto-scan or Browse")
        file_grp.setStyleSheet(GS)
        file_gl = QGridLayout()
        file_gl.setHorizontalSpacing(8)
        file_gl.setVerticalSpacing(8)
        file_gl.setContentsMargins(10, 8, 10, 8)
        file_gl.setColumnMinimumWidth(0, 180)   # label / button col
        file_gl.setColumnMinimumWidth(1, 0)     # path field (stretches)
        file_gl.setColumnMinimumWidth(2, 0)     # path field cont.
        file_gl.setColumnMinimumWidth(3, 110)   # browse button col
        file_gl.setColumnStretch(0, 0)
        file_gl.setColumnStretch(1, 1)
        file_gl.setColumnStretch(2, 1)
        file_gl.setColumnStretch(3, 0)
        file_grp.setLayout(file_gl)

        # Row 0: auto-scan button + status
        self.evc_autoscan_btn = QPushButton("🔍  Auto-Scan Output Folder")
        self.evc_autoscan_btn.setFixedHeight(32)
        self.evc_autoscan_btn.setStyleSheet(
            "QPushButton { background:#2980b9; color:white; font-weight:bold; "
            "font-size:12px; padding:6px 14px; border-radius:4px; }"
            "QPushButton:hover { background:#3498db; }")
        self.evc_autoscan_btn.clicked.connect(self.evc_autoscan_output_folder)
        file_gl.addWidget(self.evc_autoscan_btn, 0, 0, 1, 1)

        self.evc_scan_status = QLabel("Not scanned yet")
        self.evc_scan_status.setStyleSheet("font-size:11px; color:#555; padding-left:8px;")
        file_gl.addWidget(self.evc_scan_status, 0, 1, 1, 3)

        # Row 1: FDS file
        file_gl.addWidget(_lbl("FDS Input File:"), 1, 0)
        self.evc_fds_path_le = _le(ph="Auto-detected or browse…", ro=True)
        file_gl.addWidget(self.evc_fds_path_le, 1, 1, 1, 2)
        btn_fds = QPushButton("📂 Browse FDS")
        btn_fds.setStyleSheet("QPushButton{background:#1abc9c;color:white;font-weight:bold;"
                              "padding:5px 10px;border-radius:4px;}")
        btn_fds.clicked.connect(self.evc_browse_fds)
        file_gl.addWidget(btn_fds, 1, 3)

        # Row 2: FDB file
        file_gl.addWidget(_lbl("FDB Database:"), 2, 0)
        self.evc_fdb_path_le = _le(ph="Auto-detected or browse…", ro=True)
        file_gl.addWidget(self.evc_fdb_path_le, 2, 1, 1, 2)
        btn_fdb = QPushButton("📂 Browse FDB")
        btn_fdb.setStyleSheet("QPushButton{background:#8e44ad;color:white;font-weight:bold;"
                              "padding:5px 10px;border-radius:4px;}")
        btn_fdb.clicked.connect(self.evc_browse_fdb)
        file_gl.addWidget(btn_fdb, 2, 3)

        # Row 3: action buttons
        self.generate_evc_btn = QPushButton("⚙️  Generate EVC File")
        self.generate_evc_btn.setStyleSheet(
            "QPushButton{background:#27ae60;color:white;font-weight:bold;"
            "font-size:12px;padding:7px 16px;border-radius:4px;}"
            "QPushButton:hover{background:#2ecc71;}")
        self.generate_evc_btn.clicked.connect(self.generate_evc_files)

        self.run_evc_btn = QPushButton("▶  Run EVC / FED Analysis")
        self.run_evc_btn.setStyleSheet(
            "QPushButton{background:#e67e22;color:white;font-weight:bold;"
            "font-size:12px;padding:7px 16px;border-radius:4px;}"
            "QPushButton:hover{background:#f39c12;}")
        self.run_evc_btn.clicked.connect(self.run_evc_analysis)

        self.import_ascii_btn = QPushButton("📥  Load ASCII Files")
        self.import_ascii_btn.setStyleSheet(
            "QPushButton{background:#3498db;color:white;font-weight:bold;"
            "font-size:12px;padding:7px 16px;border-radius:4px;}"
            "QPushButton:hover{background:#5dade2;}")
        self.import_ascii_btn.clicked.connect(self.import_ascii_files)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.evc_autoscan_btn)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.import_ascii_btn)
        btn_row.addWidget(self.generate_evc_btn)
        btn_row.addWidget(self.run_evc_btn)
        btn_row.addStretch()
        file_gl.addLayout(btn_row, 3, 0, 1, 4)

        # Status log (compact, dark terminal style)
        self.evc_status_text = QTextEdit()
        self.evc_status_text.setReadOnly(True)
        self.evc_status_text.setFixedHeight(70)
        self.evc_status_text.setStyleSheet(
            "background:#1e272e; color:#dfe6e9; "
            "font-family:'Courier New'; font-size:10px; border-radius:3px;")
        file_gl.addWidget(self.evc_status_text, 4, 0, 1, 4)

        # Hidden scenario table (kept for ASCII import compatibility)
        self.scenario_table = QTableWidget(0, 4)
        self.scenario_table.setHorizontalHeaderLabels(
            ["Scenario (CHID)", "HRR", "Position", "ASCII Files"])
        self.scenario_table.setMaximumHeight(0)   # hidden by default
        file_gl.addWidget(self.scenario_table, 5, 0, 1, 4)

        outer_layout.addWidget(file_grp)

        # ══════════════════════════════════════════════════════════════════════
        # INNER SUB-TABS
        # ══════════════════════════════════════════════════════════════════════
        self.evc_inner_tabs = QTabWidget()
        self.evc_inner_tabs.setStyleSheet(
            "QTabBar::tab { min-width: 115px; padding: 7px 10px; "
            "font-size: 12px; font-weight: bold; }"
            "QTabBar::tab:selected { background:#2980b9; color:white; border-radius:3px; }"
            "QTabWidget::pane { border: 1px solid #bdc3c7; }")
        outer_layout.addWidget(self.evc_inner_tabs, stretch=1)

        # ─────────────────────────────────────────────────────────────────────
        # GRID HELPER: compact row spacing, consistent column widths
        # ─────────────────────────────────────────────────────────────────────
        def _make_gl():
            gl = QGridLayout()
            gl.setHorizontalSpacing(12)
            gl.setVerticalSpacing(7)
            gl.setContentsMargins(10, 8, 10, 8)
            gl.setColumnMinimumWidth(0, 210)   # label col left — wide enough for long labels
            gl.setColumnMinimumWidth(1, SB_W)  # widget col left
            gl.setColumnMinimumWidth(2, 210)   # label col right
            gl.setColumnMinimumWidth(3, SB_W)  # widget col right
            gl.setColumnStretch(0, 0)          # labels: fixed
            gl.setColumnStretch(1, 1)          # widgets: stretch equally
            gl.setColumnStretch(2, 0)
            gl.setColumnStretch(3, 1)
            return gl

        # ══════════════════════════════════════════════════════════════════════
        # SUB-TAB 1 — 터널기본정보  (Tunnel Basic Info)
        # ══════════════════════════════════════════════════════════════════════
        t1 = QWidget(); t1s = QScrollArea()
        t1s.setWidgetResizable(True); t1s.setWidget(t1)
        t1l = QVBoxLayout(t1); t1l.setSpacing(10); t1l.setContentsMargins(8, 8, 8, 8)

        # ── Tunnel Geometry ───────────────────────────────────────────────────
        geo_grp = QGroupBox("🏗️  Tunnel Geometry  (auto-populated from FDS)")
        geo_grp.setStyleSheet(GS); geo_gl = _make_gl(); geo_grp.setLayout(geo_gl)
        r = 0
        self.evc_tunnel_length = _dsb(10,20000,710.0,1,ro=True,unit="m",step=1)
        self.evc_tunnel_width  = _dsb(2,50,10.83,2,ro=True,unit="m",step=0.01)
        _row_pair(geo_gl, r, "Tunnel Length (터널길이):", self.evc_tunnel_length,
                             "Tunnel Width (터널폭):",    self.evc_tunnel_width); r+=1

        self.evc_tunnel_height = _dsb(2,30,6.77,2,ro=True,unit="m",step=0.01)
        self.evc_cross_area    = _dsb(1,5000,73.37,2,ro=True,unit="m²",step=0.1)
        _row_pair(geo_gl, r, "Tunnel Height (터널높이):", self.evc_tunnel_height,
                             "Cross-section Area:",       self.evc_cross_area); r+=1

        self.evc_num_lanes    = _dsb(1,10,2.0,1,step=0.5,unit="lanes")
        self.evc_traffic_dir  = QComboBox()
        self.evc_traffic_dir.addItems(["One-way (편도)", "Two-way (양방향)"])
        self.evc_traffic_dir.setFixedHeight(SB_H)
        geo_gl.addWidget(_lbl("Number of Lanes (차선수):"), r, 0)
        geo_gl.addWidget(self.evc_num_lanes, r, 1)
        geo_gl.addWidget(_lbl("Traffic Direction (교통방향):"), r, 2)
        geo_gl.addWidget(self.evc_traffic_dir, r, 3); r+=1

        self.evc_sim_duration = _dsb(60,7200,1200.0,0,ro=True,unit="s",step=60)
        self.evc_ambient_temp = _dsb(-20,60,20.0,1,ro=True,unit="°C",step=1)
        _row_pair(geo_gl, r, "Simulation Duration (TWFIN):", self.evc_sim_duration,
                             "Ambient Temperature (TMPA):", self.evc_ambient_temp)
        t1l.addWidget(geo_grp)

        # ── Fire Parameters ────────────────────────────────────────────────────
        fire_grp = QGroupBox("🔥  Fire Parameters  (auto-populated from FDS)")
        fire_grp.setStyleSheet(GS); fire_gl = _make_gl(); fire_grp.setLayout(fire_gl)
        r = 0
        self.evc_fire_x   = _dsb(0,20000,356.0,2,ro=True,unit="m",step=1)
        self.evc_fire_y   = _dsb(0,100,5.53,2,ro=True,unit="m",step=0.1)
        _row_pair(fire_gl, r, "Fire Location X:", self.evc_fire_x,
                             "Fire Location Y:", self.evc_fire_y); r+=1

        self.evc_fire_z   = _dsb(0,50,1.25,2,ro=True,unit="m",step=0.1)
        self.evc_peak_hrr = _dsb(0,500,17.3,2,ro=True,unit="MW",step=1)
        _row_pair(fire_gl, r, "Fire Location Z:", self.evc_fire_z,
                             "Peak HRR:", self.evc_peak_hrr); r+=1

        self.evc_soot_yield = _dsb(0,1,0.133,4,ro=True,unit="kg/kg",step=0.001)
        self.evc_co_yield   = _dsb(0,1,0.168,4,ro=True,unit="kg/kg",step=0.001)
        _row_pair(fire_gl, r, "Soot Yield:", self.evc_soot_yield,
                             "CO Yield:", self.evc_co_yield); r+=1

        self.evc_rad_frac = _dsb(0,1,0.30,3,ro=True,step=0.01)
        self.evc_mass_ext = _dsb(0,20000,8700.0,1,ro=True,unit="m²/kg",step=100)
        _row_pair(fire_gl, r, "Radiative Fraction:", self.evc_rad_frac,
                             "Mass Extinction Coeff:", self.evc_mass_ext)
        t1l.addWidget(fire_grp)

        # ── Vehicle Distribution Table ─────────────────────────────────────────
        veh_grp = QGroupBox("🚗  Vehicle & Occupant Distribution  (교통량 및 자동차점유)")
        veh_grp.setStyleSheet(GS); veh_layout = QVBoxLayout(veh_grp)
        self.evc_vehicle_table = QTableWidget(7, 8)
        self.evc_vehicle_table.setHorizontalHeaderLabels([
            "Category","PC (승용차)","BS (버스)","BL (대형버스)",
            "TS (소형화물)","TM (중형화물)","TL (대형화물)","Total"])
        self.evc_vehicle_table.setVerticalHeaderLabels([
            "Vehicle % (차량비율)","PCU Factor","Vehicles in tunnel",
            "Occupants/vehicle","Total occupants","Idle density (veh/km)","Speed (km/h)"])
        for r_i, row_data in enumerate([
            ["90.13","0","0.89","8.35","0.38","0.25","100"],
            ["1.0","2.0","1.5","1.0","1.5","1.5","—"],
            ["4.34","0","0.18","0.45","0.08","0.05","5.1"],
            ["1.5","30","30","2","2","1","—"],
            ["6.51","0","5.4","0.9","0.16","0.05","13.02"],
            ["150","150","150","150","150","150","—"],
            ["5","5","5","5","5","5","—"],
        ]):
            for c_i, val in enumerate(row_data):
                itm = QTableWidgetItem(val); itm.setTextAlignment(Qt.AlignCenter)
                self.evc_vehicle_table.setItem(r_i, c_i+1, itm)
        self.evc_vehicle_table.resizeColumnsToContents()
        self.evc_vehicle_table.setMinimumHeight(210)
        veh_layout.addWidget(self.evc_vehicle_table)
        t1l.addWidget(veh_grp)
        t1l.addStretch()
        self.evc_inner_tabs.addTab(t1s, "1. 터널기본정보")

        # ══════════════════════════════════════════════════════════════════════
        # SUB-TAB 2 — Traffic_Man
        # ══════════════════════════════════════════════════════════════════════
        t2 = QWidget(); t2s = QScrollArea()
        t2s.setWidgetResizable(True); t2s.setWidget(t2)
        t2l = QVBoxLayout(t2); t2l.setSpacing(10); t2l.setContentsMargins(8, 8, 8, 8)

        tc_grp = QGroupBox("🚦  Traffic Control Parameters  (교통 제어 매개변수)")
        tc_grp.setStyleSheet(GS); tc_gl = _make_gl(); tc_grp.setLayout(tc_gl)
        r = 0
        self.evc_max_vehicles   = _dsb(10,5000,150.0,0,unit="veh",step=10)
        self.evc_normal_traffic = _dsb(100,10000,1600.0,0,unit="veh/h",step=100)
        _row_pair(tc_gl, r, "Max vehicles — congestion:", self.evc_max_vehicles,
                            "Normal hourly traffic:", self.evc_normal_traffic); r+=1
        self.evc_fire_speed   = _dsb(0,130,5.0,1,unit="km/h",step=1)
        self.evc_normal_speed = _dsb(0,130,80.0,1,unit="km/h",step=5)
        _row_pair(tc_gl, r, "Speed during fire:", self.evc_fire_speed,
                            "Normal driving speed:", self.evc_normal_speed)
        t2l.addWidget(tc_grp)

        zone_grp = QGroupBox("📍  Zone Distribution Table  (Zone별 위치 및 정체차량수)")
        zone_grp.setStyleSheet(GS); zone_layout = QVBoxLayout(zone_grp)
        zh = QHBoxLayout()
        _za = QPushButton("➕ Add Zone"); _za.setFixedWidth(110)
        _zd = QPushButton("➖ Remove");  _zd.setFixedWidth(110)
        zh.addWidget(_za); zh.addWidget(_zd); zh.addStretch()
        zone_layout.addLayout(zh)
        self.evc_zone_table = QTableWidget(5, 11)
        self.evc_zone_table.setHorizontalHeaderLabels(
            ["Zone","From (m)","To (m)","Exit Pt","PC","BS","BL","TS","TM","TL","SUM"])
        for r_i, rd in enumerate([
            ["1","0.0","68.33","0","2","0","0","0","0","0","2"],
            ["2","68.33","180.0","205","3","0","0","1","0","0","4"],
            ["3","180.0","256.25","205","2","0","0","0","0","0","2"],
            ["4","256.25","330.0","410","2","0","0","1","0","0","3"],
            ["5","330.0","410.0","410","2","0","0","0","0","0","2"],
        ]):
            for c_i, v in enumerate(rd):
                itm = QTableWidgetItem(v); itm.setTextAlignment(Qt.AlignCenter)
                self.evc_zone_table.setItem(r_i, c_i, itm)
        _za.clicked.connect(lambda: self.evc_zone_table.insertRow(self.evc_zone_table.rowCount()))
        _zd.clicked.connect(lambda: self.evc_zone_table.removeRow(self.evc_zone_table.currentRow())
                            if self.evc_zone_table.currentRow() >= 0 else None)
        self.evc_zone_table.resizeColumnsToContents()
        self.evc_zone_table.setMinimumHeight(180)
        zone_layout.addWidget(self.evc_zone_table)
        t2l.addWidget(zone_grp)
        t2l.addStretch()
        self.evc_inner_tabs.addTab(t2s, "2. Traffic_Man")

        # ══════════════════════════════════════════════════════════════════════
        # SUB-TAB 3 — HRR_EVAC
        # ══════════════════════════════════════════════════════════════════════
        t3 = QWidget(); t3s = QScrollArea()
        t3s.setWidgetResizable(True); t3s.setWidget(t3)
        t3l = QVBoxLayout(t3); t3l.setSpacing(10); t3l.setContentsMargins(8, 8, 8, 8)

        ps_grp = QGroupBox("⚙️  Program Settings  (프로그램설정)")
        ps_grp.setStyleSheet(GS); ps_gl = _make_gl(); ps_grp.setLayout(ps_gl)
        r = 0
        self.evc_sim_interval = _dsb(0.1,60,2.0,1,unit="s",step=0.5)
        self.evc_monitor_pt   = _sb(1,10000,200,step=10)
        _row_pair(ps_gl, r, "Simulation Time Interval:", self.evc_sim_interval,
                            "Monitoring Point ID:", self.evc_monitor_pt); r+=1
        self.evc_monitor_save = _dsb(1,300,10.0,1,unit="s",step=5)
        ps_gl.addWidget(_lbl("Monitoring Data Save Interval:"), r, 0)
        ps_gl.addWidget(self.evc_monitor_save, r, 1)
        t3l.addWidget(ps_grp)

        fp_grp = QGroupBox("🔥  Fire Point & Evacuation Zone  (화재위치 및 대피구역)")
        fp_grp.setStyleSheet(GS); fp_gl = _make_gl(); fp_grp.setLayout(fp_gl)
        r = 0
        self.evc_fp_evc    = _dsb(0,20000,68.33,2,unit="m",step=1)
        self.evc_fp_fdb    = _dsb(0,20000,205.0,2,unit="m",step=1)
        _row_pair(fp_gl, r, "EVC Fire Point:", self.evc_fp_evc,
                            "FDB Fire Point:", self.evc_fp_fdb); r+=1
        self.evc_zone_factor = _dsb(0.0,1.0,0.75,3,step=0.05)
        self.evc_num_fp      = _sb(1,100,6,step=1)
        _row_pair(fp_gl, r, "Zone Divide Factor:", self.evc_zone_factor,
                            "Number of Fire Points:", self.evc_num_fp); r+=1
        fp_gl.addWidget(_lbl("Fire Intensity Scenarios:"), r, 0)
        fi_row = QHBoxLayout()
        self.evc_fi_20  = QCheckBox("20 MW"); self.evc_fi_20.setChecked(True)
        self.evc_fi_50  = QCheckBox("50 MW")
        self.evc_fi_100 = QCheckBox("100 MW")
        fi_row.addWidget(self.evc_fi_20); fi_row.addWidget(self.evc_fi_50)
        fi_row.addWidget(self.evc_fi_100); fi_row.addStretch()
        fp_gl.addLayout(fi_row, r, 1, 1, 3)
        t3l.addWidget(fp_grp)

        fpm_grp = QGroupBox("📋  Fire Point Mapping  (화재지점 매핑)")
        fpm_grp.setStyleSheet(GS); fpm_layout = QVBoxLayout(fpm_grp)
        fh2 = QHBoxLayout()
        _fa = QPushButton("➕ Add Row"); _fa.setFixedWidth(100)
        _fd = QPushButton("➖ Remove");  _fd.setFixedWidth(100)
        fh2.addWidget(_fa); fh2.addWidget(_fd); fh2.addStretch()
        fpm_layout.addLayout(fh2)
        self.evc_fpm_table = QTableWidget(6, 5)
        self.evc_fpm_table.setHorizontalHeaderLabels(["No.","Fire_pt","MDB_pt","FDS_pt","X (m)"])
        for i in range(6):
            for j, v in enumerate([str(i+1),str(i+1),str(i+1),str(i+1),
                                    str(round(68.33+i*28.0,2))]):
                itm = QTableWidgetItem(v); itm.setTextAlignment(Qt.AlignCenter)
                self.evc_fpm_table.setItem(i, j, itm)
        _fa.clicked.connect(lambda: self.evc_fpm_table.insertRow(self.evc_fpm_table.rowCount()))
        _fd.clicked.connect(lambda: self.evc_fpm_table.removeRow(self.evc_fpm_table.currentRow())
                            if self.evc_fpm_table.currentRow() >= 0 else None)
        self.evc_fpm_table.resizeColumnsToContents()
        self.evc_fpm_table.setMinimumHeight(175)
        fpm_layout.addWidget(self.evc_fpm_table)
        t3l.addWidget(fpm_grp)

        pmt_grp = QGroupBox("🚶  Pre-movement & Evacuation Zones  (대피전시간 및 대피구역)")
        pmt_grp.setStyleSheet(GS); pmt_layout = QVBoxLayout(pmt_grp)
        ph2 = QHBoxLayout()
        _pa = QPushButton("➕ Add Row"); _pa.setFixedWidth(100)
        _pd = QPushButton("➖ Remove");  _pd.setFixedWidth(100)
        ph2.addWidget(_pa); ph2.addWidget(_pd); ph2.addStretch()
        pmt_layout.addLayout(ph2)
        self.evc_pmt_table = QTableWidget(3, 4)
        self.evc_pmt_table.setHorizontalHeaderLabels(
            ["From (m)","To (m)","Exit Point (m)","Pre-movement (s)"])
        for r_i, rd in enumerate([["0.0","68.33","0","180"],
                                   ["68.33","256.25","205","180"],
                                   ["256.25","410.0","410","180"]]):
            for c_i, v in enumerate(rd):
                itm = QTableWidgetItem(v); itm.setTextAlignment(Qt.AlignCenter)
                self.evc_pmt_table.setItem(r_i, c_i, itm)
        _pa.clicked.connect(lambda: self.evc_pmt_table.insertRow(self.evc_pmt_table.rowCount()))
        _pd.clicked.connect(lambda: self.evc_pmt_table.removeRow(self.evc_pmt_table.currentRow())
                            if self.evc_pmt_table.currentRow() >= 0 else None)
        self.evc_pmt_table.resizeColumnsToContents()
        self.evc_pmt_table.setMinimumHeight(120)
        pmt_layout.addWidget(self.evc_pmt_table)
        t3l.addWidget(pmt_grp)
        t3l.addStretch()
        self.evc_inner_tabs.addTab(t3s, "3. HRR_EVAC")


        # ══════════════════════════════════════════════════════════════════════
        # SUB-TAB 4 — 시뮬레이션  (Evacuation & FED Simulator)
        # ══════════════════════════════════════════════════════════════════════
        t4 = QWidget()
        t4l_main = QHBoxLayout(t4)
        t4l_main.setContentsMargins(6, 6, 6, 6)
        t4l_main.setSpacing(8)

        # ─── LEFT: scrollable control panel ──────────────────────────────────
        # Panel is wide enough for labels + full-size input boxes.
        #   col 0 (fixed, right-aligned label) | col 1 (stretching input widget)
        t4_ctrl = QWidget()
        t4_ctrl.setMinimumWidth(420)
        t4_ctrl.setMaximumWidth(540)
        t4_ctrl_scroll = QScrollArea()
        t4_ctrl_scroll.setWidgetResizable(True)
        t4_ctrl_scroll.setWidget(t4_ctrl)
        t4_ctrl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        t4l = QVBoxLayout(t4_ctrl)
        t4l.setSpacing(8)
        t4l.setContentsMargins(6, 6, 6, 6)

        # ── 2-column grid factory for the narrow left panel ──────────────────
        def _make_gl2():
            """2-column grid: col-0 = left-aligned label (auto), col-1 = input (auto)."""
            gl = QGridLayout()
            gl.setHorizontalSpacing(6)
            gl.setVerticalSpacing(6)
            gl.setContentsMargins(8, 8, 8, 8)
            gl.setColumnMinimumWidth(0, 0)     # label column — auto width
            gl.setColumnMinimumWidth(1, 0)     # input column — auto width
            gl.setColumnStretch(0, 0)          # label: no stretch
            gl.setColumnStretch(1, 0)          # input: no stretch
            return gl

        def _row2(gl, row, label_txt, widget):
            """Add one label + widget row to a 2-column grid (left-aligned)."""
            lw = QLabel(label_txt)
            lw.setStyleSheet(LBL)
            lw.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            widget.setFixedWidth(140)          # consistent input width
            gl.addWidget(lw,     row, 0, Qt.AlignLeft)
            gl.addWidget(widget, row, 1, Qt.AlignLeft)

        # ── Fire & Combustion Parameters ──────────────────────────────────────
        fh_grp = QGroupBox("🌡️  Fire & Combustion Parameters")
        fh_grp.setStyleSheet(GS)
        fh_gl = _make_gl2()
        fh_grp.setLayout(fh_gl)
        r = 0

        self.evc_heat_method = QComboBox()
        self.evc_heat_method.addItems(["by Equation", "by MDB"])
        self.evc_heat_method.setFixedHeight(SB_H)
        _row2(fh_gl, r, "Heat Method:", self.evc_heat_method); r += 1

        self.evc_design_fire = _dsb(1, 500, 20.0, 1, unit="MW", step=5)
        _row2(fh_gl, r, "Design Fire:", self.evc_design_fire); r += 1

        self.evc_growth_rate = _dsb(0.001, 10.0, 0.15, 4, step=0.01)
        _row2(fh_gl, r, "Growth Rate (α):", self.evc_growth_rate); r += 1

        self.evc_inertia = _dsb(0, 1, 0.001, 4, step=0.0001)
        _row2(fh_gl, r, "Inertia Layer:", self.evc_inertia); r += 1

        self.evc_impact = _dsb(0, 1000, 32.0, 2, unit="GJ", step=1)
        _row2(fh_gl, r, "Impact Upper Layer:", self.evc_impact); r += 1

        self.evc_air_vel = _dsb(0, 20, 2.5, 2, unit="m/s", step=0.1)
        _row2(fh_gl, r, "Air Velocity:", self.evc_air_vel); r += 1

        self.evc_peak_hrr_s4 = _dsb(1, 500, 20.0, 1, unit="MW", step=1)
        _row2(fh_gl, r, "Peak HRR:", self.evc_peak_hrr_s4); r += 1

        self.evc_soot_yield_s4 = _dsb(0, 1, 0.10, 3, step=0.01)
        _row2(fh_gl, r, "Soot Yield:", self.evc_soot_yield_s4); r += 1

        self.evc_co_yield_s4 = _dsb(0, 1, 0.05, 3, step=0.005)
        _row2(fh_gl, r, "CO Yield:", self.evc_co_yield_s4); r += 1

        self.evc_mass_ext_s4 = _dsb(0, 1e5, 8700.0, 0, step=100)
        _row2(fh_gl, r, "Mass Extinction Coeff:", self.evc_mass_ext_s4); r += 1

        self.evc_rad_frac_s4 = _dsb(0, 1, 0.35, 3, step=0.01)
        _row2(fh_gl, r, "Radiative Fraction:", self.evc_rad_frac_s4)
        t4l.addWidget(fh_grp)

        # ── Simulation Settings ────────────────────────────────────────────────
        sim_grp = QGroupBox("⚙️  Simulation Settings  (시뮬레이션 설정)")
        sim_grp.setStyleSheet(GS)
        sim_gl = _make_gl2()
        sim_grp.setLayout(sim_gl)
        r = 0

        self.evc_sim_t_end = _dsb(60, 7200, 600.0, 0, unit="s", step=60)
        _row2(sim_gl, r, "Simulation End Time:", self.evc_sim_t_end); r += 1

        self.evc_sim_dt = _dsb(0.1, 60, 2.0, 1, unit="s", step=0.5)
        _row2(sim_gl, r, "Time Step (dt):", self.evc_sim_dt); r += 1

        self.evc_fire_x_s4 = _dsb(-500, 5000, 205.0, 2, unit="m", step=1)
        _row2(sim_gl, r, "Fire X Position:", self.evc_fire_x_s4); r += 1

        self.evc_fire_y_s4 = _dsb(-50, 50, 0.0, 2, unit="m", step=0.1)
        _row2(sim_gl, r, "Fire Y Position:", self.evc_fire_y_s4); r += 1

        self.evc_fire_z_s4 = _dsb(-10, 50, 0.0, 2, unit="m", step=0.1)
        _row2(sim_gl, r, "Fire Z Position:", self.evc_fire_z_s4); r += 1

        self.evc_monitor_pt_s4 = _sb(1, 10000, 200, step=10)
        _row2(sim_gl, r, "Monitoring Point ID:", self.evc_monitor_pt_s4); r += 1

        self.evc_sim_interval_s4 = _dsb(0.1, 60, 2.0, 1, unit="s", step=0.5)
        _row2(sim_gl, r, "Sim. Time Interval:", self.evc_sim_interval_s4); r += 1

        self.evc_monitor_save_s4 = _dsb(1, 300, 10.0, 1, unit="s", step=5)
        _row2(sim_gl, r, "Monitor Save Interval:", self.evc_monitor_save_s4)
        t4l.addWidget(sim_grp)

        # ── Evacuation Strategy checkboxes ────────────────────────────────────
        es_grp = QGroupBox("🏃  Evacuation Strategy  (대피전략 선택)")
        es_grp.setStyleSheet(GS)
        es_gl = QGridLayout()
        es_gl.setHorizontalSpacing(10)
        es_gl.setVerticalSpacing(6)
        es_gl.setContentsMargins(8, 8, 8, 8)
        es_grp.setLayout(es_gl)
        CB_SS = "QCheckBox { font-size: 12px; }"
        self.evc_es_reaction  = QCheckBox("Reaction Time")
        self.evc_es_leave_car = QCheckBox("Leave Car Time")
        self.evc_es_hesitate  = QCheckBox("Hesitation Time")
        self.evc_es_hesitate.setChecked(True)
        self.evc_es_temp  = QCheckBox("Temperature Threshold")
        self.evc_es_smoke = QCheckBox("Smoke Threshold")
        for cb in [self.evc_es_reaction, self.evc_es_leave_car, self.evc_es_hesitate,
                   self.evc_es_temp, self.evc_es_smoke]:
            cb.setStyleSheet(CB_SS)
        es_gl.addWidget(self.evc_es_reaction,  0, 0)
        es_gl.addWidget(self.evc_es_leave_car, 0, 1)
        es_gl.addWidget(self.evc_es_hesitate,  1, 0)
        es_gl.addWidget(self.evc_es_temp,      1, 1)
        es_gl.addWidget(self.evc_es_smoke,     2, 0)
        t4l.addWidget(es_grp)

        # ── Occupant Movement Speeds ────────────────────────────────────────────
        ms_grp = QGroupBox("🚶  Occupant Movement Speeds  (이동속도 설정)")
        ms_grp.setStyleSheet(GS)
        ms_gl = _make_gl2()
        ms_grp.setLayout(ms_gl)
        r = 0

        self.evc_min_speed = _dsb(0.1, 5.0, 0.45, 2, unit="m/s", step=0.05)
        _row2(ms_gl, r, "Minimum Speed:", self.evc_min_speed); r += 1

        self.evc_elderly_speed = _dsb(0.1, 5.0, 0.60, 2, unit="m/s", step=0.05)
        _row2(ms_gl, r, "Elderly Speed:", self.evc_elderly_speed); r += 1

        self.evc_elderly_ratio = _dsb(0.0, 1.0, 0.40, 2, step=0.05)
        _row2(ms_gl, r, "Elderly Ratio:", self.evc_elderly_ratio); r += 1

        self.evc_speed_reduc = _dsb(0.0, 1.0, 1.0, 3, step=0.05)
        _row2(ms_gl, r, "Speed Reduction:", self.evc_speed_reduc)
        t4l.addWidget(ms_grp)

        # ── Simulation Control Buttons ─────────────────────────────────────────
        act_grp = QGroupBox("▶  Simulation Controls")
        act_grp.setStyleSheet(GS)
        act_vl = QVBoxLayout(act_grp)
        act_vl.setSpacing(6)
        act_vl.setContentsMargins(8, 8, 8, 8)
        act_vl.setAlignment(Qt.AlignLeft)

        # Row 1: Run / Stop / Clear
        btn_row1 = QHBoxLayout()
        self.evc_sim_run_btn = QPushButton("▶  Run Evacuation Simulation")
        self.evc_sim_run_btn.setFixedHeight(36)
        self.evc_sim_run_btn.setStyleSheet(
            "QPushButton{background:#e74c3c;color:white;font-weight:bold;"
            "font-size:12px;border-radius:4px;}"
            "QPushButton:hover{background:#c0392b;}"
            "QPushButton:disabled{background:#bdc3c7;}")
        self.evc_sim_run_btn.clicked.connect(self.run_evacuation_simulation)

        self.evc_sim_stop_btn = QPushButton("Stop")
        self.evc_sim_stop_btn.setFixedHeight(36)
        self.evc_sim_stop_btn.setFixedWidth(72)
        self.evc_sim_stop_btn.setEnabled(False)
        self.evc_sim_stop_btn.setStyleSheet(
            "QPushButton{background:#7f8c8d;color:white;font-weight:bold;"
            "font-size:12px;border-radius:4px;}"
            "QPushButton:hover{background:#636e72;}")
        self.evc_sim_stop_btn.clicked.connect(self._evac_sim_stop)

        self.evc_sim_clear_btn = QPushButton("Clear")
        self.evc_sim_clear_btn.setFixedHeight(36)
        self.evc_sim_clear_btn.setFixedWidth(72)
        self.evc_sim_clear_btn.setStyleSheet(
            "QPushButton{background:#95a5a6;color:white;font-weight:bold;"
            "font-size:12px;border-radius:4px;}"
            "QPushButton:hover{background:#7f8c8d;}")
        self.evc_sim_clear_btn.clicked.connect(self._evac_sim_clear)

        btn_row1.addWidget(self.evc_sim_run_btn)
        btn_row1.addWidget(self.evc_sim_stop_btn)
        btn_row1.addWidget(self.evc_sim_clear_btn)
        btn_row1.addStretch()
        act_vl.addLayout(btn_row1)

        # Progress bar
        self.evc_sim_progress = QProgressBar()
        self.evc_sim_progress.setFixedHeight(18)
        self.evc_sim_progress.setRange(0, 100)
        self.evc_sim_progress.setValue(0)
        self.evc_sim_progress.setStyleSheet(
            "QProgressBar{border:1px solid #bdc3c7;border-radius:3px;"
            "text-align:center;font-size:10px;}"
            "QProgressBar::chunk{background:#e74c3c;}")
        act_vl.addWidget(self.evc_sim_progress)

        # Speed slider row
        spd_row = QHBoxLayout()
        spd_lbl = QLabel("Animation Speed:")
        spd_lbl.setFixedWidth(120)
        spd_row.addWidget(spd_lbl)
        self.evc_sim_speed_sl = QSlider(Qt.Horizontal)
        self.evc_sim_speed_sl.setRange(1, 20)
        self.evc_sim_speed_sl.setValue(5)
        self.evc_sim_speed_sl.setFixedHeight(22)
        spd_row.addWidget(self.evc_sim_speed_sl)
        self.evc_sim_speed_lbl = QLabel("5x")
        self.evc_sim_speed_lbl.setFixedWidth(30)
        self.evc_sim_speed_sl.valueChanged.connect(
            lambda v: self.evc_sim_speed_lbl.setText("{}x".format(v)))
        spd_row.addWidget(self.evc_sim_speed_lbl)
        act_vl.addLayout(spd_row)
        t4l.addWidget(act_grp)

        # ── Mini simulation log ────────────────────────────────────────────────
        sim_log_grp = QGroupBox("📋  Simulation Log")
        sim_log_grp.setStyleSheet(GS)
        sim_log_vl = QVBoxLayout(sim_log_grp)
        sim_log_vl.setAlignment(Qt.AlignLeft)
        self.evc_sim_log = QTextEdit()
        self.evc_sim_log.setReadOnly(True)
        self.evc_sim_log.setMinimumHeight(90)
        self.evc_sim_log.setMaximumHeight(130)
        self.evc_sim_log.setStyleSheet(
            "background:#1e272e;color:#dfe6e9;"
            "font-family:'Courier New';font-size:10px;border-radius:3px;")
        sim_log_vl.addWidget(self.evc_sim_log)
        t4l.addWidget(sim_log_grp)
        t4l.addStretch()

        t4l_main.addWidget(t4_ctrl_scroll, stretch=0)

        # ─── RIGHT: matplotlib canvas ─────────────────────────────────────────
        try:
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            import matplotlib.gridspec as gridspec

            canvas_container = QWidget()
            canvas_vl = QVBoxLayout(canvas_container)
            canvas_vl.setContentsMargins(0, 0, 0, 0)
            canvas_vl.setSpacing(0)

            self.evc_sim_fig = Figure(figsize=(8, 9), dpi=90)
            self.evc_sim_fig.set_tight_layout(False)
            self.evc_sim_fig.patch.set_facecolor('#f5f6fa')
            gs_layout = gridspec.GridSpec(3, 1, figure=self.evc_sim_fig,
                                          hspace=0.44, top=0.96, bottom=0.07,
                                          left=0.10, right=0.97)
            self.evc_ax_tunnel = self.evc_sim_fig.add_subplot(gs_layout[0])
            self.evc_ax_fed    = self.evc_sim_fig.add_subplot(gs_layout[1])
            self.evc_ax_hist   = self.evc_sim_fig.add_subplot(gs_layout[2])

            self.evc_sim_canvas = FigureCanvas(self.evc_sim_fig)
            self.evc_sim_canvas.setMinimumWidth(550)
            self.evc_sim_canvas.setMinimumHeight(500)
            canvas_vl.addWidget(self.evc_sim_canvas)

            self._evac_draw_placeholder()
            t4l_main.addWidget(canvas_container, stretch=1)
            self._evac_has_canvas = True

        except ImportError:
            no_mpl = QLabel("matplotlib not available.\nInstall: pip install matplotlib")
            no_mpl.setAlignment(Qt.AlignCenter)
            no_mpl.setStyleSheet("color:#e74c3c;font-size:13px;")
            t4l_main.addWidget(no_mpl, stretch=1)
            self._evac_has_canvas = False

        # Internal state for the simulator
        self._evac_timer   = None
        self._evac_running = False
        self._evac_state   = {}

        # Note: t4 uses HBoxLayout with a scrollable left panel + right canvas.
        # No outer scroll area needed — it prevents the right canvas from expanding.
        self.evc_inner_tabs.addTab(t4, "4. 시뮬레이션")


        # ══════════════════════════════════════════════════════════════════════
        # SUB-TAB 5 — MDB Create
        # ══════════════════════════════════════════════════════════════════════
        t5 = QWidget(); t5s = QScrollArea()
        t5s.setWidgetResizable(True); t5s.setWidget(t5)
        t5l = QVBoxLayout(t5); t5l.setSpacing(10); t5l.setContentsMargins(8, 8, 8, 8)

        db_grp = QGroupBox("🗄️  FDB Database Configuration  (FDB 데이터베이스 설정)")
        db_grp.setStyleSheet(GS); db_gl = _make_gl(); db_grp.setLayout(db_gl)
        r = 0
        self.evc_db_type = QComboBox()
        self.evc_db_type.addItems(["TYPE1","TYPE2"]); self.evc_db_type.setFixedHeight(SB_H)
        self.evc_db_fds_id = _le("TN","e.g. TN")
        db_gl.addWidget(_lbl("DB Set Type:"), r, 0); db_gl.addWidget(self.evc_db_type, r, 1)
        db_gl.addWidget(_lbl("FDS ID (CHID):"), r, 2); db_gl.addWidget(self.evc_db_fds_id, r, 3); r+=1

        self.evc_db_cfdidx = _sb(0,10000,0,step=1)
        self.evc_db_cnvfac = _dsb(0,1e8,1000000.0,1,step=100000)
        _row_pair(db_gl, r, "CFD Index (CFDIDX):", self.evc_db_cfdidx,
                            "Conv. Factor (CNV_FAC):", self.evc_db_cnvfac); r+=1

        # Row: Soot (col 0-1)  |  CO₂ (col 2-3)
        self.evc_db_soot = _sb(0, 10000, 0)
        self.evc_db_co2  = _sb(0, 10000, 0)
        db_gl.addWidget(_lbl("Soot:"),          r, 0); db_gl.addWidget(self.evc_db_soot, r, 1)
        db_gl.addWidget(_lbl("CO₂:"),           r, 2); db_gl.addWidget(self.evc_db_co2,  r, 3); r += 1
        # Row: CO (col 0-1)   |  Temp (col 2-3)
        self.evc_db_co   = _sb(0, 10000, 0)
        self.evc_db_temp = _sb(0, 10000, 0)
        db_gl.addWidget(_lbl("CO:"),            r, 0); db_gl.addWidget(self.evc_db_co,   r, 1)
        db_gl.addWidget(_lbl("Temp:"),          r, 2); db_gl.addWidget(self.evc_db_temp, r, 3); r += 1
        # Row: Radiation (col 0-1)  |  Oxygen (col 2-3)
        self.evc_db_rad = _sb(0, 10000, 0)
        self.evc_db_o2  = _sb(0, 10000, 0)
        db_gl.addWidget(_lbl("Radiation:"),     r, 0); db_gl.addWidget(self.evc_db_rad,  r, 1)
        db_gl.addWidget(_lbl("Oxygen:"),        r, 2); db_gl.addWidget(self.evc_db_o2,   r, 3)
        r+=1
        self.evc_db_slf_dt   = _dsb(0.1,300,30.0,1,unit="s",step=5)
        self.evc_db_slf_tmax = _dsb(60,86400,1200.0,0,unit="s",step=60)
        _row_pair(db_gl, r, "FDS SLF Time Interval:", self.evc_db_slf_dt,
                            "FDS SLF Last Time:", self.evc_db_slf_tmax); r+=1
        self.evc_db_axis = QComboBox()
        self.evc_db_axis.addItems(["X","Y","Z"]); self.evc_db_axis.setFixedHeight(SB_H)
        db_gl.addWidget(_lbl("Tunnel Axis Direction:"), r, 0)
        db_gl.addWidget(self.evc_db_axis, r, 1)
        t5l.addWidget(db_grp)

        idx_grp = QGroupBox("📑  Index File List")
        idx_grp.setStyleSheet(GS); idx_layout = QVBoxLayout(idx_grp)
        self.evc_idx_list = QListWidget()
        for it in ["Road_QRA","MakeQRAFrame_ROA","Sample"]: self.evc_idx_list.addItem(it)
        self.evc_idx_list.setMaximumHeight(90)
        idx_layout.addWidget(self.evc_idx_list)
        t5l.addWidget(idx_grp)
        t5l.addStretch()
        self.evc_inner_tabs.addTab(t5s, "5. MDB Create")

        self.tabs.addTab(outer_scroll, "4. EVC/FED Analysis")

    # ── File-loader helpers ───────────────────────────────────────────────────

    def evc_autoscan_output_folder(self):
        """Scan fds_outputs/ for the first .fds and .fdb files and populate paths."""
        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Open a project first.")
            return

        out_base = Path(self.project_dir) / "fds_outputs"
        found = []

        # FDS — search project root + fds_outputs recursively
        fds_candidates = list(Path(self.project_dir).rglob("*.fds"))
        if fds_candidates:
            self.evc_fds_path_le.setText(str(fds_candidates[0]))
            self._evc_parse_fds(fds_candidates[0])
            found.append(f"FDS: {fds_candidates[0].name}")
        else:
            found.append("FDS: not found")

        # FDB — search fds_outputs recursively
        fdb_candidates = list(out_base.rglob("*.fdb")) if out_base.exists() else []
        if not fdb_candidates:
            fdb_candidates = list(Path(self.project_dir).rglob("*.fdb"))
        if fdb_candidates:
            self.evc_fdb_path_le.setText(str(fdb_candidates[0]))
            # populate MDB tab CHID + SLF last time from filename heuristic
            stem = fdb_candidates[0].stem
            self.evc_db_fds_id.setText(stem)
            found.append(f"FDB: {fdb_candidates[0].name}")
        else:
            found.append("FDB: not found")

        msg = "  ·  ".join(found)
        self.evc_scan_status.setText(msg)
        self.evc_status_text.append(f"🔍 Auto-scan: {msg}")

    def evc_browse_fds(self):
        """Browse for a single FDS input file."""
        from PyQt5.QtWidgets import QFileDialog
        p, _ = QFileDialog.getOpenFileName(
            self, "Select FDS Input File",
            str(Path(self.project_dir) if self.project_dir else ""),
            "FDS Files (*.fds *.FDS);;All Files (*.*)")
        if p:
            self.evc_fds_path_le.setText(p)
            self._evc_parse_fds(Path(p))
            self.evc_status_text.append(f"📂 FDS loaded: {Path(p).name}")

    def evc_browse_fdb(self):
        """Browse for a single FDB database file."""
        from PyQt5.QtWidgets import QFileDialog
        p, _ = QFileDialog.getOpenFileName(
            self, "Select FDB Database File",
            str(Path(self.project_dir) if self.project_dir else ""),
            "FDB Files (*.fdb *.FDB);;All Files (*.*)")
        if p:
            self.evc_fdb_path_le.setText(p)
            self.evc_db_fds_id.setText(Path(p).stem)
            self.evc_status_text.append(f"📂 FDB loaded: {Path(p).name}")

    def _evc_parse_fds(self, fds_path: Path):
        """Parse an FDS file and populate all sub-tab 1 (and MDB) fields."""
        import re as _re
        try:
            content = fds_path.read_text(errors='replace')
            log = []

            # CHID
            m = _re.search(r"CHID\s*=\s*['\"]([^'\"]+)['\"]", content, _re.I)
            if m:
                self.evc_db_fds_id.setText(m.group(1))
                log.append(f"CHID={m.group(1)}")

            # MESH → tunnel dims
            m = _re.search(
                r"&MESH[^/]*XB\s*=\s*([\d.\-]+),([\d.\-]+),([\d.\-]+),([\d.\-]+),([\d.\-]+),([\d.\-]+)",
                content, _re.I | _re.S)
            if m:
                x0,x1,y0,y1,z0,z1 = [float(m.group(i)) for i in range(1,7)]
                L,W,H = round(x1-x0,2), round(y1-y0,2), round(z1-z0,2)
                self.evc_tunnel_length.setValue(L); self.evc_tunnel_width.setValue(W)
                self.evc_tunnel_height.setValue(H); self.evc_cross_area.setValue(round(W*H,2))
                log.append(f"L={L}m W={W}m H={H}m")

            # TIME
            m = _re.search(r"&TIME[^/]*TWFIN\s*=\s*([\d.]+)", content, _re.I|_re.S)
            if m:
                tf = float(m.group(1))
                self.evc_sim_duration.setValue(tf); self.evc_db_slf_tmax.setValue(tf)
                log.append(f"TWFIN={tf}s")

            # TMPA
            m = _re.search(r"TMPA\s*=\s*([\d.\-]+)", content, _re.I)
            if m:
                t = float(m.group(1))
                self.evc_ambient_temp.setValue(t)
                # evc_amb_temp2 is an alias; update if it exists
                if hasattr(self, 'evc_amb_temp2'):
                    self.evc_amb_temp2.setValue(t)
                log.append(f"TMPA={t}°C")

            # REAC
            for pat, widget, tag in [
                (r"SOOT_YIELD\s*=\s*([\d.]+)",             self.evc_soot_yield, "Soot"),
                (r"CO_YIELD\s*=\s*([\d.]+)",               self.evc_co_yield,   "CO"),
                (r"MASS_EXTINCTION_COEFFICIENT\s*=\s*([\d.]+)", self.evc_mass_ext, "MEC"),
                (r"RADIATIVE_FRACTION\s*=\s*([\d.]+)",     self.evc_rad_frac,   "RadF"),
            ]:
                mx = _re.search(pat, content, _re.I)
                if mx: widget.setValue(float(mx.group(1))); log.append(f"{tag}={mx.group(1)}")

            # HRRPUA + VENT → fire location + peak HRR
            mh = _re.search(r"HRRPUA\s*=\s*([\d.]+)", content, _re.I)
            mv = _re.search(
                r"&VENT[^/]*XB\s*=\s*([\d.\-]+),([\d.\-]+),([\d.\-]+),([\d.\-]+),([\d.\-]+),([\d.\-]+)[^/]*SURF_ID",
                content, _re.I|_re.S)
            if mh and mv:
                vx0,vx1,vy0,vy1,vz0,vz1 = [float(mv.group(i)) for i in range(1,7)]
                fx,fy,fz = round((vx0+vx1)/2,2), round((vy0+vy1)/2,2), round((vz0+vz1)/2,2)
                peak = round(float(mh.group(1)) * abs(vx1-vx0) * abs(vy1-vy0) / 1000, 2)
                self.evc_fire_x.setValue(fx); self.evc_fire_y.setValue(fy)
                self.evc_fire_z.setValue(fz); self.evc_peak_hrr.setValue(peak)
                log.append(f"Fire=({fx},{fy},{fz})m HRR={peak}MW")

            self.evc_inner_tabs.setCurrentIndex(0)
            self.evc_status_text.append("✅ FDS parsed: " + "  ".join(log))

        except Exception as e:
            self.evc_status_text.append(f"❌ FDS parse error: {e}")

    # kept for back-compat (called by old button wiring in generate/run methods)
    def evc_load_fds_and_populate(self):
        self.evc_browse_fds()
    

    # ══════════════════════════════════════════════════════════════════════════
    # EVACUATION & FED SIMULATOR  — backend methods
    # ══════════════════════════════════════════════════════════════════════════

    def _evac_draw_placeholder(self):
        """Draw a schematic placeholder on all three axes."""
        import numpy as np

        ax = self.evc_ax_tunnel
        ax.clear()
        ax.set_facecolor('#eaf4fb')
        ax.set_title("[TUNNEL]  Tunnel Evacuation View  (press Run to start)", fontsize=10,
                     fontweight='bold', pad=4)
        tunnel_len = 410.0
        tunnel_h   = 7.5
        from matplotlib.patches import FancyBboxPatch
        rect = FancyBboxPatch((0, 0), tunnel_len, tunnel_h,
                              boxstyle="round,pad=1", linewidth=1.5,
                              edgecolor='#2c3e50', facecolor='#d6eaf8', zorder=1)
        ax.add_patch(rect)
        for ex in [0, 205, 410]:
            ax.axvline(ex, color='#27ae60', lw=2, ls='--', zorder=2)
            ax.text(ex, tunnel_h + 0.3, 'Exit\n{}m'.format(ex), ha='center',
                    va='bottom', fontsize=7, color='#27ae60')
        ax.set_xlim(-20, tunnel_len + 20)
        ax.set_ylim(-1.5, tunnel_h + 2)
        ax.set_xlabel("Tunnel Position (m)", fontsize=8)
        ax.set_ylabel("Height (m)", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.text(205, tunnel_h / 2, "Set parameters & press Run",
                ha='center', va='center', fontsize=11, color='#636e72',
                style='italic')

        ax2 = self.evc_ax_fed
        ax2.clear()
        ax2.set_facecolor('#fef9e7')
        ax2.set_title("FED vs Time  (Purser Model)", fontsize=10,
                      fontweight='bold', pad=4)
        ax2.set_xlabel("Time (s)", fontsize=8)
        ax2.set_ylabel("Cumulative FED", fontsize=8)
        ax2.axhline(1.0, color='red',    lw=1.2, ls='--', label='FED=1 (Incapacitation)')
        ax2.axhline(0.3, color='orange', lw=1.0, ls=':',  label='FED=0.3 (Design)')
        ax2.legend(fontsize=7, loc='upper left')
        ax2.set_ylim(0, 1.5)
        ax2.set_xlim(0, 600)
        ax2.tick_params(labelsize=7)
        ax2.text(300, 0.75, "No data yet", ha='center', va='center',
                 fontsize=11, color='#95a5a6', style='italic')

        ax3 = self.evc_ax_hist
        ax3.clear()
        ax3.set_facecolor('#eafaf1')
        ax3.set_title("Occupant FED Distribution", fontsize=10,
                      fontweight='bold', pad=4)
        ax3.set_xlabel("FED Bin", fontsize=8)
        ax3.set_ylabel("Occupants", fontsize=8)
        bins_l  = ['0.0-0.1', '0.1-0.3', '0.3-0.5', '0.5-1.0', '>=1.0']
        colors  = ['#27ae60','#2ecc71','#f39c12','#e67e22','#e74c3c']
        ax3.bar(bins_l, [0]*5, color=colors, edgecolor='white', linewidth=0.8)
        ax3.set_ylim(0, 100)
        ax3.tick_params(axis='x', labelsize=7, rotation=15)
        ax3.tick_params(axis='y', labelsize=7)

        self.evc_sim_fig.canvas.draw_idle()

    def run_evacuation_simulation(self):
        """Launch the step-by-step evacuation + FED simulation."""
        import numpy as np
        from PyQt5.QtCore import QTimer

        if self._evac_running:
            return
        if not getattr(self, '_evac_has_canvas', False):
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Canvas", "matplotlib canvas not available.")
            return

        try:
            t_end       = float(self.evc_sim_t_end.value())
            dt          = float(self.evc_sim_dt.value())
            walk_speed  = max(0.1, float(self.evc_min_speed.value()))
            eld_speed   = max(0.1, float(self.evc_elderly_speed.value()))
            eld_ratio   = min(1.0, max(0.0, float(self.evc_elderly_ratio.value())))
            speed_reduc = float(self.evc_speed_reduc.value())
            fire_x      = float(self.evc_fire_x.value())
            design_fire = float(self.evc_design_fire.value())
            growth_rate = float(self.evc_growth_rate.value())
            co_yield    = float(self.evc_co_yield.value())
        except Exception as e:
            self.evc_sim_log.append("Parameter error: {}".format(e))
            return

        times   = np.arange(0, t_end + dt, dt)
        n_steps = len(times)

        # Fire HRR (t-squared growth)
        q_peak  = design_fire * 1000.0   # kW
        hrr_arr = np.minimum(growth_rate * times**2, q_peak)

        # Simplified gas concentrations (Purser-style)
        k_co   = co_yield * 1e6 / (3600 * 50.0)
        k_o2   = 0.001
        k_temp = 0.015
        co_arr   = np.clip(k_co  * hrr_arr,               0,  50000)
        o2_arr   = np.clip(21.0 - k_o2 * hrr_arr / 1000., 5,  21)
        temp_arr = 20.0 + k_temp * np.sqrt(np.clip(hrr_arr, 0, None))

        dt_min = dt / 60.0
        fed_co_rate   = np.where(co_arr > 0,   (co_arr**1.036) / 35000., 0.)
        fed_o2_rate   = np.where(o2_arr < 21., ((21.-o2_arr)/11.)**3/60., 0.)
        fed_heat_rate = np.where(temp_arr>20., temp_arr**3.4/5e7, 0.)
        fed_co_cum    = np.cumsum(fed_co_rate   * dt_min)
        fed_o2_cum    = np.cumsum(fed_o2_rate   * dt_min)
        fed_heat_cum  = np.cumsum(fed_heat_rate * dt_min)
        fed_total     = fed_co_cum + fed_o2_cum + fed_heat_cum

        n_occ = max(10, self._get_total_occupants())
        rng   = np.random.default_rng(42)
        positions  = rng.uniform(0, 410., n_occ)
        exits      = np.array([0., 205., 410.])
        exit_idx   = np.argmin(np.abs(positions[:,None] - exits[None,:]), axis=1)
        occ_exits  = exits[exit_idx]
        is_elderly = rng.random(n_occ) < eld_ratio
        speeds     = np.where(is_elderly, eld_speed, walk_speed) * speed_reduc

        has_hesitate = getattr(self, 'evc_es_hesitate', None)
        premovement  = 180. if (has_hesitate and has_hesitate.isChecked()) else 60.
        start_move   = rng.uniform(premovement*0.7, premovement*1.3, n_occ)
        travel_dist  = np.abs(positions - occ_exits)
        evac_time    = np.clip(start_move + travel_dist / speeds, 0, t_end*1.2)

        self._evac_state = dict(
            times=times, n_steps=n_steps, step=0,
            hrr=hrr_arr, co=co_arr, o2=o2_arr, temp=temp_arr,
            fed_total=fed_total, fed_co=fed_co_cum,
            fed_o2=fed_o2_cum, fed_heat=fed_heat_cum,
            positions=positions.copy(), occ_exits=occ_exits,
            speeds=speeds, evac_time=evac_time, is_elderly=is_elderly,
            escaped=np.zeros(n_occ, dtype=bool), n_occ=n_occ,
            tunnel_len=410., fire_x=fire_x,
            hist_time=[], hist_fed=[],
        )

        self.evc_sim_run_btn.setEnabled(False)
        self.evc_sim_stop_btn.setEnabled(True)
        self.evc_sim_progress.setValue(0)
        self.evc_sim_log.clear()
        self.evc_sim_log.append("Run started:  t_end={:.0f}s  dt={}s  occ={}  fire@{:.1f}m  HRR_peak={:.0f}MW".format(
            t_end, dt, n_occ, fire_x, design_fire))
        self._evac_running = True

        self._evac_timer = QTimer()
        anim_ms = max(30, 200 - self.evc_sim_speed_sl.value() * 9)
        self._evac_timer.setInterval(anim_ms)
        self._evac_timer.timeout.connect(self._evac_step)
        self._evac_timer.start()

    def _evac_step(self):
        """Advance simulation and redraw."""
        import numpy as np
        st   = self._evac_state
        skip = max(1, self.evc_sim_speed_sl.value())
        step = st['step']
        n    = min(step + skip, st['n_steps'] - 1)
        t    = st['times'][n]
        fed  = float(st['fed_total'][n])

        positions  = st['positions']
        escaped    = st['escaped']
        speeds     = st['speeds']
        occ_exits  = st['occ_exits']
        ev_time    = st['evac_time']
        dt_eff     = (st['times'][1] - st['times'][0]) * skip

        for i in range(st['n_occ']):
            if not escaped[i] and t >= ev_time[i] - (ev_time[i] - st['times'][0]):
                direction = np.sign(occ_exits[i] - positions[i])
                positions[i] += direction * speeds[i] * dt_eff
                if direction >= 0 and positions[i] >= occ_exits[i]:
                    positions[i] = occ_exits[i]; escaped[i] = True
                elif direction < 0 and positions[i] <= occ_exits[i]:
                    positions[i] = occ_exits[i]; escaped[i] = True

        n_escaped = int(np.sum(escaped))
        n_active  = int(np.sum(~escaped))
        st['hist_time'].append(t)
        st['hist_fed'].append(fed)
        st['step'] = n + 1

        self.evc_sim_progress.setValue(int(100 * (n + 1) / st['n_steps']))
        self._evac_draw_frame(t, n, n_escaped, n_active, positions, escaped, fed)

        if n + 1 >= st['n_steps'] or (n_active == 0 and n > 10):
            self._evac_sim_finish(n_escaped, n_active, t, fed)

    def _evac_draw_frame(self, t, step_idx, n_escaped, n_active, positions, escaped, fed_now):
        """Redraw all three axes."""
        import numpy as np
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyBboxPatch, Wedge

        st = self._evac_state

        # ── Ax0: Tunnel view ─────────────────────────────────────────────────
        ax = self.evc_ax_tunnel
        ax.clear()
        ax.set_facecolor('#eaf4fb')
        tunnel_len = st['tunnel_len']
        tunnel_h   = 7.5

        ax.add_patch(FancyBboxPatch((0, 0), tunnel_len, tunnel_h,
                                   boxstyle="round,pad=0.5", linewidth=1.5,
                                   edgecolor='#2c3e50', facecolor='#d6eaf8', zorder=1))
        # Smoke
        co_ppm       = float(st['co'][step_idx])
        smoke_alpha  = min(0.45, co_ppm / 30000.)
        ax.add_patch(FancyBboxPatch((0, 0), tunnel_len, tunnel_h,
                                   boxstyle="round,pad=0.5", linewidth=0,
                                   facecolor='#636e72', alpha=smoke_alpha, zorder=2))
        # Fire
        fx = st['fire_x']
        hrr_all = st['hrr']
        q_peak_ref = max(float(np.max(hrr_all)), 1.)
        if 0 <= fx <= tunnel_len:
            hrr = float(hrr_all[step_idx])
            fire_h = min(tunnel_h * 0.8, 0.5 + hrr / q_peak_ref * tunnel_h * 0.6)
            for fi, fc in enumerate(['#e74c3c', '#e67e22', '#f1c40f']):
                ax.add_patch(Wedge((fx, 0), fire_h * (1 - fi * 0.25),
                                   45 + fi * 10, 135 - fi * 10,
                                   facecolor=fc, zorder=4, alpha=0.85 - fi * 0.15))
            ax.text(fx, fire_h + 0.3, '{:.0f} kW'.format(hrr),
                    ha='center', va='bottom', fontsize=7,
                    color='#e74c3c', fontweight='bold', zorder=5)

        # Exits
        for ex, elab in [(0, 'EXIT <'), (205, 'EXIT ^'), (410, 'EXIT >')]:
            ax.axvline(ex, color='#27ae60', lw=2, ls='--', zorder=3)
            ax.text(ex, tunnel_h + 0.25, elab, ha='center', va='bottom',
                    fontsize=7, color='#27ae60', fontweight='bold')

        # Occupants
        rng2       = np.random.default_rng(step_idx)
        pos_act    = positions[~escaped]
        is_eld_act = st['is_elderly'][~escaped]
        if len(pos_act):
            y_jit = rng2.uniform(0.5, tunnel_h - 0.5, len(pos_act))
            fed_frac = min(fed_now, 1.0)
            c_act = (fed_frac, 1. - fed_frac, 0.)
            ax.scatter(pos_act[~is_eld_act], y_jit[~is_eld_act],
                       s=18, c=[c_act], zorder=5, marker='o', label='Occupant')
            if np.any(is_eld_act):
                ax.scatter(pos_act[is_eld_act], y_jit[is_eld_act],
                           s=22, c='#8e44ad', zorder=5, marker='^', label='Elderly')
        pos_esc = positions[escaped]
        for ex_pt in [0., 205., 410.]:
            cnt = int(np.sum(np.abs(pos_esc - ex_pt) < 1.))
            if cnt:
                ax.text(ex_pt, -1.0, 'OK:{}'.format(cnt), ha='center',
                        va='top', fontsize=7, color='#27ae60', fontweight='bold')

        ax.set_xlim(-15, tunnel_len + 15)
        ax.set_ylim(-2, tunnel_h + 2.5)
        ax.set_xlabel("Tunnel Position (m)", fontsize=8)
        ax.set_ylabel("Height (m)", fontsize=8)
        ax.set_title("Tunnel t={:.0f}s  Active:{}  Escaped:{}  FED={:.3f}".format(
            t, n_active, n_escaped, fed_now), fontsize=9, fontweight='bold', pad=3)
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=7, loc='upper right', framealpha=0.7)

        # ── Ax1: FED time-series ─────────────────────────────────────────────
        ax2 = self.evc_ax_fed
        ax2.clear()
        ax2.set_facecolor('#fef9e7')
        t_pl   = st['times'][:step_idx + 1]
        fc_pl  = st['fed_co'][:step_idx + 1]
        fo_pl  = st['fed_o2'][:step_idx + 1]
        fh_pl  = st['fed_heat'][:step_idx + 1]
        ft_pl  = fc_pl + fo_pl + fh_pl
        ax2.plot(t_pl, fc_pl, color='#e67e22', lw=1.2, ls='-',  label='FED_CO')
        ax2.plot(t_pl, fo_pl, color='#3498db', lw=1.2, ls='--', label='FED_O2')
        ax2.plot(t_pl, fh_pl, color='#e74c3c', lw=1.2, ls=':',  label='FED_Heat')
        ax2.plot(t_pl, ft_pl, color='#2c3e50', lw=2.0, ls='-',  label='FED_Total')
        ax2.axhline(1.0, color='red',    lw=1.2, ls='--', alpha=0.7)
        ax2.axhline(0.3, color='orange', lw=1.0, ls=':',  alpha=0.7)
        ax2.axvline(t,   color='#8e44ad', lw=1.0, ls=':', alpha=0.8)
        ax2.set_xlim(0, st['times'][-1])
        ax2.set_ylim(0, max(1.6, float(np.max(ft_pl)) * 1.15 + 0.05))
        ax2.set_xlabel("Time (s)", fontsize=8)
        ax2.set_ylabel("Cumulative FED", fontsize=8)
        ax2.set_title("FED vs Time  (Purser Model)", fontsize=9, fontweight='bold', pad=3)
        ax2.legend(fontsize=7, loc='upper left', ncol=2, framealpha=0.8)
        ax2.tick_params(labelsize=7)

        # ── Ax2: histogram ───────────────────────────────────────────────────
        ax3 = self.evc_ax_hist
        ax3.clear()
        ax3.set_facecolor('#eafaf1')
        evac_feds = np.interp(
            np.clip(st['evac_time'], st['times'][0], st['times'][-1]),
            st['times'], st['fed_total'])
        bins_e  = [0, 0.1, 0.3, 0.5, 1.0, 1e9]
        bins_l  = ['0.0-0.1', '0.1-0.3', '0.3-0.5', '0.5-1.0', '>=1.0']
        cols_h  = ['#27ae60','#2ecc71','#f39c12','#e67e22','#e74c3c']
        cnts    = [int(np.sum((evac_feds >= bins_e[i]) & (evac_feds < bins_e[i+1])))
                   for i in range(5)]
        bars = ax3.bar(bins_l, cnts, color=cols_h, edgecolor='white', linewidth=0.8)
        for bar, cnt in zip(bars, cnts):
            if cnt:
                ax3.text(bar.get_x() + bar.get_width()/2.,
                         bar.get_height() + 0.5, str(cnt),
                         ha='center', va='bottom', fontsize=7, fontweight='bold')
        ax3.set_xlabel("FED Bin", fontsize=8)
        ax3.set_ylabel("Occupants", fontsize=8)
        ax3.set_title("Occupant FED Distribution", fontsize=9, fontweight='bold', pad=3)
        ax3.set_ylim(0, max(10, max(cnts) * 1.15 + 1))
        ax3.tick_params(axis='x', labelsize=7, rotation=15)
        ax3.tick_params(axis='y', labelsize=7)

        self.evc_sim_fig.canvas.draw_idle()

    def _evac_sim_finish(self, n_escaped, n_active, t_final, fed_final):
        """Called when simulation completes."""
        if self._evac_timer:
            self._evac_timer.stop()
        self._evac_running = False
        self.evc_sim_run_btn.setEnabled(True)
        self.evc_sim_stop_btn.setEnabled(False)
        self.evc_sim_progress.setValue(100)
        n_occ = self._evac_state.get('n_occ', 0)
        self.evc_sim_log.append(
            "Done  t={:.0f}s  Escaped:{}/{}  Remaining:{}  FED_final={:.4f}".format(
                t_final, n_escaped, n_occ, n_active, fed_final))
        fp = min(100., max(0., (fed_final - 1.) * 50)) if fed_final >= 1. else 0.
        self.evc_sim_log.append("   Est. fatality risk: {:.1f}%".format(fp))

    def _evac_sim_stop(self):
        if self._evac_timer:
            self._evac_timer.stop()
        self._evac_running = False
        self.evc_sim_run_btn.setEnabled(True)
        self.evc_sim_stop_btn.setEnabled(False)
        self.evc_sim_log.append("Simulation stopped by user.")

    def _evac_sim_clear(self):
        self._evac_sim_stop()
        self._evac_state = {}
        self.evc_sim_progress.setValue(0)
        self.evc_sim_log.clear()
        if getattr(self, '_evac_has_canvas', False):
            self._evac_draw_placeholder()

    def create_tab5_statistics(self):
        """Tab 5: Statistics (Monte Carlo)"""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        header_label = QLabel("📊 Statistical Analysis (Monte Carlo)")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 10px;")
        layout.addWidget(header_label)
        
        info_label = QLabel(
            "Perform Monte Carlo analysis to calculate scenario statistics with uncertainty quantification."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #ebf5fb; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # Configuration
        config_group = QGroupBox("Monte Carlo Configuration")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        config_layout = QGridLayout()
        config_group.setLayout(config_layout)
        
        config_layout.addWidget(QLabel("Number of Iterations:"), 0, 0)
        self.mc_iterations_input = QSpinBox()
        self.mc_iterations_input.setRange(5, 1000)
        self.mc_iterations_input.setValue(10)
        config_layout.addWidget(self.mc_iterations_input, 0, 1)
        
        config_layout.addWidget(QLabel("Trim Percentage (%):"), 0, 2)
        self.mc_trim_input = QDoubleSpinBox()
        self.mc_trim_input.setRange(0, 25)
        self.mc_trim_input.setValue(10)
        self.mc_trim_input.setDecimals(1)
        config_layout.addWidget(self.mc_trim_input, 0, 3)
        
        layout.addWidget(config_group)
        
        # Results
        results_group = QGroupBox("Statistics Results")
        results_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        results_layout = QVBoxLayout()
        results_group.setLayout(results_layout)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setStyleSheet("background-color: #f8f9fa; font-family: 'Courier New';")
        results_layout.addWidget(self.stats_text)
        
        layout.addWidget(results_group)
        
        # Action button
        button_layout = QHBoxLayout()
        self.run_stats_btn = QPushButton("📈 Run Statistical Analysis")
        self.run_stats_btn.clicked.connect(self.run_statistics)
        self.run_stats_btn.setStyleSheet("QPushButton { background-color: #8e44ad; color: white; padding: 10px; font-weight: bold; }")
        button_layout.addWidget(self.run_stats_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addStretch()
        
        self.tabs.addTab(scroll, "5. Statistics")
    
    def create_tab6_risk_calculation(self):
        """Tab 6: Risk Calculation"""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        header_label = QLabel("⚠️ Risk Calculation")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 10px;")
        layout.addWidget(header_label)
        
        info_label = QLabel(
            "Calculate risk metrics including scenario frequencies, risk indices, and F-N curve data."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #fadbd8; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # Configuration
        config_group = QGroupBox("Risk Calculation Parameters")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        config_layout = QGridLayout()
        config_group.setLayout(config_layout)
        
        config_layout.addWidget(QLabel("Base Fire Frequency (events/year):"), 0, 0)
        self.base_freq_input = QDoubleSpinBox()
        self.base_freq_input.setRange(0.0001, 1)
        self.base_freq_input.setValue(0.001)
        self.base_freq_input.setDecimals(6)
        config_layout.addWidget(self.base_freq_input, 0, 1)
        
        layout.addWidget(config_group)
        
        # Results
        results_group = QGroupBox("Risk Calculation Results")
        results_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        results_layout = QVBoxLayout()
        results_group.setLayout(results_layout)
        
        self.risk_text = QTextEdit()
        self.risk_text.setReadOnly(True)
        self.risk_text.setStyleSheet("background-color: #f8f9fa; font-family: 'Courier New';")
        results_layout.addWidget(self.risk_text)
        
        layout.addWidget(results_group)
        
        # Action button
        button_layout = QHBoxLayout()
        self.calc_risk_btn = QPushButton("🎯 Calculate Risk Metrics")
        self.calc_risk_btn.clicked.connect(self.calculate_risk)
        self.calc_risk_btn.setStyleSheet("QPushButton { background-color: #c0392b; color: white; padding: 10px; font-weight: bold; }")
        button_layout.addWidget(self.calc_risk_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addStretch()
        
        self.tabs.addTab(scroll, "6. Risk Calculation")
    
    def create_tab7_results(self):
        """Tab 7: Results and Visualization"""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        header_label = QLabel("📋 Results and Visualization")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 10px;")
        layout.addWidget(header_label)
        
        # Results summary
        summary_group = QGroupBox("QRA Results Summary")
        summary_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        summary_layout = QVBoxLayout()
        summary_group.setLayout(summary_layout)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("Complete QRA results will appear here after all analysis steps...")
        self.results_text.setStyleSheet("background-color: #f8f9fa; font-family: 'Courier New'; font-size: 11px;")
        summary_layout.addWidget(self.results_text)
        
        layout.addWidget(summary_group)
        
        # Visualization and Export buttons
        button_group = QGroupBox("Visualization and Export")
        button_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        button_layout = QHBoxLayout()
        button_group.setLayout(button_layout)
        
        self.view_fn_curve_btn = QPushButton("📈 View F-N Curve")
        self.view_fn_curve_btn.clicked.connect(self.view_fn_curve)
        self.view_fn_curve_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; padding: 10px; }")
        
        self.export_excel_btn = QPushButton("📊 Export to Excel")
        self.export_excel_btn.clicked.connect(self.export_to_excel)
        self.export_excel_btn.setStyleSheet("QPushButton { background-color: #16a085; color: white; padding: 10px; }")
        
        self.export_pdf_btn = QPushButton("📄 Export to PDF")
        self.export_pdf_btn.clicked.connect(self.export_to_pdf)
        self.export_pdf_btn.setStyleSheet("QPushButton { background-color: #2980b9; color: white; padding: 10px; }")
        
        button_layout.addWidget(self.view_fn_curve_btn)
        button_layout.addWidget(self.export_excel_btn)
        button_layout.addWidget(self.export_pdf_btn)
        
        layout.addWidget(button_group)
        
        layout.addStretch()
        
        self.tabs.addTab(scroll, "7. Results")
        
        # Initialize FDS version-dependent UI state
        self.on_fds_version_changed()
    
    # ==================== Event Handlers ====================
    
    def browse_home_directory(self):
        """Browse for home directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Home Directory", str(Path.home())
        )
        if directory:
            self.home_dir_input.setText(directory)
    
    def update_directory_preview(self):
        """Update directory structure preview"""
        project_name = self.project_name_input.text().strip()
        home_dir = self.home_dir_input.text().strip()
        
        if project_name and home_dir:
            full_path = str(Path(home_dir) / project_name)
            self.full_path_display.setText(full_path)
            self.create_project_btn.setEnabled(True)
        else:
            self.full_path_display.setText("")
            self.create_project_btn.setEnabled(False)
        
        # Update tree
        self.dir_tree.clear()
        if project_name:
            root = QTreeWidgetItem(self.dir_tree)
            root.setText(0, f"📁 {project_name}/")
            root.setExpanded(True)
            
            # Database name based on project name (lowercase)
            db_name = project_name.lower().replace(' ', '_') + ".db"
            
            folders = [
                ("📂 fds_inputs/", ["020/", "030/", "100/"]),
                ("📂 fds_outputs/", []),
                ("📂 ascii_files/", []),
                ("📂 evc_files/", []),
                ("📂 fed_results/", []),
                ("📂 logs/", []),
                (f"📄 {db_name}", None),
                ("📄 run_all_simulations.bat", None)
            ]
            
            for folder, subfolders in folders:
                child = QTreeWidgetItem(root)
                child.setText(0, folder)
                if subfolders:
                    child.setExpanded(True)
                    for sub in subfolders:
                        subchild = QTreeWidgetItem(child)
                        subchild.setText(0, f"  {sub}")
    
    def create_project(self):
        """Create new project"""
        project_name = self.project_name_input.text().strip()
        home_dir = self.home_dir_input.text().strip()
        
        if not project_name or not home_dir:
            QMessageBox.warning(self, "Missing Information",
                              "Please enter both project name and home directory.")
            return
        
        self.project_dir = str(Path(home_dir) / project_name)
        
        try:
            # Create directory structure
            dirs = [
                "fds_inputs/020",
                "fds_inputs/030",
                "fds_inputs/100",
                "fds_outputs",
                "ascii_files",
                "evc_files",
                "fed_results",
                "logs"
            ]
            
            self.dir_progress_bar.setValue(0)
            self.dir_status_text.append(f"Creating project: {self.project_dir}")
            
            Path(self.project_dir).mkdir(parents=True, exist_ok=True)
            
            for i, d in enumerate(dirs):
                (Path(self.project_dir) / d).mkdir(parents=True, exist_ok=True)
                progress = int((i + 1) / len(dirs) * 100)
                self.dir_progress_bar.setValue(progress)
                self.dir_status_text.append(f"✓ Created: {d}")
            
            # Create batch script
            batch_file = Path(self.project_dir) / "run_all_simulations.bat"
            batch_file.write_text("@echo off\necho FDS simulations batch script\npause\n")
            self.dir_status_text.append("✓ Created: run_all_simulations.bat")
            
            # Initialize database with automatic naming (project name in lowercase)
            # Database is optional - only create if module is available
            db_name = project_name.lower().replace(' ', '_') + ".db"
            db_path = Path(self.project_dir) / db_name
            
            if QRADatabase is not None:
                try:
                    self.database = QRADatabase(str(db_path))
                    self.database.connect()
                    
                    self.current_project_id = self.database.add_project(
                        project_name=project_name,
                        description="QRA Project v2.0",
                        home_directory=home_dir
                    )
                    self.dir_status_text.append("✓ Database initialized")
                except Exception as e:
                    self.dir_status_text.append(f"⚠️ Database initialization failed: {e}")
                    self.dir_status_text.append("ℹ️ Continuing without database...")
            else:
                self.dir_status_text.append("ℹ️ Database module not available (optional)")
            
            self.dir_status_text.append("✓ Database initialized")
            self.dir_status_text.append(f"\n✅ Project created successfully!")
            
            # Enable next tab
            self.generate_fds_btn.setEnabled(True)
            self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage(f"Project created: {project_name}")
            
            QMessageBox.information(self, "Success",
                                  f"Project created successfully!\n\n{self.project_dir}")
            
        except Exception as e:
            self.dir_status_text.append(f"\n❌ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to create project:\n{str(e)}")
    
    def open_existing_project(self):
        """Open existing project"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", str(Path.home())
        )
        
        if directory:
            self.project_dir = directory
            self.project_name_input.setText(Path(directory).name)
            self.home_dir_input.setText(str(Path(directory).parent))
            
            # Initialize database - look for existing database files
            project_name = Path(directory).name
            db_name = project_name.lower().replace(' ', '_') + ".db"
            db_path = Path(self.project_dir) / db_name
            
            # Fallback to qra_database.db if new naming doesn't exist
            if not db_path.exists():
                old_db_path = Path(self.project_dir) / "qra_database.db"
                if old_db_path.exists():
                    db_path = old_db_path
            
            # Database is optional - only load if module is available
            if QRADatabase is not None and db_path.exists():
                try:
                    self.database = QRADatabase(str(db_path))
                    self.database.connect()
                    
                    projects = self.database.get_projects()
                    if projects:
                        self.current_project_id = projects[-1]['id']
                except Exception as e:
                    print(f"⚠️ Database loading failed: {e}")
            else:
                print("ℹ️ Database not available (optional)")
            
            self.generate_fds_btn.setEnabled(True)
            self.dir_status_text.append(f"✓ Opened project: {self.project_dir}")

            # Ensure all expected subdirectories exist (handles legacy projects)
            _ensure = ["ascii_files", "evc_files", "fed_results", "fds_outputs",
                       "fds_inputs/020", "fds_inputs/030", "fds_inputs/100", "logs"]
            for _d in _ensure:
                _p = Path(self.project_dir) / _d
                if not _p.exists():
                    _p.mkdir(parents=True, exist_ok=True)
                    self.dir_status_text.append(f"  ✦ Created missing dir: {_d}")

            self.statusBar().showMessage(f"Project opened: {Path(directory).name}")
            
            QMessageBox.information(self, "Success",
                                  f"Project opened successfully!\n\n{self.project_dir}")
    
    def calculate_tunnel_dimensions(self):
        """Calculate tunnel width and height from radius"""
        radius = self.tunnel_radius_input.value()
        width = radius * 2
        height = 2 * radius + 0.4  # Full circle height + road offset
        
        self.tunnel_width_input.setValue(width)
        self.tunnel_height_input.setValue(height)
        
        QMessageBox.information(self, "Calculated",
                              f"Width: {width:.2f} m\nHeight: {height:.2f} m")
    
    def add_custom_hrr(self):
        """Add custom HRR value"""
        hrr_value = self.custom_hrr_input.value()
        
        if hrr_value in self.custom_hrr_list:
            QMessageBox.warning(self, "Duplicate", "This HRR value already exists in the custom list.")
            return
        
        self.custom_hrr_list.append(hrr_value)
        self.custom_hrr_list_widget.addItem(f"{hrr_value} MW")
        self.fds_status_text.append(f"Added custom HRR: {hrr_value} MW")
    
    def remove_custom_hrr(self):
        """Remove selected custom HRR"""
        current_item = self.custom_hrr_list_widget.currentItem()
        if current_item:
            row = self.custom_hrr_list_widget.row(current_item)
            self.custom_hrr_list.pop(row)
            self.custom_hrr_list_widget.takeItem(row)
            self.fds_status_text.append(f"Removed custom HRR")
    
    def on_fuel_type_changed(self, fuel_type):
        """Handle fuel type selection changes"""
        # Define fuel properties for each type
        fuel_properties = {
            "Petrol": {
                "fuel_id": "PETROL_CAR_FIRE",
                "fuel": "ISO_OCTANE",
                "soot_yield": 0.08,
                "co_yield": 0.025,
                "heat_of_combustion": 4.4e7,
                "editable": True
            },
            "Diesel": {
                "fuel_id": "DIESEL",
                "fuel": "N-DODECANE",
                "soot_yield": 0.133,
                "co_yield": 0.168,
                "heat_of_combustion": 4.3e7,
                "editable": True
            },
            "CNG": {
                "fuel_id": "CNG",
                "fuel": "METHANE",
                "soot_yield": 0.01,
                "co_yield": 0.01,
                "heat_of_combustion": 5.0e7,
                "editable": False
            },
            "LPG": {
                "fuel_id": "LPG",
                "fuel": "PROPANE",
                "soot_yield": 0.024,
                "co_yield": 0.015,
                "heat_of_combustion": 4.6e7,
                "editable": False
            },
            "EVC": {
                "fuel_id": "EVC",
                "fuel": "PROPANE",  # Placeholder for EV battery
                "soot_yield": 0.15,
                "co_yield": 0.20,
                "heat_of_combustion": 3.8e7,
                "editable": False
            }
        }
        
        props = fuel_properties.get(fuel_type, fuel_properties["Diesel"])
        
        # Update UI values
        self.soot_yield_input.setValue(props["soot_yield"])
        self.co_yield_input.setValue(props["co_yield"])
        self.heat_of_combustion_input.setValue(props["heat_of_combustion"])
        
        # Enable/disable editing based on fuel type
        is_editable = props["editable"]
        self.soot_yield_input.setEnabled(is_editable)
        self.co_yield_input.setEnabled(is_editable)
        self.heat_of_combustion_input.setEnabled(is_editable)
        
        # Update status
        if is_editable:
            self.fds_status_text.append(f"Selected {fuel_type}: Properties are editable")
        else:
            self.fds_status_text.append(f"Selected {fuel_type}: Properties are fixed")
    
    def auto_select_fuel_for_hrr(self, hrr_mw):
        """Automatically select fuel type based on HRR threshold"""
        if hrr_mw >= 20:
            self.fuel_type_combo.setCurrentText("Diesel")
        else:
            self.fuel_type_combo.setCurrentText("Petrol")
    
    def on_fds_version_changed(self):
        """Handle FDS version changes to enable/disable appropriate batch file fields"""
        if self.fds6_radio.isChecked():
            # FDS6 selected - enable FDS6 batch file, disable FDS5
            self.fds6_batch_label.setEnabled(True)
            self.fds6_batch_path.setEnabled(True)
            self.browse_fds6_batch_btn.setEnabled(True)
            
            # Highlight FDS6 field as active
            self.fds6_batch_label.setStyleSheet("font-weight: bold; color: #27ae60;")
            self.fds6_batch_path.setStyleSheet("background-color: #eafaf1; border: 2px solid #27ae60;")
            
            self.fds5_batch_label.setEnabled(False)
            self.fds5_batch_path.setEnabled(False)
            self.browse_fds5_batch_btn.setEnabled(False)
            
            # Dim FDS5 field as inactive
            self.fds5_batch_label.setStyleSheet("color: #95a5a6;")
            self.fds5_batch_path.setStyleSheet("background-color: #ecf0f1; color: #95a5a6;")
            
            # Update status
            if hasattr(self, 'fds_status_text'):
                self.fds_status_text.append("\n✓ FDS6 selected - Only FDS6 batch file will be used")
            if hasattr(self, 'sim_status_text'):
                self.sim_status_text.append("\n✓ FDS6 mode active - Configure FDS6 batch file")
        else:
            # FDS5 selected - enable FDS5 batch file, disable FDS6
            self.fds5_batch_label.setEnabled(True)
            self.fds5_batch_path.setEnabled(True)
            self.browse_fds5_batch_btn.setEnabled(True)
            
            # Highlight FDS5 field as active
            self.fds5_batch_label.setStyleSheet("font-weight: bold; color: #e67e22;")
            self.fds5_batch_path.setStyleSheet("background-color: #fef5e7; border: 2px solid #e67e22;")
            
            self.fds6_batch_label.setEnabled(False)
            self.fds6_batch_path.setEnabled(False)
            self.browse_fds6_batch_btn.setEnabled(False)
            
            # Dim FDS6 field as inactive
            self.fds6_batch_label.setStyleSheet("color: #95a5a6;")
            self.fds6_batch_path.setStyleSheet("background-color: #ecf0f1; color: #95a5a6;")
            
            # Update status
            if hasattr(self, 'fds_status_text'):
                self.fds_status_text.append("\n✓ FDS5 selected - Only FDS5 batch file will be used")
            if hasattr(self, 'sim_status_text'):
                self.sim_status_text.append("\n✓ FDS5 mode active - Configure FDS5 batch file")
    
    def on_hrr_selection_changed(self):
        """Handle HRR selection changes to auto-select appropriate fuel"""
        # Get all selected HRR values
        selected_hrrs = []
        if self.hrr_005_check.isChecked():
            selected_hrrs.append(5)
        if self.hrr_010_check.isChecked():
            selected_hrrs.append(10)
        if self.hrr_020_check.isChecked():
            selected_hrrs.append(20)
        if self.hrr_030_check.isChecked():
            selected_hrrs.append(30)
        if self.hrr_050_check.isChecked():
            selected_hrrs.append(50)
        if self.hrr_100_check.isChecked():
            selected_hrrs.append(100)
        
        # Add custom HRR values
        selected_hrrs.extend(self.custom_hrr_list)
        
        if not selected_hrrs:
            return  # No HRR selected
        
        # Find the maximum HRR to determine fuel type
        max_hrr = max(selected_hrrs)
        
        # Auto-select fuel based on maximum HRR
        if max_hrr >= 20:
            recommended_fuel = "Diesel"
        else:
            recommended_fuel = "Petrol"
        
        # Only auto-select if current fuel is Petrol or Diesel (don't override CNG/LPG/EVC)
        current_fuel = self.fuel_type_combo.currentText()
        if current_fuel in ["Petrol", "Diesel"]:
            if current_fuel != recommended_fuel:
                self.fuel_type_combo.setCurrentText(recommended_fuel)
                self.fds_status_text.append(f"Auto-selected {recommended_fuel} fuel (max HRR: {max_hrr} MW)")
    
    # ── Fire position helpers ─────────────────────────────────────────────────

    def _get_auto_fire_positions(self):
        """Return the auto-computed fire position list (floats, metres)."""
        L = self.tunnel_length_input.value()
        n = self.num_fire_positions_spin.value()
        if n < 1 or L <= 0:
            return []
        step = (L * 331.0 / 356.0) / n
        half = step / 2.0
        return [round(half + i * step + 1e-9, 1) for i in range(n)]

    def recalculate_fire_positions(self):
        """Recompute positions from tunnel length + N and update the preview label."""
        positions = self._get_auto_fire_positions()
        L = self.tunnel_length_input.value()
        n = self.num_fire_positions_spin.value()
        if positions:
            pos_str = ",  ".join(f"{x:.1f}" for x in positions)
            span    = positions[-1] - positions[0] if len(positions) > 1 else 0
            step    = (positions[1] - positions[0]) if len(positions) > 1 else 0
            self.fp_preview_label.setText(
                f"[{pos_str}]\n"
                f"  → {n} positions,  step ≈ {step:.1f} m,  "
                f"span {positions[0]:.1f} – {positions[-1]:.1f} m  "
                f"(tunnel = {L:.0f} m)"
            )
            # Mirror into the manual text field so generate_fds_files can
            # always read self.fire_positions_input regardless of mode
            self.fire_positions_input.setText(", ".join(str(x) for x in positions))
        else:
            self.fp_preview_label.setText("—  (set tunnel length and N > 0)")

    def _on_fp_mode_changed(self):
        """Show/hide the auto or manual widgets when the mode radio changes."""
        auto = self.fp_mode_auto.isChecked()
        self.fp_auto_widget.setVisible(auto)
        self.fp_manual_widget.setVisible(not auto)
        if auto:
            self.recalculate_fire_positions()

    def calculate_scenario_count(self):
        """Calculate total scenario count"""
        # Count HRR selections
        hrr_count = sum([
            self.hrr_005_check.isChecked(),
            self.hrr_010_check.isChecked(),
            self.hrr_020_check.isChecked(),
            self.hrr_030_check.isChecked(),
            self.hrr_050_check.isChecked(),
            self.hrr_100_check.isChecked()
        ]) + len(self.custom_hrr_list)
        
        # Count positions
        if self.fp_mode_auto.isChecked():
            pos_count = self.num_fire_positions_spin.value()
        else:
            positions = [p.strip() for p in self.fire_positions_input.text().split(',') if p.strip()]
            pos_count = len(positions)
        
        # Count traffic
        traffic_count = sum([
            self.traffic_normal_check.isChecked(),
            self.traffic_congested_check.isChecked()
        ])
        
        # Count ventilation
        vent_count = sum([
            self.vent_nvc_check.isChecked(),
            self.vent_nv0_check.isChecked(),
            self.vent_fvp_check.isChecked(),
            self.vent_fv0_check.isChecked(),
            self.vent_fvm_check.isChecked()
        ])
        
        total = hrr_count * pos_count * traffic_count * vent_count
        self.scenario_count_label.setText(str(total))
        
        self.fds_status_text.append(f"\nScenario Count Calculation:")
        self.fds_status_text.append(f"  HRR levels: {hrr_count}")
        self.fds_status_text.append(f"  Fire positions: {pos_count}")
        self.fds_status_text.append(f"  Traffic conditions: {traffic_count}")
        self.fds_status_text.append(f"  Ventilation conditions: {vent_count}")
        self.fds_status_text.append(f"  TOTAL: {total} scenarios")
    
    def generate_fds_files(self):
        """Generate FDS input files"""
        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return
        
        self.fds_status_text.append("\n" + "="*50)
        self.fds_status_text.append("Starting FDS file generation...")
        self.fds_status_text.append("="*50)
        
        try:
            # Collect HRR values
            hrr_list = []
            if self.hrr_005_check.isChecked():
                hrr_list.append(("005", 5000))
            if self.hrr_010_check.isChecked():
                hrr_list.append(("010", 10000))
            if self.hrr_020_check.isChecked():
                hrr_list.append(("020", 20000))
            if self.hrr_030_check.isChecked():
                hrr_list.append(("030", 30000))
            if self.hrr_050_check.isChecked():
                hrr_list.append(("050", 50000))
            if self.hrr_100_check.isChecked():
                hrr_list.append(("100", 100000))
            
            # Add custom HRR values
            for hrr_val in self.custom_hrr_list:
                hrr_code = f"{int(hrr_val):03d}"
                hrr_list.append((hrr_code, hrr_val * 1000))  # Convert MW to kW
            
            # Collect traffic conditions
            traffic_list = []
            if self.traffic_normal_check.isChecked():
                traffic_list.append("Normal")
            if self.traffic_congested_check.isChecked():
                traffic_list.append("Congested")
            
            # Collect ventilation conditions
            vent_list = []
            if self.vent_nvc_check.isChecked():
                vent_list.append("NVC")
            if self.vent_nv0_check.isChecked():
                vent_list.append("NV0")
            if self.vent_fvp_check.isChecked():
                vent_list.append("FVP")
            if self.vent_fv0_check.isChecked():
                vent_list.append("FV0")
            if self.vent_fvm_check.isChecked():
                vent_list.append("FVM")
            
            # Validate selections
            if not hrr_list:
                QMessageBox.warning(self, "No HRR", "Please select at least one HRR value.")
                return
            if not traffic_list:
                QMessageBox.warning(self, "No Traffic", "Please select at least one traffic condition.")
                return
            if not vent_list:
                QMessageBox.warning(self, "No Ventilation", "Please select at least one ventilation condition.")
                return
            
            # Parse fire positions
            if self.fp_mode_auto.isChecked():
                fire_positions = self._get_auto_fire_positions()
                if not fire_positions:
                    QMessageBox.warning(self, "No Positions",
                                        "Could not compute fire positions. "
                                        "Check tunnel length and number of positions.")
                    return
            else:
                positions_text = self.fire_positions_input.text().strip()
                if not positions_text:
                    QMessageBox.warning(self, "No Positions",
                                        "Please enter at least one fire position.")
                    return
                fire_positions = [float(p.strip()) for p in positions_text.split(',')]
            
            # Get FDS version
            fds_version = "FDS6" if self.fds6_radio.isChecked() else "FDS5"
            
            # Get fuel properties
            fuel_type = self.fuel_type_combo.currentText()
            
            # Map fuel type to fuel properties
            fuel_properties = {
                "Petrol": {"fuel_id": "PETROL_CAR_FIRE", "fuel": "ISO_OCTANE"},
                "Diesel": {"fuel_id": "DIESEL", "fuel": "N-DODECANE"},
                "CNG": {"fuel_id": "CNG", "fuel": "METHANE"},
                "LPG": {"fuel_id": "LPG", "fuel": "PROPANE"},
                "EVC": {"fuel_id": "EVC", "fuel": "PROPANE"}
            }
            
            fuel_props = fuel_properties.get(fuel_type, fuel_properties["Diesel"])
            fuel_id = fuel_props["fuel_id"]
            fuel = fuel_props["fuel"]
            soot_yield = self.soot_yield_input.value()
            co_yield = self.co_yield_input.value()
            heat_of_combustion = self.heat_of_combustion_input.value()
            
            self.fds_status_text.append(f"\nFDS Version: {fds_version}")
            self.fds_status_text.append(f"Fuel Type: {fuel_type} ({fuel_id})")
            self.fds_status_text.append(f"Fuel Properties: SOOT={soot_yield:.3f}, CO={co_yield:.3f}, HOC={heat_of_combustion:.2E}")
            
            # Generate FDS files
            import sys
            from pathlib import Path
            fds_workflow_path = Path(self.project_dir).parent / "qra_system_v2" / "fds_workflow"
            if fds_workflow_path.exists():
                sys.path.insert(0, str(fds_workflow_path))
            
            try:
                from fds_generator import FDSInputGenerator
            except ImportError:
                # Try alternative path
                fds_workflow_path = Path(__file__).parent / "fds_workflow"
                if fds_workflow_path.exists():
                    sys.path.insert(0, str(fds_workflow_path))
                from fds_generator import FDSInputGenerator
            
            total_scenarios = len(hrr_list) * len(traffic_list) * len(vent_list) * len(fire_positions)
            self.fds_status_text.append(f"\nGenerating {total_scenarios} scenarios...")
            
            # Import required classes
            from fds_generator import TunnelGeometry, FireScenario
            
            # Create tunnel geometry
            # Calculate width and height from radius (assuming circular tunnel)
            radius = self.tunnel_radius_input.value()
            tunnel = TunnelGeometry(
                length=self.tunnel_length_input.value(),
                width=radius * 2,   # Diameter
                height=radius * 2   # Diameter (assuming circular cross-section)
            )
            
            # Create generator
            generator = FDSInputGenerator(tunnel)
            
            count = 0
            for hrr_code, hrr_val in hrr_list:
                # Create HRR-specific directory
                hrr_dir = Path(self.project_dir) / "fds_inputs" / hrr_code
                hrr_dir.mkdir(parents=True, exist_ok=True)
                
                for traffic in traffic_list:
                    traffic_code = traffic[0]  # N or C
                    traffic_folder = "normal" if traffic == "Normal" else "congested"
                    
                    # Create traffic-specific subdirectory
                    traffic_dir = hrr_dir / traffic_folder
                    traffic_dir.mkdir(parents=True, exist_ok=True)
                    
                    for vent in vent_list:
                        for pos in fire_positions:
                            # Generate filename
                            filename = f"{hrr_code}_{traffic_code}_{vent}_pos{int(pos)}.fds"
                            filepath = traffic_dir / filename
                            
                            # Create fire scenario
                            scenario = FireScenario(
                                hrr_type=hrr_code,
                                hrr_value=hrr_val,
                                fire_position=pos,
                                flashover_time=self.flashover_input.value(),
                                traffic_condition=traffic,
                                ventilation_condition=vent,
                                t_end=self.tend_input.value(),
                                # Fuel properties
                                fuel_type=fuel_type,
                                fuel_id=fuel_id,
                                fuel=fuel,
                                soot_yield=soot_yield,
                                co_yield=co_yield,
                                heat_of_combustion=heat_of_combustion,
                                # FDS version
                                fds_version=fds_version
                            )
                            
                            # Generate file
                            generator.generate_fds_input(scenario, str(filepath))
                            
                            count += 1
                            progress = int((count / total_scenarios) * 100)
                            self.fds_progress_bar.setValue(progress)
                            
                            if count % 10 == 0:
                                self.fds_status_text.append(f"  Generated {count}/{total_scenarios} files...")
                                QApplication.processEvents()
            
            self.fds_status_text.append(f"\n✅ Generated {count} FDS files successfully!")
            self.fds_status_text.append(f"✅ Files organized in fds_inputs/[HRR]/[traffic]/ structure")
            self.fds_progress_bar.setValue(100)
            
            QMessageBox.information(self, "Success", 
                                  f"Generated {count} FDS input files!\n\n"
                                  f"Location: {self.project_dir}/fds_inputs/")
            
            self.tabs.setCurrentIndex(2)
            
            # Update time estimates in Tab 3
            self.update_time_estimates()
            
        except Exception as e:
            self.fds_status_text.append(f"\n❌ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to generate FDS files:\n{str(e)}")
    
    def open_batch_script(self):
        """Open batch script location"""
        if self.project_dir:
            batch_file = Path(self.project_dir) / "run_all_simulations.bat"
            if batch_file.exists():
                import platform
                import subprocess
                
                try:
                    if platform.system() == "Windows":
                        os.startfile(str(batch_file.parent))
                    elif platform.system() == "Darwin":
                        subprocess.run(["open", str(batch_file.parent)])
                    else:
                        subprocess.run(["xdg-open", str(batch_file.parent)])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")
            else:
                QMessageBox.warning(self, "Not Found", "Batch script not found.")
    
    def check_simulation_outputs(self):
        """Check for simulation outputs"""
        if self.project_dir:
            output_dir = Path(self.project_dir) / "fds_outputs"
            if output_dir.exists():
                smv_files = list(output_dir.glob("**/*.smv"))
                self.sim_status_text.append(f"\n✓ Found {len(smv_files)} .smv files")
                for f in smv_files[:10]:
                    self.sim_status_text.append(f"  - {f.name}")
            else:
                self.sim_status_text.append("\n❌ No output directory found")
    
    def browse_fds6_batch(self):
        """Browse for FDS6 batch file location"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FDS6 Batch File",
            "C:/FDS6",
            "Batch Files (*.bat);;All Files (*.*)"
        )
        
        if file_path:
            self.fds6_batch_path.setText(file_path)
            self.sim_status_text.append(f"\n✓ FDS6 batch file set: {file_path}")
    
    def browse_fds5_batch(self):
        """Browse for FDS5 batch file location"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FDS5 Batch File",
            "C:/FDS5",
            "Batch Files (*.bat);;All Files (*.*)"
        )
        
        if file_path:
            self.fds5_batch_path.setText(file_path)
            self.sim_status_text.append(f"\n✓ FDS5 batch file set: {file_path}")
    
    def browse_fds_exe(self):
        """Browse for FDS.exe location"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FDS Executable or Batch File",
            "",
            "FDS Files (*.exe *.bat);;Executable Files (*.exe);;Batch Files (*.bat);;All Files (*.*)"
        )
        
        if file_path:
            # Check if user selected a batch file - suggest using .exe instead
            if file_path.lower().endswith('.bat'):
                # Find fds.exe in the same directory
                fds_exe_path = Path(file_path).parent / 'fds.exe'
                if fds_exe_path.exists():
                    reply = QMessageBox.question(
                        self,
                        "Use fds.exe Instead?",
                        f"You selected a batch file, but batch files can have parameter issues.\n\n"
                        f"Found 'fds.exe' in the same directory:\n{fds_exe_path}\n\n"
                        f"Would you like to use fds.exe directly instead?\n"
                        f"(This is more reliable)",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if reply == QMessageBox.Yes:
                        file_path = str(fds_exe_path)
                        self.sim_status_text.append(f"\n✓ Using fds.exe (direct execution)")
                    else:
                        self.sim_status_text.append(f"\n⚠️ Using batch file (may have issues)")
                else:
                    QMessageBox.warning(
                        self,
                        "Batch File Selected",
                        "Batch files can have parameter parsing issues.\n\n"
                        "If simulations fail, try using fds.exe directly instead."
                    )
                    self.sim_status_text.append(f"\n⚠️ Using batch file: {file_path}")
            
            # If user selected fds.exe or fds, check for fds_openmp first
            if file_path.lower().endswith('fds.exe') or file_path.lower().endswith('fds'):
                # Check if fds_openmp exists in the same directory
                fds_dir = Path(file_path).parent
                fds_openmp_path = fds_dir / 'fds_openmp'
                fds_openmp_exe_path = fds_dir / 'fds_openmp.exe'
                
                if fds_openmp_path.exists() or fds_openmp_exe_path.exists():
                    # Prefer fds_openmp for multi-core performance
                    openmp_path = fds_openmp_path if fds_openmp_path.exists() else fds_openmp_exe_path
                    reply = QMessageBox.question(
                        self,
                        "Use fds_openmp for Better Performance?",
                        f"Found 'fds_openmp' in the same directory!\n\n"
                        f"fds_openmp uses OpenMP for multi-core execution,\n"
                        f"making each simulation significantly faster.\n\n"
                        f"Recommended: Use fds_openmp\n\n"
                        f"Would you like to use fds_openmp instead?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if reply == QMessageBox.Yes:
                        file_path = str(openmp_path)
                        self.sim_status_text.append(f"\n✓ Using fds_openmp (multi-core OpenMP)")
                        QMessageBox.information(
                            self,
                            "fds_openmp Selected",
                            f"Using fds_openmp for multi-core execution.\n\n"
                            f"Each simulation will utilize multiple CPU cores\n"
                            f"for faster completion.\n\n"
                            f"Expected speedup: 2-4x depending on CPU."
                        )
                    else:
                        self.sim_status_text.append(f"\n✓ Using {Path(file_path).name} with mpiexec wrapper")
                else:
                    self.sim_status_text.append(f"\n✓ Using {Path(file_path).name} with mpiexec wrapper")
                    QMessageBox.information(
                        self,
                        "FDS Executable Selected",
                        f"Selected: {Path(file_path).name}\n\n"
                        f"The application will run FDS with mpiexec for local execution:\n"
                        f"mpiexec -localonly -n 1 fds filename.fds\n\n"
                        f"Note: If fds_openmp is available, it would be faster\n"
                        f"as it uses multiple CPU cores per simulation."
                    )
            
            # Validate: Don't allow fds2ascii to be set as FDS executable
            if 'fds2ascii' in Path(file_path).name.lower():
                QMessageBox.warning(
                    self,
                    "Wrong Tool Selected",
                    f"You selected 'fds2ascii', which is a conversion tool, not the FDS simulator.\n\n"
                    f"Please select the FDS executable instead:\n"
                    f"  • fds_openmp.exe (recommended for multi-core)\n"
                    f"  • fds.exe (standard version)\n\n"
                    f"These are usually in the same directory as fds2ascii."
                )
                self.sim_status_text.append(f"\n❌ Cannot use fds2ascii as FDS executable")
                return
            
            self.fds_exe_path.setText(file_path)
            self.sim_status_text.append(f"\n✓ FDS path set: {file_path}")
            
            # Auto-detect fds2ascii in the same directory
            fds_dir = Path(file_path).parent
            fds2ascii_exe = fds_dir / 'fds2ascii.exe'
            if not fds2ascii_exe.exists():
                fds2ascii_exe = fds_dir / 'fds2ascii'  # Linux/Mac
            
            if fds2ascii_exe.exists() and not self.fds2ascii_path.text():
                self.fds2ascii_path.setText(str(fds2ascii_exe))
                self.sim_status_text.append(f"✓ Auto-detected fds2ascii: {fds2ascii_exe}")
            
            # Auto-detect FDS2FDB.exe in the same bin directory
            for fdb_candidate in ['FDS2FDB.exe', 'fds2fdb.exe', 'FDS2FDB']:
                fds2fdb_candidate = fds_bin_dir / fdb_candidate
                if fds2fdb_candidate.exists() and hasattr(self, 'fds2fdb_exe_path') and not self.fds2fdb_exe_path.text():
                    self.fds2fdb_exe_path.setText(str(fds2fdb_candidate))
                    self.sim_status_text.append(f"✓ Auto-detected FDS2FDB: {fds2fdb_candidate}")
                    break
    
    def browse_fds2ascii(self):
        """Browse for fds2ascii.exe location"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select fds2ascii Executable",
            "",
            "Executable Files (*.exe);;All Files (*.*)"
        )
        
        if file_path:
            self.fds2ascii_path.setText(file_path)
    
    def on_mode_changed(self):
        """Handle workflow mode change"""
        is_simple_mode = self.simple_mode_radio.isChecked()
        self.simple_mode_widget.setVisible(is_simple_mode)
        
        if is_simple_mode:
            self.sim_status_text.append("\n🎯 Switched to Simple Mode - Select a single FDS file")
        else:
            self.sim_status_text.append("\n📦 Switched to Batch Mode - Run all generated scenarios")
    
    def browse_single_fds_file(self):
        """Browse for a single FDS file in Simple Mode"""
        from PyQt5.QtWidgets import QFileDialog
        
        # Start from project fds_inputs directory if available
        start_dir = ""
        if self.project_dir:
            fds_inputs_dir = Path(self.project_dir) / "fds_inputs"
            if fds_inputs_dir.exists():
                start_dir = str(fds_inputs_dir)
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FDS Input File",
            start_dir,
            "FDS Files (*.fds);;All Files (*.*)"
        )
        
        if file_path:
            self.simple_fds_file_input.setText(file_path)
            self.sim_status_text.append(f"\n✓ Selected FDS file: {Path(file_path).name}")
            
            # Extract scenario info from filename
            filename = Path(file_path).stem
            self.sim_status_text.append(f"  Scenario: {filename}")
            
            # Auto-detect FDS executable in the same directory
            fds_dir = Path(file_path).parent
            
            # Look for fds_openmp first (preferred)
            fds_openmp_exe = fds_dir / 'fds_openmp.exe'
            if not fds_openmp_exe.exists():
                fds_openmp_exe = fds_dir / 'fds_openmp'  # Linux/Mac
            
            # Fall back to regular fds
            fds_exe = fds_dir / 'fds.exe'
            if not fds_exe.exists():
                fds_exe = fds_dir / 'fds'  # Linux/Mac
            
            # Auto-set FDS executable if not already set
            if fds_openmp_exe.exists() and not self.fds_exe_path.text():
                self.fds_exe_path.setText(str(fds_openmp_exe))
                self.sim_status_text.append(f"✓ Auto-detected FDS: {fds_openmp_exe.name} (OpenMP)")
            elif fds_exe.exists() and not self.fds_exe_path.text():
                self.fds_exe_path.setText(str(fds_exe))
                self.sim_status_text.append(f"✓ Auto-detected FDS: {fds_exe.name}")
    
    def is_simple_mode(self):
        """Check if Simple Mode is active"""
        return self.simple_mode_radio.isChecked()
    
    def run_fds_simulations(self):
        """Run FDS simulations on all generated input files (in background thread)"""
        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return
        
        # Determine FDS version from radio button
        fds_version = "FDS6" if self.fds6_radio.isChecked() else "FDS5"
        
        # Get appropriate batch file or executable
        if fds_version == "FDS6":
            fds_batch = self.fds6_batch_path.text().strip()
            if fds_batch and Path(fds_batch).exists():
                fds_exe = fds_batch
                self.sim_status_text.append(f"\n✓ Using FDS6 batch file: {fds_batch}")
            else:
                fds_exe = self.fds_exe_path.text().strip()
                if not fds_exe or not Path(fds_exe).exists():
                    QMessageBox.warning(self, "FDS6 Not Found", 
                                      "Please specify either:\n\n"
                                      "1. FDS6 Batch File (run_fds6.bat) - Recommended\n"
                                      "2. FDS6 Executable (fds_openmp.exe)\n\n"
                                      "The batch file method avoids conflicts with FDS5.")
                    return
        else:  # FDS5
            fds_batch = self.fds5_batch_path.text().strip()
            if fds_batch and Path(fds_batch).exists():
                fds_exe = fds_batch
                self.sim_status_text.append(f"\n✓ Using FDS5 batch file: {fds_batch}")
            else:
                fds_exe = self.fds_exe_path.text().strip()
                if not fds_exe or not Path(fds_exe).exists():
                    QMessageBox.warning(self, "FDS5 Not Found", 
                                      "Please specify either:\n\n"
                                      "1. FDS5 Batch File (run_fds5.bat) - Recommended\n"
                                      "2. FDS5 Executable (fds.exe)\n\n"
                                      "The batch file method avoids conflicts with FDS6.")
                    return
        
        # Check mode and get FDS files accordingly
        if self.is_simple_mode():
            # Simple Mode: Single file
            single_file = self.simple_fds_file_input.text().strip()
            if not single_file or not Path(single_file).exists():
                QMessageBox.warning(self, "No File Selected", 
                                  "Please select an FDS input file using the Browse button.")
                return
            fds_files = [Path(single_file)]
        else:
            # Batch Mode: All files
            fds_inputs_dir = Path(self.project_dir) / "fds_inputs"
            if not fds_inputs_dir.exists():
                QMessageBox.warning(self, "No Input Files", 
                                  "No FDS input files found. Please generate them first in Tab 2.")
                return
            
            fds_files = list(fds_inputs_dir.glob("**/*.fds"))
            if not fds_files:
                QMessageBox.warning(self, "No Input Files", 
                                  "No FDS input files found. Please generate them first in Tab 2.")
                return
        
        # Confirm before starting
        reply = QMessageBox.question(
            self,
            "Run Simulations",
            f"Found {len(fds_files)} FDS input files.\n\n"
            f"This will run all simulations sequentially.\n"
            f"Estimated time: {len(fds_files) * 15} minutes (approx 15 min per simulation).\n\n"
            f"Do you want to continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Prepare output directory
        output_dir = Path(self.project_dir) / "fds_outputs"
        output_dir.mkdir(exist_ok=True)
        
        self.sim_status_text.append("\n" + "="*50)
        self.sim_status_text.append("Starting FDS Simulations...")
        self.sim_status_text.append("="*50)
        self.sim_status_text.append(f"FDS.exe: {fds_exe}")
        self.sim_status_text.append(f"Total simulations: {len(fds_files)}")
        self.sim_status_text.append(f"Output directory: {output_dir}")
        
        # Calculate timeout based on T_END values
        # Read T_END from first file as representative
        t_end = 900.0  # default
        try:
            with open(fds_files[0], 'r') as f:
                for line in f:
                    if 'T_END' in line and '&TIME' in line:
                        parts = line.split('T_END')
                        if len(parts) > 1:
                            value_part = parts[1].split('/')[0].strip().replace('=', '').strip()
                            t_end = float(value_part)
                        break
        except:
            pass
        
        # Calculate timeout per file based on cores and mesh complexity
        # Large mesh (2.3M cells) runs at ~0.76x real-time with 4 cores
        # With 16 cores: ~3x real-time speedup
        # Safety factor: 60x to account for mesh size and ensure completion
        timeout_per_file = int(t_end * 60)  # 60x safety factor for large meshes
        
        # Get user-selected cores
        num_cores = self.cores_spinbox.value()
        
        self.sim_status_text.append(f"CPU cores: {num_cores}")
        self.sim_status_text.append(f"T_END: {t_end:.0f} seconds")
        self.sim_status_text.append(f"Timeout per file: {timeout_per_file:.0f} seconds ({timeout_per_file/60:.1f} minutes)")
        
        # Enable/disable buttons
        self.run_sim_btn.setEnabled(False)
        self.stop_sim_btn.setEnabled(True)
        self.sim_progress_bar.setValue(0)
        
        # Get parallel jobs setting
        parallel_jobs = self.parallel_jobs_spinbox.value()
        
        # Start simulation in background thread
        self.simulation_stopped = False
        self.sim_thread = FDSSimulationThread(fds_exe, fds_files, output_dir, num_cores, timeout_per_file, parallel_jobs)
        self.sim_thread.progress_signal.connect(self.update_simulation_progress)
        self.sim_thread.status_signal.connect(self.update_simulation_status)
        self.sim_thread.finished_signal.connect(self.simulation_finished)
        self.sim_thread.start()
    
    def update_simulation_progress(self, progress):
        """Update progress bar from thread"""
        self.sim_progress_bar.setValue(progress)
    
    def update_simulation_status(self, message):
        """Update status text from thread"""
        self.sim_status_text.append(message)
    
    def simulation_finished(self, completed, failed, total):
        """Handle simulation completion"""
        # Summary
        self.sim_status_text.append("\n" + "="*50)
        self.sim_status_text.append("Simulation Summary:")
        self.sim_status_text.append(f"  ✓ Completed: {completed}")
        self.sim_status_text.append(f"  ✗ Failed: {failed}")
        self.sim_status_text.append(f"  Total: {total}")
        self.sim_status_text.append("="*50)
        
        # Re-enable buttons
        self.run_sim_btn.setEnabled(True)
        self.stop_sim_btn.setEnabled(False)
        self.sim_progress_bar.setValue(100)
        
        QMessageBox.information(
            self,
            "Simulations Complete",
            f"Completed: {completed}\nFailed: {failed}\nTotal: {total}"
        )
    
    def stop_fds_simulations(self):
        """Stop running FDS simulations"""
        if hasattr(self, 'sim_thread') and self.sim_thread.isRunning():
            self.sim_thread.stop()
            self.sim_status_text.append("\n⏸️ Stopping simulations...")
        else:
            self.sim_status_text.append("\n⚠️ No simulations running")
    

    # ══════════════════════════════════════════════════════════════════════════
    # FDS2FDB and fds2ascii integration
    # ══════════════════════════════════════════════════════════════════════════

    def browse_fds2fdb_exe(self):
        """Browse for FDS2FDB.exe"""
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FDS2FDB Executable", "C:/",
            "Executables (FDS2FDB.exe *.exe);;All Files (*.*)"
        )
        if file_path:
            self.fds2fdb_exe_path.setText(file_path)
            self.sim_status_text.append(f"\n✓ FDS2FDB executable set: {file_path}")

    def browse_convert_des(self):
        """Browse for CONVERT.DES and parse its contents into the preview label"""
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CONVERT.DES Configuration File", "",
            "DES Files (*.DES *.des);;All Files (*.*)"
        )
        if file_path:
            self.convert_des_path.setText(file_path)
            self._parse_and_preview_convert_des(file_path)

    def _parse_and_preview_convert_des(self, des_path):
        """Parse CONVERT.DES and show a human-readable summary in the preview label.

        Expected format (from the project's CONVERT.DES):
            Line 0: header
            Line 1: FDS_ID  AxisDir  VertDir  TimeDtep  iTempSkip  SLC_1 SLC_2 ... SLC_N
            Line 2: header
            Line 3: SOOT  CO2  CO  TEMP  RADI  OXYGEN  ...
            Line 4: factor values
        """
        try:
            with open(des_path, 'r', errors='replace') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]

            # Parse simulation parameters (line index 1)
            params = lines[1].split()
            fds_id     = params[0]
            axis_dir   = params[1]
            vert_dir   = params[2]
            time_step  = params[3]
            temp_skip  = params[4]
            slc_nums   = [x for x in params[5:] if x != '0']

            # Parse variable names (line index 3) and factors (line index 4)
            var_names   = lines[3].split()
            factor_vals = lines[4].split()
            factors = {var_names[i]: factor_vals[i]
                       for i in range(min(len(var_names), len(factor_vals)))}

            preview = (
                f"✅  CONVERT.DES loaded  |  "
                f"FDS_ID: {fds_id}  |  "
                f"Axis: {axis_dir}  Vert: {vert_dir}  |  "
                f"TimeStep: {time_step} s  SkipEvery: {temp_skip}  |  "
                f"Slice files: {', '.join(slc_nums)}  |  "
                f"Factors — " +
                "  ".join(f"{k}×{v}" for k, v in factors.items())
            )
            self.convert_des_preview.setText(preview)
            self.convert_des_preview.setStyleSheet(
                "color: #1a6e2e; font-size: 11px; font-weight: bold; "
                "margin-left: 4px; padding: 3px; background: #eafaf1; border-radius: 3px;")
            self.sim_status_text.append(
                f"\n✓ CONVERT.DES parsed:"
                f"\n  FDS_ID={fds_id}  Axis={axis_dir}  Vert={vert_dir}"
                f"\n  TimeStep={time_step}s  SkipEvery={temp_skip}"
                f"\n  Slice files: {', '.join(slc_nums)}"
                f"\n  Conversion factors: {factors}"
            )
        except Exception as e:
            self.convert_des_preview.setText(f"⚠️  Could not parse CONVERT.DES: {e}")
            self.convert_des_preview.setStyleSheet(
                "color: #c0392b; font-size: 11px; margin-left: 4px; padding: 3px;")

    # ── CONVERT.DES helper ────────────────────────────────────────────────────

    def _parse_convert_des_params(self, des_path: Path):
        """Return (fds_id, slice_list) from CONVERT.DES — read-only, never modified.

        CONVERT.DES line 1 (2nd non-empty line):
            FDS_ID  AxisDir  VertDir  TimeStep  iSkip  SLC_1 SLC_2 … SLC_N
        """
        try:
            with open(des_path, 'r', errors='replace') as f:
                non_empty = [l.strip() for l in f if l.strip()]
            params   = non_empty[1].split()
            fds_id   = params[0].strip()
            slc_nums = [x for x in params[5:] if x.strip() not in ('', '0')]
            return fds_id, slc_nums
        except Exception:
            return None, []

    # ── FDS2FDB runner ────────────────────────────────────────────────────────

    def convert_smv_to_fdb_with_exe(self):
        """Run FDS2FDB.exe automatically, replicating exactly what works manually.

        What the working manual workflow looks like (confirmed from screenshot):
        ─────────────────────────────────────────────────────────────────────────
          fds_outputs/
            FDS2FDB.exe      ← placed here manually
            CONVERT.DES      ← placed here manually
            TN.smv           ← already here from FDS run
            TN_0001.sf … .sf ← already here from FDS run
          → double-click FDS2FDB.exe → 020CFV0.FDB generated ✓

        Automated replication
        ─────────────────────
        For each simulation output folder found under fds_outputs/:

          Step 1 — Copy FDS2FDB.exe into the sim folder (if not already there).
          Step 2 — Copy CONVERT.DES into the sim folder verbatim (no changes).
          Step 3 — Run FDS2FDB.exe with CWD = that sim folder.
          Step 4 — Collect any .fdb files produced.
          Step 5 — Remove the temporary exe + DES copies (keep the .fdb output).

        CONVERT.DES is NEVER edited.  FDS_ID, slice numbers, factors — untouched.
        """
        import subprocess, shutil

        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return

        fds2fdb_exe = self.fds2fdb_exe_path.text().strip()
        convert_des = self.convert_des_path.text().strip()

        # ── Validate UI fields ────────────────────────────────────────────────
        errors = []
        if not fds2fdb_exe or not Path(fds2fdb_exe).exists():
            errors.append("• FDS2FDB.exe not found — use Browse… to locate it.")
        if not convert_des or not Path(convert_des).exists():
            errors.append("• CONVERT.DES not found — use Browse… to locate it.")
        if errors:
            QMessageBox.warning(self, "Missing Files", "\n".join(errors))
            return

        fds2fdb_exe_path = Path(fds2fdb_exe)
        convert_des_path = Path(convert_des)

        # Read for display only
        fds_id, des_slices = self._parse_convert_des_params(convert_des_path)
        self.sim_status_text.append(
            f"\n  CONVERT.DES  →  FDS_ID='{fds_id}'  Slices: {des_slices}  (verbatim)")

        # ── Find simulation output folders ────────────────────────────────────
        output_base = Path(self.project_dir) / "fds_outputs"
        sim_dirs = []
        for f in list(output_base.rglob("*.sf")) + list(output_base.rglob("*.smv")) + \
                  list(output_base.rglob("*.out")):
            if f.parent not in sim_dirs:
                sim_dirs.append(f.parent)

        if not sim_dirs:
            QMessageBox.warning(self, "No Simulation Outputs",
                "No FDS output files (.sf / .smv / .out) found under fds_outputs/.\n\n"
                "Run your FDS simulations first.")
            return

        # ── Confirm dialog ────────────────────────────────────────────────────
        info_lines = [
            f"Found {len(sim_dirs)} simulation folder(s).\n",
            f"FDS2FDB.exe and CONVERT.DES will be copied into each folder,",
            f"then FDS2FDB.exe will run there (exactly as the manual process).",
            f"Temporary copies are removed after each run.\n",
        ]
        for d in sim_dirs:
            smv_files = list(d.glob("*.smv"))
            sf_files  = list(d.glob("*.sf"))
            info_lines.append(
                f"  📂 {d.name}  —  "
                f"{len(sf_files)} .sf file(s)  |  "
                f"{'✓ .smv present' if smv_files else '⚠ no .smv found'}"
            )
        info_lines.append("\nContinue?")

        reply = QMessageBox.question(
            self, "Run FDS2FDB",
            "\n".join(info_lines),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        self.sim_status_text.append("\n" + "=" * 60)
        self.sim_status_text.append("  FDS2FDB.exe  —  Automated In-Place Conversion")
        self.sim_status_text.append("=" * 60)

        from PyQt5.QtWidgets import QApplication
        converted, failed = 0, 0

        for idx, sim_dir in enumerate(sim_dirs, 1):
            self.sim_status_text.append(f"\n[{idx}/{len(sim_dirs)}] 📂 {sim_dir}")
            QApplication.processEvents()

            log_path  = sim_dir / "fds2fdb_run.log"

            # Destination paths inside the sim folder
            exe_dest = sim_dir / fds2fdb_exe_path.name   # e.g. FDS2FDB.exe
            des_dest = sim_dir / "CONVERT.DES"

            # Remember whether WE placed these (so we only delete what we added)
            we_placed_exe = False
            we_placed_des = False

            try:
                # ── Step 1: Copy FDS2FDB.exe into sim folder ──────────────────
                if exe_dest.resolve() != fds2fdb_exe_path.resolve():
                    shutil.copy2(fds2fdb_exe_path, exe_dest)
                    we_placed_exe = True
                    self.sim_status_text.append(
                        f"     ✓  FDS2FDB.exe  →  {sim_dir.name}/")
                else:
                    self.sim_status_text.append(
                        f"     ✓  FDS2FDB.exe already in sim folder")

                # ── Step 2: Copy CONVERT.DES verbatim into sim folder ─────────
                if des_dest.resolve() != convert_des_path.resolve():
                    shutil.copy2(convert_des_path, des_dest)
                    we_placed_des = True
                    self.sim_status_text.append(
                        f"     ✓  CONVERT.DES  →  {sim_dir.name}/  (verbatim)")
                else:
                    self.sim_status_text.append(
                        f"     ✓  CONVERT.DES already in sim folder")

                # Warn if .smv is absent (FDS2FDB needs it — unit 11)
                smv_files = list(sim_dir.glob("*.smv"))
                if not smv_files:
                    self.sim_status_text.append(
                        f"     ⚠️  No .smv file found in this folder.\n"
                        f"        FDS2FDB will fail with 'file not found, unit 11'.\n"
                        f"        Copy the FDS-generated <CHID>.smv into:\n"
                        f"        {sim_dir}")
                else:
                    self.sim_status_text.append(
                        f"     ✓  {smv_files[0].name} present")

                # ── Step 3: Run FDS2FDB.exe with CWD = sim folder ─────────────
                self.sim_status_text.append(
                    f"     ▶  Running {exe_dest.name}  (CWD = sim folder) …")
                QApplication.processEvents()

                result = subprocess.run(
                    [str(exe_dest)],
                    cwd=str(sim_dir),
                    capture_output=True,
                    text=True,
                    timeout=3600
                )

                rc_hex = hex(result.returncode & 0xFFFFFFFF)

                # ── Write log ─────────────────────────────────────────────────
                with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
                    lf.write(f"FDS2FDB Run Log\n{'='*60}\n")
                    lf.write(f"Sim folder      : {sim_dir}\n")
                    lf.write(f"FDS2FDB.exe     : {fds2fdb_exe_path}\n")
                    lf.write(f"CONVERT.DES     : {convert_des_path}\n")
                    lf.write(f"DES FDS_ID      : {fds_id}\n")
                    lf.write(f"DES slices      : {des_slices}\n")
                    lf.write(f"Return code     : {result.returncode}\n")
                    lf.write(f"Return code hex : {rc_hex}\n\n")
                    lf.write("=== STDOUT ===\n")
                    lf.write(result.stdout or "(no output)\n")
                    lf.write("\n=== STDERR ===\n")
                    lf.write(result.stderr or "(no errors)\n")

                # ── Step 4: Check for .fdb output ─────────────────────────────
                fdb_files = list(sim_dir.glob("*.fdb"))
                if fdb_files:
                    for fdb in fdb_files:
                        size_mb = fdb.stat().st_size / (1024 * 1024)
                        self.sim_status_text.append(
                            f"  ✅  {fdb.name}  ({size_mb:.2f} MB)")
                    converted += 1
                else:
                    self.sim_status_text.append(
                        f"  ❌  No .fdb produced  |  RC={result.returncode} ({rc_hex})")

                    known = {
                        0xC000001D: (
                            "Fortran runtime abort — check STDERR in log.\n"
                            "        'unit 11' = <CHID>.smv not found in the sim folder."),
                        0xC0000005: (
                            "Access Violation — a .sf file listed in CONVERT.DES is missing."),
                        0xC000007B: (
                            "Bad Image — install Microsoft Visual C++ 2005 Redistributable (x86)."),
                        0xC0000135: (
                            "DLL Not Found — install VC++ 2005 Redistributable (x86)."),
                    }
                    rc_u = result.returncode & 0xFFFFFFFF
                    msg  = known.get(rc_u, "Unexpected exit — see log for details.")
                    self.sim_status_text.append(f"     • {msg}")

                    stderr_lower = (result.stderr or "").lower()
                    if "unit 11" in stderr_lower:
                        smv_name = f"{fds_id}.smv" if fds_id else "<CHID>.smv"
                        self.sim_status_text.append(
                            f"     • Copy {smv_name} into the sim folder and retry.")

                    self.sim_status_text.append(f"     📄 {log_path}")
                    failed += 1

            except subprocess.TimeoutExpired:
                self.sim_status_text.append("  ⏱️  Timeout (> 60 min).")
                failed += 1
            except FileNotFoundError as e:
                self.sim_status_text.append(f"  ❌  {e}")
                failed += 1
            except PermissionError as e:
                self.sim_status_text.append(
                    f"  ❌  Permission denied: {e}  (try Run as Administrator)")
                failed += 1
            except Exception as e:
                self.sim_status_text.append(f"  ❌  {e}")
                failed += 1
            finally:
                # ── Step 5: Remove only the copies WE placed ──────────────────
                for tmp, placed in [(exe_dest, we_placed_exe),
                                    (des_dest, we_placed_des)]:
                    if placed and tmp.exists():
                        try:
                            tmp.unlink()
                        except Exception:
                            pass

        # ── Summary ───────────────────────────────────────────────────────────
        self.sim_status_text.append("\n" + "=" * 60)
        self.sim_status_text.append(
            f"  FDS2FDB Summary:  ✅ {converted} converted   "
            f"❌ {failed} failed   Total: {len(sim_dirs)}")
        self.sim_status_text.append("=" * 60)

        if converted > 0 and failed == 0:
            QMessageBox.information(
                self, "FDS2FDB Complete ✅",
                f"All {converted} simulation(s) converted successfully!\n\n"
                f".fdb files are in each simulation output folder.\n"
                f"Ready for EVC/FED analysis in Tab 4."
            )
        elif converted > 0:
            QMessageBox.warning(
                self, "FDS2FDB – Partial Success ⚠️",
                f"Converted: {converted}   Failed: {failed}\n\n"
                f"Check fds2fdb_run.log in each failed folder for details."
            )
        else:
            QMessageBox.critical(
                self, "FDS2FDB Failed ❌",
                f"No .fdb files were produced.\n\n"
                f"Check fds2fdb_run.log in the output folder.\n\n"
                f"Common causes:\n"
                f"1. <CHID>.smv missing from the sim folder  "
                f"(RC=0xC000001D / 'unit 11' in log)\n"
                f"2. A .sf file listed in CONVERT.DES is missing  "
                f"(RC=0xC0000005)\n"
                f"3. VC++ 2005 Redistributable (x86) not installed  "
                f"(RC=0xC000007B or 0xC0000135)\n"
                f"4. FDS simulation did not fully complete"
            )

    # ── fds2ascii runner ──────────────────────────────────────────────────────

    def run_fds2ascii_conversion(self):
        """Run fds2ascii_win_64.exe on all FDS output directories to produce
        ASCII/CSV files from binary slice, boundary, and Plot3D files.

        fds2ascii is interactive by default — we drive it with a pipe/stdin
        sequence:
            1  → convert slice files
            <stem>  → base name (CHID)
            (blank) → default output filename
            0  → quit

        Outputs land in the ascii_files/ subdirectory of the project.
        """
        import subprocess, shutil, sys

        if not self.project_dir:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Project", "Please open a project first.")
            return

        fds2ascii_exe = self.fds2ascii_path.text().strip()
        if not fds2ascii_exe or not Path(fds2ascii_exe).exists():
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "fds2ascii Not Found",
                "Please specify the path to fds2ascii / fds2ascii_win_64.exe "
                "in the fds2ascii Tool field.")
            return

        output_base = Path(self.project_dir) / "fds_outputs"
        ascii_out_root = Path(self.project_dir) / "ascii_files"
        ascii_out_root.mkdir(parents=True, exist_ok=True)

        # Find simulation directories that have .sf (slice) files
        sim_dirs = []
        for sf in output_base.rglob("*.sf"):
            d = sf.parent
            if d not in sim_dirs:
                sim_dirs.append(d)

        if not sim_dirs:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Slice Files",
                "No FDS slice files (.sf) found.\n\nRun simulations first.")
            return

        from PyQt5.QtWidgets import QMessageBox, QApplication
        reply = QMessageBox.question(
            self, "Run fds2ascii",
            f"Found {len(sim_dirs)} folder(s) with FDS slice files.\n\n"
            f"fds2ascii will convert binary .sf slice files to ASCII/CSV.\n"
            f"Output will be written to:\n  {ascii_out_root}\n\n"
            f"This is useful for:\n"
            f"  • Inspecting raw FDS data in Excel or Python\n"
            f"  • Debugging slice file contents\n"
            f"  • Extracting time-series at specific locations\n\n"
            f"Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        self.sim_status_text.append("\n" + "=" * 50)
        self.sim_status_text.append("Running fds2ascii...")
        self.sim_status_text.append("=" * 50)

        converted, failed = 0, 0

        for sim_dir in sim_dirs:
            self.sim_status_text.append(f"\n📂 {sim_dir.name}")
            QApplication.processEvents()

            # Derive CHID from .smv or .out filename
            chid = None
            for smv in sim_dir.glob("*.smv"):
                chid = smv.stem
                break
            if not chid:
                for out in sim_dir.glob("*.out"):
                    chid = out.stem
                    break
            if not chid:
                self.sim_status_text.append("  ⚠️  Cannot determine CHID — skipping")
                failed += 1
                continue

            # ASCII-safe temp work dir (same Unicode workaround as FDS5)
            if sys.platform == 'win32':
                ascii_base = Path('C:/FDS5_run')
            else:
                ascii_base = Path('/tmp/fds5_run')

            ascii_work = ascii_base / ("asc_" + sim_dir.name[:20])
            ascii_work.mkdir(parents=True, exist_ok=True)
            ascii_dest = ascii_out_root / sim_dir.name
            ascii_dest.mkdir(parents=True, exist_ok=True)

            try:
                # Copy all FDS outputs to ASCII work dir
                for f in sim_dir.iterdir():
                    try:
                        shutil.copy2(f, ascii_work / f.name)
                    except Exception:
                        pass

                # Build stdin for fds2ascii interactive prompts:
                #   '1' = convert slice files
                #   chid = base name / CHID
                #   '' = accept default output file name
                #   '0' = quit
                stdin_input = f"1\n{chid}\n\n0\n"

                result = subprocess.run(
                    [str(Path(fds2ascii_exe))],
                    input=stdin_input,
                    cwd=str(ascii_work),
                    capture_output=True,
                    text=True,
                    timeout=3600
                )

                # Log
                log_path = ascii_dest / "fds2ascii_run.log"
                with open(log_path, 'w', encoding='utf-8') as lf:
                    lf.write("=== fds2ascii STDOUT ===\n")
                    lf.write(result.stdout or "(no output)\n")
                    lf.write("\n=== fds2ascii STDERR ===\n")
                    lf.write(result.stderr or "(no errors)\n")
                    lf.write(f"\n=== RETURN CODE: {result.returncode} ===\n")

                # Copy ASCII/CSV output files to ascii_dest
                csv_files = []
                for out_f in ascii_work.iterdir():
                    if out_f.suffix.lower() in ('.csv', '.txt', '.dat', '.asc'):
                        shutil.copy2(out_f, ascii_dest / out_f.name)
                        csv_files.append(out_f.name)

                try:
                    shutil.rmtree(ascii_work)
                except Exception:
                    pass

                if csv_files:
                    self.sim_status_text.append(f"  ✓ {len(csv_files)} ASCII file(s) → {ascii_dest.name}/")
                    for fn in csv_files[:5]:
                        self.sim_status_text.append(f"    • {fn}")
                    if len(csv_files) > 5:
                        self.sim_status_text.append(f"    … and {len(csv_files)-5} more")
                    converted += 1
                else:
                    self.sim_status_text.append(f"  ⚠️  No ASCII files produced. RC={result.returncode}")
                    out_preview = (result.stdout or result.stderr or "")[:200]
                    self.sim_status_text.append(f"     {out_preview}")
                    failed += 1

            except subprocess.TimeoutExpired:
                self.sim_status_text.append("  ⏱️ Timeout")
                try:
                    shutil.rmtree(ascii_work)
                except Exception:
                    pass
                failed += 1
            except Exception as e:
                self.sim_status_text.append(f"  ❌ {e}")
                try:
                    shutil.rmtree(ascii_work)
                except Exception:
                    pass
                failed += 1

        self.sim_status_text.append("\n" + "=" * 50)
        self.sim_status_text.append(f"fds2ascii Summary: ✓ {converted}   ✗ {failed}   Total: {len(sim_dirs)}")
        self.sim_status_text.append(f"ASCII output folder: {ascii_out_root}")
        self.sim_status_text.append("=" * 50)

        if converted > 0:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "fds2ascii Complete",
                f"Converted {converted} simulation(s) to ASCII/CSV!\n\n"
                f"Files saved to:\n{ascii_out_root}\n\n"
                f"You can now:\n"
                f"  • Open .csv files in Excel\n"
                f"  • Load into Python/pandas for analysis\n"
                f"  • Use in Tab 4 (EVC/FED Analysis)"
            )

    def convert_smv_to_fdb(self):
        """Legacy Python converter — now replaced by convert_smv_to_fdb_with_exe() which uses FDS2FDB.exe.
        Kept for backwards compatibility. The button now calls convert_smv_to_fdb_with_exe()."""
        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return
        
        # Find FDS output directories
        output_base_dir = Path(self.project_dir) / "fds_outputs"
        if not output_base_dir.exists():
            QMessageBox.warning(self, "No Outputs", 
                              "No FDS outputs directory found.\n\n"
                              "Please run simulations first.")
            return
        
        # Find all simulation output directories (containing .smv files)
        sim_dirs = []
        for smv_file in output_base_dir.rglob("*.smv"):
            sim_dir = smv_file.parent
            if sim_dir not in sim_dirs:
                sim_dirs.append(sim_dir)
        
        if not sim_dirs:
            QMessageBox.warning(self, "No Simulations", 
                              "No FDS simulation outputs found.\n\n"
                              "Please run simulations first.")
            return
        
        # Confirm conversion
        reply = QMessageBox.question(
            self,
            "Convert FDS to FDB",
            f"Found {len(sim_dirs)} FDS simulation(s).\n\n"
            f"This will convert FDS slice files to FDB database format\n"
            f"using the Python FDS-to-FDB converter.\n\n"
            f"FDB files are used for EVC/FED analysis.\n\n"
            f"Do you want to continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Import FDS to FDB converter
        # try:
        #     from fds_workflow.fds_to_fdb_converter import convert_fds_to_fdb
        #     from database.fdb_conversion_db import get_fdb_conversion_db
        # except ImportError as e:
        #     QMessageBox.critical(self, "Import Error",
        #                        f"Failed to import FDS to FDB converter:\n{e}\n\n"
        #                        f"Please ensure fds_to_fdb_converter.py is in fds_workflow/ directory.")
        #     return

                # Check if converter is available
        if convert_fds_to_fdb is None or get_fdb_conversion_db is None:
            QMessageBox.critical(self, "Import Error",
                               "FDS to FDB converter is not available.\n\n"
                               "Please check the installation.")
            return

        
        self.sim_status_text.append("\n" + "="*50)
        self.sim_status_text.append("Converting FDS to FDB (Python Converter)...")
        self.sim_status_text.append("="*50)
        
        # Get database connection
        db = get_fdb_conversion_db(Path(self.project_dir))
        
        converted = 0
        failed = 0
        
        for sim_dir in sim_dirs:
            self.sim_status_text.append(f"\nProcessing: {sim_dir.name}")
            QApplication.processEvents()
            
            try:
                # Create conversion record in database
                conversion_id = db.create_conversion(
                    fds_output_dir=sim_dir,
                    simulation_id=None,  # Could link to FDS simulation table if available
                    config_file_path=None  # Using default configuration
                )
                
                # Update status to running
                db.update_conversion_status(conversion_id, 'running')
                
                # Convert FDS to FDB
                fdb_file_str = convert_fds_to_fdb(
                    simulation_dir=sim_dir,
                    config_file=None  # Use default configuration
                )
                
                # Convert string path to Path object
                fdb_file = Path(fdb_file_str)
                
                # Update database with completion info
                db.update_conversion_complete(
                    conversion_id=conversion_id,
                    fdb_file_path=str(fdb_file),
                    config={'fds_id': sim_dir.name, 'axis_dir': 'X', 'vert_dir': 'Z', 
                           'time_step': 30, 'temp_skip': 6,
                           'conversion_factors': {'SOOT': 1000000.0, 'CO2': 100.0, 'CO': 1000000.0,
                                                 'TEMP': 1.0, 'RADI': 0.25, 'OXYGEN': 100.0}},
                    metadata={'variables': ['SOOT', 'CO2', 'CO', 'TEMP', 'RADI', 'OXYGEN'],
                             'num_time_steps': 0, 'num_variables': 6,
                             'mesh_dimensions': {}}
                )
                
                self.sim_status_text.append(f"  ✓ Created: {fdb_file.name}")
                self.sim_status_text.append(f"  → Size: {fdb_file.stat().st_size / (1024*1024):.1f} MB")
                self.sim_status_text.append(f"  → Database ID: {conversion_id}")
                converted += 1
                
            except Exception as e:
                self.sim_status_text.append(f"  ❌ Error: {str(e)}")
                
                # Update database with failure
                try:
                    db.update_conversion_status(conversion_id, 'failed', str(e))
                except:
                    pass
                
                failed += 1
        
        # Close database connection
        db.close()
        
        self.sim_status_text.append("\n" + "="*50)
        self.sim_status_text.append("Conversion Summary:")
        self.sim_status_text.append(f"✓ Converted: {converted}")
        self.sim_status_text.append(f"✗ Failed: {failed}")
        self.sim_status_text.append(f"Total: {len(sim_dirs)}")
        self.sim_status_text.append("="*50)
        
        if converted > 0:
            QMessageBox.information(self, "Conversion Complete", 
                                  f"Successfully converted {converted} FDS simulation(s) to FDB format!\n\n"
                                  f"FDB files are in the simulation output directories.\n"
                                  f"Conversion records saved to database.\n\n"
                                  f"Ready for EVC/FED analysis in Tab 4!")
        else:
            QMessageBox.warning(self, "Conversion Failed", 
                              f"Failed to convert FDS simulations.\n\n"
                              f"Check the simulation status for details.")
    # ──────────────────────────────────────────────────────────────────────────
    # EVC PARAMETER COLLECTION HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def _collect_evc_params(self) -> dict:
        """Collect all EVC parameters from the five sub-tab widgets.

        Returns a structured dict with keys:
          scenario, tunnel, fire, vehicles, traffic, zones,
          fire_point_mapping, premovement_zones,
          hrr_settings, simulation, mdb
        """
        import datetime

        # ── Sub-tab 1: Tunnel Basic Info ─────────────────────────────────────
        tunnel = {
            "length":      self.evc_tunnel_length.value(),
            "width":       self.evc_tunnel_width.value(),
            "height":      self.evc_tunnel_height.value(),
            "cross_area":  self.evc_cross_area.value(),
            "num_lanes":   self.evc_num_lanes.value(),
            "traffic_dir": self.evc_traffic_dir.currentText(),
            "sim_duration":self.evc_sim_duration.value(),
            "ambient_temp":self.evc_ambient_temp.value(),
        }
        fire = {
            "x":        self.evc_fire_x.value(),
            "y":        self.evc_fire_y.value(),
            "z":        self.evc_fire_z.value(),
            "peak_hrr": self.evc_peak_hrr.value(),
            "soot_yield":self.evc_soot_yield.value(),
            "co_yield": self.evc_co_yield.value(),
            "rad_frac": self.evc_rad_frac.value(),
            "mass_ext": self.evc_mass_ext.value(),
        }

        # Vehicle distribution table
        VEH_ROWS = ["Passenger Car","Bus","Large Bus","Small Cargo",
                    "Medium Cargo","Large Cargo","Total"]
        VEH_COLS = ["Count","Occ/Veh","Total Occ","Length(m)","Width(m)",
                    "Weight(t)","Speed(km/h)"]
        vehicles = []
        tbl = self.evc_vehicle_table
        for r in range(tbl.rowCount()):
            row_data = {"type": VEH_ROWS[r] if r < len(VEH_ROWS) else f"Row{r+1}"}
            for c in range(tbl.columnCount()):
                item = tbl.item(r, c)
                row_data[VEH_COLS[c] if c < len(VEH_COLS) else f"col{c}"] = \
                    item.text() if item else ""
            vehicles.append(row_data)

        # ── Sub-tab 2: Traffic_Man ────────────────────────────────────────────
        traffic = {
            "max_vehicles":   self.evc_max_vehicles.value(),
            "normal_traffic": self.evc_normal_traffic.value(),
            "fire_speed":     self.evc_fire_speed.value(),
            "normal_speed":   self.evc_normal_speed.value(),
        }
        zones = []
        zt = self.evc_zone_table
        ZH = ["Zone","From(m)","To(m)","ExitPt","PC","BS","BL","TS","TM","TL","SUM"]
        for r in range(zt.rowCount()):
            row_data = {}
            for c in range(zt.columnCount()):
                item = zt.item(r, c)
                row_data[ZH[c] if c < len(ZH) else f"col{c}"] = \
                    item.text() if item else ""
            zones.append(row_data)

        # ── Sub-tab 3: HRR_EVAC ──────────────────────────────────────────────
        hrr_settings = {
            "sim_interval":   self.evc_sim_interval.value(),
            "monitor_pt":     self.evc_monitor_pt.value(),
            "monitor_save":   self.evc_monitor_save.value(),
            "fp_evc":         self.evc_fp_evc.value(),
            "fp_fdb":         self.evc_fp_fdb.value(),
            "zone_factor":    self.evc_zone_factor.value(),
            "num_fp":         self.evc_num_fp.value(),
            "fi_20":          self.evc_fi_20.isChecked(),
            "fi_50":          self.evc_fi_50.isChecked(),
            "fi_100":         self.evc_fi_100.isChecked(),
        }
        fire_point_mapping = []
        fpt = self.evc_fpm_table
        FPH = ["No","Fire_pt","MDB_pt","FDS_pt","X(m)"]
        for r in range(fpt.rowCount()):
            row_data = {}
            for c in range(fpt.columnCount()):
                item = fpt.item(r, c)
                row_data[FPH[c] if c < len(FPH) else f"col{c}"] = \
                    item.text() if item else ""
            fire_point_mapping.append(row_data)
        premovement_zones = []
        pmt = self.evc_pmt_table
        PMH = ["From(m)","To(m)","ExitPoint(m)","Premovement(s)"]
        for r in range(pmt.rowCount()):
            row_data = {}
            for c in range(pmt.columnCount()):
                item = pmt.item(r, c)
                row_data[PMH[c] if c < len(PMH) else f"col{c}"] = \
                    item.text() if item else ""
            premovement_zones.append(row_data)

        # ── Sub-tab 4: 시뮬레이션 ─────────────────────────────────────────────
        def _wval(attr, default=0.0):
            """Safely read a spinbox / doublespinbox value."""
            w = getattr(self, attr, None)
            if w is None:
                return default
            return w.value() if hasattr(w, 'value') else default

        def _wchecked(attr, default=False):
            w = getattr(self, attr, None)
            return w.isChecked() if w is not None and hasattr(w, 'isChecked') else default

        simulation = {
            "heat_method":      self.evc_heat_method.currentText() if hasattr(self, 'evc_heat_method') else "by Equation",
            "design_fire_mw":   _wval("evc_design_fire", 20.0),
            "growth_rate":      _wval("evc_growth_rate", 0.15),
            "inertia":          _wval("evc_inertia", 0.001),
            "impact":           _wval("evc_impact", 32.0),
            "air_velocity":     _wval("evc_air_vel", 2.5),
            "ambient_temp2":    _wval("evc_ambient_temp", 20.0),   # alias to evc_ambient_temp
            "reaction_time":    _wval("evc_reaction_time", 30.0),
            "leave_car_time":   _wval("evc_leave_car", 60.0),
            "hesitation_time":  _wval("evc_hesitation", 180.0),
            "es_reaction":      _wchecked("evc_es_reaction"),
            "es_leave_car":     _wchecked("evc_es_leave_car"),
            "es_hesitate":      _wchecked("evc_es_hesitate", True),
            "es_temp":          _wchecked("evc_es_temp"),
            "es_smoke":         _wchecked("evc_es_smoke"),
            "min_speed":        _wval("evc_min_speed", 0.45),
            "elderly_speed":    _wval("evc_elderly_speed", 0.60),
            "elderly_ratio":    _wval("evc_elderly_ratio", 0.40),
            "speed_reduc":      _wval("evc_speed_reduc", 1.0),
        }

        # ── Sub-tab 5: MDB Create ─────────────────────────────────────────────
        idx_items = [self.evc_idx_list.item(i).text()
                     for i in range(self.evc_idx_list.count())]
        mdb = {
            "db_type":    self.evc_db_type.currentText(),
            "fds_id":     self.evc_db_fds_id.text().strip(),
            "cfdidx":     self.evc_db_cfdidx.value(),
            "cnv_fac":    self.evc_db_cnvfac.value(),
            "soot":       self.evc_db_soot.value(),
            "co2":        self.evc_db_co2.value(),
            "co":         self.evc_db_co.value(),
            "temp":       self.evc_db_temp.value(),
            "radiation":  self.evc_db_rad.value(),
            "oxygen":     self.evc_db_o2.value(),
            "slf_dt":     self.evc_db_slf_dt.value(),
            "slf_tmax":   self.evc_db_slf_tmax.value(),
            "axis_dir":   self.evc_db_axis.currentText(),
            "index_files":idx_items,
        }

        fdb_path = self.evc_fdb_path_le.text().strip()
        fds_path = self.evc_fds_path_le.text().strip()

        scenario = {
            "name":       mdb["fds_id"] or "TN",
            "fds_file":   fds_path,
            "fdb_file":   fdb_path,
            "generated":  datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return dict(
            scenario=scenario,
            tunnel=tunnel,
            fire=fire,
            vehicles=vehicles,
            traffic=traffic,
            zones=zones,
            hrr_settings=hrr_settings,
            fire_point_mapping=fire_point_mapping,
            premovement_zones=premovement_zones,
            simulation=simulation,
            mdb=mdb,
        )

    def _write_evc_file(self, evc_path: Path, params: dict, chid: str,
                        csv_files=None,
                        fire_point_x: float = None) -> None:
        """Write a .evc file in the exact legacy QRA binary+text format.

        Delegates to EVCGenerator so the output is byte-for-byte compatible
        with the reference 020CFV0_P*.evc files.
        Falls back to a simple key=value format if evc_generator is unavailable.

        Args:
            evc_path:      Full path of the file to create.
            params:        Dict returned by _collect_evc_params().
            chid:          Scenario identifier (e.g. "020CFV0").
            csv_files:     Optional list of associated CSV paths (metadata only).
            fire_point_x:  Fire position along tunnel axis (m).
                           If None, taken from hrr_settings.fp_evc or 0.
        """
        # ── Use the new legacy-format generator ──────────────────────────────
        if EVCGenerator is not None and params_from_qra_dict is not None:
            try:
                evc_params = params_from_qra_dict(params)
                if fire_point_x is None:
                    hr = params.get("hrr_settings", {})
                    fire_point_x = float(hr.get("fp_evc") or 0.0)
                gen = EVCGenerator(evc_params)
                gen.write(evc_path, fire_point_x=fire_point_x, chid=chid)
                return
            except Exception as exc:
                import traceback
                self.evc_status_text.append(
                    f"  ⚠️ EVCGenerator error ({exc}); using fallback writer.")
                traceback.print_exc()

        # ── Legacy fallback: simple key=value format ──────────────────────────
        import datetime
        p  = params
        sc = p.get("scenario", {})
        tn = p.get("tunnel", {})
        fi = p.get("fire", {})
        sm = p.get("simulation", {})
        mb = p.get("mdb", {})
        lines = []
        lines.append(f"# EVC Input File — generated by QRA System")
        lines.append(f"# CHID      : {chid}")
        lines.append(f"# Generated : {sc.get('generated', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
        lines.append(f"[SCENARIO]")
        lines.append(f"CHID={chid}")
        lines.append(f"FDS_File={sc.get('fds_file', '')}")
        lines.append(f"FDB_File={sc.get('fdb_file', '')}")
        lines.append(f"[TUNNEL]")
        lines.append(f"Length_m={tn.get('length', 356)}")
        lines.append(f"Width_m={tn.get('width', 10.83)}")
        lines.append(f"Height_m={tn.get('height', 6.77)}")
        lines.append(f"[FIRE]")
        lines.append(f"Location_X_m={fire_point_x or fi.get('x', 0)}")
        lines.append(f"PeakHRR_MW={fi.get('peak_hrr', 20)}")
        lines.append(f"[SIMULATION]")
        lines.append(f"ReactionTime_s={sm.get('reaction_time', 30)}")
        lines.append(f"LeaveCarTime_s={sm.get('leave_car_time', 60)}")
        lines.append(f"HesitationTime_s={sm.get('hesitation_time', 180)}")
        lines.append(f"[MDB]")
        lines.append(f"FDS_ID={mb.get('fds_id', chid)}")
        lines.append(f"[DATA]")
        if csv_files:
            for cf in csv_files:
                fn = cf.name if hasattr(cf, "name") else str(cf)
                lines.append(f"#   {fn}")
        else:
            lines.append("#   (no CSV files linked)")
        evc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_evc_file_set(self, output_dir: Path, params: dict, chid: str,
                            fire_positions=None, num_positions: int = None) -> list:
        """Generate one .evc file per fire position for a scenario.

        Args:
            output_dir:     Directory where files are written.
            params:         Dict from _collect_evc_params().
            chid:           Scenario CHID (e.g. "020CFV0").
            fire_positions: Explicit list of fire X positions (m).
                            Auto-computed if None.
            num_positions:  Number of positions to auto-compute.

        Returns:
            List of written file Paths.
        """
        if EVCGenerator is None or params_from_qra_dict is None:
            self.evc_status_text.append(
                "  ⚠️ evc_generator not available; cannot generate position set.")
            return []
        try:
            evc_params = params_from_qra_dict(params)
            if num_positions is None:
                hr = params.get("hrr_settings", {})
                num_positions = int(hr.get("num_fp") or evc_params.num_positions)
            gen = EVCGenerator(evc_params)
            written = gen.write_position_set(
                output_dir=output_dir,
                chid=chid,
                num_positions=num_positions,
                fire_positions=fire_positions,
            )
            return written
        except Exception as exc:
            import traceback
            self.evc_status_text.append(f"  ❌ EVC position set error: {exc}")
            traceback.print_exc()
            return []

    def generate_evc_from_ascii(self):
        """Generate fully-structured EVC files from the GUI parameters + ASCII CSV files."""
        try:
            ascii_dir = Path(self.project_dir) / "ascii_files"
            evc_dir   = Path(self.project_dir) / "evc_files"
            evc_dir.mkdir(exist_ok=True)

            # Collect all parameters from sub-tabs
            try:
                params = self._collect_evc_params()
            except Exception as pe:
                self.sim_status_text.append(f"\n⚠️ Parameter collection warning: {pe}")
                params = {}

            # Group ASCII files by scenario (CHID)
            csv_files = list(ascii_dir.glob("*.csv")) if ascii_dir.exists() else []

            if not csv_files:
                # Generate a single EVC file from GUI params alone
                chid = (params.get("scenario", {}).get("name") or
                        params.get("mdb", {}).get("fds_id") or
                        getattr(self, 'evc_db_fds_id', None) and self.evc_db_fds_id.text().strip() or "TN")
                if params:
                    evc_path = evc_dir / f"{chid}.evc"
                    self._write_evc_file(evc_path, params, chid, csv_files=None)
                    self.sim_status_text.append(f"\n✓ Generated EVC (GUI params only): {evc_path.name}")
                    QMessageBox.information(
                        self, "EVC Generated",
                        f"Generated EVC file from GUI parameters:\n  {evc_path.name}\n\n"
                        f"No CSV files found — link an FDB for data source.\n"
                        f"Location: {evc_dir}"
                    )
                else:
                    self.sim_status_text.append("\n❌ No CSV files and no GUI params available.")
                    QMessageBox.warning(self, "No Data",
                                        "No CSV files found in ascii_files/ and no GUI parameters "
                                        "could be collected.\n\nPlease configure Sub-tabs 1–5 first.")
                return

            # Extract unique CHIDs
            chids = set()
            for cf in csv_files:
                parts = cf.stem.split("_")
                if len(parts) >= 3:
                    chids.add("_".join(parts[:4]) if len(parts) >= 4 else "_".join(parts[:3]))

            self.sim_status_text.append(f"\n{'='*50}")
            self.sim_status_text.append(f"Generating EVC Files…")
            self.sim_status_text.append(f"{'='*50}\n")
            self.sim_status_text.append(f"Found {len(chids)} scenario(s) | {len(csv_files)} CSV file(s)")
            QApplication.processEvents()

            generated = 0
            failed = 0

            for chid in sorted(chids):
                self.sim_status_text.append(f"\nProcessing: {chid}")
                QApplication.processEvents()
                try:
                    scenario_files = [f for f in csv_files if f.stem.startswith(chid)]
                    if not scenario_files:
                        self.sim_status_text.append("  ⚠️ No CSV files found")
                        failed += 1
                        continue

                    # Override scenario name with actual CHID
                    if params:
                        params.setdefault("scenario", {})["name"] = chid
                        params.setdefault("mdb", {})["fds_id"]    = chid

                    evc_path = evc_dir / f"{chid}.evc"
                    self._write_evc_file(evc_path, params, chid, csv_files=scenario_files)

                    self.sim_status_text.append(f"  ✓ Generated: {evc_path.name}")
                    self.sim_status_text.append(f"    Source: {len(scenario_files)} CSV file(s)")
                    generated += 1
                except Exception as e:
                    self.sim_status_text.append(f"  ❌ Error: {str(e)[:80]}")
                    import traceback; traceback.print_exc()
                    failed += 1

            self.sim_status_text.append(f"\n{'='*50}")
            self.sim_status_text.append(f"EVC Generation Summary:")
            self.sim_status_text.append(f"  ✓ Generated : {generated}")
            if failed:
                self.sim_status_text.append(f"  ✗ Failed    : {failed}")
            self.sim_status_text.append(f"  Total       : {len(chids)}")
            self.sim_status_text.append(f"{'='*50}")
            self.sim_status_text.append(f"\nEVC files saved to: {evc_dir}")
            self.sim_status_text.append("Ready for Tab 4 (EVC/FED Analysis)!")

            QMessageBox.information(
                self, "EVC Generation Complete",
                f"Generated {generated} EVC file(s).\n\n"
                f"Location: {evc_dir}\n\n"
                f"Each file contains full tunnel geometry, fire parameters,\n"
                f"zone distribution, fire point mapping, pre-movement times,\n"
                f"simulation settings, and FDB database linkage.\n\n"
                f"Proceed to Tab 4 for EVC/FED Analysis."
            )

        except Exception as e:
            error_msg = f"Error generating EVC files: {str(e)}"
            self.sim_status_text.append(f"\n❌ {error_msg}")
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Error", error_msg)
    
    def import_ascii_files(self):
        """Scan ascii_files/ directory, organise CSV outputs by scenario (CHID),
        populate the scenario table, and update both status logs.

        Naming convention expected from fds2ascii:
            <HRR>_<traffic>_<vent>_<posXXX>_<datatype>.csv
            e.g.  020_N_NVC_pos500_temp.csv
                  020_N_NVC_pos500_devc.csv

        The method tolerates nested sub-directories produced by the
        convert_smv_to_fdb_with_exe workflow (ascii_files/<sim_dir>/*.csv).
        """
        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return

        ascii_dir = Path(self.project_dir) / "ascii_files"

        # Create the directory if it doesn't exist yet
        if not ascii_dir.exists():
            ascii_dir.mkdir(parents=True, exist_ok=True)

        # Search recursively so nested sim-dir layouts are found too
        csv_files = list(ascii_dir.rglob("*.csv"))

        if not csv_files:
            msg = (f"No CSV files found in:\n  {ascii_dir}\n\n"
                   "Run 'Convert FDB → ASCII (fds2ascii)' in Tab 3 first,\n"
                   "or place CSV files manually in the ascii_files/ folder.")
            QMessageBox.warning(self, "No ASCII Files", msg)
            return

        # ── Organise by CHID ────────────────────────────────────────────────
        # CHID = first 4 underscore-separated tokens of the file stem,
        # e.g.  "020_N_NVC_pos500"  from  "020_N_NVC_pos500_temp.csv"
        # Falls back to 3 tokens if filename has fewer than 5 parts.
        scenarios: dict[str, list[Path]] = {}
        ungrouped: list[Path] = []
        for cf in csv_files:
            parts = cf.stem.split("_")
            if len(parts) >= 4:
                chid = "_".join(parts[:4])
            elif len(parts) >= 3:
                chid = "_".join(parts[:3])
            else:
                ungrouped.append(cf)
                continue
            scenarios.setdefault(chid, []).append(cf)

        # Files that don't match the convention go into a catch-all group
        if ungrouped:
            scenarios.setdefault("_misc", []).extend(ungrouped)

        # ── Populate the hidden scenario table (used by generate_evc_files) ─
        self.scenario_table.setRowCount(len(scenarios))
        for row, (chid, files) in enumerate(sorted(scenarios.items())):
            parts = chid.split("_")
            hrr      = parts[0] if len(parts) > 0 else "?"
            position = parts[3] if len(parts) > 3 else (parts[-1] if parts else "?")
            self.scenario_table.setItem(row, 0, QTableWidgetItem(chid))
            self.scenario_table.setItem(row, 1, QTableWidgetItem(f"{hrr} MW"))
            self.scenario_table.setItem(row, 2, QTableWidgetItem(position))
            self.scenario_table.setItem(row, 3, QTableWidgetItem(str(len(files))))
        self.scenario_table.resizeColumnsToContents()

        # ── Update both status logs ──────────────────────────────────────────
        summary_lines = [
            f"\n✓ Loaded {len(csv_files)} ASCII file(s) from {ascii_dir}",
            f"✓ Organised into {len(scenarios)} scenario(s):",
        ]
        for chid in sorted(scenarios):
            summary_lines.append(f"    • {chid}: {len(scenarios[chid])} file(s)")

        summary = "\n".join(summary_lines)

        # Tab 3 status widget (may not exist in all code paths)
        try:
            self.sim_status_text.append(summary)
        except AttributeError:
            pass

        # Tab 4 status widget
        try:
            self.evc_status_text.append(summary)
        except AttributeError:
            pass

        QMessageBox.information(
            self, "ASCII Files Loaded",
            f"Found {len(csv_files)} CSV file(s) in ascii_files/\n\n"
            f"Organised into {len(scenarios)} scenario(s).\n\n"
            f"Ready to generate EVC files!"
        )
    
    def generate_evc_files(self):
        """Generate EVC files for each loaded scenario (Tab 4 button).

        Produces one .evc file per fire position per scenario, in the exact
        legacy QRA binary+text format matching 020CFV0_P*.evc reference files.
        """
        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return

        ascii_dir = Path(self.project_dir) / "ascii_files"
        evc_dir   = Path(self.project_dir) / "evc_files"
        evc_dir.mkdir(exist_ok=True)

        # Collect parameters from EVC sub-tabs
        try:
            params = self._collect_evc_params()
        except Exception as pe:
            self.evc_status_text.append(f"⚠️ Parameter collection warning: {pe}")
            params = {}

        self.evc_status_text.append("\n" + "=" * 50)
        self.evc_status_text.append("Generating EVC files…")
        self.evc_status_text.append("=" * 50)
        generated = 0
        failed    = 0

        # Number of fire positions from GUI
        hr     = params.get("hrr_settings", {})
        num_fp = int(hr.get("num_fp") or 6)

        # Determine scenario list from loaded table OR from CSV files on disk
        scenarios_to_process = []
        if hasattr(self, "scenario_table") and self.scenario_table.rowCount() > 0:
            for row in range(self.scenario_table.rowCount()):
                item = self.scenario_table.item(row, 0)
                if item:
                    scenarios_to_process.append(item.text())
        else:
            csv_all = list(ascii_dir.glob("*.csv")) if ascii_dir.exists() else []
            chids = set()
            for cf in csv_all:
                parts = cf.stem.split("_")
                if len(parts) >= 3:
                    chids.add("_".join(parts[:4]) if len(parts) >= 4 else "_".join(parts[:3]))
            scenarios_to_process = sorted(chids)

        if not scenarios_to_process:
            # No CSV-based scenarios — generate from GUI params alone
            chid = (params.get("scenario", {}).get("name") or
                    params.get("mdb", {}).get("fds_id") or
                    getattr(self, 'evc_db_fds_id', None) and self.evc_db_fds_id.text().strip() or "TN")
            try:
                written = self._write_evc_file_set(evc_dir, params, chid, num_positions=num_fp)
                if written:
                    for w in written:
                        self.evc_status_text.append(f"  ✓ Created: {w.name}")
                    generated += len(written)
                else:
                    # Fallback: single file at fp_evc position
                    evc_path = evc_dir / f"{chid}.evc"
                    self._write_evc_file(evc_path, params, chid, csv_files=None)
                    self.evc_status_text.append(f"  ✓ Created: {evc_path.name} (single file)")
                    generated = 1
            except Exception as e:
                import traceback; traceback.print_exc()
                self.evc_status_text.append(f"  ❌ Error: {e}")
                failed = 1
        else:
            for chid in scenarios_to_process:
                self.evc_status_text.append(f"\nProcessing: {chid}")
                QApplication.processEvents()
                try:
                    if params:
                        params.setdefault("scenario", {})["name"] = chid
                        params.setdefault("mdb", {})["fds_id"]    = chid
                    written = self._write_evc_file_set(evc_dir, params, chid, num_positions=num_fp)
                    if written:
                        for w in written:
                            self.evc_status_text.append(f"  ✓ Created: {w.name}")
                        generated += len(written)
                    else:
                        # Fallback: single file
                        csv_files = list(ascii_dir.glob(f"{chid}*.csv")) if ascii_dir.exists() else []
                        evc_path = evc_dir / f"{chid}.evc"
                        self._write_evc_file(evc_path, params, chid, csv_files=csv_files or None)
                        self.evc_status_text.append(f"  ✓ Created: {evc_path.name} (single file)")
                        generated += 1
                except Exception as e:
                    import traceback; traceback.print_exc()
                    self.evc_status_text.append(f"  ❌ Error: {str(e)}")
                    failed += 1

        self.evc_status_text.append("\n" + "=" * 50)
        self.evc_status_text.append("EVC Generation Summary:")
        self.evc_status_text.append(f"  ✓ Generated : {generated}")
        if failed:
            self.evc_status_text.append(f"  ✗ Failed    : {failed}")
        self.evc_status_text.append("=" * 50)

        if generated > 0:
            QMessageBox.information(
                self, "EVC Files Generated",
                f"Successfully generated {generated} EVC file(s)!\n\n"
                f"Location: {evc_dir}\n\n"
                f"Files are in the legacy QRA binary+text format,\n"
                f"one file per fire position (e.g. {chid}_P1.evc … _P{num_fp}.evc).\n"
                f"Ready for EVC/FED analysis!")
        else:
            QMessageBox.warning(self, "Generation Failed",
                                "Failed to generate EVC files.\nCheck the status log for details.")

    # import_ascii_files is defined earlier (single consolidated implementation)

    # generate_evc_files is defined above (Tab-3 button / main EVC generation)
    
    def run_evc_analysis(self):
        """Run complete EVC/FED analysis, supporting both ASCII and direct FDB inputs."""
        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return

        ascii_dir   = Path(self.project_dir) / "ascii_files"
        fdb_dir     = Path(self.project_dir) / "fds_outputs"
        evc_dir     = Path(self.project_dir) / "evc_files"
        results_dir = Path(self.project_dir) / "fed_results"

        # Ensure all required directories exist
        for _d in (ascii_dir, fdb_dir, evc_dir, results_dir):
            _d.mkdir(parents=True, exist_ok=True)

        self.evc_status_text.clear()
        self.evc_status_text.append("="*60)
        self.evc_status_text.append("EVC/FED ANALYSIS ENGINE")
        self.evc_status_text.append("="*60)
        self.evc_status_text.append("")
        QApplication.processEvents()

        try:
            # ── 1. Discover scenarios from ASCII files ─────────────────────────
            csv_files = list(ascii_dir.rglob("*.csv"))
            scenarios = {}
            for csv_file in csv_files:
                # Try to extract CHID (usually the first 3-4 parts of filename)
                parts = csv_file.stem.split('_')
                chid = '_'.join(parts[:4]) if len(parts) >= 4 else parts[0]
                if chid not in scenarios: scenarios[chid] = []
                scenarios[chid].append(csv_file)

            # ── 2. Discover scenarios from FDB files ───────────────────────────
            fdb_files = list(fdb_dir.glob("*.fdb"))
            for fdb in fdb_files:
                chid = fdb.stem
                if chid not in scenarios:
                    scenarios[chid] = [fdb]  # Single FDB source

            if not scenarios:
                QMessageBox.warning(self, "No Data Sources",
                                  "No ASCII (.csv) or FDB files found.\n\n"
                                  "Please load simulation results first.")
                return

            # ── 3. Simple Mode Filtering ───────────────────────────────────────
            if self.is_simple_mode():
                single_fds = self.simple_fds_file_input.text().strip()
                if single_fds:
                    target_chid = Path(single_fds).stem
                    if target_chid in scenarios:
                        scenarios = {target_chid: scenarios[target_chid]}
                        self.evc_status_text.append(f"🎯 Simple Mode: Analyzing: {target_chid}\n")
                    else:
                        self.evc_status_text.append(f"⚠️ Warning: No data found for {target_chid}")
                        self.evc_status_text.append(f"Available: {', '.join(scenarios.keys())}\n")
                else:
                    QMessageBox.warning(self, "No File", "Select an FDS file in Tab 3 first.")
                    return

            self.evc_status_text.append(f"Found {len(scenarios)} scenario(s) to analyze\n")
            QApplication.processEvents()

            all_results = []
            for chid in sorted(scenarios.keys()):
                self.evc_status_text.append(f"\n{'─'*60}")
                self.evc_status_text.append(f"SCENARIO: {chid}")
                self.evc_status_text.append(f"{'─'*60}")
                QApplication.processEvents()

                source_files = scenarios[chid]
                
                # Check if it's a direct FDB or ASCII set
                if len(source_files) == 1 and source_files[0].suffix.lower() == '.fdb':
                    self.evc_status_text.append(f"  Reading direct FDB: {source_files[0].name}")
                    data = self.parse_ascii_data(source_files, chid) # parse_ascii handles .fdb too
                else:
                    self.evc_status_text.append(f"  Parsing ASCII set ({len(source_files)} files)")
                    data = self.parse_ascii_data(source_files, chid)

                if not data or len(data.get('time', [])) == 0:
                    self.evc_status_text.append("  ⚠️ No valid time-series data extracted.")
                    continue

                # Core FED Calculation (Purser Model)
                fed_results = self.calculate_fed(data, chid)

                # Occupant-level Fatality Estimation (Zone-based)
                fatalities = self.estimate_fatalities(fed_results, chid)

                all_results.append({
                    'chid': chid, 'data': data, 'fed': fed_results, 'fatalities': fatalities
                })

                self.evc_status_text.append(f"\n  ✓ Analysis Complete")
                self.evc_status_text.append(f"    Max FED:    {fed_results['max_fed']:.4f}")
                self.evc_status_text.append(f"    Fatalities: {fatalities['total']} / {fatalities['n_people']}")
                QApplication.processEvents()

            if not all_results:
                self.evc_status_text.append("\n❌ No results generated.")
                return

            # Save to JSON, CSV, and TEC
            self.save_fed_results(all_results, results_dir)

            # Final Summary
            self.evc_status_text.append(f"\n{'='*60}")
            self.evc_status_text.append("GLOBAL SUMMARY")
            self.evc_status_text.append(f"{'='*60}")
            total_f = sum(r['fatalities']['total'] for r in all_results)
            total_p = sum(r['fatalities']['n_people'] for r in all_results)
            self.evc_status_text.append(f"Scenarios : {len(all_results)}")
            self.evc_status_text.append(f"Fatalities: {total_f} (from {total_p} total occupants)")
            self.evc_status_text.append(f"\nResults saved to: {results_dir}")
            self.evc_status_text.append(f"{'='*60}")

            QMessageBox.information(self, "Analysis Complete",
                                  f"FED analysis completed for {len(all_results)} scenario(s).\n\n"
                                  f"Total Fatalities: {total_f}\n"
                                  f"Output Folder: {results_dir}")

        except Exception as e:
            error_msg = f"Analysis Error: {str(e)}"
            self.evc_status_text.append(f"\n❌ {error_msg}")
            QMessageBox.critical(self, "Error", error_msg)
            import traceback; traceback.print_exc()
    
    def _parse_fdb_structured(self, fdb_path):
        """Parse the FIRE ANALYSIS DB (.fdb) structured text format.

        FDB file layout (CRLF text):
          ...header sections...
          DATA START
          t  x  soot  co2  co  temp  radi  oxygen
          ...rows...
          DATA END   (optional)

        Column order (0-indexed):
          0=TIME[s]  1=X-COOR[m]  2=SOOT[kg/m³]  3=CO2[%]
          4=CO[ppm]  5=TEMP[°C]   6=RADI[kW/m²]  7=OXYGEN[%]

        Strategy: for each unique time step, average all X positions
        so we get a single representative value per time step.
        """
        import numpy as np
        from collections import defaultdict

        rows_by_time = defaultdict(lambda: {
            'soot': [], 'co2': [], 'co': [], 'temp': [], 'radi': [], 'oxygen': []
        })

        col_map = None   # will be set from header line
        in_data = False
        n_rows  = 0

        # Read with multiple encoding fallbacks
        for enc in ('utf-8', 'latin-1', 'cp1252'):
            try:
                raw = fdb_path.read_bytes().decode(enc, errors='replace')
                break
            except Exception:
                continue

        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith('!') or line.startswith('#'):
                continue

            # Detect DATA START sentinel
            if 'DATA START' in line.upper():
                in_data = True
                col_map = None   # reset; next non-separator line is data
                continue

            if 'DATA END' in line.upper():
                break

            if not in_data:
                continue

            # Skip separator lines (all * or | or -)
            if all(c in '*|-= \t' for c in line):
                continue

            # Try to parse as space-separated numbers
            parts = line.split()
            try:
                nums = [float(p) for p in parts]
            except ValueError:
                # Could be column header line like "TIME  X-COOR  SOOT  CO2..."
                # Try to build col_map from it
                up = [p.upper() for p in parts]
                col_map = {}
                for i, h in enumerate(up):
                    if 'TIME' in h:         col_map['time']   = i
                    elif 'X' in h:          col_map['x']      = i
                    elif 'SOOT' in h:       col_map['soot']   = i
                    elif 'CO2' in h:        col_map['co2']    = i
                    elif 'CO' in h and 'CO2' not in h: col_map['co'] = i
                    elif 'TEMP' in h:       col_map['temp']   = i
                    elif 'RADI' in h:       col_map['radi']   = i
                    elif 'OXY' in h or 'O2' in h: col_map['oxygen'] = i
                continue

            if len(nums) < 2:
                continue

            # Default col positions if no header was found
            if col_map is None:
                col_map = {
                    'time': 0, 'x': 1, 'soot': 2, 'co2': 3,
                    'co': 4, 'temp': 5, 'radi': 6, 'oxygen': 7
                }

            def _g(key, default=0.0):
                idx = col_map.get(key)
                return nums[idx] if idx is not None and idx < len(nums) else default

            t = _g('time')
            rows_by_time[t]['soot'].append(_g('soot'))
            rows_by_time[t]['co2'].append(_g('co2'))
            rows_by_time[t]['co'].append(_g('co'))
            rows_by_time[t]['temp'].append(_g('temp', 20.0))
            rows_by_time[t]['radi'].append(_g('radi'))
            rows_by_time[t]['oxygen'].append(_g('oxygen', 21.0))
            n_rows += 1

        if not rows_by_time:
            return None

        times_sorted = sorted(rows_by_time.keys())

        def _avg(d, key, default):
            vals = d[key]
            return float(np.mean(vals)) if vals else default

        result = {
            'time':        np.array(times_sorted, dtype=float),
            'temperature': np.array([_avg(rows_by_time[t], 'temp',   20.0) for t in times_sorted]),
            'co':          np.array([_avg(rows_by_time[t], 'co',      0.0)  for t in times_sorted]),
            'co2':         np.array([_avg(rows_by_time[t], 'co2',     0.04) for t in times_sorted]),
            'o2':          np.array([_avg(rows_by_time[t], 'oxygen', 21.0)  for t in times_sorted]),
            'soot':        np.array([_avg(rows_by_time[t], 'soot',    0.0)  for t in times_sorted]),
            'radiation':   np.array([_avg(rows_by_time[t], 'radi',    0.0)  for t in times_sorted]),
        }

        # Derive visibility from soot density: Vis = C_vis / (K * rho_soot)
        # Using Purser: Vis[m] = 8 / (K_e * C_s) where K_e≈8700 m²/kg, C_s=soot [kg/m³]
        C_vis = 8.0
        K_ext = 8700.0
        with np.errstate(divide='ignore', invalid='ignore'):
            vis = np.where(result['soot'] > 1e-10, C_vis / (K_ext * result['soot']), 30.0)
        result['visibility'] = np.clip(vis, 0.1, 200.0)

        return result, n_rows

    def parse_ascii_data(self, source_files, chid):
        """Parse ASCII CSV or direct FDB files to extract time-series hazard data.

        Handles:
          - FIRE ANALYSIS DB (.fdb) structured text files  ← primary format
          - fds2ascii CSV files (devc, temp, co, etc.)
        """
        import pandas as pd
        import numpy as np

        data = {
            'chid': chid, 'time': [], 'temperature': [], 'co': [],
            'co2': [], 'o2': [], 'visibility': []
        }

        for src_file in source_files:
            fn = src_file.name.lower()
            try:
                # ── FIRE ANALYSIS DB structured text ──────────────────────────
                if fn.endswith('.fdb'):
                    self.evc_status_text.append(f"    Parsing FDB: {src_file.name}")
                    QApplication.processEvents()
                    result = self._parse_fdb_structured(src_file)
                    if result is None:
                        self.evc_status_text.append(f"    ⚠️ FDB parse returned no rows")
                        continue
                    parsed, n_rows = result
                    data['time']        = parsed['time']
                    data['temperature'] = parsed['temperature']
                    data['co']          = parsed['co']
                    data['co2']         = parsed['co2']
                    data['o2']          = parsed['o2']
                    data['visibility']  = parsed['visibility']
                    self.evc_status_text.append(
                        f"    ✓ Loaded FDB: {src_file.name}  "
                        f"({n_rows} data rows → {len(parsed['time'])} time steps)")
                    self.evc_status_text.append(
                        f"      T_max={parsed['temperature'].max():.1f}°C  "
                        f"CO_max={parsed['co'].max():.1f}ppm  "
                        f"O2_min={parsed['o2'].min():.1f}%")
                    continue

                # ── fds2ascii CSV files ───────────────────────────────────────
                df = pd.read_csv(src_file, skiprows=1)
                if len(df) == 0:
                    continue

                if len(data['time']) == 0:
                    data['time'] = df.iloc[:, 0].values

                if 'devc' in fn:
                    for key, pattern in [('temperature', 'temp'), ('co', 'co'),
                                         ('co2', 'co2'), ('o2', 'o2'), ('visibility', 'vis')]:
                        match_cols = [c for c in df.columns if pattern in c.lower()]
                        if match_cols and len(data[key]) == 0:
                            data[key] = df[match_cols].mean(axis=1).values
                            self.evc_status_text.append(f"    ✓ {key.capitalize()} from devc")
                elif 'temp' in fn:
                    data['temperature'] = df.iloc[:, 1:].mean(axis=1).values
                elif 'co' in fn and 'co2' not in fn:
                    data['co'] = df.iloc[:, 1:].mean(axis=1).values
                elif 'co2' in fn:
                    data['co2'] = df.iloc[:, 1:].mean(axis=1).values
                elif 'o2' in fn or 'oxygen' in fn:
                    data['o2'] = df.iloc[:, 1:].mean(axis=1).values
                elif 'vis' in fn:
                    data['visibility'] = df.iloc[:, 1:].mean(axis=1).values

                QApplication.processEvents()

            except Exception as e:
                self.evc_status_text.append(f"    ⚠️ Error reading {fn}: {str(e)[:80]}")
                import traceback; traceback.print_exc()

        # Fill missing fields with physical defaults
        n_steps = len(data['time'])
        if n_steps > 0:
            if len(data['temperature']) == 0: data['temperature'] = np.full(n_steps, 20.0)
            if len(data['co']) == 0:          data['co']          = np.zeros(n_steps)
            if len(data['co2']) == 0:         data['co2']         = np.full(n_steps, 0.04)
            if len(data['o2']) == 0:          data['o2']          = np.full(n_steps, 21.0)
            if len(data['visibility']) == 0:  data['visibility']  = np.full(n_steps, 30.0)

        return data
    
    def calculate_fed(self, data, chid):
        """Calculate FED using the Purser model (ISO 13571 / QRA formulas).

        The three FED rate components are:
          FED_CO_rate   = CO^1.036 / 35000          [per minute]
          FED_O2_rate   = ((21 - O2) / 11)^3 / 60  [per minute]
          FED_Heat_rate = Temp^3.4 / 5e7            [per minute]

        The constants 35000, 60, and 5e7 are all normalised *per minute*,
        so dt must be converted from seconds to minutes before accumulation.
        """
        import numpy as np

        self.evc_status_text.append(f"\n  Calculating FED (Purser model)...")
        QApplication.processEvents()

        time = np.array(data['time'], dtype=float)
        temp = np.array(data['temperature'], dtype=float)
        co   = np.array(data['co'],          dtype=float)   # ppm
        co2  = np.array(data['co2'],         dtype=float)   # % vol
        o2   = np.array(data['o2'],          dtype=float)   # % vol

        n_steps = len(time)
        if n_steps == 0:
            return {
                'time': time, 'fed_co': np.array([]), 'fed_o2': np.array([]),
                'fed_heat': np.array([]), 'fed_total': np.array([]),
                'max_fed': 0.0, 'final_fed': 0.0,
                'fed_co_rate': np.array([]), 'fed_o2_rate': np.array([]),
                'fed_heat_rate': np.array([])
            }

        # ── Per-time-step FED rate (dimensionless per minute) ─────────────────
        # FED_CO:   CO must be in ppm; constant 35000 is in ppm·min
        fed_co_rate = np.where(co > 0, (co ** 1.036) / 35000.0, 0.0)

        # FED_O2:   O2 in %; constant 60 is in min
        fed_o2_rate = np.where(
            o2 < 21.0,
            ((21.0 - o2) / 11.0) ** 3 / 60.0,
            0.0
        )

        # FED_Heat: Temp in °C; constant 5e7 is in °C^3.4·min
        # Only meaningful above ambient (~20 °C)
        fed_heat_rate = np.where(temp > 20.0, (temp ** 3.4) / 5e7, 0.0)

        # ── Time step (dt) in MINUTES ─────────────────────────────────────────
        # time array is in seconds; divide by 60 to convert to minutes
        dt_s = np.diff(time, prepend=time[0])   # seconds
        dt_s[0] = dt_s[1] if n_steps > 1 else dt_s[0]  # fix prepend artefact
        dt_min = dt_s / 60.0                             # minutes

        # ── Cumulative FED ────────────────────────────────────────────────────
        fed_co_cumulative   = np.cumsum(fed_co_rate   * dt_min)
        fed_o2_cumulative   = np.cumsum(fed_o2_rate   * dt_min)
        fed_heat_cumulative = np.cumsum(fed_heat_rate * dt_min)
        fed_total           = fed_co_cumulative + fed_o2_cumulative + fed_heat_cumulative

        results = {
            'time':       time,
            'fed_co':     fed_co_cumulative,
            'fed_o2':     fed_o2_cumulative,
            'fed_heat':   fed_heat_cumulative,
            'fed_total':  fed_total,
            'max_fed':    float(np.max(fed_total)),
            'final_fed':  float(fed_total[-1]) if n_steps > 0 else 0.0,
            # instantaneous rates (useful for Tecplot export)
            'fed_co_rate':   fed_co_rate,
            'fed_o2_rate':   fed_o2_rate,
            'fed_heat_rate': fed_heat_rate,
        }

        self.evc_status_text.append(f"    FED_CO   (max cumul.): {np.max(fed_co_cumulative):.4f}")
        self.evc_status_text.append(f"    FED_O2   (max cumul.): {np.max(fed_o2_cumulative):.4f}")
        self.evc_status_text.append(f"    FED_Heat (max cumul.): {np.max(fed_heat_cumulative):.4f}")
        self.evc_status_text.append(f"    FED_Total (max):       {results['max_fed']:.4f}")
        if results['max_fed'] >= 1.0:
            self.evc_status_text.append("    ⚠️  FED ≥ 1.0 — incapacitation threshold exceeded!")
        elif results['max_fed'] >= 0.3:
            self.evc_status_text.append("    ⚠️  FED ≥ 0.3 — design criterion threshold exceeded.")

        return results
    
    def _get_total_occupants(self) -> int:
        """Read total occupant count from the vehicle distribution table (Sub-tab 1).

        Row 4 (index 4) of evc_vehicle_table is "Total occupants"; the last
        column (index 7) is the grand total.  Falls back to 1000 if the table
        is not populated or the value cannot be parsed.
        """
        try:
            tbl = self.evc_vehicle_table
            # Row 4 = "Total occupants", last column = grand total
            item = tbl.item(4, tbl.columnCount() - 1)
            if item and item.text().strip() not in ("", "—", "-"):
                return max(1, int(float(item.text().strip())))
            # Fallback: sum column values in row 4 (skip first label column)
            total = 0
            for c in range(1, tbl.columnCount() - 1):
                it = tbl.item(4, c)
                if it and it.text().strip() not in ("", "—", "-"):
                    try:
                        total += float(it.text())
                    except ValueError:
                        pass
            return max(1, int(total)) if total > 0 else 1000
        except Exception:
            return 1000

    def estimate_fatalities(self, fed_results, chid):
        """Estimate fatalities based on FED distribution across tunnel occupants.

        The QRA system distributes occupants across five FED bins according to
        their evacuation-time FED exposure.  Because the FED time-series
        represents conditions at a single monitoring point, we model the
        occupant distribution by sampling the cumulative FED curve at the
        pre-movement + travel times read from the zone table.

        FED bins (matching the VB result analysis form):
            0.0 – 0.1   : negligible
            0.1 – 0.3   : slight
            0.3 – 0.5   : moderate (design criterion)
            0.5 – 1.0   : severe
            ≥ 1.0       : incapacitation / fatality
        """
        import numpy as np

        self.evc_status_text.append(f"\n  Estimating fatalities...")
        QApplication.processEvents()

        fed_time  = np.array(fed_results['time'],      dtype=float)
        fed_total = np.array(fed_results['fed_total'], dtype=float)
        n_steps   = len(fed_time)

        # ── Total occupants from vehicle table ─────────────────────────────
        n_people = self._get_total_occupants()

        # ── Read zone table to build per-zone occupant counts & evacuation times ──
        # Zone table columns: Zone | From(m) | To(m) | ExitPt | PC | BS | BL | TS | TM | TL | SUM
        zones = []
        zt = self.evc_zone_table
        for r in range(zt.rowCount()):
            try:
                sum_item = zt.item(r, 10)   # SUM column
                exit_item = zt.item(r, 3)   # ExitPt column
                from_item = zt.item(r, 1)   # From(m)
                to_item   = zt.item(r, 2)   # To(m)
                if sum_item and sum_item.text().strip() not in ("", "—"):
                    occ = int(float(sum_item.text()))
                    exit_pt = float(exit_item.text()) if exit_item else 0.0
                    from_m  = float(from_item.text()) if from_item else 0.0
                    to_m    = float(to_item.text())   if to_item   else 0.0
                    zones.append({'occ': occ, 'exit_pt': exit_pt,
                                  'from_m': from_m, 'to_m': to_m})
            except (ValueError, TypeError):
                pass

        # ── Pre-movement times from pre-movement table ──────────────────────────
        # Columns: From(m) | To(m) | ExitPoint(m) | Premovement(s)
        pmt_map = []   # list of (from_m, to_m, premovement_s)
        pmt = self.evc_pmt_table
        for r in range(pmt.rowCount()):
            try:
                fi = pmt.item(r, 0); ti = pmt.item(r, 1); pi = pmt.item(r, 3)
                if fi and ti and pi:
                    pmt_map.append((
                        float(fi.text()), float(ti.text()), float(pi.text())
                    ))
            except (ValueError, TypeError):
                pass

        def _premovement(x_m):
            """Return pre-movement time (s) for a position x_m."""
            for (fm, tm, pm) in pmt_map:
                if fm <= x_m <= tm:
                    return pm
            return 180.0   # default 3 min

        # Walking speed (m/s) — use minimum speed from simulation tab
        try:
            walk_speed = max(0.1, self.evc_min_speed.value())
        except Exception:
            walk_speed = 0.45

        # ── For each zone, compute evacuation time and sample FED ───────────────
        # Evacuation time = pre-movement + travel time to exit
        # Travel distance = |mid-point of zone - exit point|
        # FED at evacuation = cumulative FED at that time (interpolated)
        occupant_feds = []   # list of (fed_value, occupant_count)

        if zones and n_steps > 0:
            for z in zones:
                mid_x = (z['from_m'] + z['to_m']) / 2.0
                travel_dist = abs(mid_x - z['exit_pt'])
                travel_time = travel_dist / walk_speed   # seconds
                pre_move    = _premovement(mid_x)
                evac_time   = pre_move + travel_time

                # Interpolate cumulative FED at evacuation time
                if evac_time <= fed_time[-1]:
                    fed_at_evac = float(np.interp(evac_time, fed_time, fed_total))
                else:
                    fed_at_evac = float(fed_total[-1])   # use final value

                occupant_feds.append((fed_at_evac, z['occ']))
        else:
            # Fallback: use final FED for all occupants
            occupant_feds = [(float(fed_total[-1]) if n_steps > 0 else 0.0, n_people)]

        # ── Distribute occupants into FED bins ─────────────────────────────────
        bins = {
            '0.0-0.1': 0,
            '0.1-0.3': 0,
            '0.3-0.5': 0,
            '0.5-1.0': 0,
            '>=1.0':   0,
        }
        total_from_zones = sum(o for _, o in occupant_feds)
        scale = n_people / total_from_zones if total_from_zones > 0 else 1.0

        for (fed_val, occ) in occupant_feds:
            scaled_occ = int(round(occ * scale))
            if fed_val < 0.1:
                bins['0.0-0.1'] += scaled_occ
            elif fed_val < 0.3:
                bins['0.1-0.3'] += scaled_occ
            elif fed_val < 0.5:
                bins['0.3-0.5'] += scaled_occ
            elif fed_val < 1.0:
                bins['0.5-1.0'] += scaled_occ
            else:
                bins['>=1.0']   += scaled_occ

        # Fatalities = occupants with FED ≥ 1.0
        fatalities = bins['>=1.0']
        final_fed  = float(fed_total[-1]) if n_steps > 0 else 0.0
        max_fed    = fed_results['max_fed']

        results = {
            'total':       fatalities,
            'n_people':    n_people,
            'categories':  bins,
            'final_fed':   final_fed,
            'max_fed':     max_fed,
            'zone_feds':   occupant_feds,   # (fed_val, occ) per zone
        }

        self.evc_status_text.append(f"    Occupants  : {n_people}")
        self.evc_status_text.append(f"    Final FED  : {final_fed:.4f}")
        self.evc_status_text.append(f"    FED bins   : " +
            " | ".join(f"{k}: {v}" for k, v in bins.items()))
        self.evc_status_text.append(f"    Fatalities : {fatalities}")

        return results
    
    def save_fed_results(self, results, results_dir):
        """Save FED analysis results to files (JSON, CSV, and Tecplot .tec)."""
        import json
        import pandas as pd
        import datetime

        self.evc_status_text.append(f"\n  Saving results to {results_dir}...")
        QApplication.processEvents()

        # ── 1. Save summary JSON ──────────────────────────────────────────────
        summary = []
        for r in results:
            summary.append({
                'chid':       r['chid'],
                'max_fed':    r['fed']['max_fed'],
                'final_fed':  r['fed']['final_fed'],
                'fatalities': r['fatalities']['total'],
                'n_people':   r['fatalities']['n_people'],
                'categories': r['fatalities']['categories'],
                'timestamp':  datetime.datetime.now().isoformat()
            })

        summary_file = results_dir / "fed_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        self.evc_status_text.append(f"    ✓ Summary: {summary_file.name}")

        # ── 2. Save detailed CSV and Tecplot (.tec) for each scenario ─────────
        for r in results:
            chid = r['chid']
            fed  = r['fed']
            
            # CSV export
            df = pd.DataFrame({
                'Time_s':        fed['time'],
                'FED_CO':        fed['fed_co'],
                'FED_O2':        fed['fed_o2'],
                'FED_Heat':      fed['fed_heat'],
                'FED_Total':     fed['fed_total'],
                'Rate_CO':       fed['fed_co_rate'],
                'Rate_O2':       fed['fed_o2_rate'],
                'Rate_Heat':     fed['fed_heat_rate']
            })
            csv_file = results_dir / f"{chid}_fed.csv"
            df.to_csv(csv_file, index=False)

            # Tecplot (.tec) export — matching QRA LocData2Techplot format
            tec_file = results_dir / f"{chid}_fed.tec"
            try:
                with open(tec_file, 'w', encoding='utf-8') as f:
                    f.write(f'TITLE = "QRA FED Analysis Results - {chid}"\n')
                    f.write('VARIABLES = "Time", "FED_CO", "FED_O2", "FED_Heat", "FED_Total", "Rate_CO", "Rate_O2", "Rate_Heat"\n')
                    f.write(f'ZONE T="{chid}", I={len(fed["time"])}, F=POINT\n')
                    for i in range(len(fed['time'])):
                        f.write(f"{fed['time'][i]:.2f} {fed['fed_co'][i]:.6f} {fed['fed_o2'][i]:.6f} "
                                f"{fed['fed_heat'][i]:.6f} {fed['fed_total'][i]:.6f} "
                                f"{fed['fed_co_rate'][i]:.8f} {fed['fed_o2_rate'][i]:.8f} "
                                f"{fed['fed_heat_rate'][i]:.8f}\n")
            except Exception as te:
                self.evc_status_text.append(f"    ⚠️ Tecplot export error: {te}")

        self.evc_status_text.append(f"    ✓ Detailed results: {len(results)} CSV/TEC files")

    def run_statistics(self):
        """Run Monte Carlo statistical analysis on FED results"""
        if not self.project_dir:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return
        
        fed_results_dir = Path(self.project_dir) / "fed_results"
        if not fed_results_dir.exists():
            QMessageBox.warning(self, "No FED Results",
                              "No FED results found.\n\n"
                              "Please run EVC/FED analysis first (Tab 4).")
            return
        
        # Load FED summary
        summary_file = fed_results_dir / "fed_summary.json"
        if not summary_file.exists():
            QMessageBox.warning(self, "No Summary",
                              "FED summary file not found.\n\n"
                              "Please run EVC/FED analysis first.")
            return
        
        self.stats_text.clear()
        self.stats_text.append("="*60)
        self.stats_text.append("MONTE CARLO STATISTICAL ANALYSIS")
        self.stats_text.append("="*60)
        self.stats_text.append("")
        QApplication.processEvents()
        
        try:
            import json
            import numpy as np
            from scipy import stats as scipy_stats
            from scipy.stats import norm
            
            # Load FED results
            with open(summary_file, 'r') as f:
                fed_summary = json.load(f)
            
            n_iterations = self.mc_iterations_input.value()
            trim_pct = self.mc_trim_input.value()
            
            self.stats_text.append(f"Configuration:")
            self.stats_text.append(f"  Iterations: {n_iterations}")
            self.stats_text.append(f"  Trim percentage: {trim_pct}%")
            self.stats_text.append(f"  Scenarios: {len(fed_summary)}")
            self.stats_text.append("")
            QApplication.processEvents()
            
            # Perform Monte Carlo simulation
            self.stats_text.append("Running Monte Carlo simulation...")
            self.stats_text.append("")
            QApplication.processEvents()
            
            mc_results = self.run_monte_carlo_simulation(fed_summary, n_iterations)
            
            # Calculate statistics with trimming
            self.stats_text.append("Calculating statistics...")
            QApplication.processEvents()
            
            stats_results = self.calculate_monte_carlo_statistics(mc_results, trim_pct)
            
            # Display results
            self.display_statistics_results(stats_results, mc_results)
            
            # Save results
            stats_dir = Path(self.project_dir) / "statistics"
            stats_dir.mkdir(exist_ok=True)
            
            self.save_statistics_results(stats_results, mc_results, stats_dir)
            
            self.stats_text.append("")
            self.stats_text.append("="*60)
            self.stats_text.append(f"Results saved to: {stats_dir}")
            self.stats_text.append("="*60)
            
            QMessageBox.information(self, "Analysis Complete",
                                  f"Monte Carlo analysis completed!\n\n"
                                  f"Iterations: {n_iterations}\n"
                                  f"Results saved to: {stats_dir}")
            
        except ImportError as e:
            error_msg = f"Missing required package: {str(e)}\n\n"
            if 'scipy' in str(e):
                error_msg += "Please install scipy:\nsudo pip3 install scipy"
            self.stats_text.append(f"\n❌ {error_msg}")
            QMessageBox.critical(self, "Missing Package", error_msg)
        except Exception as e:
            error_msg = f"Error during statistical analysis: {str(e)}"
            self.stats_text.append(f"\n❌ {error_msg}")
            QMessageBox.critical(self, "Error", error_msg)
            import traceback
            traceback.print_exc()
    
    def run_monte_carlo_simulation(self, fed_summary, n_iterations):
        """Run Monte Carlo simulation with parameter variation"""
        import numpy as np
        
        # Extract baseline data
        scenarios = []
        for result in fed_summary:
            scenarios.append({
                'chid': result['chid'],
                'max_fed': result['max_fed'],
                'final_fed': result['final_fed'],
                'fatalities': result['fatalities'],
                'n_people': result['n_people'],
                'categories': result.get('categories', {}),   # FED bin counts
            })
        
        # Monte Carlo iterations
        mc_results = {
            'iterations': [],
            'scenarios': scenarios
        }
        
        for i in range(n_iterations):
            iteration_data = {
                'iteration': i + 1,
                'scenario_results': [],
                'total_fatalities': 0
            }
            
            for scenario in scenarios:
                # Apply random variation to FED (±20% uncertainty)
                variation_factor = np.random.uniform(0.8, 1.2)
                varied_fed = scenario['final_fed'] * variation_factor
                
                # Recalculate fatalities based on varied FED
                # Using probabilistic approach instead of binary threshold
                fatality_prob = self.calculate_fatality_probability(varied_fed)
                
                # Apply binomial sampling for number of fatalities
                n_people = scenario['n_people']
                fatalities = np.random.binomial(n_people, fatality_prob)
                
                iteration_data['scenario_results'].append({
                    'chid': scenario['chid'],
                    'varied_fed': varied_fed,
                    'fatality_prob': fatality_prob,
                    'fatalities': fatalities
                })
                
                iteration_data['total_fatalities'] += fatalities
            
            mc_results['iterations'].append(iteration_data)
            
            if (i + 1) % max(1, n_iterations // 10) == 0:
                self.stats_text.append(f"  Progress: {i+1}/{n_iterations} iterations")
                QApplication.processEvents()
        
        return mc_results
    
    def calculate_fatality_probability(self, fed):
        """Calculate probability of fatality from FED using probit function"""
        import numpy as np
        from scipy.stats import norm
        
        # Probit model: P = Φ((ln(FED) - μ) / σ)
        # where Φ is standard normal CDF
        # μ = 0 (FED=1 gives 50% probability)
        # σ = 0.5 (controls steepness)
        
        if fed <= 0:
            return 0.0
        
        # Standard probit function
        # ln(FED) with mean=0 (FED=1 → 50%), std=0.5
        z = (np.log(fed) - 0) / 0.5
        prob = norm.cdf(z)
        
        return np.clip(prob, 0.0, 1.0)
    
    def calculate_monte_carlo_statistics(self, mc_results, trim_pct):
        """Calculate statistics from Monte Carlo results with trimming"""
        import numpy as np
        
        # Extract fatality data
        fatalities = [iteration['total_fatalities'] for iteration in mc_results['iterations']]
        fatalities_array = np.array(fatalities)
        
        # Apply trimming (remove outliers)
        trim_fraction = trim_pct / 100.0
        n_trim = int(len(fatalities_array) * trim_fraction)
        
        if n_trim > 0:
            sorted_fatalities = np.sort(fatalities_array)
            trimmed_fatalities = sorted_fatalities[n_trim:-n_trim] if n_trim < len(sorted_fatalities)//2 else sorted_fatalities
        else:
            trimmed_fatalities = fatalities_array
        
        # Calculate statistics
        stats = {
            'raw': {
                'mean': float(np.mean(fatalities_array)),
                'median': float(np.median(fatalities_array)),
                'std': float(np.std(fatalities_array)),
                'min': float(np.min(fatalities_array)),
                'max': float(np.max(fatalities_array)),
                'p5': float(np.percentile(fatalities_array, 5)),
                'p25': float(np.percentile(fatalities_array, 25)),
                'p75': float(np.percentile(fatalities_array, 75)),
                'p95': float(np.percentile(fatalities_array, 95))
            },
            'trimmed': {
                'mean': float(np.mean(trimmed_fatalities)),
                'median': float(np.median(trimmed_fatalities)),
                'std': float(np.std(trimmed_fatalities)),
                'min': float(np.min(trimmed_fatalities)),
                'max': float(np.max(trimmed_fatalities)),
                'p5': float(np.percentile(trimmed_fatalities, 5)),
                'p25': float(np.percentile(trimmed_fatalities, 25)),
                'p75': float(np.percentile(trimmed_fatalities, 75)),
                'p95': float(np.percentile(trimmed_fatalities, 95))
            },
            'trim_pct': trim_pct,
            'n_samples': len(fatalities_array),
            'n_trimmed': len(trimmed_fatalities)
        }
        
        return stats
    
    def display_statistics_results(self, stats, mc_results):
        """Display statistical analysis results including the QRA FED distribution table."""
        import numpy as np
        self.stats_text.append("")
        self.stats_text.append("="*60)
        self.stats_text.append("STATISTICAL ANALYSIS RESULTS")
        self.stats_text.append("="*60)
        self.stats_text.append("")

        # ── 1. FED Distribution Table (Averaged across scenarios) ──────────
        self.stats_text.append("FED Distribution Summary (Averaged):")
        self.stats_text.append("-" * 60)
        self.stats_text.append(f"  {'FED Range':<15} | {'Description':<15} | {'Occupants':<10}")
        self.stats_text.append("-" * 60)
        
        # Aggregate real category data from mc_results['scenarios']
        agg_cats = {'0.0-0.1': 0, '0.1-0.3': 0, '0.3-0.5': 0, '0.5-1.0': 0, '>=1.0': 0}
        has_cats = False
        for sc in mc_results.get('scenarios', []):
            cats = sc.get('categories', {})
            if cats:
                has_cats = True
                for k in agg_cats:
                    agg_cats[k] += cats.get(k, 0)

        def _cat(k):
            return str(agg_cats[k]) if has_cats else '--'

        self.stats_text.append(f"  {'0.0 – 0.1':<15} | {'Negligible':<15} | {_cat('0.0-0.1')}")
        self.stats_text.append(f"  {'0.1 – 0.3':<15} | {'Slight':<15} | {_cat('0.1-0.3')}")
        self.stats_text.append(f"  {'0.3 – 0.5':<15} | {'Moderate':<15} | {_cat('0.3-0.5')}")
        self.stats_text.append(f"  {'0.5 – 1.0':<15} | {'Severe':<15} | {_cat('0.5-1.0')}")
        self.stats_text.append(f"  {'>= 1.0':<15} | {'Incapacitation':<15} | {_cat('>=1.0')}")
        self.stats_text.append("-" * 60)
        self.stats_text.append("")

        # ── 2. Raw statistics ──────────────────────────────────────────────
        self.stats_text.append("Fatality Statistics (All Iterations):")
        self.stats_text.append("-" * 60)
        raw = stats['raw']
        self.stats_text.append(f"  Mean:              {raw['mean']:.2f} fatalities")
        self.stats_text.append(f"  Median:            {raw['median']:.2f} fatalities")
        self.stats_text.append(f"  Std Deviation:     {raw['std']:.2f}")
        self.stats_text.append(f"  Min / Max:         {raw['min']:.0f} / {raw['max']:.0f}")
        self.stats_text.append("")
        self.stats_text.append("  Percentiles:")
        self.stats_text.append(f"    5th  (P05):      {raw['p5']:.2f}")
        self.stats_text.append(f"    50th (P50):      {raw['median']:.2f}")
        self.stats_text.append(f"    95th (P95):      {raw['p95']:.2f}")
        self.stats_text.append("")

        # ── 3. Trimmed statistics ──────────────────────────────────────────
        if stats['trim_pct'] > 0:
            self.stats_text.append(f"Trimmed Statistics ({stats['trim_pct']}% trim):")
            self.stats_text.append("-" * 60)
            trimmed = stats['trimmed']
            self.stats_text.append(f"  Samples used:      {stats['n_trimmed']} / {stats['n_samples']}")
            self.stats_text.append(f"  Trimmed Mean:      {trimmed['mean']:.2f}")
            self.stats_text.append(f"  Trimmed Std Dev:   {trimmed['std']:.2f}")
            self.stats_text.append("")

        # ── 4. Confidence intervals ────────────────────────────────────────
        self.stats_text.append("Confidence Intervals (Fatality Count):")
        self.stats_text.append("-" * 60)
        all_fats = np.array([it['total_fatalities'] for it in mc_results['iterations']], dtype=float)
        ci_50 = (float(np.percentile(all_fats, 25)), float(np.percentile(all_fats, 75)))
        ci_90 = (float(np.percentile(all_fats,  5)), float(np.percentile(all_fats, 95)))
        ci_95 = (float(np.percentile(all_fats,  2.5)), float(np.percentile(all_fats, 97.5)))
        self.stats_text.append(f"  50% CI (P25-P75):  [{ci_50[0]:.1f}, {ci_50[1]:.1f}]")
        self.stats_text.append(f"  90% CI (P05-P95):  [{ci_90[0]:.1f}, {ci_90[1]:.1f}]")
        self.stats_text.append(f"  95% CI (P02-P97):  [{ci_95[0]:.1f}, {ci_95[1]:.1f}]")
        self.stats_text.append("")
    
    def save_statistics_results(self, stats, mc_results, stats_dir):
        """Save statistical analysis results to files"""
        import json
        import pandas as pd
        
        # Save summary statistics as JSON
        summary_file = stats_dir / "statistics_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        self.stats_text.append(f"  ✓ Saved: {summary_file.name}")
        
        # Save iteration data as CSV
        iterations_data = []
        for iteration in mc_results['iterations']:
            iterations_data.append({
                'iteration': iteration['iteration'],
                'total_fatalities': iteration['total_fatalities']
            })
        
        df = pd.DataFrame(iterations_data)
        csv_file = stats_dir / "monte_carlo_iterations.csv"
        df.to_csv(csv_file, index=False)
        
        self.stats_text.append(f"  ✓ Saved: {csv_file.name}")
        
        # Save detailed scenario results
        scenario_data = []
        for iteration in mc_results['iterations']:
            for scenario_result in iteration['scenario_results']:
                scenario_data.append({
                    'iteration': iteration['iteration'],
                    'chid': scenario_result['chid'],
                    'varied_fed': scenario_result['varied_fed'],
                    'fatality_prob': scenario_result['fatality_prob'],
                    'fatalities': scenario_result['fatalities']
                })
        
        df_scenarios = pd.DataFrame(scenario_data)
        scenarios_file = stats_dir / "monte_carlo_scenarios.csv"
        df_scenarios.to_csv(scenarios_file, index=False)
        
        self.stats_text.append(f"  ✓ Saved: {scenarios_file.name}")
    
    def calculate_risk(self):
        """Calculate risk metrics"""
        QMessageBox.information(self, "Risk Calculation", "Risk calculation will be implemented.")
    
    def view_fn_curve(self):
        """View F-N curve"""
        QMessageBox.information(self, "F-N Curve", "F-N curve visualization will be implemented.")
    
    def export_to_excel(self):
        """Export to Excel"""
        QMessageBox.information(self, "Export", "Excel export will be implemented.")
    
    def export_to_pdf(self):
        """Export to PDF"""
        QMessageBox.information(self, "Export", "PDF export will be implemented.")
    
    def update_parallel_config(self):
        """Update parallel processing configuration display"""
        try:
            parallel_jobs = self.parallel_jobs_spinbox.value()
            cores_total = self.cores_spinbox.value()
            ram_percent = int(self.ram_usage_combo.currentText().rstrip('%'))
            
            # Calculate resources per job
            cores_per_job = max(1, cores_total // parallel_jobs)
            ram_limit_gb = self.system_ram_gb * (ram_percent / 100.0)
            ram_per_job_gb = 5.0  # Estimated RAM per FDS simulation
            total_ram_needed = parallel_jobs * ram_per_job_gb
            
            # Check if configuration is valid
            if total_ram_needed > ram_limit_gb:
                status_color = "#e74c3c"  # Red
                status_icon = "⚠️"
                status_text = "WARNING: May exceed RAM limit!"
            else:
                status_color = "#27ae60"  # Green
                status_icon = "✅"
                status_text = "Configuration OK"
            
            # Update display
            info_text = (
                f"{status_icon} {status_text}\n"
                f"\u2022 {parallel_jobs} simulation(s) running in parallel\n"
                f"• {cores_per_job} CPU cores per simulation\n"
                f"• ~{ram_per_job_gb:.1f} GB RAM per simulation\n"
                f"• Total RAM usage: ~{total_ram_needed:.1f} GB / {ram_limit_gb:.1f} GB limit"
            )
            self.resource_info_label.setText(info_text)
            self.resource_info_label.setStyleSheet(
                f"padding: 8px; background-color: {status_color}22; "
                f"border: 1px solid {status_color}; border-radius: 5px; font-size: 11px;"
            )
        except Exception as e:
            print(f"Error updating parallel config: {e}")
    
    def auto_calculate_parallel(self):
        """Automatically calculate optimal number of parallel jobs"""
        try:
            # Get RAM limit
            ram_percent = int(self.ram_usage_combo.currentText().rstrip('%'))
            ram_limit_gb = self.system_ram_gb * (ram_percent / 100.0)
            
            # Estimate RAM per simulation (conservative)
            ram_per_sim_gb = 5.0
            
            # Calculate max parallel based on RAM
            max_parallel_ram = int(ram_limit_gb / ram_per_sim_gb)
            
            # Calculate max parallel based on CPU (minimum 4 cores per sim)
            min_cores_per_sim = 4
            cores_total = self.cores_spinbox.value()
            max_parallel_cpu = max(1, cores_total // min_cores_per_sim)
            
            # Take minimum to be safe, cap at 8
            optimal_parallel = min(max_parallel_ram, max_parallel_cpu, 8)
            optimal_parallel = max(1, optimal_parallel)  # At least 1
            
            # Set the value
            self.parallel_jobs_spinbox.setValue(optimal_parallel)
            
            # Show info
            QMessageBox.information(
                self,
                "Auto-Calculate Complete",
                f"Optimal parallel jobs: {optimal_parallel}\n\n"
                f"Based on:\n"
                f"• RAM limit: {ram_limit_gb:.1f} GB ({ram_percent}%)\n"
                f"• RAM per simulation: ~{ram_per_sim_gb:.1f} GB\n"
                f"• CPU cores: {cores_total}\n"
                f"• Min cores per sim: {min_cores_per_sim}\n\n"
                f"This configuration will use:\n"
                f"• {optimal_parallel} parallel simulations\n"
                f"• {cores_total // optimal_parallel} cores per simulation\n"
                f"• ~{optimal_parallel * ram_per_sim_gb:.1f} GB total RAM"
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to auto-calculate: {e}")
    
    def update_time_estimates(self):
        """Update simulation time estimates based on cores, parallel jobs, and FDS files"""
        try:
            if not self.project_dir:
                return
            
            # Count FDS files
            fds_inputs_dir = Path(self.project_dir) / "fds_inputs"
            if not fds_inputs_dir.exists():
                self.time_estimate_text.setPlainText("No FDS files generated yet. Generate files in Tab 2 first.")
                return
            
            fds_files = list(fds_inputs_dir.rglob("*.fds"))
            num_files = len(fds_files)
            
            if num_files == 0:
                self.time_estimate_text.setPlainText("No FDS files found. Generate files in Tab 2 first.")
                return
            
            # Read T_END from first FDS file
            t_end = 900.0  # default
            if fds_files:
                try:
                    with open(fds_files[0], 'r') as f:
                        for line in f:
                            if 'T_END' in line and '&TIME' in line:
                                # Parse T_END value
                                parts = line.split('T_END')
                                if len(parts) > 1:
                                    value_part = parts[1].split('/')[0].strip().replace('=', '').strip()
                                    t_end = float(value_part)
                                break
                except:
                    pass
            
            # Get selected cores and parallel jobs
            cores_total = self.cores_spinbox.value()
            parallel_jobs = self.parallel_jobs_spinbox.value()
            cores_per_job = max(1, cores_total // parallel_jobs)
            
            # Calculate total simulation time
            total_sim_time = num_files * t_end
            total_sim_minutes = total_sim_time / 60
            
            # Estimate real time based on cores per job
            # Based on observed performance: 4 cores gives ~0.76x real-time for large mesh
            # Scaling factor: approximately linear with cores up to ~16 cores
            base_speedup = 0.76  # 4 cores baseline from user's test
            core_scaling = cores_per_job / 4.0
            estimated_speedup = base_speedup * core_scaling
            
            # Real time per simulation
            real_time_per_sim = t_end / estimated_speedup
            
            # Total real time with parallel processing
            # If parallel_jobs > num_files, some jobs will be idle
            effective_parallel = min(parallel_jobs, num_files)
            num_batches = (num_files + effective_parallel - 1) // effective_parallel  # Ceiling division
            real_time_seconds = num_batches * real_time_per_sim
            real_time_hours = real_time_seconds / 3600
            real_time_minutes = real_time_seconds / 60
            
            # Format output
            output = []
            output.append(f"Files to Simulate: {num_files}")
            output.append(f"T_END per file: {t_end:.0f} seconds ({t_end/60:.1f} minutes)")
            output.append(f"Total Simulation Time: {total_sim_time:.0f} seconds ({total_sim_minutes:.1f} minutes)")
            output.append("")
            output.append(f"Current Configuration:")
            output.append(f"  • Parallel Jobs: {effective_parallel}")
            output.append(f"  • Cores per Job: {cores_per_job}")
            output.append(f"  • Total Cores Used: {cores_total}")
            output.append("")
            output.append(f"Estimated Real Time:")
            output.append(f"  • Per Simulation: ~{real_time_per_sim/60:.1f} minutes")
            output.append(f"  • Number of Batches: {num_batches}")
            output.append(f"  • Total Time: ~{real_time_hours:.2f} hours ({real_time_minutes:.1f} minutes)")
            
            # Show speedup from parallelization
            if parallel_jobs > 1:
                sequential_time = num_files * real_time_per_sim / 3600
                speedup = sequential_time / real_time_hours
                time_saved = sequential_time - real_time_hours
                output.append("")
                output.append(f"Parallel Processing Benefit:")
                output.append(f"  • Sequential time: ~{sequential_time:.2f} hours")
                output.append(f"  • Parallel time: ~{real_time_hours:.2f} hours")
                output.append(f"  • Speedup: {speedup:.2f}x")
                output.append(f"  • Time saved: ~{time_saved:.2f} hours")
            
            output.append("")
            output.append("Note: Estimates based on large mesh (2.3M cells).")
            output.append("Actual time may vary depending on mesh resolution.")
            
            self.time_estimate_text.setPlainText("\n".join(output))
            
        except Exception as e:
            self.time_estimate_text.setPlainText(f"Error calculating estimates: {str(e)}")


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = EVCMainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()