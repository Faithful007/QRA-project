"""
FDS Project Setup GUI
Interactive PyQt5 interface for creating FDS project directory structure
"""

import os
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
    QGroupBox, QMessageBox, QProgressBar, QTreeWidget, QTreeWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon


class DirectoryCreationThread(QThread):
    """Thread for creating directory structure"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, base_path, project_name):
        super().__init__()
        self.base_path = base_path
        self.project_name = project_name
        self.project_dir = Path(base_path) / project_name
    
    def run(self):
        """Create directory structure"""
        try:
            # Define directory structure
            # Base directories
            directories = [
                "fds_outputs",
                "fdb_files",
                "ascii_files",
                "evc_files",
                "fed_results",
                "logs"
            ]
            
            # FDS Inputs nested structure: fds_inputs/{HRR}/{Cong|Norm}/{VentilationType}/
            hrr_values = ["020", "030", "100"]
            traffic_conditions = ["Cong", "Norm"]
            ventilation_types = ["FV0", "FVM", "FVP", "NV0", "NVC"]
            
            for hrr in hrr_values:
                for traffic in traffic_conditions:
                    for vent in ventilation_types:
                        directories.append(f"fds_inputs/{hrr}/{traffic}/{vent}")
            
            total_steps = len(directories) + 2  # +2 for project dir and batch file
            current_step = 0
            
            # Create project root directory
            self.progress.emit(int((current_step / total_steps) * 100), 
                             f"Creating project directory: {self.project_name}")
            self.project_dir.mkdir(parents=True, exist_ok=True)
            current_step += 1
            
            # Create subdirectories
            for dir_path in directories:
                self.progress.emit(int((current_step / total_steps) * 100),
                                 f"Creating: {dir_path}")
                (self.project_dir / dir_path).mkdir(parents=True, exist_ok=True)
                current_step += 1
            
            # Create batch script placeholder
            self.progress.emit(int((current_step / total_steps) * 100),
                             "Creating batch script template")
            batch_file = self.project_dir / "run_all_simulations.bat"
            with open(batch_file, 'w') as f:
                f.write("@echo off\n")
                f.write("REM FDS Batch Execution Script\n")
                f.write("REM This file will be populated when FDS input files are generated\n")
                f.write("echo No simulations configured yet\n")
                f.write("pause\n")
            current_step += 1
            
            # Complete
            self.progress.emit(100, "Directory structure created successfully!")
            self.finished.emit(True, str(self.project_dir))
            
        except Exception as e:
            self.finished.emit(False, str(e))


class ProjectSetupGUI(QMainWindow):
    """Main GUI window for FDS project setup"""
    
    def __init__(self):
        super().__init__()
        self.project_dir = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("FDS Project Setup - Directory Structure Creator")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title
        title_label = QLabel("FDS Project Directory Structure Setup")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Create organized directory structure for FDS simulations and QRA analysis")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: gray; margin-bottom: 20px;")
        main_layout.addWidget(subtitle_label)
        
        # Project Configuration Group
        config_group = QGroupBox("Project Configuration")
        config_layout = QVBoxLayout()
        config_group.setLayout(config_layout)
        
        # Project Name
        name_layout = QHBoxLayout()
        name_label = QLabel("Project Name:")
        name_label.setMinimumWidth(120)
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("Enter project name (e.g., TunnelFireQRA_2026)")
        self.project_name_input.textChanged.connect(self.update_preview)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.project_name_input)
        config_layout.addLayout(name_layout)
        
        # Home Directory
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Home Directory:")
        dir_label.setMinimumWidth(120)
        self.home_dir_input = QLineEdit()
        self.home_dir_input.setPlaceholderText("Select home directory location")
        self.home_dir_input.textChanged.connect(self.update_preview)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.home_dir_input)
        dir_layout.addWidget(browse_btn)
        config_layout.addLayout(dir_layout)
        
        # Full Path Display
        path_layout = QHBoxLayout()
        path_label = QLabel("Full Project Path:")
        path_label.setMinimumWidth(120)
        self.full_path_display = QLineEdit()
        self.full_path_display.setReadOnly(True)
        self.full_path_display.setStyleSheet("background-color: #f0f0f0;")
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.full_path_display)
        config_layout.addLayout(path_layout)
        
        main_layout.addWidget(config_group)
        
        # Directory Structure Preview Group
        preview_group = QGroupBox("Directory Structure Preview")
        preview_layout = QVBoxLayout()
        preview_group.setLayout(preview_layout)
        
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("Directory Structure")
        self.tree_widget.setMinimumHeight(250)
        preview_layout.addWidget(self.tree_widget)
        
        main_layout.addWidget(preview_group)
        
        # Progress Group
        progress_group = QGroupBox("Creation Progress")
        progress_layout = QVBoxLayout()
        progress_group.setLayout(progress_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        self.status_text.setPlaceholderText("Status messages will appear here...")
        progress_layout.addWidget(self.status_text)
        
        main_layout.addWidget(progress_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.create_btn = QPushButton("Create Project Structure")
        self.create_btn.setMinimumHeight(40)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.create_btn.clicked.connect(self.create_structure)
        self.create_btn.setEnabled(False)
        
        self.open_btn = QPushButton("Open Project Folder")
        self.open_btn.setMinimumHeight(40)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_project_folder)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumHeight(40)
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.create_btn)
        button_layout.addWidget(self.open_btn)
        button_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(button_layout)
        
        # Initialize preview
        self.update_preview()
    
    def browse_directory(self):
        """Open directory browser dialog"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Home Directory",
            str(Path.home()),
            QFileDialog.ShowDirsOnly
        )
        
        if directory:
            self.home_dir_input.setText(directory)
    
    def update_preview(self):
        """Update directory structure preview"""
        project_name = self.project_name_input.text().strip()
        home_dir = self.home_dir_input.text().strip()
        
        # Update full path display
        if project_name and home_dir:
            full_path = str(Path(home_dir) / project_name)
            self.full_path_display.setText(full_path)
            self.create_btn.setEnabled(True)
        else:
            self.full_path_display.setText("")
            self.create_btn.setEnabled(False)
        
        # Update tree widget
        self.tree_widget.clear()
        
        if project_name:
            # Root item
            root = QTreeWidgetItem(self.tree_widget)
            root.setText(0, f"{project_name}/")
            root.setExpanded(True)
            
            # FDS Inputs
            fds_inputs = QTreeWidgetItem(root)
            fds_inputs.setText(0, "fds_inputs/  # Generated FDS input files")
            fds_inputs.setExpanded(True)
            
            hrr_values = [("020", "20 MW"), ("030", "30 MW"), ("100", "100 MW")]
            traffic_conditions = ["Cong", "Norm"]
            ventilation_types = ["FV0", "FVM", "FVP", "NV0", "NVC"]
            
            for hrr_code, hrr_desc in hrr_values:
                hrr_item = QTreeWidgetItem(fds_inputs)
                hrr_item.setText(0, f"{hrr_code}/  # {hrr_desc} scenarios")
                
                for traffic in traffic_conditions:
                    traffic_item = QTreeWidgetItem(hrr_item)
                    traffic_item.setText(0, f"{traffic}/")
                    
                    for vent in ventilation_types:
                        vent_item = QTreeWidgetItem(traffic_item)
                        vent_item.setText(0, f"{vent}/")
            
            # FDS Outputs
            fds_outputs = QTreeWidgetItem(root)
            fds_outputs.setText(0, "fds_outputs/  # FDS simulation outputs (.smv, .out, .sf, etc.)")
            
            # FDB Files
            fdb_files = QTreeWidgetItem(root)
            fdb_files.setText(0, "fdb_files/  # Converted FDB files for EVC")

            # ASCII Files
            ascii_files = QTreeWidgetItem(root)
            ascii_files.setText(0, "ascii_files/  # CSV/ASCII exports from fds2ascii")

            # EVC Files
            evc_files = QTreeWidgetItem(root)
            evc_files.setText(0, "evc_files/  # Generated EVC input files for FED analysis")

            # FED Results
            fed_results = QTreeWidgetItem(root)
            fed_results.setText(0, "fed_results/  # FED analysis results and reports")

            # Logs
            logs = QTreeWidgetItem(root)
            logs.setText(0, "logs/  # Workflow logs")
            
            # Batch script
            batch = QTreeWidgetItem(root)
            batch.setText(0, "run_all_simulations.bat  # Batch script for manual execution")
    
    def create_structure(self):
        """Create directory structure"""
        project_name = self.project_name_input.text().strip()
        home_dir = self.home_dir_input.text().strip()
        
        if not project_name or not home_dir:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter both project name and home directory."
            )
            return
        
        # Check if directory already exists
        project_path = Path(home_dir) / project_name
        if project_path.exists():
            reply = QMessageBox.question(
                self,
                "Directory Exists",
                f"The directory '{project_path}' already exists.\n\nDo you want to continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                return
        
        # Disable create button during creation
        self.create_btn.setEnabled(False)
        self.status_text.clear()
        self.progress_bar.setValue(0)
        
        # Create thread for directory creation
        self.creation_thread = DirectoryCreationThread(home_dir, project_name)
        self.creation_thread.progress.connect(self.update_progress)
        self.creation_thread.finished.connect(self.creation_finished)
        self.creation_thread.start()
    
    def update_progress(self, value, message):
        """Update progress bar and status"""
        self.progress_bar.setValue(value)
        self.status_text.append(message)
        
        # Auto-scroll to bottom
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.End)
        self.status_text.setTextCursor(cursor)
    
    def creation_finished(self, success, message):
        """Handle creation completion"""
        if success:
            self.project_dir = message
            self.status_text.append("\n" + "="*50)
            self.status_text.append("✓ SUCCESS: Project structure created!")
            self.status_text.append(f"Location: {message}")
            self.status_text.append("="*50)
            
            self.open_btn.setEnabled(True)
            
            QMessageBox.information(
                self,
                "Success",
                f"Project directory structure created successfully!\n\nLocation:\n{message}"
            )
        else:
            self.status_text.append("\n" + "="*50)
            self.status_text.append(f"✗ ERROR: {message}")
            self.status_text.append("="*50)
            
            self.create_btn.setEnabled(True)
            
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create directory structure:\n\n{message}"
            )
    
    def open_project_folder(self):
        """Open project folder in file explorer"""
        if self.project_dir and Path(self.project_dir).exists():
            import platform
            import subprocess
            
            system = platform.system()
            
            try:
                if system == "Windows":
                    os.startfile(self.project_dir)
                elif system == "Darwin":  # macOS
                    subprocess.run(["open", self.project_dir])
                else:  # Linux
                    subprocess.run(["xdg-open", self.project_dir])
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Could not open folder:\n{e}"
                )


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show window
    window = ProjectSetupGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


