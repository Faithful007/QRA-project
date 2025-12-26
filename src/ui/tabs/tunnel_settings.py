from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QLineEdit, QRadioButton, QGroupBox, QGridLayout,
                              QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)
from PyQt6.QtCore import Qt

# Define vehicle types
VEHICLE_TYPES = [
    {"vehicle_type": "Car", "default_pcu": 1.0, "default_length": 4.0, "default_occupancy": 2},
    {"vehicle_type": "Van", "default_pcu": 1.5, "default_length": 5.0, "default_occupancy": 3},
    {"vehicle_type": "Bus", "default_pcu": 2.5, "default_length": 12.0, "default_occupancy": 40},
    {"vehicle_type": "Truck", "default_pcu": 2.0, "default_length": 10.0, "default_occupancy": 2},
]

class TunnelSettingsTab(QWidget):
    def __init__(self, language_manager):
        super().__init__()
        self.language_manager = language_manager
        
        # Connect to language change signal
        self.language_manager.language_changed.connect(self._update_ui_text)
        
        main_layout = QVBoxLayout()
        
        # Create tunnel info group
        self.tunnel_group = self._create_tunnel_info_group()
        main_layout.addWidget(self.tunnel_group)
        
        # Create traffic volume group
        self.volume_group = self._create_traffic_volume_group()
        main_layout.addWidget(self.volume_group)
        
        main_layout.addStretch()
        self.setLayout(main_layout)
    
    def _update_ui_text(self):
        """Update all UI text when language changes"""
        lm = self.language_manager
        
        # Update tunnel group
        self.tunnel_group.setTitle(lm.translate("Tunnel Basic Specifications"))
        self.name_label.setText(lm.translate("Name :"))
        self.mode_label.setText(lm.translate("Traffic Mode :"))
        self.oneway_radio.setText(lm.translate("One-Way "))
        self.twoway_radio.setText(lm.translate("Two-Way "))
        self.length_label.setText(lm.translate("Length :"))
        self.entrance_length_label.setText(lm.translate("Entrance Length :"))
        self.slope_label.setText(lm.translate("Slope :"))
        self.area_label.setText(lm.translate("Cross-sectional area :"))
        self.height_label.setText(lm.translate("Height :"))
        self.lanes_label.setText(lm.translate("Lanes :"))
        self.lane_width_label.setText(lm.translate("Lane Width :"))
        self.shoulder_width_label.setText(lm.translate("Shoulder Width :"))
        self.ratio_group.setTitle(lm.translate("Two-Way Traffic Ratios "))
        self.forward_ratio_label.setText(lm.translate("Forward Ratio :"))
        self.backward_ratio_label.setText(lm.translate("Backward Ratio :"))
        self.forward_lanes_label.setText(lm.translate("Forward Lanes :"))
        self.backward_lanes_label.setText(lm.translate("Backward Lanes :"))
        
        # Update volume group and table
        self.volume_group.setTitle(lm.translate("Traffic Volume"))
        self.volume_table.setVerticalHeaderItem(0, QTableWidgetItem(lm.translate("+Direction ")))
        self.volume_table.setVerticalHeaderItem(1, QTableWidgetItem(lm.translate("-Direction ")))
        self.volume_table.setVerticalHeaderItem(2, QTableWidgetItem(lm.translate("+Mixing Ratio ")))
        self.volume_table.setVerticalHeaderItem(3, QTableWidgetItem(lm.translate("-Mixing Ratio ")))
        self.volume_table.setVerticalHeaderItem(4, QTableWidgetItem(lm.translate("PCU")))
        self.volume_table.setVerticalHeaderItem(5, QTableWidgetItem(lm.translate("Length ")))
        self.volume_table.setVerticalHeaderItem(6, QTableWidgetItem(lm.translate("Occupancy ")))
    
    def _create_tunnel_info_group(self):
        """Create the tunnel basic specifications group"""
        lm = self.language_manager
        group = QGroupBox(lm.translate("Tunnel Basic Specifications"))
        layout = QGridLayout()
        
        row = 0
        # Name
        self.name_label = QLabel(lm.translate("Name :"))
        self.name_input = QLineEdit()
        layout.addWidget(self.name_label, row, 0)
        layout.addWidget(self.name_input, row, 1, 1, 2)
        row += 1
        
        # Traffic Mode
        self.mode_label = QLabel(lm.translate("Traffic Mode :"))
        self.oneway_radio = QRadioButton(lm.translate("One-Way "))
        self.twoway_radio = QRadioButton(lm.translate("Two-Way "))
        self.oneway_radio.setChecked(True)
        layout.addWidget(self.mode_label, row, 0)
        layout.addWidget(self.oneway_radio, row, 1)
        layout.addWidget(self.twoway_radio, row, 2)
        row += 1
        
        # Length
        self.length_label = QLabel(lm.translate("Length :"))
        self.length_input = QLineEdit()
        layout.addWidget(self.length_label, row, 0)
        layout.addWidget(self.length_input, row, 1, 1, 2)
        row += 1
        
        # Entrance Length
        self.entrance_length_label = QLabel(lm.translate("Entrance Length :"))
        self.entrance_length_input = QLineEdit()
        layout.addWidget(self.entrance_length_label, row, 0)
        layout.addWidget(self.entrance_length_input, row, 1, 1, 2)
        row += 1
        
        # Slope
        self.slope_label = QLabel(lm.translate("Slope :"))
        self.slope_input = QLineEdit()
        layout.addWidget(self.slope_label, row, 0)
        layout.addWidget(self.slope_input, row, 1, 1, 2)
        row += 1
        
        # Cross-sectional area
        self.area_label = QLabel(lm.translate("Cross-sectional area :"))
        self.area_input = QLineEdit()
        layout.addWidget(self.area_label, row, 0)
        layout.addWidget(self.area_input, row, 1, 1, 2)
        row += 1
        
        # Height
        self.height_label = QLabel(lm.translate("Height :"))
        self.height_input = QLineEdit()
        layout.addWidget(self.height_label, row, 0)
        layout.addWidget(self.height_input, row, 1, 1, 2)
        row += 1
        
        # Lanes
        self.lanes_label = QLabel(lm.translate("Lanes :"))
        self.lanes_input = QLineEdit()
        layout.addWidget(self.lanes_label, row, 0)
        layout.addWidget(self.lanes_input, row, 1, 1, 2)
        row += 1
        
        # Lane Width
        self.lane_width_label = QLabel(lm.translate("Lane Width :"))
        self.lane_width_input = QLineEdit()
        layout.addWidget(self.lane_width_label, row, 0)
        layout.addWidget(self.lane_width_input, row, 1, 1, 2)
        row += 1
        
        # Shoulder Width
        self.shoulder_width_label = QLabel(lm.translate("Shoulder Width :"))
        self.shoulder_width_input = QLineEdit()
        layout.addWidget(self.shoulder_width_label, row, 0)
        layout.addWidget(self.shoulder_width_input, row, 1, 1, 2)
        row += 1
        
        # Two-Way Traffic Ratios (initially hidden)
        self.ratio_group = QGroupBox(lm.translate("Two-Way Traffic Ratios "))
        ratio_layout = QGridLayout()
        
        self.forward_ratio_label = QLabel(lm.translate("Forward Ratio :"))
        self.forward_ratio_input = QLineEdit("0.5")
        ratio_layout.addWidget(self.forward_ratio_label, 0, 0)
        ratio_layout.addWidget(self.forward_ratio_input, 0, 1)
        
        self.backward_ratio_label = QLabel(lm.translate("Backward Ratio :"))
        self.backward_ratio_input = QLineEdit("0.5")
        ratio_layout.addWidget(self.backward_ratio_label, 1, 0)
        ratio_layout.addWidget(self.backward_ratio_input, 1, 1)
        
        self.forward_lanes_label = QLabel(lm.translate("Forward Lanes :"))
        self.forward_lanes_input = QLineEdit("2")
        ratio_layout.addWidget(self.forward_lanes_label, 2, 0)
        ratio_layout.addWidget(self.forward_lanes_input, 2, 1)
        
        self.backward_lanes_label = QLabel(lm.translate("Backward Lanes :"))
        self.backward_lanes_input = QLineEdit("2")
        ratio_layout.addWidget(self.backward_lanes_label, 3, 0)
        ratio_layout.addWidget(self.backward_lanes_input, 3, 1)
        
        self.ratio_group.setLayout(ratio_layout)
        self.ratio_group.setVisible(False)
        
        layout.addWidget(self.ratio_group, row, 0, 1, 3)
        
        # Connect radio buttons
        self.twoway_radio.toggled.connect(self._on_mode_changed)
        
        group.setLayout(layout)
        return group

    def _on_mode_changed(self, checked):
        """Show/hide two-way traffic ratio inputs"""
        self.ratio_group.setVisible(checked)

    def _create_traffic_volume_group(self):
        """Create the traffic volume table group"""
        lm = self.language_manager
        group = QGroupBox(lm.translate("Traffic Volume"))
        layout = QVBoxLayout()
        
        # Create table
        self.volume_table = QTableWidget()
        self.volume_table.setRowCount(7)
        self.volume_table.setColumnCount(len(VEHICLE_TYPES))
        
        # Set horizontal headers (vehicle types - don't translate)
        for col_idx, vtype in enumerate(VEHICLE_TYPES):
            self.volume_table.setHorizontalHeaderItem(col_idx, QTableWidgetItem(vtype["vehicle_type"]))
        
        # Set vertical headers (translated)
        self.volume_table.setVerticalHeaderItem(0, QTableWidgetItem(lm.translate("+Direction ")))
        self.volume_table.setVerticalHeaderItem(1, QTableWidgetItem(lm.translate("-Direction ")))
        self.volume_table.setVerticalHeaderItem(2, QTableWidgetItem(lm.translate("+Mixing Ratio ")))
        self.volume_table.setVerticalHeaderItem(3, QTableWidgetItem(lm.translate("-Mixing Ratio ")))
        self.volume_table.setVerticalHeaderItem(4, QTableWidgetItem(lm.translate("PCU")))
        self.volume_table.setVerticalHeaderItem(5, QTableWidgetItem(lm.translate("Length ")))
        self.volume_table.setVerticalHeaderItem(6, QTableWidgetItem(lm.translate("Occupancy ")))
        
        # Initialize with default values
        for col_idx, vtype in enumerate(VEHICLE_TYPES):
            self.volume_table.setItem(0, col_idx, QTableWidgetItem("0"))
            self.volume_table.setItem(1, col_idx, QTableWidgetItem("0"))
            self.volume_table.setItem(2, col_idx, QTableWidgetItem("0.0"))
            self.volume_table.setItem(3, col_idx, QTableWidgetItem("0.0"))
            self.volume_table.setItem(4, col_idx, QTableWidgetItem(str(vtype["default_pcu"])))
            self.volume_table.setItem(5, col_idx, QTableWidgetItem(str(vtype["default_length"])))
            self.volume_table.setItem(6, col_idx, QTableWidgetItem(str(vtype["default_occupancy"])))
        
        self.volume_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.volume_table)
        group.setLayout(layout)
        return group

    def get_data(self):
        """Extracts data from the UI elements."""
        lm = self.language_manager
        try:
            # Safe parsers: treat empty strings as zero to avoid startup errors
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

            data = {
                "name": self.name_input.text(),
                "mode": "Two-Way" if self.twoway_radio.isChecked() else "One-Way",
                "length": f(self.length_input.text()),
                "entrance_length": f(self.entrance_length_input.text()),
                "slope": f(self.slope_input.text()),
                "area": f(self.area_input.text()),
                "height": f(self.height_input.text()),
                "lanes": i(self.lanes_input.text()),
                "lane_width": f(self.lane_width_input.text()),
                "shoulder_width": f(self.shoulder_width_input.text()),
                "forward_ratio": f(self.forward_ratio_input.text()) if self.twoway_radio.isChecked() else 0.0,
                "backward_ratio": f(self.backward_ratio_input.text()) if self.twoway_radio.isChecked() else 0.0,
                "forward_lanes": i(self.forward_lanes_input.text()) if self.twoway_radio.isChecked() else 0,
                "backward_lanes": i(self.backward_lanes_input.text()) if self.twoway_radio.isChecked() else 0,
                "vehicle_data": []
            }
            
            # Extract vehicle data from the table
            for col_idx, vehicle_type_data in enumerate(VEHICLE_TYPES):
                # Helper to safely get float/int from table item
                def get_table_value(row, col, type_func=float):
                    item = self.volume_table.item(row, col)
                    if item and item.text():
                        txt = item.text().strip()
                        if txt == "":
                            return 0 if type_func is int else 0.0
                        return type_func(txt)
                    return 0 if type_func is int else 0.0
                    
                vehicle_data = {
                    "vehicle_type": vehicle_type_data["vehicle_type"],
                    "volume_plus": get_table_value(0, col_idx),
                    "volume_minus": get_table_value(1, col_idx),
                    "mixing_ratio_plus": get_table_value(2, col_idx),
                    "mixing_ratio_minus": get_table_value(3, col_idx),
                    "pcu": get_table_value(4, col_idx),
                    "length": get_table_value(5, col_idx),
                    "occupancy": get_table_value(6, col_idx, type_func=int),
                }
                data["vehicle_data"].append(vehicle_data)
                
            return data
        except Exception as e:
            QMessageBox.critical(self, lm.translate("Input Error"), f"Invalid input value. Please check all fields. Error: {e}")
            return None

    def set_data(self, tunnel_config, vehicle_data):
        """Populates the UI elements with data from the database models."""
        self.name_input.setText(tunnel_config.name)
        if tunnel_config.mode == "Two-Way":
            self.twoway_radio.setChecked(True)
        else:
            self.oneway_radio.setChecked(True)
            
        self.length_input.setText(str(tunnel_config.length))
        self.entrance_length_input.setText(str(tunnel_config.entrance_length))
        self.slope_input.setText(str(tunnel_config.slope))
        self.area_input.setText(str(tunnel_config.area))
        self.height_input.setText(str(tunnel_config.height))
        self.lanes_input.setText(str(tunnel_config.lanes))
        self.lane_width_input.setText(str(tunnel_config.lane_width))
        self.shoulder_width_input.setText(str(tunnel_config.shoulder_width))
        
        self.forward_ratio_input.setText(str(tunnel_config.forward_ratio))
        self.backward_ratio_input.setText(str(tunnel_config.backward_ratio))
        self.forward_lanes_input.setText(str(tunnel_config.forward_lanes))
        self.backward_lanes_input.setText(str(tunnel_config.backward_lanes))
        
        # Populate vehicle data table
        for col_idx, v_data in enumerate(vehicle_data):
            self.volume_table.setItem(0, col_idx, QTableWidgetItem(str(v_data.volume_plus)))
            self.volume_table.setItem(1, col_idx, QTableWidgetItem(str(v_data.volume_minus)))
            self.volume_table.setItem(2, col_idx, QTableWidgetItem(str(v_data.mixing_ratio_plus)))
            self.volume_table.setItem(3, col_idx, QTableWidgetItem(str(v_data.mixing_ratio_minus)))
            self.volume_table.setItem(4, col_idx, QTableWidgetItem(str(v_data.pcu)))
            self.volume_table.setItem(5, col_idx, QTableWidgetItem(str(v_data.length)))
            self.volume_table.setItem(6, col_idx, QTableWidgetItem(str(v_data.occupancy)))
