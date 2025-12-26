from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QGroupBox, QComboBox, QCheckBox, QMessageBox, QPushButton, QRadioButton, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from src.database.data_manager import DataManager
from src.language_manager import get_language_manager

class HAREVACAnalysisTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.language_manager = get_language_manager()
        
        # Connect to language change signal
        self.language_manager.language_changed.connect(self._on_language_changed)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Top section: Hazard definition
        main_layout.addWidget(self._create_hazard_group())
        
        # Middle section: Fire characteristics and evacuation settings
        middle_layout = QHBoxLayout()
        middle_layout.addWidget(self._create_fire_group(), 1)
        middle_layout.addWidget(self._create_evac_char_group(), 1)
        main_layout.addLayout(middle_layout)
        
        # Bottom section: Evacuation timing settings with graph
        main_layout.addWidget(self._create_evac_timing_group())
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.export_btn = QPushButton("Export Data")
        self.export_btn.clicked.connect(self.save_data)
        button_layout.addWidget(self.export_btn)
        main_layout.addLayout(button_layout)
        
        main_layout.addStretch(1)
        self.load_data()

    def _create_hazard_group(self):
        lm = self.language_manager
        self.hazard_group = QGroupBox(lm.translate("Tunnel Environment Handling"))
        layout = QGridLayout(self.hazard_group)
        
        # Radio buttons for calculation method
        self.handling_method_label = QLabel(lm.translate("Handling Method:"))
        layout.addWidget(self.handling_method_label, 0, 0)
        self.calc_method_group = QButtonGroup()
        self.by_equation = QRadioButton(lm.translate("by Equation"))
        self.by_mdb = QRadioButton(lm.translate("by MDB"))
        self.calc_method_group.addButton(self.by_equation, 1)
        self.calc_method_group.addButton(self.by_mdb, 2)
        self.by_equation.setChecked(True)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.by_equation)
        h_layout.addWidget(self.by_mdb)
        layout.addLayout(h_layout, 0, 1, 1, 2)
        
        # Fire characteristics inputs
        self.design_fire_label = QLabel(lm.translate("Design Fire Intensity:"))
        layout.addWidget(self.design_fire_label, 1, 0)
        self.hrr_input = QLineEdit("20")
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(self.hrr_input)
        h_layout1.addWidget(QLabel("(MW)"))
        layout.addLayout(h_layout1, 1, 1)
        
        self.growth_rate_label = QLabel(lm.translate("Growth Rate:"))
        layout.addWidget(self.growth_rate_label, 1, 2)
        self.growth_rate_input = QLineEdit("0.15")
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.growth_rate_input)
        h_layout2.addWidget(QLabel("(kW/s²)"))
        layout.addLayout(h_layout2, 1, 3)
        
        self.target_layer_label = QLabel(lm.translate("Target Layer:"))
        layout.addWidget(self.target_layer_label, 1, 4)
        self.target_layer_input = QLineEdit("0.001")
        h_layout3 = QHBoxLayout()
        h_layout3.addWidget(self.target_layer_input)
        h_layout3.addWidget(QLabel("(m)"))
        layout.addLayout(h_layout3, 1, 5)
        
        # Second row
        self.total_heat_label = QLabel(lm.translate("Total Heat Energy:"))
        layout.addWidget(self.total_heat_label, 2, 0)
        self.complete_layer_input = QLineEdit("0.001")
        h_layout4 = QHBoxLayout()
        h_layout4.addWidget(self.complete_layer_input)
        h_layout4.addWidget(QLabel("(GJ)"))
        layout.addLayout(h_layout4, 2, 1)
        
        return self.hazard_group

    def _create_fire_group(self):
        lm = self.language_manager
        self.fire_group = QGroupBox(lm.translate("Fire Growth Curve"))
        layout = QGridLayout(self.fire_group)
        
        # Heat Release Rate
        self.fire_design_fire_label = QLabel(lm.translate("Design Fire Intensity:"))
        layout.addWidget(self.fire_design_fire_label, 0, 0)
        self.hrr_display = QLineEdit("20")
        self.hrr_display.setReadOnly(True)
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(self.hrr_display)
        h_layout1.addWidget(QLabel("(MW)"))
        layout.addLayout(h_layout1, 0, 1)
        
        # Growth Rate
        self.fire_growth_rate_label = QLabel(lm.translate("Growth Rate:"))
        layout.addWidget(self.fire_growth_rate_label, 1, 0)
        self.growth_rate_display = QLineEdit("0.15")
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.growth_rate_display)
        h_layout2.addWidget(QLabel("(kW/s²)"))
        layout.addLayout(h_layout2, 1, 1)
        
        # Add a simple chart area (placeholder)
        layout.addWidget(QLabel(""), 2, 0, 3, 3)  # Space for future chart
        
        return self.fire_group

    def _create_evac_char_group(self):
        lm = self.language_manager
        self.evac_char_group = QGroupBox(lm.translate("Evacuation Safety"))
        layout = QGridLayout(self.evac_char_group)
        
        # Visibility Limit
        self.evac_visibility_limit_label = QLabel(lm.translate("Design Fire Intensity:"))
        layout.addWidget(self.evac_visibility_limit_label, 0, 0)
        self.visibility_input = QLineEdit("20")
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(self.visibility_input)
        h_layout1.addWidget(QLabel("(MW)"))
        layout.addLayout(h_layout1, 0, 1)
        
        # Temperature Limit
        self.evac_temp_limit_label = QLabel(lm.translate("Growth Rate:"))
        layout.addWidget(self.evac_temp_limit_label, 1, 0)
        self.temp_input = QLineEdit("0.15")
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.temp_input)
        h_layout2.addWidget(QLabel("(kW/s²)"))
        layout.addLayout(h_layout2, 1, 1)
        
        # CO Limit
        self.evac_co_limit_label = QLabel(lm.translate("Target Layer:"))
        layout.addWidget(self.evac_co_limit_label, 2, 0)
        self.co_input = QLineEdit("0.001")
        h_layout3 = QHBoxLayout()
        h_layout3.addWidget(self.co_input)
        h_layout3.addWidget(QLabel("(m)"))
        layout.addLayout(h_layout3, 2, 1)
        
        return self.evac_char_group

    def _create_evac_timing_group(self):
        lm = self.language_manager
        self.evac_timing_group = QGroupBox(lm.translate("Evacuation Timing and Speed"))
        layout = QGridLayout(self.evac_timing_group)
        
        # Reaction Time
        self.evac_time_label = QLabel(lm.translate("Evacuation Time:"))
        layout.addWidget(self.evac_time_label, 0, 0)
        self.reaction_time_input = QLineEdit("180")
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(self.reaction_time_input)
        self.evac_time_unit = QLabel("(sec)")
        h_layout1.addWidget(self.evac_time_unit)
        layout.addLayout(h_layout1, 0, 1)
        
        self.waiting_time_label = QLabel(lm.translate("Waiting Time:"))
        layout.addWidget(self.waiting_time_label, 0, 2)
        self.hesitation_time_input = QLineEdit("60")
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.hesitation_time_input)
        self.waiting_time_unit = QLabel("(sec)")
        h_layout2.addWidget(self.waiting_time_unit)
        layout.addLayout(h_layout2, 0, 3)
        
        self.contact_time_label = QLabel(lm.translate("Contact Time:"))
        layout.addWidget(self.contact_time_label, 0, 4)
        self.contact_time_input = QLineEdit("180")
        h_layout3 = QHBoxLayout()
        h_layout3.addWidget(self.contact_time_input)
        self.contact_time_unit = QLabel("(sec)")
        h_layout3.addWidget(self.contact_time_unit)
        layout.addLayout(h_layout3, 0, 5)
        
        # Evacuation speeds
        self.min_evac_speed_label = QLabel(lm.translate("Minimum Evacuation Speed:"))
        layout.addWidget(self.min_evac_speed_label, 1, 0)
        self.min_evac_speed = QLineEdit("0.45")
        h_layout4 = QHBoxLayout()
        h_layout4.addWidget(self.min_evac_speed)
        self.min_evac_speed_unit = QLabel("(m/s)")
        h_layout4.addWidget(self.min_evac_speed_unit)
        layout.addLayout(h_layout4, 1, 1)
        
        self.elderly_evac_speed_label = QLabel(lm.translate("Elderly Evacuation Speed:"))
        layout.addWidget(self.elderly_evac_speed_label, 1, 2)
        self.elderly_evac_speed = QLineEdit("0.6")
        h_layout5 = QHBoxLayout()
        h_layout5.addWidget(self.elderly_evac_speed)
        self.elderly_evac_speed_unit = QLabel("(m/s)")
        h_layout5.addWidget(self.elderly_evac_speed_unit)
        layout.addLayout(h_layout5, 1, 3)
        
        self.elderly_factor_label = QLabel(lm.translate("Elderly Factor (IDahl):"))
        layout.addWidget(self.elderly_factor_label, 1, 4)
        self.elderly_factor = QLineEdit("0.4")
        h_layout6 = QHBoxLayout()
        h_layout6.addWidget(self.elderly_factor)
        self.elderly_factor_unit = QLabel("(-)")
        h_layout6.addWidget(self.elderly_factor_unit)
        layout.addLayout(h_layout6, 1, 5)
        
        # Checkboxes for conditions
        self.condition_review_label = QLabel(lm.translate("Evacuee Environment Condition Review:"))
        layout.addWidget(self.condition_review_label, 2, 0, 1, 6)
        
        self.reaction_time_check = QCheckBox(lm.translate("Reaction Time"))
        self.hesitation_time_check = QCheckBox(lm.translate("Time for Leave Car"))
        self.visibility_check = QCheckBox(lm.translate("Visibility"))
        self.temperature_check = QCheckBox(lm.translate("Temperature"))
        self.smoke_check = QCheckBox(lm.translate("Smoke"))
        
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.reaction_time_check)
        h_layout.addWidget(self.hesitation_time_check)
        h_layout.addWidget(self.visibility_check)
        h_layout.addWidget(self.temperature_check)
        h_layout.addWidget(self.smoke_check)
        layout.addLayout(h_layout, 3, 0, 1, 6)
        
        return self.evac_timing_group

    def get_data(self):
        """Extracts data from the UI elements with safe parsing."""
        try:
            return {
                "hazard_calculation_method": "by Equation" if self.by_equation.isChecked() else "by MDB",
                "heat_release_rate": float(self.hrr_input.text()),
                "fire_growth_rate": float(self.growth_rate_input.text()),
            }
        except ValueError as e:
            QMessageBox.critical(self, "Input Error", f"Invalid input value. Error: {e}")
            return None

    def set_data(self, har_evac_config):
        """Populates the UI elements with data from the database models."""
        self.hrr_input.setText(str(har_evac_config.heat_release_rate))
        self.growth_rate_input.setText(str(har_evac_config.fire_growth_rate))

    def load_data(self):
        """Loads data from the database and populates the UI."""
        pass
            
    def save_data(self):
        """Extracts data from the UI and saves it to the database."""
        pass
        #     self.data_manager.save_har_evac_data(data)
        pass    
    def _on_language_changed(self, language_code: str):
        """Handle language change event."""
        lm = self.language_manager
        
        # Update group box titles
        if hasattr(self, 'hazard_group'):
            self.hazard_group.setTitle(lm.translate("Tunnel Environment Handling"))
        if hasattr(self, 'fire_group'):
            self.fire_group.setTitle(lm.translate("Fire Growth Curve"))
        if hasattr(self, 'evac_char_group'):
            self.evac_char_group.setTitle(lm.translate("Evacuation Safety"))
        
        # Update labels
        if hasattr(self, 'handling_method_label'):
            self.handling_method_label.setText(lm.translate("Handling Method:"))
        if hasattr(self, 'by_equation'):
            self.by_equation.setText(lm.translate("by Equation"))
        if hasattr(self, 'by_mdb'):
            self.by_mdb.setText(lm.translate("by MDB"))

        if hasattr(self, 'design_fire_label'):
            self.design_fire_label.setText(lm.translate("Design Fire Intensity:"))
        if hasattr(self, 'growth_rate_label'):
            self.growth_rate_label.setText(lm.translate("Growth Rate:"))
        if hasattr(self, 'target_layer_label'):
            self.target_layer_label.setText(lm.translate("Target Layer:"))
        if hasattr(self, 'total_heat_label'):
            self.total_heat_label.setText(lm.translate("Total Heat Energy:"))
        if hasattr(self, 'fire_design_fire_label'):
            self.fire_design_fire_label.setText(lm.translate("Design Fire Intensity:"))
        if hasattr(self, 'fire_growth_rate_label'):
            self.fire_growth_rate_label.setText(lm.translate("Growth Rate:"))
        if hasattr(self, 'evac_visibility_limit_label'):
            self.evac_visibility_limit_label.setText(lm.translate("Design Fire Intensity:"))
        if hasattr(self, 'evac_temp_limit_label'):
            self.evac_temp_limit_label.setText(lm.translate("Growth Rate:"))
        if hasattr(self, 'evac_co_limit_label'):
            self.evac_co_limit_label.setText(lm.translate("Target Layer:"))

        if hasattr(self, 'evac_timing_group'):
            self.evac_timing_group.setTitle(lm.translate("Evacuation Timing and Speed"))
        if hasattr(self, 'evac_time_label'):
            self.evac_time_label.setText(lm.translate("Evacuation Time:"))
        if hasattr(self, 'waiting_time_label'):
            self.waiting_time_label.setText(lm.translate("Waiting Time:"))
        if hasattr(self, 'contact_time_label'):
            self.contact_time_label.setText(lm.translate("Contact Time:"))
        if hasattr(self, 'min_evac_speed_label'):
            self.min_evac_speed_label.setText(lm.translate("Minimum Evacuation Speed:"))
        if hasattr(self, 'elderly_evac_speed_label'):
            self.elderly_evac_speed_label.setText(lm.translate("Elderly Evacuation Speed:"))
        if hasattr(self, 'elderly_factor_label'):
            self.elderly_factor_label.setText(lm.translate("Elderly Factor (IDahl):"))

        if hasattr(self, 'condition_review_label'):
            self.condition_review_label.setText(lm.translate("Evacuee Environment Condition Review:"))
        if hasattr(self, 'reaction_time_check'):
            self.reaction_time_check.setText(lm.translate("Reaction Time"))
        if hasattr(self, 'hesitation_time_check'):
            self.hesitation_time_check.setText(lm.translate("Time for Leave Car"))
        if hasattr(self, 'visibility_check'):
            self.visibility_check.setText(lm.translate("Visibility"))
        if hasattr(self, 'temperature_check'):
            self.temperature_check.setText(lm.translate("Temperature"))
        if hasattr(self, 'smoke_check'):
            self.smoke_check.setText(lm.translate("Smoke"))
        
        if hasattr(self, 'hrr_max_label'):
            self.hrr_max_label.setText(lm.translate("HRR Max:"))
        if hasattr(self, 'steady_label'):
            self.steady_label.setText(lm.translate("Steady:"))
        if hasattr(self, 'decay_label'):
            self.decay_label.setText(lm.translate("Decay:"))
        
        if hasattr(self, 'aset_criteria_label'):
            self.aset_criteria_label.setText(lm.translate("ASET Criteria:"))
        if hasattr(self, 'temperature_label'):
            self.temperature_label.setText(lm.translate("Temperature:"))
        if hasattr(self, 'co_concentration_label'):
            self.co_concentration_label.setText(lm.translate("CO Concentration:"))
        if hasattr(self, 'visibility_label'):
            self.visibility_label.setText(lm.translate("Visibility:"))
        
        # Update button
        if hasattr(self, 'export_btn'):
            self.export_btn.setText(lm.translate("Export Data"))