# """
# FDS Project Setup GUI
# Interactive PyQt5 interface for creating FDS project directory structure
# """

# import os
# import sys
# from pathlib import Path
# from PyQt5.QtWidgets import (
#     QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
#     QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
#     QGroupBox, QMessageBox, QProgressBar, QTreeWidget, QTreeWidgetItem
# )
# from PyQt5.QtCore import Qt, QThread, pyqtSignal
# from PyQt5.QtGui import QFont, QIcon


# class DirectoryCreationThread(QThread):
#     """Thread for creating directory structure"""
#     progress = pyqtSignal(int, str)
#     finished = pyqtSignal(bool, str)
    
#     def __init__(self, base_path, project_name):
#         super().__init__()
#         self.base_path = base_path
#         self.project_name = project_name
#         self.project_dir = Path(base_path) / project_name
    
#     def run(self):
#         """Create directory structure"""
#         try:
#             # Define directory structure
#             # Base directories
#             directories = [
#                 "fds_outputs",
#                 "fdb_files",
#                 "ascii_files",
#                 "evc_files",
#                 "fed_results",
#                 "logs"
#             ]
            
#             # FDS Inputs nested structure: fds_inputs/{HRR}/{Cong|Norm}/{VentilationType}/
#             hrr_values = ["020", "030", "100"]
#             traffic_conditions = ["Cong", "Norm"]
#             ventilation_types = ["FV0", "FVM", "FVP", "NV0", "NVC"]
            
#             for hrr in hrr_values:
#                 for traffic in traffic_conditions:
#                     for vent in ventilation_types:
#                         directories.append(f"fds_inputs/{hrr}/{traffic}/{vent}")
            
#             total_steps = len(directories) + 2  # +2 for project dir and batch file
#             current_step = 0
            
#             # Create project root directory
#             self.progress.emit(int((current_step / total_steps) * 100), 
#                              f"Creating project directory: {self.project_name}")
#             self.project_dir.mkdir(parents=True, exist_ok=True)
#             current_step += 1
            
#             # Create subdirectories
#             for dir_path in directories:
#                 self.progress.emit(int((current_step / total_steps) * 100),
#                                  f"Creating: {dir_path}")
#                 (self.project_dir / dir_path).mkdir(parents=True, exist_ok=True)
#                 current_step += 1
            
#             # Create batch script placeholder
#             self.progress.emit(int((current_step / total_steps) * 100),
#                              "Creating batch script template")
#             batch_file = self.project_dir / "run_all_simulations.bat"
#             with open(batch_file, 'w') as f:
#                 f.write("@echo off\n")
#                 f.write("REM FDS Batch Execution Script\n")
#                 f.write("REM This file will be populated when FDS input files are generated\n")
#                 f.write("echo No simulations configured yet\n")
#                 f.write("pause\n")
#             current_step += 1
            
#             # Complete
#             self.progress.emit(100, "Directory structure created successfully!")
#             self.finished.emit(True, str(self.project_dir))
            
