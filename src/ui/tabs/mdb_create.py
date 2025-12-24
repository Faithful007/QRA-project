from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox, QGridLayout, QFileDialog
from src.database.data_manager import DataManager

class MDBDatabaseCreationTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.layout = QVBoxLayout(self)
        
        # 1. EVC File Generation Group (New Focus)
        self.layout.addWidget(self._create_evc_generation_group())
        
        # 2. Database Type Group
        self.layout.addWidget(self._create_database_type_group())
        
        # 3. Chemical Properties Group
        self.layout.addWidget(self._create_chemical_properties_group())
        
        # 4. FDS File Settings Group
        self.layout.addWidget(self._create_fds_settings_group())
        
        # 5. File Management Buttons
        self.layout.addLayout(self._create_file_management_buttons())
        
        self.layout.addStretch(1)
        
        self.load_data()

    def _create_evc_generation_group(self):
        group = QGroupBox("EVC File Generation (EVC/FDB Location & Vehicle Scope)")
        layout = QGridLayout(group)
        
        # Row 1: Sample EVC File
        layout.addWidget(QLabel("Sample EVC File:"), 0, 0)
        self.sample_evc_path = QLineEdit("/path/to/sample/evc.txt")
        layout.addWidget(self.sample_evc_path, 0, 1)
        self.browse_evc_btn = QPushButton("Browse")
        self.browse_evc_btn.clicked.connect(lambda: self._browse_file(self.sample_evc_path))
        layout.addWidget(self.browse_evc_btn, 0, 2)
        
        # Row 2: Vehicle Type Options (Small Vehicles Only / All Vehicles)
        layout.addWidget(QLabel("Vehicle Type Scope:"), 1, 0)
        self.vehicle_scope_combo = QComboBox()
        # MUST have 4 options for small vehicles, 3+ for all vehicles
        self.vehicle_scope_combo.addItems([
            "Small Vehicles Only (Option 1)", "Small Vehicles Only (Option 2)", 
            "Small Vehicles Only (Option 3)", "Small Vehicles Only (Option 4)",
            "All Vehicles (Option A)", "All Vehicles (Option B)", "All Vehicles (Option C)",
            "All Vehicles (Option D)", "All Vehicles (Option E)", "All Vehicles (Option F)"
        ])
        self.vehicle_scope_combo.currentTextChanged.connect(self.save_data)
        layout.addWidget(self.vehicle_scope_combo, 1, 1, 1, 2)
        
        # Row 3: MDB Pt X (FDB Location)
        layout.addWidget(QLabel("MDB Pt X (FDB Location):"), 2, 0)
        self.mdb_pt_x = QLineEdit("100.0")
        self.mdb_pt_x.editingFinished.connect(self.save_data)
        layout.addWidget(self.mdb_pt_x, 2, 1)
        
        # Row 4: Fire Pt X (EVC Location)
        layout.addWidget(QLabel("Fire Pt X (EVC Location):"), 3, 0)
        self.fire_pt_x = QLineEdit("100.0")
        self.fire_pt_x.editingFinished.connect(self.save_data)
        layout.addWidget(self.fire_pt_x, 3, 1)
        
        # Row 5: Generate Button
        self.generate_evc_btn = QPushButton("Generate EVC File Set")
        self.generate_evc_btn.setStyleSheet("font-weight: bold; background-color: #ccf;")
        # self.generate_evc_btn.clicked.connect(self._generate_evc_files) # Logic to be implemented later
        layout.addWidget(self.generate_evc_btn, 4, 0, 1, 3)
     
        return group

    def _create_database_type_group(self):
        # TODO: build database type UI elements
        return QGroupBox("Database Type")

    def _create_chemical_properties_group(self):
        group = QGroupBox("Chemical Properties")
        layout = QGridLayout(group)
        # Placeholder controls
        layout.addWidget(QLabel("Chemical:"), 0, 0)
        self.chemical_name = QLineEdit()
        self.chemical_name.editingFinished.connect(self.save_data)
        layout.addWidget(self.chemical_name, 0, 1)
        layout.addWidget(QLabel("Heat of Combustion (MJ/kg):"), 1, 0)
        self.heat_of_combustion = QLineEdit()
        self.heat_of_combustion.editingFinished.connect(self.save_data)
        layout.addWidget(self.heat_of_combustion, 1, 1)
        return group

    def _create_fds_settings_group(self):
        group = QGroupBox("FDS File Settings")
        layout = QGridLayout(group)
        layout.addWidget(QLabel("FDS Template File:"), 0, 0)
        self.fds_template_path = QLineEdit()
        layout.addWidget(self.fds_template_path, 0, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(lambda: self._browse_file(self.fds_template_path))
        layout.addWidget(browse_btn, 0, 2)
        return group

    def _create_file_management_buttons(self):
        layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_data)
        export_btn = QPushButton("Export Files")
        # export_btn.clicked.connect(self._export_files)  # Implement when ready
        layout.addWidget(save_btn)
        layout.addWidget(export_btn)
        layout.addStretch(1)
        return layout

    def _browse_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            line_edit.setText(file_path)

    def _generate_evc_files(self):
        # This method will orchestrate the EVC file generation
        # 1. Load data from Tunnel, Traffic, HAR EVAC tabs (via DataManager)
        # 2. Use MDB Pt X and Fire Pt X
        # 3. Use Vehicle Scope
        # 4. Generate EVC files based on the sample template
        print("Generating EVC files...")
        # Placeholder for actual generation logic
        pass

    def load_data(self):
        # Placeholder load hook until persistence is implemented
        pass

    def save_data(self):
        # Save MDB settings (paths, options) to the database
        print("Saving MDB Database Creation tab data...")
        # Placeholder for actual save logic
        pass
