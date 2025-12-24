from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QGroupBox, QRadioButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt
from src.models import VEHICLE_TYPES
from src.database.data_manager import DataManager

class TunnelBasicSettingsTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.layout = QVBoxLayout(self)
        
        # 1. Tunnel Basic Info Group
        self.layout.addWidget(self._create_tunnel_info_group())
        
        # 2. Traffic Volume and Vehicle Specs Group
        self.layout.addWidget(self._create_traffic_volume_group())
        
        self.layout.addStretch(1)
        
        # Load initial data
        self.load_data()

    def _create_tunnel_info_group(self):
        group = QGroupBox("Tunnel Basic Settings (터널기본제원)")
        layout = QGridLayout(group)
        
        # Row 1: Name and Mode
        layout.addWidget(QLabel("Name (명칭):"), 0, 0)
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input, 0, 1)
        
        layout.addWidget(QLabel("Traffic Mode (통행방식):"), 0, 2)
        mode_layout = QHBoxLayout()
        self.oneway_radio = QRadioButton("One-Way (일방통행)")
        self.twoway_radio = QRadioButton("Two-Way (대면통행)")
        self.oneway_radio.setChecked(True)
        mode_layout.addWidget(self.oneway_radio)
        mode_layout.addWidget(self.twoway_radio)
        layout.addLayout(mode_layout, 0, 3, 1, 3)
        
        # Row 2: Length, Entrance Length, Slope
        layout.addWidget(QLabel("Length (연장):"), 1, 0)
        self.length_input = QLineEdit()
        layout.addWidget(self.length_input, 1, 1)
        
        layout.addWidget(QLabel("Entrance Length (접수길이):"), 1, 2)
        self.entrance_length_input = QLineEdit()
        layout.addWidget(self.entrance_length_input, 1, 3)
        
        layout.addWidget(QLabel("Slope (구배):"), 1, 4)
        self.slope_input = QLineEdit()
        layout.addWidget(self.slope_input, 1, 5)
        
        # Row 3: Area, Height, Lanes
        layout.addWidget(QLabel("Area (단면적):"), 2, 0)
        self.area_input = QLineEdit()
        layout.addWidget(self.area_input, 2, 1)
        
        layout.addWidget(QLabel("Height (높이):"), 2, 2)
        self.height_input = QLineEdit()
        layout.addWidget(self.height_input, 2, 3)
        
        layout.addWidget(QLabel("Lanes (차선수):"), 2, 4)
        self.lanes_input = QLineEdit()
        layout.addWidget(self.lanes_input, 2, 5)
        
        # Row 4: Lane Width, Shoulder Width
        layout.addWidget(QLabel("Lane Width (차로폭):"), 3, 0)
        self.lane_width_input = QLineEdit()
        layout.addWidget(self.lane_width_input, 3, 1)
        
        layout.addWidget(QLabel("Shoulder Width (갓길폭):"), 3, 2)
        self.shoulder_width_input = QLineEdit()
        layout.addWidget(self.shoulder_width_input, 3, 3)
        
        # Two-Way Traffic Ratios Group (Conditional)
        self.twoway_group = QGroupBox("Two-Way Traffic Ratios (대면통행시)")
        self.twoway_group.setFlat(True)
        twoway_layout = QGridLayout(self.twoway_group)
        
        twoway_layout.addWidget(QLabel("Forward Ratio (기준방향):"), 0, 0)
        self.forward_ratio_input = QLineEdit()
        twoway_layout.addWidget(self.forward_ratio_input, 0, 1)
        twoway_layout.addWidget(QLabel("Forward Lanes (교통량(Lane)):"), 0, 2)
        self.forward_lanes_input = QLineEdit()
        twoway_layout.addWidget(self.forward_lanes_input, 0, 3)
        
        twoway_layout.addWidget(QLabel("Backward Ratio (반대방향):"), 1, 0)
        self.backward_ratio_input = QLineEdit()
        twoway_layout.addWidget(self.backward_ratio_input, 1, 1)
        twoway_layout.addWidget(QLabel("Backward Lanes (교통량(Lane)):"), 1, 2)
        self.backward_lanes_input = QLineEdit()
        twoway_layout.addWidget(self.backward_lanes_input, 1, 3)
        
        layout.addWidget(self.twoway_group, 0, 6, 4, 3)
        
        # Connect radio buttons to toggle visibility
        self.oneway_radio.toggled.connect(self._toggle_twoway_group)
        
        # Connect inputs to save data on change (simple auto-save)
        for input_field in [self.name_input, self.length_input, self.entrance_length_input, self.slope_input, self.area_input, self.height_input, self.lanes_input, self.lane_width_input, self.shoulder_width_input, self.forward_ratio_input, self.backward_ratio_input, self.forward_lanes_input, self.backward_lanes_input]:
            input_field.editingFinished.connect(self.save_data)
        self.oneway_radio.toggled.connect(self.save_data)
        
        return group

    def _toggle_twoway_group(self):
        is_twoway = self.twoway_radio.isChecked()
        self.twoway_group.setVisible(is_twoway)

    def _create_traffic_volume_group(self):
        group = QGroupBox("Traffic Volume and Vehicle Specs (교통량 및 차량제원)")
        layout = QVBoxLayout(group)
        
        self.volume_table = QTableWidget()
        
        # Define columns: 7 data columns (Vehicle Types)
        self.volume_table.setColumnCount(len(VEHICLE_TYPES))
        
        # Define rows: 7 data rows (+Direction, -Direction, +Mixing, -Mixing, PCU, Length, Occupancy)
        self.volume_table.setRowCount(7)
        
        # Set column headers
        col_headers = [v["vehicle_type"] for v in VEHICLE_TYPES]
        self.volume_table.setHorizontalHeaderLabels(col_headers)
        
        # Set row headers
        row_headers = ["+Direction (교통량)", "-Direction (교통량)", "+Mixing Ratio (혼입율)", "-Mixing Ratio (혼입율)", 
                       "PCU", "Length (차량길이)", "Occupancy (탑승인원)"]
        self.volume_table.setVerticalHeaderLabels(row_headers)
        
        # Resize columns to fit content
        self.volume_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Connect table to save data on change
        self.volume_table.cellChanged.connect(self.save_data)
        
        layout.addWidget(self.volume_table)
        return group

    def get_data(self):
        """Extracts data from the UI elements."""
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
        except ValueError as e:
            QMessageBox.critical(self, "Input Error", f"Invalid input value. Please check all fields. Error: {e}")
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
            # Row 0: +Direction (Traffic Volume)
            self.volume_table.setItem(0, col_idx, QTableWidgetItem(str(v_data.volume_plus)))
            # Row 1: -Direction (Traffic Volume)
            self.volume_table.setItem(1, col_idx, QTableWidgetItem(str(v_data.volume_minus)))
            # Row 2: +Mixing Ratio (혼입율)
            self.volume_table.setItem(2, col_idx, QTableWidgetItem(str(v_data.mixing_ratio_plus)))
            # Row 3: -Mixing Ratio (혼입율)
            self.volume_table.setItem(3, col_idx, QTableWidgetItem(str(v_data.mixing_ratio_minus)))
            # Row 4: PCU (Read-only)
            item_pcu = QTableWidgetItem(str(v_data.pcu))
            item_pcu.setFlags(item_pcu.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.volume_table.setItem(4, col_idx, item_pcu)
            # Row 5: Length (Read-only)
            item_len = QTableWidgetItem(str(v_data.length))
            item_len.setFlags(item_len.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.volume_table.setItem(5, col_idx, item_len)
            # Row 6: Occupancy (Read-only)
            item_occ = QTableWidgetItem(str(v_data.occupancy))
            item_occ.setFlags(item_occ.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.volume_table.setItem(6, col_idx, item_occ)

    def load_data(self):
        """Loads data from the database and populates the UI."""
        tunnel_config, vehicle_data = self.data_manager.load_tunnel_data()
        if tunnel_config and vehicle_data:
            self.set_data(tunnel_config, vehicle_data)
            
    def save_data(self):
        """Extracts data from the UI and saves it to the database."""
        data = self.get_data()
        if data:
            if self.data_manager.save_tunnel_data(data):
                # Update status bar or show a small notification
                pass
            else:
                QMessageBox.warning(self, "Save Error", "Failed to save Tunnel Basic Settings data.")