#         except Exception as e:
#             self.finished.emit(False, str(e))


# class ProjectSetupGUI(QMainWindow):
#     """Main GUI window for FDS project setup"""
    
#     def __init__(self):
#         super().__init__()
#         self.project_dir = None
#         self.init_ui()
    
#     def init_ui(self):
#         """Initialize user interface"""
#         self.setWindowTitle("FDS Project Setup - Directory Structure Creator")
#         self.setGeometry(100, 100, 900, 700)
        
#         # Central widget
#         central_widget = QWidget()
#         self.setCentralWidget(central_widget)
        
#         # Main layout
#         main_layout = QVBoxLayout()
#         central_widget.setLayout(main_layout)
        
#         # Title
#         title_label = QLabel("FDS Project Directory Structure Setup")
#         title_font = QFont()
#         title_font.setPointSize(16)
#         title_font.setBold(True)
#         title_label.setFont(title_font)
#         title_label.setAlignment(Qt.AlignCenter)
#         main_layout.addWidget(title_label)
        
#         # Subtitle
#         subtitle_label = QLabel("Create organized directory structure for FDS simulations and QRA analysis")
#         subtitle_label.setAlignment(Qt.AlignCenter)
#         subtitle_label.setStyleSheet("color: gray; margin-bottom: 20px;")
#         main_layout.addWidget(subtitle_label)
        
#         # Project Configuration Group
#         config_group = QGroupBox("Project Configuration")
#         config_layout = QVBoxLayout()
#         config_group.setLayout(config_layout)
        
#         # Project Name
#         name_layout = QHBoxLayout()
#         name_label = QLabel("Project Name:")
#         name_label.setMinimumWidth(120)
#         self.project_name_input = QLineEdit()
#         self.project_name_input.setPlaceholderText("Enter project name (e.g., TunnelFireQRA_2026)")
#         self.project_name_input.textChanged.connect(self.update_preview)
#         name_layout.addWidget(name_label)
#         name_layout.addWidget(self.project_name_input)
#         config_layout.addLayout(name_layout)
        
#         # Home Directory
#         dir_layout = QHBoxLayout()
#         dir_label = QLabel("Home Directory:")
#         dir_label.setMinimumWidth(120)
#         self.home_dir_input = QLineEdit()
#         self.home_dir_input.setPlaceholderText("Select home directory location")
#         self.home_dir_input.textChanged.connect(self.update_preview)
#         browse_btn = QPushButton("Browse...")
#         browse_btn.clicked.connect(self.browse_directory)
#         dir_layout.addWidget(dir_label)
#         dir_layout.addWidget(self.home_dir_input)
#         dir_layout.addWidget(browse_btn)
#         config_layout.addLayout(dir_layout)
        
#         # Full Path Display
#         path_layout = QHBoxLayout()
#         path_label = QLabel("Full Project Path:")
#         path_label.setMinimumWidth(120)
#         self.full_path_display = QLineEdit()
#         self.full_path_display.setReadOnly(True)
#         self.full_path_display.setStyleSheet("background-color: #f0f0f0;")
#         path_layout.addWidget(path_label)
#         path_layout.addWidget(self.full_path_display)
#         config_layout.addLayout(path_layout)
        
#         main_layout.addWidget(config_group)
        
#         # Directory Structure Preview Group
#         preview_group = QGroupBox("Directory Structure Preview")
#         preview_layout = QVBoxLayout()
#         preview_group.setLayout(preview_layout)
        
#         self.tree_widget = QTreeWidget()
#         self.tree_widget.setHeaderLabel("Directory Structure")
#         self.tree_widget.setMinimumHeight(250)
#         preview_layout.addWidget(self.tree_widget)
        
#         main_layout.addWidget(preview_group)
        
#         # Progress Group
#         progress_group = QGroupBox("Creation Progress")
#         progress_layout = QVBoxLayout()
#         progress_group.setLayout(progress_layout)
        
#         self.progress_bar = QProgressBar()
#         self.progress_bar.setValue(0)
#         progress_layout.addWidget(self.progress_bar)
        
#         self.status_text = QTextEdit()
#         self.status_text.setReadOnly(True)
#         self.status_text.setMaximumHeight(100)
#         self.status_text.setPlaceholderText("Status messages will appear here...")
#         progress_layout.addWidget(self.status_text)
        
#         main_layout.addWidget(progress_group)
        
#         # Buttons
#         button_layout = QHBoxLayout()
        
#         self.create_btn = QPushButton("Create Project Structure")
#         self.create_btn.setMinimumHeight(40)
#         self.create_btn.setStyleSheet("""
#             QPushButton {
#                 background-color: #4CAF50;
#                 color: white;
#                 font-size: 14px;
#                 font-weight: bold;
#                 border-radius: 5px;
#             }
#             QPushButton:hover {
#                 background-color: #45a049;
#             }
#             QPushButton:disabled {
#                 background-color: #cccccc;
#                 color: #666666;
#             }
#         """)
#         self.create_btn.clicked.connect(self.create_structure)
#         self.create_btn.setEnabled(False)
        
#         self.open_btn = QPushButton("Open Project Folder")
#         self.open_btn.setMinimumHeight(40)
#         self.open_btn.setEnabled(False)
#         self.open_btn.clicked.connect(self.open_project_folder)
        
#         self.close_btn = QPushButton("Close")
#         self.close_btn.setMinimumHeight(40)
#         self.close_btn.clicked.connect(self.close)
        
#         button_layout.addWidget(self.create_btn)
#         button_layout.addWidget(self.open_btn)
#         button_layout.addWidget(self.close_btn)
        
#         main_layout.addLayout(button_layout)
        
#         # Initialize preview
#         self.update_preview()
    
#     def browse_directory(self):
#         """Open directory browser dialog"""
#         directory = QFileDialog.getExistingDirectory(
#             self,
#             "Select Home Directory",
#             str(Path.home()),
#             QFileDialog.ShowDirsOnly
#         )
        
#         if directory:
#             self.home_dir_input.setText(directory)
    
#     def update_preview(self):
#         """Update directory structure preview"""
#         project_name = self.project_name_input.text().strip()
#         home_dir = self.home_dir_input.text().strip()
        
#         # Update full path display
#         if project_name and home_dir:
#             full_path = str(Path(home_dir) / project_name)
#             self.full_path_display.setText(full_path)
#             self.create_btn.setEnabled(True)
#         else:
#             self.full_path_display.setText("")
#             self.create_btn.setEnabled(False)
        
#         # Update tree widget
#         self.tree_widget.clear()
        
#         if project_name:
#             # Root item
#             root = QTreeWidgetItem(self.tree_widget)
#             root.setText(0, f"{project_name}/")
#             root.setExpanded(True)
            
#             # FDS Inputs
#             fds_inputs = QTreeWidgetItem(root)
#             fds_inputs.setText(0, "fds_inputs/  # Generated FDS input files")
#             fds_inputs.setExpanded(True)
            
