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
        group = QGroupBox(lm.translate("Tunnel Environment Handling"))
        layout = QGridLayout(group)
        
        # Radio buttons for calculation method
        layout.addWidget(QLabel(lm.translate("Handling Method:")), 0, 0)
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
        layout.addWidget(QLabel(lm.translate("Design Fire Intensity:")), 1, 0)
        self.hrr_input = QLineEdit("20")
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(self.hrr_input)
        h_layout1.addWidget(QLabel("(MW)"))
        layout.addLayout(h_layout1, 1, 1)
        
        layout.addWidget(QLabel(lm.translate("Growth Rate:")), 1, 2)
        self.growth_rate_input = QLineEdit("0.15")
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.growth_rate_input)
        h_layout2.addWidget(QLabel("(kW/s²)"))
        layout.addLayout(h_layout2, 1, 3)
        
        layout.addWidget(QLabel(lm.translate("Target Layer:")), 1, 4)
        self.target_layer_input = QLineEdit("0.001")
        h_layout3 = QHBoxLayout()
        h_layout3.addWidget(self.target_layer_input)
        h_layout3.addWidget(QLabel("(m)"))
        layout.addLayout(h_layout3, 1, 5)
        
        # Second row
        layout.addWidget(QLabel(lm.translate("Total Heat Energy:")), 2, 0)
        self.complete_layer_input = QLineEdit("0.001")
        h_layout4 = QHBoxLayout()
        h_layout4.addWidget(self.complete_layer_input)
        h_layout4.addWidget(QLabel("(GJ)"))
        layout.addLayout(h_layout4, 2, 1)
        
        return group

    def _create_fire_group(self):
        lm = self.language_manager
        group = QGroupBox(lm.translate("Fire Growth Curve"))
        layout = QGridLayout(group)
        
        # Heat Release Rate
        layout.addWidget(QLabel(lm.translate("Design Fire Intensity:")), 0, 0)
        self.hrr_display = QLineEdit("20")
        self.hrr_display.setReadOnly(True)
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(self.hrr_display)
        h_layout1.addWidget(QLabel("(MW)"))
        layout.addLayout(h_layout1, 0, 1)
        
        # Growth Rate
        layout.addWidget(QLabel(lm.translate("Growth Rate:")), 1, 0)
        self.growth_rate_display = QLineEdit("0.15")
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.growth_rate_display)
        h_layout2.addWidget(QLabel("(kW/s²)"))
        layout.addLayout(h_layout2, 1, 1)
        
        # Add a simple chart area (placeholder)
        layout.addWidget(QLabel(""), 2, 0, 3, 3)  # Space for future chart
        
        return group

    def _create_evac_char_group(self):
        lm = self.language_manager
        group = QGroupBox(lm.translate("Evacuation Safety"))
        layout = QGridLayout(group)
        
        # Visibility Limit
        layout.addWidget(QLabel(lm.translate("Design Fire Intensity:")), 0, 0)
        self.visibility_input = QLineEdit("20")
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(self.visibility_input)
        h_layout1.addWidget(QLabel("(MW)"))
        layout.addLayout(h_layout1, 0, 1)
        
        # Temperature Limit
        layout.addWidget(QLabel(lm.translate("Growth Rate:")), 1, 0)
        self.temp_input = QLineEdit("0.15")
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.temp_input)
        h_layout2.addWidget(QLabel("(kW/s²)"))
        layout.addLayout(h_layout2, 1, 1)
        
        # CO Limit
        layout.addWidget(QLabel(lm.translate("Target Layer:")), 2, 0)
        self.co_input = QLineEdit("0.001")
        h_layout3 = QHBoxLayout()
        h_layout3.addWidget(self.co_input)
        h_layout3.addWidget(QLabel("(m)"))
        layout.addLayout(h_layout3, 2, 1)
        
        return group

    def _create_evac_timing_group(self):
        group = QGroupBox("Evacuation Timing and Speed")  # Evacuation timing and speed
        layout = QGridLayout(group)
        
        # Reaction Time
        layout.addWidget(QLabel("Evacuation Time:"), 0, 0)
        self.reaction_time_input = QLineEdit("180")
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(self.reaction_time_input)
        h_layout1.addWidget(QLabel("(sec)"))
        layout.addLayout(h_layout1, 0, 1)
        
        layout.addWidget(QLabel("Waiting Time:"), 0, 2)
        self.hesitation_time_input = QLineEdit("60")
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(self.hesitation_time_input)
        h_layout2.addWidget(QLabel("(sec)"))
        layout.addLayout(h_layout2, 0, 3)
        
        layout.addWidget(QLabel("Contact Time:"), 0, 4)
        self.contact_time_input = QLineEdit("180")
        h_layout3 = QHBoxLayout()
        h_layout3.addWidget(self.contact_time_input)
        h_layout3.addWidget(QLabel("(sec)"))
        layout.addLayout(h_layout3, 0, 5)
        
        # Evacuation speeds
        layout.addWidget(QLabel("Minimum Evacuation Speed:"), 1, 0)
        self.min_evac_speed = QLineEdit("0.45")
        h_layout4 = QHBoxLayout()
        h_layout4.addWidget(self.min_evac_speed)
        h_layout4.addWidget(QLabel("(m/s)"))
        layout.addLayout(h_layout4, 1, 1)
        
        layout.addWidget(QLabel("Elderly Evacuation Speed:"), 1, 2)
        self.elderly_evac_speed = QLineEdit("0.6")
        h_layout5 = QHBoxLayout()
        h_layout5.addWidget(self.elderly_evac_speed)
        h_layout5.addWidget(QLabel("(m/s)"))
        layout.addLayout(h_layout5, 1, 3)
        
        layout.addWidget(QLabel("Elderly Factor (IDahl):"), 1, 4)
        self.elderly_factor = QLineEdit("0.4")
        h_layout6 = QHBoxLayout()
        h_layout6.addWidget(self.elderly_factor)
        h_layout6.addWidget(QLabel("(-)"))
        layout.addLayout(h_layout6, 1, 5)
        
        # Checkboxes for conditions
        layout.addWidget(QLabel("Evacuee Environment Condition Review:"), 2, 0, 1, 6)
        
        self.reaction_time_check = QCheckBox("Reaction Time")
        self.hesitation_time_check = QCheckBox("Time for Leave Car")
        self.visibility_check = QCheckBox("Visibility")
        self.temperature_check = QCheckBox("Temperature")
        self.smoke_check = QCheckBox("Smoke")
        
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.reaction_time_check)
        h_layout.addWidget(self.hesitation_time_check)
        h_layout.addWidget(self.visibility_check)
        h_layout.addWidget(self.temperature_check)
        h_layout.addWidget(self.smoke_check)
        layout.addLayout(h_layout, 3, 0, 1, 6)
        
        return group

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
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QGroupBox):
                if "Tunnel Environment" in widget.title():
                    widget.setTitle(lm.translate("Tunnel Environment Handling"))
                elif "Fire Growth" in widget.title():
                    widget.setTitle(lm.translate("Fire Growth Curve"))
                elif "Evacuation Safety" in widget.title():
                    widget.setTitle(lm.translate("Evacuation Safety"))
                elif "Evacuation Timing" in widget.title():
                    widget.setTitle(lm.translate("Evacuation Timing and Speed"))