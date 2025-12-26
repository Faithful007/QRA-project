from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox,
    QRadioButton, QButtonGroup, QCheckBox, QComboBox
)
from PyQt6.QtCore import Qt
from src.database.data_manager import DataManager
from src.language_manager import get_language_manager

class SimulationSettingsTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.language_manager = get_language_manager()
        
        # Connect to language change signal
        self.language_manager.language_changed.connect(self._on_language_changed)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Top section: Program settings
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._create_program_settings_group(), 1)
        top_layout.addWidget(self._create_fire_scenario_group(), 1)
        main_layout.addLayout(top_layout)
        
        # Middle section: Fire point configuration
        main_layout.addWidget(self._create_fire_point_group())
        
        # FDS settings
        main_layout.addWidget(self._create_fds_settings_group())
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        lm = self.language_manager
        self.simulation_btn = QPushButton(lm.translate("Simulation"))
        self.result_btn = QPushButton(lm.translate("Result Analysis"))
        self.print_btn = QPushButton(lm.translate("Print"))
        self.save_btn = QPushButton(lm.translate("Save"))
        self.simulation_btn.clicked.connect(self.save_data)
        button_layout.addWidget(self.simulation_btn)
        button_layout.addWidget(self.result_btn)
        button_layout.addWidget(self.print_btn)
        button_layout.addWidget(self.save_btn)
        main_layout.addLayout(button_layout)
        
        main_layout.addStretch(1)
        self.load_data()

    def _create_program_settings_group(self):
        lm = self.language_manager
        self.program_settings_group = QGroupBox(lm.translate("Program Settings"))
        layout = QGridLayout(self.program_settings_group)
        
        # Project Name
        self.project_name_label = QLabel(lm.translate("Project Name:"))
        layout.addWidget(self.project_name_label, 0, 0)
        self.project_name_input = QLineEdit("QRA_Simulation_001")
        self.project_name_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.project_name_input, 0, 1)
        
        # Time Interval
        self.time_interval_label = QLabel(lm.translate("Time Interval:"))
        layout.addWidget(self.time_interval_label, 1, 0)
        self.time_interval_input = QLineEdit("5.0")
        layout.addWidget(self.time_interval_input, 1, 1)
        
        # Total Simulation Time
        self.total_sim_time_label = QLabel(lm.translate("Total Simulation Time:"))
        layout.addWidget(self.total_sim_time_label, 2, 0)
        self.total_time_input = QLineEdit("3600.0")
        layout.addWidget(self.total_time_input, 2, 1)
        
        return self.program_settings_group

    def _create_fire_scenario_group(self):
        lm = self.language_manager
        self.fire_scenario_group = QGroupBox(lm.translate("Fire Scenario"))
        layout = QGridLayout(self.fire_scenario_group)
        
        self.tunnel_type_label = QLabel(lm.translate("Tunnel Type:"))
        layout.addWidget(self.tunnel_type_label, 0, 0)
        self.tunnel_type_combo = QComboBox()
        self.tunnel_type_combo.addItems([lm.translate("One-way"), lm.translate("Two-way"), lm.translate("Mixed")])
        layout.addWidget(self.tunnel_type_combo, 0, 1)
        
        self.scenario_number_label = QLabel(lm.translate("Scenario Number:"))
        layout.addWidget(self.scenario_number_label, 1, 0)
        self.scenario_number = QLineEdit("1")
        layout.addWidget(self.scenario_number, 1, 1)
        
        return self.fire_scenario_group

    def _create_fire_point_group(self):
        lm = self.language_manager
        self.fire_point_group = QGroupBox(lm.translate("Fire Point and Waiting Area"))
        layout = QVBoxLayout(self.fire_point_group)
        
        # Fire Point List Table
        self.fire_point_table = QTableWidget(0, 4)
        self.fire_point_table.setHorizontalHeaderLabels([lm.translate("Name"), 
                                                         lm.translate("Location X (m)"), 
                                                         lm.translate("Location Y (m)"), 
                                                         lm.translate("Location Z (m)")])
        self.fire_point_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fire_point_table.cellChanged.connect(self.save_data)
        layout.addWidget(self.fire_point_table)
        
        # Buttons for managing fire points
        button_layout = QHBoxLayout()
        self.add_fire_point_btn = QPushButton(lm.translate("Add Fire Point"))
        self.remove_fire_point_btn = QPushButton(lm.translate("Remove Selected"))
        button_layout.addWidget(self.add_fire_point_btn)
        button_layout.addWidget(self.remove_fire_point_btn)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)
        
        # Connect buttons to methods
        self.add_fire_point_btn.clicked.connect(self._add_fire_point)
        self.remove_fire_point_btn.clicked.connect(self._remove_fire_point)
        
        return self.fire_point_group

    def _create_fds_settings_group(self):
        lm = self.language_manager
        self.fds_settings_group = QGroupBox(lm.translate("FDS File and Save Settings"))
        layout = QGridLayout(self.fds_settings_group)
        
        self.fds_template_label = QLabel(lm.translate("FDS Template File:"))
        layout.addWidget(self.fds_template_label, 0, 0)
        self.fds_template_path = QLineEdit()
        layout.addWidget(self.fds_template_path, 0, 1)
        self.browse_btn = QPushButton(lm.translate("Browse"))
        layout.addWidget(self.browse_btn, 0, 2)
        
        return self.fds_settings_group

    def _add_fire_point(self):
        row_count = self.fire_point_table.rowCount()
        self.fire_point_table.insertRow(row_count)
        
        # Set default values
        self.fire_point_table.setItem(row_count, 0, QTableWidgetItem(f"FP_{row_count + 1}"))
        self.fire_point_table.setItem(row_count, 1, QTableWidgetItem("0.0"))
        self.fire_point_table.setItem(row_count, 2, QTableWidgetItem("0.0"))
        self.fire_point_table.setItem(row_count, 3, QTableWidgetItem("0.0"))
        self.save_data()

    def _remove_fire_point(self):
        selected_rows = self.fire_point_table.selectionModel().selectedRows()
        for row in sorted(selected_rows, reverse=True):
            self.fire_point_table.removeRow(row.row())
        self.save_data()

    def get_data(self):
        """Extracts data from the UI elements with safe parsing."""
        try:
            def f(text, default=0.0):
                t = text.strip()
                if t == "":
                    return default
                return float(t)

            def i(text, default=0):
                t = text.strip()
                if t == "":
                    return default
                return int(t)

            def item_text(row, col, default=""):
                item = self.fire_point_table.item(row, col)
                return item.text() if item and item.text() is not None else default

            data = {
                "project_name": self.project_name_input.text(),
                "time_interval": f(self.time_interval_input.text()),
                "total_simulation_time": f(self.total_time_input.text()),
                "fire_points": [
                    {
                        "name": item_text(r, 0, f"FP_{r+1}"),
                        "location_x": f(item_text(r, 1, "0")),
                        "location_y": f(item_text(r, 2, "0")),
                        "location_z": f(item_text(r, 3, "0")),
                    }
                    for r in range(self.fire_point_table.rowCount())
                ]
            }
            return data
        except ValueError as e:
            QMessageBox.critical(self, "Input Error", f"Invalid input value. Please check all fields. Error: {e}")
            return None

    def set_data(self, simulation_settings_config, fire_points):
        """Populates the UI elements with data from the database models."""
        self.project_name_input.setText(simulation_settings_config.project_name)
        self.time_interval_input.setText(str(simulation_settings_config.time_interval))
        self.total_time_input.setText(str(simulation_settings_config.total_simulation_time))
        
        # Populate fire points table
        self.fire_point_table.setRowCount(0)
        for fp in fire_points:
            row_count = self.fire_point_table.rowCount()
            self.fire_point_table.insertRow(row_count)
            self.fire_point_table.setItem(row_count, 0, QTableWidgetItem(fp.name))
            self.fire_point_table.setItem(row_count, 1, QTableWidgetItem(str(fp.location_x)))
            self.fire_point_table.setItem(row_count, 2, QTableWidgetItem(str(fp.location_y)))
            self.fire_point_table.setItem(row_count, 3, QTableWidgetItem(str(fp.location_z)))

    def load_data(self):
        """Loads data from the database and populates the UI."""
        pass
            
    def save_data(self):
        """Extracts data from the UI and saves it to the database."""
        pass


    def get_data(self):
        """Extracts data from the UI elements with safe parsing."""
        try:
            def f(text, default=0.0):
                t = text.strip()
                if t == "":
                    return default
                return float(t)

            def i(text, default=0):
                t = text.strip()
                if t == "":
                    return default
                return int(t)

            def item_text(row, col, default=""):
                item = self.fire_point_table.item(row, col)
                return item.text() if item and item.text() is not None else default

            data = {
                "project_name": self.project_name_input.text(),
                "time_interval": f(self.time_interval_input.text()),
                "total_simulation_time": f(self.total_time_input.text()),
                "monitoring_point_count": i(self.monitoring_count_input.text()),
                "fire_points": [
                    {
                        "name": item_text(r, 0, f"FP_{r+1}"),
                        "location_x": f(item_text(r, 1, "0")),
                        "location_y": f(item_text(r, 2, "0")),
                        "location_z": f(item_text(r, 3, "0")),
                    }
                    for r in range(self.fire_point_table.rowCount())
                ]
            }
            return data
        except ValueError as e:
            QMessageBox.critical(self, "Input Error", f"Invalid input value. Please check all fields. Error: {e}")
            return None

    def set_data(self, simulation_settings_config, fire_points):
        """Populates the UI elements with data from the database models."""
        self.project_name_input.setText(simulation_settings_config.project_name)
        self.time_interval_input.setText(str(simulation_settings_config.time_interval))
        self.total_time_input.setText(str(simulation_settings_config.total_simulation_time))
        self.monitoring_count_input.setText(str(simulation_settings_config.monitoring_point_count))
        
        # Populate fire points table
        self.fire_point_table.setRowCount(0)
        for fp in fire_points:
            row_count = self.fire_point_table.rowCount()
            self.fire_point_table.insertRow(row_count)
            self.fire_point_table.setItem(row_count, 0, QTableWidgetItem(fp.name))
            self.fire_point_table.setItem(row_count, 1, QTableWidgetItem(str(fp.location_x)))
            self.fire_point_table.setItem(row_count, 2, QTableWidgetItem(str(fp.location_y)))
            self.fire_point_table.setItem(row_count, 3, QTableWidgetItem(str(fp.location_z)))

    def load_data(self):
        """Loads data from the database and populates the UI."""
        # config, fire_points = self.data_manager.load_simulation_data()
        # if config:
        #     self.set_data(config, fire_points)
        pass
            
    def save_data(self):
        """Extracts data from the UI and saves it to the database."""
        # data = self.get_data()
        # if data:
        #     self.data_manager.save_simulation_data(data)
        pass    
    def _on_language_changed(self, language_code: str):
        """Handle language change event."""
        lm = self.language_manager
        
        # Update group box titles
        if hasattr(self, 'program_settings_group'):
            self.program_settings_group.setTitle(lm.translate("Program Settings"))
        if hasattr(self, 'fire_scenario_group'):
            self.fire_scenario_group.setTitle(lm.translate("Fire Scenario"))
        if hasattr(self, 'fire_point_group'):
            self.fire_point_group.setTitle(lm.translate("Fire Point and Waiting Area"))
        if hasattr(self, 'fds_settings_group'):
            self.fds_settings_group.setTitle(lm.translate("FDS File and Save Settings"))
        
        # Update labels
        if hasattr(self, 'project_name_label'):
            self.project_name_label.setText(lm.translate("Project Name:"))
        if hasattr(self, 'time_interval_label'):
            self.time_interval_label.setText(lm.translate("Time Interval:"))
        if hasattr(self, 'total_sim_time_label'):
            self.total_sim_time_label.setText(lm.translate("Total Simulation Time:"))
        if hasattr(self, 'tunnel_type_label'):
            self.tunnel_type_label.setText(lm.translate("Tunnel Type:"))
        if hasattr(self, 'scenario_number_label'):
            self.scenario_number_label.setText(lm.translate("Scenario Number:"))
        if hasattr(self, 'fds_template_label'):
            self.fds_template_label.setText(lm.translate("FDS Template File:"))
        
        # Update buttons
        if hasattr(self, 'add_fire_point_btn'):
            self.add_fire_point_btn.setText(lm.translate("Add Fire Point"))
        if hasattr(self, 'simulation_btn'):
            self.simulation_btn.setText(lm.translate("Simulation"))
        if hasattr(self, 'result_btn'):
            self.result_btn.setText(lm.translate("Result Analysis"))
        if hasattr(self, 'print_btn'):
            self.print_btn.setText(lm.translate("Print"))
        if hasattr(self, 'save_btn'):
            self.save_btn.setText(lm.translate("Save"))
        if hasattr(self, 'browse_btn'):
            self.browse_btn.setText(lm.translate("Browse"))
        
        # Update fire type combo box items
        # Update fire point table headers
        if hasattr(self, 'fire_point_table'):
            self.fire_point_table.setHorizontalHeaderLabels([
                lm.translate("Name"),
                lm.translate("Location X (m)"),
                lm.translate("Location Y (m)"),
                lm.translate("Location Z (m)")
            ])