#             hrr_values = [("020", "20 MW"), ("030", "30 MW"), ("100", "100 MW")]
#             traffic_conditions = ["Cong", "Norm"]
#             ventilation_types = ["FV0", "FVM", "FVP", "NV0", "NVC"]
            
#             for hrr_code, hrr_desc in hrr_values:
#                 hrr_item = QTreeWidgetItem(fds_inputs)
#                 hrr_item.setText(0, f"{hrr_code}/  # {hrr_desc} scenarios")
                
#                 for traffic in traffic_conditions:
#                     traffic_item = QTreeWidgetItem(hrr_item)
#                     traffic_item.setText(0, f"{traffic}/")
                    
#                     for vent in ventilation_types:
#                         vent_item = QTreeWidgetItem(traffic_item)
#                         vent_item.setText(0, f"{vent}/")
            
#             # FDS Outputs
#             fds_outputs = QTreeWidgetItem(root)
#             fds_outputs.setText(0, "fds_outputs/  # FDS simulation outputs (.smv, .out, .sf, etc.)")
            
#             # FDB Files
#             fdb_files = QTreeWidgetItem(root)
#             fdb_files.setText(0, "fdb_files/  # Converted FDB files for EVC")

#             # ASCII Files
#             ascii_files = QTreeWidgetItem(root)
#             ascii_files.setText(0, "ascii_files/  # CSV/ASCII exports from fds2ascii")

#             # EVC Files
#             evc_files = QTreeWidgetItem(root)
#             evc_files.setText(0, "evc_files/  # Generated EVC input files for FED analysis")

#             # FED Results
#             fed_results = QTreeWidgetItem(root)
#             fed_results.setText(0, "fed_results/  # FED analysis results and reports")

#             # Logs
#             logs = QTreeWidgetItem(root)
#             logs.setText(0, "logs/  # Workflow logs")
            
#             # Batch script
#             batch = QTreeWidgetItem(root)
#             batch.setText(0, "run_all_simulations.bat  # Batch script for manual execution")
    
#     def create_structure(self):
#         """Create directory structure"""
#         project_name = self.project_name_input.text().strip()
#         home_dir = self.home_dir_input.text().strip()
        
#         if not project_name or not home_dir:
#             QMessageBox.warning(
#                 self,
#                 "Missing Information",
#                 "Please enter both project name and home directory."
#             )
#             return
        
#         # Check if directory already exists
#         project_path = Path(home_dir) / project_name
#         if project_path.exists():
#             reply = QMessageBox.question(
#                 self,
#                 "Directory Exists",
#                 f"The directory '{project_path}' already exists.\n\nDo you want to continue anyway?",
#                 QMessageBox.Yes | QMessageBox.No,
#                 QMessageBox.No
#             )
            
#             if reply == QMessageBox.No:
#                 return
        
#         # Disable create button during creation
#         self.create_btn.setEnabled(False)
#         self.status_text.clear()
#         self.progress_bar.setValue(0)
        
#         # Create thread for directory creation
#         self.creation_thread = DirectoryCreationThread(home_dir, project_name)
#         self.creation_thread.progress.connect(self.update_progress)
#         self.creation_thread.finished.connect(self.creation_finished)
#         self.creation_thread.start()
    
#     def update_progress(self, value, message):
#         """Update progress bar and status"""
#         self.progress_bar.setValue(value)
#         self.status_text.append(message)
        
#         # Auto-scroll to bottom
#         cursor = self.status_text.textCursor()
#         cursor.movePosition(cursor.End)
#         self.status_text.setTextCursor(cursor)
    
#     def creation_finished(self, success, message):
#         """Handle creation completion"""
#         if success:
#             self.project_dir = message
#             self.status_text.append("\n" + "="*50)
#             self.status_text.append("✓ SUCCESS: Project structure created!")
#             self.status_text.append(f"Location: {message}")
#             self.status_text.append("="*50)
            
#             self.open_btn.setEnabled(True)
            
#             QMessageBox.information(
#                 self,
#                 "Success",
#                 f"Project directory structure created successfully!\n\nLocation:\n{message}"
#             )
#         else:
#             self.status_text.append("\n" + "="*50)
#             self.status_text.append(f"✗ ERROR: {message}")
#             self.status_text.append("="*50)
            
#             self.create_btn.setEnabled(True)
            
#             QMessageBox.critical(
#                 self,
#                 "Error",
#                 f"Failed to create directory structure:\n\n{message}"
#             )
    
#     def open_project_folder(self):
#         """Open project folder in file explorer"""
#         if self.project_dir and Path(self.project_dir).exists():
#             import platform
#             import subprocess
            
#             system = platform.system()
            
#             try:
#                 if system == "Windows":
#                     os.startfile(self.project_dir)
#                 elif system == "Darwin":  # macOS
#                     subprocess.run(["open", self.project_dir])
#                 else:  # Linux
#                     subprocess.run(["xdg-open", self.project_dir])
#             except Exception as e:
#                 QMessageBox.warning(
#                     self,
#                     "Error",
#                     f"Could not open folder:\n{e}"
#                 )


# def main():
#     """Main entry point"""
#     app = QApplication(sys.argv)
    
#     # Set application style
#     app.setStyle('Fusion')
    
#     # Create and show window
#     window = ProjectSetupGUI()
#     window.show()
    
#     sys.exit(app.exec_())


# if __name__ == "__main__":
#     main()




# """
# FDS Project Setup GUI
# Interactive PyQt5 interface for creating FDS project directory structure
# """

# import os
# import sys
# from pathlib import Path
# from PyQt5.QtWidgets import (
#     QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
#     QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
#     QGroupBox, QMessageBox, QProgressBar, QTreeWidget, QTreeWidgetItem
# )
# from PyQt5.QtCore import Qt, QThread, pyqtSignal
# from PyQt5.QtGui import QFont, QIcon


# class DirectoryCreationThread(QThread):
#     """Thread for creating directory structure"""
#     progress = pyqtSignal(int, str)
#     finished = pyqtSignal(bool, str)
    
#     def __init__(self, base_path, project_name):
#         super().__init__()
#         self.base_path = base_path
#         self.project_name = project_name
#         self.project_dir = Path(base_path) / project_name
    
#     def run(self):
#         """Create directory structure"""
#         try:
#             # Define directory structure
#             directories = [
#                 "fds_inputs/020",
#                 "fds_inputs/030",
#                 "fds_inputs/100",
#                 "fds_outputs",
#                 "fdb_files",
#                 "ascii_files",
#                 "evc_files",
#                 "fed_results",
#                 "logs"
#             ]
            
#             total_steps = len(directories) + 2  # +2 for project dir and batch file
#             current_step = 0
            
#             # Create project root directory
#             self.progress.emit(int((current_step / total_steps) * 100), 
#                              f"Creating project directory: {self.project_name}")
#             self.project_dir.mkdir(parents=True, exist_ok=True)
#             current_step += 1
            
