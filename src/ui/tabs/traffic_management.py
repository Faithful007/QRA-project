from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QMessageBox,
    QPushButton, QComboBox, QRadioButton, QButtonGroup, QScrollArea
)
from PyQt6.QtCore import Qt
from src.database.data_manager import DataManager
from src.language_manager import get_language_manager

class TrafficManagementTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.language_manager = get_language_manager()
        
        # Connect to language change signal
        self.language_manager.language_changed.connect(self._on_language_changed)
        
        main_layout = QVBoxLayout(self)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 1. Traffic Flow Configuration Group - Left side
        left_layout = QVBoxLayout()
        left_layout.addWidget(self._create_traffic_flow_group())
        left_layout.addStretch(1)
        
        # Top horizontal layout for main settings and speed table
        top_layout = QHBoxLayout()
        top_layout.addLayout(left_layout, 1)
        top_layout.addWidget(self._create_speed_distribution_group(), 2)
        
        content_layout.addLayout(top_layout)
        
        # 2. Evacuation Zone Speed Group - Full width
        content_layout.addWidget(self._create_evac_speed_group())
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.save_btn = QPushButton("Calculate")
        self.save_btn.clicked.connect(self.save_data)
        button_layout.addWidget(self.save_btn)
        content_layout.addLayout(button_layout)
        
        main_layout.addWidget(content_widget)
        self.load_data()

    def _create_traffic_flow_group(self):
        lm = self.language_manager
        self.traffic_flow_group = QGroupBox(lm.translate("Max Vehicles During Congestion"))
        layout = QGridLayout(self.traffic_flow_group)
        
        # Row 1: Site Max Speed
        self.max_vehicles_label = QLabel(lm.translate("Max Vehicles During Congestion:"))
        layout.addWidget(self.max_vehicles_label, 0, 0)
        self.max_speed_input = QLineEdit("150")
        self.max_speed_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.max_speed_input, 0, 1)
        layout.addWidget(QLabel(lm.translate("pcpkpl")), 0, 2)
        
        # Row 2: Incident Traffic Volume
        self.traffic_volume_label = QLabel(lm.translate("Traffic Volume:"))
        layout.addWidget(self.traffic_volume_label, 1, 0)
        self.incident_volume_input = QLineEdit("1600")
        self.incident_volume_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.incident_volume_input, 1, 1)
        layout.addWidget(QLabel(lm.translate("pcpkpl")), 1, 2)
        
        # Row 3: Fire Point Location
        self.fire_point_alignment_label = QLabel(lm.translate("Fire Point Alignment:"))
        layout.addWidget(self.fire_point_alignment_label, 2, 0)
        self.occupancy_factor_input = QLineEdit("5")
        self.occupancy_factor_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.occupancy_factor_input, 2, 1)
        layout.addWidget(QLabel(lm.translate("km/h")), 2, 2)
        
        # Radio buttons for vehicle type
        self.vehicle_type_label = QLabel(lm.translate("Vehicle Type:"))
        layout.addWidget(self.vehicle_type_label, 3, 0)
        self.vehicle_type_group = QButtonGroup()
        self.radio_button1 = QRadioButton(lm.translate("Safety Design"))
        self.radio_button2 = QRadioButton(lm.translate("Emergency"))
        self.vehicle_type_group.addButton(self.radio_button1, 1)
        self.vehicle_type_group.addButton(self.radio_button2, 2)
        self.radio_button1.setChecked(True)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.radio_button1)
        h_layout.addWidget(self.radio_button2)
        layout.addLayout(h_layout, 3, 1, 1, 2)
        
        return self.traffic_flow_group

    def _create_speed_distribution_group(self):
        lm = self.language_manager
        self.speed_dist_group = QGroupBox(lm.translate("Zone-based Speed Distribution and Evacuation"))
        layout = QVBoxLayout(self.speed_dist_group)
        
        # Speed distribution table
        self.speed_table = QTableWidget(3, 11)
        headers = [lm.translate("Speed Type"), "10", "20", "30", "40", "50", "60", "70", "80", 
                   lm.translate("Total"), lm.translate("Status")]
        self.speed_table.setHorizontalHeaderLabels(headers)
        
        # First row: Max auto speed
        self.speed_table.setItem(0, 0, QTableWidgetItem(lm.translate("Max Auto Speed")))
        for i in range(1, 9):
            self.speed_table.setItem(0, i, QTableWidgetItem("0"))
        
        # Second row: Min auto speed
        self.speed_table.setItem(1, 0, QTableWidgetItem(lm.translate("Min Auto Speed")))
        for i in range(1, 9):
            self.speed_table.setItem(1, i, QTableWidgetItem("0"))
        
        # Third row: Medium vehicle evacuation speed
        self.speed_table.setItem(2, 0, QTableWidgetItem(lm.translate("Medium Vehicle Evac Speed")))
        for i in range(1, 9):
            self.speed_table.setItem(2, i, QTableWidgetItem("0"))
        
        self.speed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.speed_table.cellChanged.connect(self.save_data)
        layout.addWidget(self.speed_table)
        
        return self.speed_dist_group

    def _create_evac_speed_group(self):
        lm = self.language_manager
        self.evac_speed_group = QGroupBox(lm.translate("Vehicle Speed and Evacuation"))
        layout = QGridLayout(self.evac_speed_group)
        
        # Column headers
        self.time_zone_label = QLabel(lm.translate("Time Zone [hours]"))
        layout.addWidget(self.time_zone_label, 0, 0)
        self.zone5_label = QLabel(lm.translate("Zone5"))
        layout.addWidget(self.zone5_label, 0, 1)
        layout.addWidget(QLabel(""), 0, 2)
        
        self.zone_row_labels = []
        for i in range(5):
            zone_label = QLabel(f"Zone{i+1}:")
            self.zone_row_labels.append(zone_label)
            layout.addWidget(zone_label, i+1, 0)
            line_edit = QLineEdit(f"0.0" if i > 0 else "1.0")
            layout.addWidget(line_edit, i+1, 1)
            if i == 0:
                self.evac_speed_factor_input = line_edit
        
        return self.evac_speed_group

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
    def _on_language_changed(self, language_code: str):
        """Handle language change event."""
        lm = self.language_manager
        
        # Update group box titles
        if hasattr(self, 'traffic_flow_group'):
            self.traffic_flow_group.setTitle(lm.translate("Max Vehicles During Congestion"))
        if hasattr(self, 'speed_dist_group'):
            self.speed_dist_group.setTitle(lm.translate("Zone-based Speed Distribution and Evacuation"))
        if hasattr(self, 'evac_speed_group'):
            self.evac_speed_group.setTitle(lm.translate("Vehicle Speed and Evacuation"))
        
        # Update labels
        if hasattr(self, 'max_vehicles_label'):
            self.max_vehicles_label.setText(lm.translate("Max Vehicles During Congestion:"))
        if hasattr(self, 'traffic_volume_label'):
            self.traffic_volume_label.setText(lm.translate("Traffic Volume:"))
        if hasattr(self, 'fire_point_alignment_label'):
            self.fire_point_alignment_label.setText(lm.translate("Fire Point Alignment:"))
        if hasattr(self, 'vehicle_type_label'):
            self.vehicle_type_label.setText(lm.translate("Vehicle Type:"))
        if hasattr(self, 'time_zone_label'):
            self.time_zone_label.setText(lm.translate("Time Zone [hours]"))
        if hasattr(self, 'zone5_label'):
            self.zone5_label.setText(lm.translate("Zone5"))
        if hasattr(self, 'zone_row_labels'):
            for i, lbl in enumerate(self.zone_row_labels, start=1):
                lbl.setText(f"Zone{i}:")
        
        # Update button text
        if hasattr(self, 'save_btn'):
            self.save_btn.setText(lm.translate("Calculate"))
        
        # Update speed table headers and content
        if hasattr(self, 'speed_table'):
            headers = [lm.translate("Speed Type"), "10", "20", "30", "40", "50", "60", "70", "80", 
                       lm.translate("Total"), lm.translate("Status")]
            self.speed_table.setHorizontalHeaderLabels(headers)
            
            # Update row labels
            self.speed_table.setItem(0, 0, QTableWidgetItem(lm.translate("Max Auto Speed")))
            self.speed_table.setItem(1, 0, QTableWidgetItem(lm.translate("Min Auto Speed")))
            self.speed_table.setItem(2, 0, QTableWidgetItem(lm.translate("Medium Vehicle Evac Speed")))