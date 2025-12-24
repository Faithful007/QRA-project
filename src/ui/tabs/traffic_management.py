from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt
from src.database.data_manager import DataManager

class TrafficManagementTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.layout = QVBoxLayout(self)
        
        # 1. Traffic Flow Configuration Group
        self.layout.addWidget(self._create_traffic_flow_group())
        
        # 2. Speed Distribution Group
        self.layout.addWidget(self._create_speed_distribution_group())
        
        # 3. Evacuation Zone Speed Group
        self.layout.addWidget(self._create_evac_speed_group())
        
        self.layout.addStretch(1)
        
        self.load_data()

    def _create_traffic_flow_group(self):
        group = QGroupBox("Traffic Flow Configuration")
        layout = QGridLayout(group)
        
        # Row 1: Site Max Speed
        layout.addWidget(QLabel("Site Max Speed (km/h):"), 0, 0)
        self.max_speed_input = QLineEdit("80.0")
        self.max_speed_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.max_speed_input, 0, 1)
        
        # Row 2: Incident Traffic Volume
        layout.addWidget(QLabel("Incident Traffic Volume (veh/h):"), 1, 0)
        self.incident_volume_input = QLineEdit("0.0")
        self.incident_volume_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.incident_volume_input, 1, 1)
        
        # Row 3: Occupancy Factor (Simplified)
        layout.addWidget(QLabel("Occupancy Factor:"), 2, 0)
        self.occupancy_factor_input = QLineEdit("1.0")
        self.occupancy_factor_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.occupancy_factor_input, 2, 1)
        
        return group

    def _create_speed_distribution_group(self):
        group = QGroupBox("Zone-based Traffic and Speed Distribution")
        layout = QVBoxLayout(group)
        
        # Simplified table for speed distribution
        self.speed_table = QTableWidget(5, 3)
        self.speed_table.setHorizontalHeaderLabels(["Zone", "Traffic Volume (%)", "Speed (km/h)"])
        
        # Populate initial data (placeholder zones)
        for i in range(5):
            self.speed_table.setItem(i, 0, QTableWidgetItem(f"Zone {i+1}"))
            self.speed_table.setItem(i, 1, QTableWidgetItem("20.0" if i < 4 else "0.0"))
            self.speed_table.setItem(i, 2, QTableWidgetItem("80.0"))
            
            # Make Zone column read-only
            self.speed_table.item(i, 0).setFlags(self.speed_table.item(i, 0).flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.speed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.speed_table.cellChanged.connect(self.save_data)
        layout.addWidget(self.speed_table)
        
        return group

    def _create_evac_speed_group(self):
        group = QGroupBox("Evacuation Zone Speed Distribution")
        layout = QGridLayout(group)
        
        # Simplified input for Evacuation Zone Speed
        layout.addWidget(QLabel("Evac Zone Speed Factor:"), 0, 0)
        self.evac_speed_factor_input = QLineEdit("1.0")
        self.evac_speed_factor_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.evac_speed_factor_input, 0, 1)
        
        return group

    def get_data(self):
        """Extracts data from the UI elements with safe parsing."""
        try:
            def f(text, default=0.0):
                t = text.strip()
                if t == "":
                    return default
                return float(t)

            data = {
                "max_speed": f(self.max_speed_input.text()),
                "incident_traffic_volume": f(self.incident_volume_input.text()),
                "occupancy_factor": f(self.occupancy_factor_input.text()),
                "evac_zone_speed": f(self.evac_speed_factor_input.text()),
                # Speed table data extraction would go here
            }
            return data
        except ValueError as e:
            QMessageBox.critical(self, "Input Error", f"Invalid input value. Please check all fields. Error: {e}")
            return None

    def set_data(self, traffic_management_config):
        """Populates the UI elements with data from the database models."""
        self.max_speed_input.setText(str(traffic_management_config.max_speed))
        self.incident_volume_input.setText(str(traffic_management_config.incident_traffic_volume))
        self.occupancy_factor_input.setText(str(traffic_management_config.occupancy_factor))
        self.evac_speed_factor_input.setText(str(traffic_management_config.evac_zone_speed))
        # Speed table data population would go here

    def load_data(self):
        """Loads data from the database and populates the UI."""
        # traffic_config = self.data_manager.load_traffic_data()
        # if traffic_config:
        #     self.set_data(traffic_config)
        pass
            
    def save_data(self):
        """Extracts data from the UI and saves it to the database."""
        # data = self.get_data()
        # if data:
        #     self.data_manager.save_traffic_data(data)
        pass