#             # Create subdirectories
#             for dir_path in directories:
#                 self.progress.emit(int((current_step / total_steps) * 100),
#                                  f"Creating: {dir_path}")
#                 (self.project_dir / dir_path).mkdir(parents=True, exist_ok=True)
#                 current_step += 1
            
#             # Create batch script placeholder
#             self.progress.emit(int((current_step / total_steps) * 100),
#                              "Creating batch script template")
#             batch_file = self.project_dir / "run_all_simulations.bat"
#             with open(batch_file, 'w') as f:
#                 f.write("@echo off\n")
#                 f.write("REM FDS Batch Execution Script\n")
#                 f.write("REM This file will be populated when FDS input files are generated\n")
#                 f.write("echo No simulations configured yet\n")
#                 f.write("pause\n")
#             current_step += 1
            
#             # Complete
#             self.progress.emit(100, "Directory structure created successfully!")
#             self.finished.emit(True, str(self.project_dir))
            
#         except Exception as e:
#             self.finished.emit(False, str(e))


# class ProjectSetupGUI(QMainWindow):
#     """Main GUI window for FDS project setup"""
    
#     def __init__(self):
#         super().__init__()
#         self.project_dir = None
#         self.init_ui()
    
#     def init_ui(self):
#         """Initialize user interface"""
#         self.setWindowTitle("FDS Project Setup - Directory Structure Creator")
#         self.setGeometry(100, 100, 900, 700)
        
#         # Central widget
#         central_widget = QWidget()
#         self.setCentralWidget(central_widget)
        
#         # Main layout
#         main_layout = QVBoxLayout()
#         central_widget.setLayout(main_layout)
        
#         # Title
#         title_label = QLabel("FDS Project Directory Structure Setup")
#         title_font = QFont()
#         title_font.setPointSize(16)
#         title_font.setBold(True)
#         title_label.setFont(title_font)
#         title_label.setAlignment(Qt.AlignCenter)
#         main_layout.addWidget(title_label)
        
#         # Subtitle
#         subtitle_label = QLabel("Create organized directory structure for FDS simulations and QRA analysis")
#         subtitle_label.setAlignment(Qt.AlignCenter)
#         subtitle_label.setStyleSheet("color: gray; margin-bottom: 20px;")
#         main_layout.addWidget(subtitle_label)
        
#         # Project Configuration Group
#         config_group = QGroupBox("Project Configuration")
#         config_layout = QVBoxLayout()
#         config_group.setLayout(config_layout)
        
#         # Project Name
#         name_layout = QHBoxLayout()
#         name_label = QLabel("Project Name:")
#         name_label.setMinimumWidth(120)
#         self.project_name_input = QLineEdit()
#         self.project_name_input.setPlaceholderText("Enter project name (e.g., TunnelFireQRA_2026)")
#         self.project_name_input.textChanged.connect(self.update_preview)
#         name_layout.addWidget(name_label)
#         name_layout.addWidget(self.project_name_input)
#         config_layout.addLayout(name_layout)
        
#         # Home Directory
#         dir_layout = QHBoxLayout()
#         dir_label = QLabel("Home Directory:")
#         dir_label.setMinimumWidth(120)
#         self.home_dir_input = QLineEdit()
#         self.home_dir_input.setPlaceholderText("Select home directory location")
#         self.home_dir_input.textChanged.connect(self.update_preview)
#         browse_btn = QPushButton("Browse...")
#         browse_btn.clicked.connect(self.browse_directory)
#         dir_layout.addWidget(dir_label)
#         dir_layout.addWidget(self.home_dir_input)
#         dir_layout.addWidget(browse_btn)
#         config_layout.addLayout(dir_layout)
        
#         # Full Path Display
#         path_layout = QHBoxLayout()
#         path_label = QLabel("Full Project Path:")
#         path_label.setMinimumWidth(120)
#         self.full_path_display = QLineEdit()
#         self.full_path_display.setReadOnly(True)
#         self.full_path_display.setStyleSheet("background-color: #f0f0f0;")
#         path_layout.addWidget(path_label)
#         path_layout.addWidget(self.full_path_display)
#         config_layout.addLayout(path_layout)
        
#         main_layout.addWidget(config_group)
        
#         # Directory Structure Preview Group
#         preview_group = QGroupBox("Directory Structure Preview")
#         preview_layout = QVBoxLayout()
#         preview_group.setLayout(preview_layout)
        
#         self.tree_widget = QTreeWidget()
#         self.tree_widget.setHeaderLabel("Directory Structure")
#         self.tree_widget.setMinimumHeight(250)
#         preview_layout.addWidget(self.tree_widget)
        
#         main_layout.addWidget(preview_group)
        
#         # Progress Group
#         progress_group = QGroupBox("Creation Progress")
#         progress_layout = QVBoxLayout()
#         progress_group.setLayout(progress_layout)
        
#         self.progress_bar = QProgressBar()
#         self.progress_bar.setValue(0)
#         progress_layout.addWidget(self.progress_bar)
        
#         self.status_text = QTextEdit()
#         self.status_text.setReadOnly(True)
#         self.status_text.setMaximumHeight(100)
#         self.status_text.setPlaceholderText("Status messages will appear here...")
#         progress_layout.addWidget(self.status_text)
        
#         main_layout.addWidget(progress_group)
        
#         # Buttons
#         button_layout = QHBoxLayout()
        
#         self.create_btn = QPushButton("Create Project Structure")
#         self.create_btn.setMinimumHeight(40)
#         self.create_btn.setStyleSheet("""
#             QPushButton {
#                 background-color: #4CAF50;
#                 color: white;
#                 font-size: 14px;
#                 font-weight: bold;
#                 border-radius: 5px;
#             }
#             QPushButton:hover {
#                 background-color: #45a049;
#             }
#             QPushButton:disabled {
#                 background-color: #cccccc;
#                 color: #666666;
#             }
#         """)
#         self.create_btn.clicked.connect(self.create_structure)
#         self.create_btn.setEnabled(False)
        
#         self.open_btn = QPushButton("Open Project Folder")
#         self.open_btn.setMinimumHeight(40)
#         self.open_btn.setEnabled(False)
#         self.open_btn.clicked.connect(self.open_project_folder)
        
#         self.close_btn = QPushButton("Close")
#         self.close_btn.setMinimumHeight(40)
#         self.close_btn.clicked.connect(self.close)
        
#         button_layout.addWidget(self.create_btn)
#         button_layout.addWidget(self.open_btn)
#         button_layout.addWidget(self.close_btn)
        
#         main_layout.addLayout(button_layout)
        
#         # Initialize preview
#         self.update_preview()
    
#     def browse_directory(self):
#         """Open directory browser dialog"""
#         directory = QFileDialog.getExistingDirectory(
#             self,
#             "Select Home Directory",
#             str(Path.home()),
#             QFileDialog.ShowDirsOnly
#         )
        
