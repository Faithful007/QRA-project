from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QGroupBox, QComboBox, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt
from src.database.data_manager import DataManager

class HAREVACAnalysisTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.layout = QVBoxLayout(self)
        
        # 1. Hazard Definition Group
        self.layout.addWidget(self._create_hazard_group())
        
        # 2. Fire Characteristics Group
        self.layout.addWidget(self._create_fire_group())
        
        # 3. Evacuation Characteristics Group
        self.layout.addWidget(self._create_evac_char_group())
        
        # 4. Evacuation Timing and Speed Group
        self.layout.addWidget(self._create_evac_timing_group())
        
        self.layout.addStretch(1)
        
        self.load_data()

    def _create_hazard_group(self):
        group = QGroupBox("Hazard Definition")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("Calculation Method:"), 0, 0)
        self.calc_method_combo = QComboBox()
        self.calc_method_combo.addItems(["FED (Fractional Effective Dose)", "Tenability Limits", "Custom"])
        self.calc_method_combo.currentTextChanged.connect(self.save_data)
        layout.addWidget(self.calc_method_combo, 0, 1)
        
        return group

    def _create_fire_group(self):
        group = QGroupBox("Fire Characteristics")
        layout = QGridLayout(group)
        
        # Row 1: Heat Release Rate
        layout.addWidget(QLabel("Heat Release Rate (MW):"), 0, 0)
        self.hrr_input = QLineEdit("10.0")
        self.hrr_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.hrr_input, 0, 1)
        
        # Row 2: Fire Growth Rate
        layout.addWidget(QLabel("Fire Growth Rate:"), 1, 0)
        self.growth_rate_combo = QComboBox()
        self.growth_rate_combo.addItems(["Slow", "Medium", "Fast", "Ultra-Fast"])
        self.growth_rate_combo.setCurrentText("Medium")
        self.growth_rate_combo.currentTextChanged.connect(self.save_data)
        layout.addWidget(self.growth_rate_combo, 1, 1)
        
        # Row 3: Smoke Density
        layout.addWidget(QLabel("Smoke Density (m^-1):"), 2, 0)
        self.smoke_density_input = QLineEdit("0.1")
        self.smoke_density_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.smoke_density_input, 2, 1)
        
        return group

    def _create_evac_char_group(self):
        group = QGroupBox("Evacuation Characteristics (ASET/RSET Criteria)")
        layout = QGridLayout(group)
        
        # Row 1: Visibility Limit
        layout.addWidget(QLabel("Visibility Limit (m):"), 0, 0)
        self.visibility_input = QLineEdit("10.0")
        self.visibility_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.visibility_input, 0, 1)
        
        # Row 2: Temperature Limit
        layout.addWidget(QLabel("Temperature Limit (°C):"), 1, 0)
        self.temp_input = QLineEdit("60.0")
        self.temp_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.temp_input, 1, 1)
        
        # Row 3: CO Limit
        layout.addWidget(QLabel("CO Limit (ppm):"), 2, 0)
        self.co_input = QLineEdit("1000.0")
        self.co_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.co_input, 2, 1)
        
        return group

    def _create_evac_timing_group(self):
        group = QGroupBox("Evacuation Timing and Speed")
        layout = QGridLayout(group)
        
        # Row 1: Reaction Time
        layout.addWidget(QLabel("Reaction Time (s):"), 0, 0)
        self.reaction_time_input = QLineEdit("60.0")
        self.reaction_time_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.reaction_time_input, 0, 1)
        
        # Row 2: Hesitation Time
        layout.addWidget(QLabel("Hesitation Time (s):"), 1, 0)
        self.hesitation_time_input = QLineEdit("120.0")
        self.hesitation_time_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.hesitation_time_input, 1, 1)
        
        # New: Ratio of Old People (Human Factor)
        layout.addWidget(QLabel("Ratio of Old People (%):"), 2, 0)
        self.old_people_ratio_input = QLineEdit("10.0")
        self.old_people_ratio_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.old_people_ratio_input, 2, 1)
        
        # Row 4: Evacuation Speed (Walking) - Replaced with ComboBox for options
        layout.addWidget(QLabel("Walking Speed Option:"), 3, 0)
        self.walking_speed_combo = QComboBox()
        self.walking_speed_combo.addItems(["Standard (1.2 m/s)", "Reduced (0.8 m/s)", "Congested (0.5 m/s)", "Custom"])
        self.walking_speed_combo.currentTextChanged.connect(self.save_data)
        layout.addWidget(self.walking_speed_combo, 3, 1)
        
        # Row 5: Evacuation Speed (Running) - Kept for custom speed input
        layout.addWidget(QLabel("Evac Speed - Running (m/s):"), 4, 0)
        self.run_speed_input = QLineEdit("2.0")
        self.run_speed_input.editingFinished.connect(self.save_data)
        layout.addWidget(self.run_speed_input, 4, 1)
        
        # Row 6: Early Start Condition
        self.early_start_check = QCheckBox("Early Start (Evac before pre-set time)")
        self.early_start_check.stateChanged.connect(self.save_data)
        layout.addWidget(self.early_start_check, 5, 0, 1, 2)
        
        return group

    def get_data(self):
        """Extracts data from the UI elements with safe parsing."""
        try:
            def f(text, default=0.0):
                t = text.strip()
                if t == "":
                    return default
                return float(t)

            return {
                "hazard_calculation_method": self.calc_method_combo.currentText(),
                "heat_release_rate": f(self.hrr_input.text()),
                "fire_growth_rate": self.growth_rate_combo.currentText(),
                "smoke_density": f(self.smoke_density_input.text()),
                "visibility_limit": f(self.visibility_input.text()),
                "temperature_limit": f(self.temp_input.text()),
                "CO_limit": f(self.co_input.text()),
                "reaction_time": f(self.reaction_time_input.text()),
                "hesitation_time": f(self.hesitation_time_input.text()),
                "old_people_ratio": f(self.old_people_ratio_input.text()),
                "walking_speed_option": self.walking_speed_combo.currentText(),
                "evac_speed_running": f(self.run_speed_input.text()),
                "early_start_condition": self.early_start_check.isChecked(),
            }
        except ValueError as e:
            QMessageBox.critical(self, "Input Error", f"Invalid input value. Please check all fields. Error: {e}")
            return None

    def set_data(self, har_evac_config):
        """Populates the UI elements with data from the database models."""
        self.calc_method_combo.setCurrentText(har_evac_config.hazard_calculation_method)
        self.hrr_input.setText(str(har_evac_config.heat_release_rate))
        self.growth_rate_combo.setCurrentText(har_evac_config.fire_growth_rate)
        self.smoke_density_input.setText(str(har_evac_config.smoke_density))
        self.visibility_input.setText(str(har_evac_config.visibility_limit))
        self.temp_input.setText(str(har_evac_config.temperature_limit))
        self.co_input.setText(str(har_evac_config.CO_limit))
        self.reaction_time_input.setText(str(har_evac_config.reaction_time))
        self.hesitation_time_input.setText(str(har_evac_config.hesitation_time))
        self.old_people_ratio_input.setText(str(har_evac_config.old_people_ratio))
        self.walking_speed_combo.setCurrentText(har_evac_config.walking_speed_option)
        self.run_speed_input.setText(str(har_evac_config.evac_speed_running))
        self.early_start_check.setChecked(har_evac_config.early_start_condition)

    def load_data(self):
        """Loads data from the database and populates the UI."""
        # har_evac_config = self.data_manager.load_har_evac_data()
        # if har_evac_config:
        #     self.set_data(har_evac_config)
        pass
            
    def save_data(self):
        """Extracts data from the UI and saves it to the database."""
        # data = self.get_data()
        # if data:
        #     self.data_manager.save_har_evac_data(data)
        pass
