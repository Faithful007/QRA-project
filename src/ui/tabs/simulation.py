from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
from src.database.data_manager import DataManager

class SimulationSettingsTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.layout = QVBoxLayout(self)
        
        # 1. Program Settings Group
        self.layout.addWidget(self._create_program_settings_group())
        
        # 2. Fire Point Configuration Group
        self.layout.addWidget(self._create_fire_point_group())
        
        # 3. Monitoring Points Group (Simplified)
        self.layout.addWidget(self._create_monitoring_group())
        
        self.layout.addStretch(1)
        
        self.load_data()

    def _create_program_settings_group(self):
        group = QGroupBox("Program Settings")
        layout = QGridLayout(group)
        
        # Row 1: Project Name
        layout.addWidget(QLabel("Project Name:"), 0, 0)
        self.project_name_input = QLineEdit("QRA_Simulation_001")
        self.project_name_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.project_name_input, 0, 1)
        
        # Row 2: Time Interval
        layout.addWidget(QLabel("Time Interval (s):"), 1, 0)
        self.time_interval_input = QLineEdit("5.0")
        self.time_interval_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.time_interval_input, 1, 1)
        
        # Row 3: Total Simulation Time
        layout.addWidget(QLabel("Total Simulation Time (s):"), 2, 0)
        self.total_time_input = QLineEdit("3600.0")
        self.total_time_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.total_time_input, 2, 1)
        
        return group

    def _create_fire_point_group(self):
        group = QGroupBox("Fire Point and Evacuation Zone Configuration")
        layout = QVBoxLayout(group)
        
        # Fire Point List Table
        self.fire_point_table = QTableWidget(0, 4)
        self.fire_point_table.setHorizontalHeaderLabels(["Name", "Location X (m)", "Location Y (m)", "Location Z (m)"])
        self.fire_point_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fire_point_table.cellChanged.connect(self.save_data)
        layout.addWidget(self.fire_point_table)
        
        # Buttons for managing fire points
        button_layout = QHBoxLayout()
        self.add_fire_point_btn = QPushButton("Add Fire Point")
        self.remove_fire_point_btn = QPushButton("Remove Selected")
        button_layout.addWidget(self.add_fire_point_btn)
        button_layout.addWidget(self.remove_fire_point_btn)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)
        
        # Connect buttons to methods
        self.add_fire_point_btn.clicked.connect(self._add_fire_point)
        self.remove_fire_point_btn.clicked.connect(self._remove_fire_point)
        
        return group

    def _create_monitoring_group(self):
        group = QGroupBox("Monitoring Points")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("Number of Monitoring Points:"), 0, 0)
        self.monitoring_count_input = QLineEdit("10")
        self.monitoring_count_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.monitoring_count_input, 0, 1)
        
        return group

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