#         if directory:
#             self.home_dir_input.setText(directory)
    
#     def update_preview(self):
#         """Update directory structure preview"""
#         project_name = self.project_name_input.text().strip()
#         home_dir = self.home_dir_input.text().strip()
        
#         # Update full path display
#         if project_name and home_dir:
#             full_path = str(Path(home_dir) / project_name)
#             self.full_path_display.setText(full_path)
#             self.create_btn.setEnabled(True)
#         else:
#             self.full_path_display.setText("")
#             self.create_btn.setEnabled(False)
        
#         # Update tree widget
#         self.tree_widget.clear()
        
#         if project_name:
#             # Root item
#             root = QTreeWidgetItem(self.tree_widget)
#             root.setText(0, f"{project_name}/")
#             root.setExpanded(True)
            
#             # FDS Inputs
#             fds_inputs = QTreeWidgetItem(root)
#             fds_inputs.setText(0, "fds_inputs/  # Generated FDS input files")
#             fds_inputs.setExpanded(True)
            
#             hrr_020 = QTreeWidgetItem(fds_inputs)
#             hrr_020.setText(0, "020/  # 20 MW scenarios")
            
#             hrr_030 = QTreeWidgetItem(fds_inputs)
#             hrr_030.setText(0, "030/  # 30 MW scenarios")
            
#             hrr_100 = QTreeWidgetItem(fds_inputs)
#             hrr_100.setText(0, "100/  # 100 MW scenarios")
            
#             # FDS Outputs
#             fds_outputs = QTreeWidgetItem(root)
#             fds_outputs.setText(0, "fds_outputs/  # FDS simulation outputs (.smv, .out, .sf, etc.)")
            
#             # FDB Files
#             fdb_files = QTreeWidgetItem(root)
#             fdb_files.setText(0, "fdb_files/  # Converted FDB files for EVC")

#             # ASCII Files
#             ascii_files = QTreeWidgetItem(root)
#             ascii_files.setText(0, "ascii_files/  # CSV/ASCII exports from fds2ascii")

#             # EVC Files
#             evc_files = QTreeWidgetItem(root)
#             evc_files.setText(0, "evc_files/  # Generated EVC input files for FED analysis")

#             # FED Results
#             fed_results = QTreeWidgetItem(root)
#             fed_results.setText(0, "fed_results/  # FED analysis results and reports")

#             # Logs
#             logs = QTreeWidgetItem(root)
#             logs.setText(0, "logs/  # Workflow logs")
            
#             # Batch script
#             batch = QTreeWidgetItem(root)
#             batch.setText(0, "run_all_simulations.bat  # Batch script for manual execution")
    
#     def create_structure(self):
#         """Create directory structure"""
#         project_name = self.project_name_input.text().strip()
#         home_dir = self.home_dir_input.text().strip()
        
#         if not project_name or not home_dir:
#             QMessageBox.warning(
#                 self,
#                 "Missing Information",
#                 "Please enter both project name and home directory."
#             )
#             return
        
#         # Check if directory already exists
#         project_path = Path(home_dir) / project_name
#         if project_path.exists():
#             reply = QMessageBox.question(
#                 self,
#                 "Directory Exists",
#                 f"The directory '{project_path}' already exists.\n\nDo you want to continue anyway?",
#                 QMessageBox.Yes | QMessageBox.No,
#                 QMessageBox.No
#             )
            
#             if reply == QMessageBox.No:
#                 return
        
#         # Disable create button during creation
#         self.create_btn.setEnabled(False)
#         self.status_text.clear()
#         self.progress_bar.setValue(0)
        
#         # Create thread for directory creation
#         self.creation_thread = DirectoryCreationThread(home_dir, project_name)
#         self.creation_thread.progress.connect(self.update_progress)
#         self.creation_thread.finished.connect(self.creation_finished)
#         self.creation_thread.start()
    
#     def update_progress(self, value, message):
#         """Update progress bar and status"""
#         self.progress_bar.setValue(value)
#         self.status_text.append(message)
        
#         # Auto-scroll to bottom
#         cursor = self.status_text.textCursor()
#         cursor.movePosition(cursor.End)
#         self.status_text.setTextCursor(cursor)
    
#     def creation_finished(self, success, message):
#         """Handle creation completion"""
#         if success:
#             self.project_dir = message
#             self.status_text.append("\n" + "="*50)
#             self.status_text.append("✓ SUCCESS: Project structure created!")
#             self.status_text.append(f"Location: {message}")
#             self.status_text.append("="*50)
            
#             self.open_btn.setEnabled(True)
            
#             QMessageBox.information(
#                 self,
#                 "Success",
#                 f"Project directory structure created successfully!\n\nLocation:\n{message}"
#             )
#         else:
#             self.status_text.append("\n" + "="*50)
#             self.status_text.append(f"✗ ERROR: {message}")
#             self.status_text.append("="*50)
            
#             self.create_btn.setEnabled(True)
            
#             QMessageBox.critical(
#                 self,
#                 "Error",
#                 f"Failed to create directory structure:\n\n{message}"
#             )
    
#     def open_project_folder(self):
#         """Open project folder in file explorer"""
#         if self.project_dir and Path(self.project_dir).exists():
#             import platform
#             import subprocess
            
#             system = platform.system()
            
#             try:
#                 if system == "Windows":
#                     os.startfile(self.project_dir)
#                 elif system == "Darwin":  # macOS
#                     subprocess.run(["open", self.project_dir])
#                 else:  # Linux
#                     subprocess.run(["xdg-open", self.project_dir])
#             except Exception as e:
#                 QMessageBox.warning(
#                     self,
#                     "Error",
#                     f"Could not open folder:\n{e}"
#                 )


# def main():
#     """Main entry point"""
#     app = QApplication(sys.argv)
    
#     # Set application style
#     app.setStyle('Fusion')
    
#     # Create and show window
#     window = ProjectSetupGUI()
#     window.show()
    
#     sys.exit(app.exec_())


# if __name__ == "__main__":
#     main()

# # """
# # FDS Project Setup GUI
# # Interactive PyQt5 interface for creating FDS project directory structure
# # """

# # import os
# # import sys
# # from pathlib import Path
# # from PyQt5.QtWidgets import (
# #     QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
# #     QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
# #     QGroupBox, QMessageBox, QProgressBar, QTreeWidget, QTreeWidgetItem
# # )
# # from PyQt5.QtCore import Qt, QThread, pyqtSignal
# # from PyQt5.QtGui import QFont, QIcon


# # class DirectoryCreationThread(QThread):
# #     """Thread for creating directory structure"""
# #     progress = pyqtSignal(int, str)
# #     finished = pyqtSignal(bool, str)
    
# #     def __init__(self, base_path, project_name):
# #         super().__init__()
# #         self.base_path = base_path
# #         self.project_name = project_name
# #         self.project_dir = Path(base_path) / project_name
    
# #     def run(self):
# #         """Create directory structure"""
# #         try:
# #             # Define directory structure
# #             directories = [
# #                 "fds_inputs/020",
# #                 "fds_inputs/030",
# #                 "fds_inputs/100",
# #                 "fds_outputs",
# #                 "fdb_files",
# #                 "logs"
# #             ]
            
# #             total_steps = len(directories) + 2  # +2 for project dir and batch file
# #             current_step = 0
            
# #             # Create project root directory
# #             self.progress.emit(int((current_step / total_steps) * 100), 
# #                              f"Creating project directory: {self.project_name}")
# #             self.project_dir.mkdir(parents=True, exist_ok=True)
# #             current_step += 1
            
# #             # Create subdirectories
# #             for dir_path in directories:
# #                 self.progress.emit(int((current_step / total_steps) * 100),
# #                                  f"Creating: {dir_path}")
# #                 (self.project_dir / dir_path).mkdir(parents=True, exist_ok=True)
# #                 current_step += 1
            
# #             # Create batch script placeholder
# #             self.progress.emit(int((current_step / total_steps) * 100),
# #                              "Creating batch script template")
# #             batch_file = self.project_dir / "run_all_simulations.bat"
# #             with open(batch_file, 'w') as f:
# #                 f.write("@echo off\n")
# #                 f.write("REM FDS Batch Execution Script\n")
# #                 f.write("REM This file will be populated when FDS input files are generated\n")
# #                 f.write("echo No simulations configured yet\n")
# #                 f.write("pause\n")
# #             current_step += 1
            
# #             # Complete
# #             self.progress.emit(100, "Directory structure created successfully!")
# #             self.finished.emit(True, str(self.project_dir))
            
# #         except Exception as e:
# #             self.finished.emit(False, str(e))


# # class ProjectSetupGUI(QMainWindow):
# #     """Main GUI window for FDS project setup"""
    
# #     def __init__(self):
# #         super().__init__()
# #         self.project_dir = None
# #         self.init_ui()
    
# #     def init_ui(self):
# #         """Initialize user interface"""
# #         self.setWindowTitle("FDS Project Setup - Directory Structure Creator")
# #         self.setGeometry(100, 100, 900, 700)
        
# #         # Central widget
# #         central_widget = QWidget()
# #         self.setCentralWidget(central_widget)
        
# #         # Main layout
# #         main_layout = QVBoxLayout()
# #         central_widget.setLayout(main_layout)
        
# #         # Title
# #         title_label = QLabel("FDS Project Directory Structure Setup")
# #         title_font = QFont()
# #         title_font.setPointSize(16)
# #         title_font.setBold(True)
# #         title_label.setFont(title_font)
# #         title_label.setAlignment(Qt.AlignCenter)
# #         main_layout.addWidget(title_label)
        
# #         # Subtitle
# #         subtitle_label = QLabel("Create organized directory structure for FDS simulations and QRA analysis")
# #         subtitle_label.setAlignment(Qt.AlignCenter)
# #         subtitle_label.setStyleSheet("color: gray; margin-bottom: 20px;")
# #         main_layout.addWidget(subtitle_label)
        
# #         # Project Configuration Group
# #         config_group = QGroupBox("Project Configuration")
# #         config_layout = QVBoxLayout()
# #         config_group.setLayout(config_layout)
        
# #         # Project Name
# #         name_layout = QHBoxLayout()
# #         name_label = QLabel("Project Name:")
# #         name_label.setMinimumWidth(120)
# #         self.project_name_input = QLineEdit()
# #         self.project_name_input.setPlaceholderText("Enter project name (e.g., TunnelFireQRA_2026)")
# #         self.project_name_input.textChanged.connect(self.update_preview)
# #         name_layout.addWidget(name_label)
# #         name_layout.addWidget(self.project_name_input)
# #         config_layout.addLayout(name_layout)
        
# #         # Home Directory
# #         dir_layout = QHBoxLayout()
# #         dir_label = QLabel("Home Directory:")
# #         dir_label.setMinimumWidth(120)
# #         self.home_dir_input = QLineEdit()
# #         self.home_dir_input.setPlaceholderText("Select home directory location")
# #         self.home_dir_input.textChanged.connect(self.update_preview)
# #         browse_btn = QPushButton("Browse...")
# #         browse_btn.clicked.connect(self.browse_directory)
# #         dir_layout.addWidget(dir_label)
# #         dir_layout.addWidget(self.home_dir_input)
# #         dir_layout.addWidget(browse_btn)
# #         config_layout.addLayout(dir_layout)
        
# #         # Full Path Display
# #         path_layout = QHBoxLayout()
# #         path_label = QLabel("Full Project Path:")
# #         path_label.setMinimumWidth(120)
# #         self.full_path_display = QLineEdit()
# #         self.full_path_display.setReadOnly(True)
# #         self.full_path_display.setStyleSheet("background-color: #f0f0f0;")
# #         path_layout.addWidget(path_label)
# #         path_layout.addWidget(self.full_path_display)
# #         config_layout.addLayout(path_layout)
        
# #         main_layout.addWidget(config_group)
        
# #         # Directory Structure Preview Group
# #         preview_group = QGroupBox("Directory Structure Preview")
# #         preview_layout = QVBoxLayout()
# #         preview_group.setLayout(preview_layout)
        
# #         self.tree_widget = QTreeWidget()
# #         self.tree_widget.setHeaderLabel("Directory Structure")
# #         self.tree_widget.setMinimumHeight(250)
# #         preview_layout.addWidget(self.tree_widget)
        
# #         main_layout.addWidget(preview_group)
        
# #         # Progress Group
# #         progress_group = QGroupBox("Creation Progress")
# #         progress_layout = QVBoxLayout()
# #         progress_group.setLayout(progress_layout)
        
# #         self.progress_bar = QProgressBar()
# #         self.progress_bar.setValue(0)
# #         progress_layout.addWidget(self.progress_bar)
        
# #         self.status_text = QTextEdit()
# #         self.status_text.setReadOnly(True)
# #         self.status_text.setMaximumHeight(100)
# #         self.status_text.setPlaceholderText("Status messages will appear here...")
# #         progress_layout.addWidget(self.status_text)
        
# #         main_layout.addWidget(progress_group)
        
# #         # Buttons
# #         button_layout = QHBoxLayout()
        
# #         self.create_btn = QPushButton("Create Project Structure")
# #         self.create_btn.setMinimumHeight(40)
# #         self.create_btn.setStyleSheet("""
# #             QPushButton {
# #                 background-color: #4CAF50;
# #                 color: white;
# #                 font-size: 14px;
# #                 font-weight: bold;
# #                 border-radius: 5px;
# #             }
# #             QPushButton:hover {
# #                 background-color: #45a049;
# #             }
# #             QPushButton:disabled {
# #                 background-color: #cccccc;
# #                 color: #666666;
# #             }
# #         """)
# #         self.create_btn.clicked.connect(self.create_structure)
# #         self.create_btn.setEnabled(False)
        
# #         self.open_btn = QPushButton("Open Project Folder")
# #         self.open_btn.setMinimumHeight(40)
# #         self.open_btn.setEnabled(False)
# #         self.open_btn.clicked.connect(self.open_project_folder)
        
# #         self.close_btn = QPushButton("Close")
# #         self.close_btn.setMinimumHeight(40)
# #         self.close_btn.clicked.connect(self.close)
        
# #         button_layout.addWidget(self.create_btn)
# #         button_layout.addWidget(self.open_btn)
# #         button_layout.addWidget(self.close_btn)
        
# #         main_layout.addLayout(button_layout)
        
# #         # Initialize preview
# #         self.update_preview()
    
# #     def browse_directory(self):
# #         """Open directory browser dialog"""
# #         directory = QFileDialog.getExistingDirectory(
# #             self,
# #             "Select Home Directory",
# #             str(Path.home()),
# #             QFileDialog.ShowDirsOnly
# #         )
        
# #         if directory:
# #             self.home_dir_input.setText(directory)
    
# #     def update_preview(self):
# #         """Update directory structure preview"""
# #         project_name = self.project_name_input.text().strip()
# #         home_dir = self.home_dir_input.text().strip()
        
# #         # Update full path display
# #         if project_name and home_dir:
# #             full_path = str(Path(home_dir) / project_name)
# #             self.full_path_display.setText(full_path)
# #             self.create_btn.setEnabled(True)
# #         else:
# #             self.full_path_display.setText("")
# #             self.create_btn.setEnabled(False)
        
# #         # Update tree widget
# #         self.tree_widget.clear()
        
# #         if project_name:
# #             # Root item
# #             root = QTreeWidgetItem(self.tree_widget)
# #             root.setText(0, f"{project_name}/")
# #             root.setExpanded(True)
            
# #             # FDS Inputs
# #             fds_inputs = QTreeWidgetItem(root)
# #             fds_inputs.setText(0, "fds_inputs/  # Generated FDS input files")
# #             fds_inputs.setExpanded(True)
            
# #             hrr_020 = QTreeWidgetItem(fds_inputs)
# #             hrr_020.setText(0, "020/  # 20 MW scenarios")
            
# #             hrr_030 = QTreeWidgetItem(fds_inputs)
# #             hrr_030.setText(0, "030/  # 30 MW scenarios")
            
# #             hrr_100 = QTreeWidgetItem(fds_inputs)
# #             hrr_100.setText(0, "100/  # 100 MW scenarios")
            
# #             # FDS Outputs
# #             fds_outputs = QTreeWidgetItem(root)
# #             fds_outputs.setText(0, "fds_outputs/  # FDS simulation outputs (.smv, .out, etc.)")
            
# #             # FDB Files
# #             fdb_files = QTreeWidgetItem(root)
# #             fdb_files.setText(0, "fdb_files/  # Converted FDB files for EVC")
            
# #             # Logs
# #             logs = QTreeWidgetItem(root)
# #             logs.setText(0, "logs/  # Workflow logs")
            
# #             # Batch script
# #             batch = QTreeWidgetItem(root)
# #             batch.setText(0, "run_all_simulations.bat  # Batch script for manual execution")
    
# #     def create_structure(self):
# #         """Create directory structure"""
# #         project_name = self.project_name_input.text().strip()
# #         home_dir = self.home_dir_input.text().strip()
        
# #         if not project_name or not home_dir:
# #             QMessageBox.warning(
# #                 self,
# #                 "Missing Information",
# #                 "Please enter both project name and home directory."
# #             )
# #             return
        
# #         # Check if directory already exists
# #         project_path = Path(home_dir) / project_name
# #         if project_path.exists():
# #             reply = QMessageBox.question(
# #                 self,
# #                 "Directory Exists",
# #                 f"The directory '{project_path}' already exists.\n\nDo you want to continue anyway?",
# #                 QMessageBox.Yes | QMessageBox.No,
# #                 QMessageBox.No
# #             )
            
# #             if reply == QMessageBox.No:
# #                 return
        
# #         # Disable create button during creation
# #         self.create_btn.setEnabled(False)
# #         self.status_text.clear()
# #         self.progress_bar.setValue(0)
        
# #         # Create thread for directory creation
# #         self.creation_thread = DirectoryCreationThread(home_dir, project_name)
# #         self.creation_thread.progress.connect(self.update_progress)
# #         self.creation_thread.finished.connect(self.creation_finished)
# #         self.creation_thread.start()
    
# #     def update_progress(self, value, message):
# #         """Update progress bar and status"""
# #         self.progress_bar.setValue(value)
# #         self.status_text.append(message)
        
# #         # Auto-scroll to bottom
# #         cursor = self.status_text.textCursor()
# #         cursor.movePosition(cursor.End)
# #         self.status_text.setTextCursor(cursor)
    
# #     def creation_finished(self, success, message):
# #         """Handle creation completion"""
# #         if success:
# #             self.project_dir = message
# #             self.status_text.append("\n" + "="*50)
# #             self.status_text.append("✓ SUCCESS: Project structure created!")
# #             self.status_text.append(f"Location: {message}")
# #             self.status_text.append("="*50)
            
# #             self.open_btn.setEnabled(True)
            
# #             QMessageBox.information(
# #                 self,
# #                 "Success",
# #                 f"Project directory structure created successfully!\n\nLocation:\n{message}"
# #             )
# #         else:
# #             self.status_text.append("\n" + "="*50)
# #             self.status_text.append(f"✗ ERROR: {message}")
# #             self.status_text.append("="*50)
            
# #             self.create_btn.setEnabled(True)
            
# #             QMessageBox.critical(
# #                 self,
# #                 "Error",
# #                 f"Failed to create directory structure:\n\n{message}"
# #             )
    
# #     def open_project_folder(self):
# #         """Open project folder in file explorer"""
# #         if self.project_dir and Path(self.project_dir).exists():
# #             import platform
# #             import subprocess
            
# #             system = platform.system()
            
# #             try:
# #                 if system == "Windows":
# #                     os.startfile(self.project_dir)
# #                 elif system == "Darwin":  # macOS
# #                     subprocess.run(["open", self.project_dir])
# #                 else:  # Linux
# #                     subprocess.run(["xdg-open", self.project_dir])
# #             except Exception as e:
# #                 QMessageBox.warning(
# #                     self,
# #                     "Error",
# #                     f"Could not open folder:\n{e}"
# #                 )


# # def main():
# #     """Main entry point"""
# #     app = QApplication(sys.argv)
    
# #     # Set application style
# #     app.setStyle('Fusion')
    
# #     # Create and show window
# #     window = ProjectSetupGUI()
# #     window.show()
    
# #     sys.exit(app.exec_())


# # if __name__ == "__main__":
# #     main()
