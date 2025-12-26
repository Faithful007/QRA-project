from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit, QPushButton, 
    QComboBox, QGridLayout, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QRadioButton, QButtonGroup, QMessageBox
)
from PyQt6.QtCore import Qt
from src.database.data_manager import DataManager
from src.language_manager import get_language_manager

class MDBDatabaseCreationTab(QWidget):
    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.language_manager = get_language_manager()
        
        # Connect to language change signal
        self.language_manager.language_changed.connect(self._on_language_changed)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Top section: Database Set and DB Create/Import buttons
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._create_db_set_group(), 1)
        
        lm = self.language_manager
        button_group = QGroupBox("")
        button_layout = QVBoxLayout(button_group)
        self.db_create_btn = QPushButton(lm.translate("DB Create"))
        self.db_create_btn.setFixedHeight(40)
        self.db_import_btn = QPushButton(lm.translate("DB Import"))
        self.db_import_btn.setFixedHeight(40)
        button_layout.addWidget(self.db_create_btn)
        button_layout.addWidget(self.db_import_btn)
        top_layout.addWidget(button_group, 0)
        
        main_layout.addLayout(top_layout)
        
        # MDB File selection section
        main_layout.addWidget(self._create_mdb_file_section())
        
        # FDS Settings section
        main_layout.addWidget(self._create_fds_settings_group())
        
        # Bottom control buttons
        button_layout = QHBoxLayout()
        self.make_batch_btn = QPushButton(lm.translate("Make Batch File n Run"))
        self.command_btn = QPushButton(lm.translate("Command"))
        button_layout.addWidget(self.make_batch_btn)
        button_layout.addWidget(self.command_btn)
        button_layout.addStretch(1)
        main_layout.addLayout(button_layout)
        
        # Status message
        main_layout.addWidget(QLabel(lm.translate("!!! Simulation End !!!")))
        
        main_layout.addStretch(1)
        self.load_data()

    def _create_db_set_group(self):
        lm = self.language_manager
        self.db_set_group = QGroupBox(lm.translate("DB Set"))
        layout = QGridLayout(self.db_set_group)
        
        # Type selection
        self.source_selection_label = QLabel(lm.translate("Source Selection"))
        layout.addWidget(self.source_selection_label, 0, 0)
        self.type_group = QButtonGroup()
        self.type1 = QRadioButton(lm.translate("TYPE1"))
        self.type2 = QRadioButton(lm.translate("TYPE2"))
        self.type_group.addButton(self.type1, 1)
        self.type_group.addButton(self.type2, 2)
        self.type2.setChecked(True)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.type1)
        h_layout.addWidget(self.type2)
        layout.addLayout(h_layout, 0, 1)
        
        # Chemical properties table
        self.chem_table = QTableWidget(2, 8)
        headers = [lm.translate("CFDIDX"), lm.translate("VALUE"), lm.translate("Soot"), 
               lm.translate("CO2"), lm.translate("CO"), lm.translate("Temp"), 
               lm.translate("Radiation"), lm.translate("Oxygen")]
        self.chem_table.setHorizontalHeaderLabels(headers)
        
        # Row 1: CFDIDX
        self.chem_table.setItem(0, 0, QTableWidgetItem("CFDIDX"))
        self.chem_table.setItem(0, 1, QTableWidgetItem("0"))
        self.chem_table.setItem(0, 2, QTableWidgetItem("0"))
        self.chem_table.setItem(0, 3, QTableWidgetItem("0"))
        self.chem_table.setItem(0, 4, QTableWidgetItem("0"))
        self.chem_table.setItem(0, 5, QTableWidgetItem("0"))
        
        # Row 2: CNV_FAC
        self.chem_table.setItem(1, 0, QTableWidgetItem("CNV_FAC"))
        self.chem_table.setItem(1, 1, QTableWidgetItem("1000000"))
        self.chem_table.setItem(1, 2, QTableWidgetItem("100"))
        self.chem_table.setItem(1, 3, QTableWidgetItem("1000000"))
        self.chem_table.setItem(1, 4, QTableWidgetItem("1"))
        self.chem_table.setItem(1, 5, QTableWidgetItem("0.25"))
        
        self.chem_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.chem_table, 1, 0, 1, 2)
        
        return self.db_set_group

    def _create_mdb_file_section(self):
        lm = self.language_manager
        self.mdb_file_group = QGroupBox(lm.translate("MDB File Selection"))
        layout = QGridLayout(self.mdb_file_group)
        
        # Drive selection
        self.drive_label = QLabel("C:")
        layout.addWidget(self.drive_label, 0, 0)
        self.drive_combo = QComboBox()
        self.drive_combo.addItems(["C:", "D:", "E:"])
        layout.addWidget(self.drive_combo, 0, 1)
        
        # File tree/list
        self.index_file_label = QLabel(lm.translate("Index File Name"))
        layout.addWidget(self.index_file_label, 0, 2)
        self.mdb_file_label = QLabel(lm.translate("MDB File"))
        layout.addWidget(self.mdb_file_label, 0, 3)
        self.status_label = QLabel(lm.translate("Status"))
        layout.addWidget(self.status_label, 0, 4)
        
        # Folder tree (placeholder)
        self.folder_tree = QTableWidget(5, 2)
        self.folder_tree.setColumnCount(1)
        self.folder_tree.setHorizontalHeaderLabels([lm.translate("Files")])
        self.folder_tree.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.folder_tree, 1, 0, 4, 2)
        
        # File list table
        self.file_list = QTableWidget(0, 4)
        self.file_list.setHorizontalHeaderLabels(["#", lm.translate("Index File Name"), lm.translate("MDB File"), lm.translate("Status")])
        self.file_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.file_list, 1, 2, 4, 3)
        
        return self.mdb_file_group

    def _create_fds_settings_group(self):
        lm = self.language_manager
        self.fds_settings_group = QGroupBox(lm.translate("FDS File Settings"))
        layout = QGridLayout(self.fds_settings_group)
        
        self.fds_time_interval_label = QLabel(lm.translate("FDS SLF Time Interval"))
        layout.addWidget(self.fds_time_interval_label, 0, 0)
        self.fds_time_interval = QLineEdit()
        layout.addWidget(self.fds_time_interval, 0, 1)
        
        self.fds_id_label = QLabel(lm.translate("FDS ID / Tunnel Axis Dir."))
        layout.addWidget(self.fds_id_label, 1, 0)
        self.fds_id = QLineEdit()
        self.tunnel_axis = QLineEdit()
        layout.addWidget(self.fds_id, 1, 1)
        layout.addWidget(self.tunnel_axis, 1, 2)
        
        self.fds_last_time_label = QLabel(lm.translate("FDS SLF Last Time"))
        layout.addWidget(self.fds_last_time_label, 2, 0)
        self.fds_last_time = QLineEdit()
        layout.addWidget(self.fds_last_time, 2, 1)
        
        return self.fds_settings_group

    def _browse_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            line_edit.setText(file_path)

    def load_data(self):
        pass

    def save_data(self):
        pass
    
    def _on_language_changed(self, language_code: str):
        """Handle language change event."""
        lm = self.language_manager
        
        # Update group box titles
        if hasattr(self, 'db_set_group'):
            self.db_set_group.setTitle(lm.translate("DB Set"))
        if hasattr(self, 'mdb_file_group'):
            self.mdb_file_group.setTitle(lm.translate("MDB File Selection"))
        if hasattr(self, 'fds_settings_group'):
            self.fds_settings_group.setTitle(lm.translate("FDS File Settings"))
        
        # Update labels
        if hasattr(self, 'source_selection_label'):
            self.source_selection_label.setText(lm.translate("Source Selection"))
        if hasattr(self, 'index_file_label'):
            self.index_file_label.setText(lm.translate("Index File Name"))
        if hasattr(self, 'mdb_file_label'):
            self.mdb_file_label.setText(lm.translate("MDB File"))
        if hasattr(self, 'status_label'):
            self.status_label.setText(lm.translate("Status"))
        if hasattr(self, 'fds_time_interval_label'):
            self.fds_time_interval_label.setText(lm.translate("FDS SLF Time Interval"))
        if hasattr(self, 'fds_id_label'):
            self.fds_id_label.setText(lm.translate("FDS ID / Tunnel Axis Dir."))
        if hasattr(self, 'fds_last_time_label'):
            self.fds_last_time_label.setText(lm.translate("FDS SLF Last Time"))
        
        # Update buttons
        if hasattr(self, 'db_create_btn'):
            self.db_create_btn.setText(lm.translate("DB Create"))
        if hasattr(self, 'db_import_btn'):
            self.db_import_btn.setText(lm.translate("DB Import"))
        if hasattr(self, 'make_batch_btn'):
            self.make_batch_btn.setText(lm.translate("Make Batch File n Run"))
        if hasattr(self, 'command_btn'):
            self.command_btn.setText(lm.translate("Command"))
        
        # Update combo box items
        if hasattr(self, 'type1'):
            self.type1.setText(lm.translate("TYPE1"))
        if hasattr(self, 'type2'):
            self.type2.setText(lm.translate("TYPE2"))
        
        # Update table headers
        if hasattr(self, 'chem_table'):
            self.chem_table.setHorizontalHeaderItem(0, QTableWidgetItem(lm.translate("CFDIDX")))
            self.chem_table.setHorizontalHeaderItem(1, QTableWidgetItem(lm.translate("VALUE")))
            self.chem_table.setHorizontalHeaderItem(2, QTableWidgetItem(lm.translate("Soot")))
            self.chem_table.setHorizontalHeaderItem(3, QTableWidgetItem(lm.translate("CO2")))
            self.chem_table.setHorizontalHeaderItem(4, QTableWidgetItem(lm.translate("CO")))
            self.chem_table.setHorizontalHeaderItem(5, QTableWidgetItem(lm.translate("Temp")))
            self.chem_table.setHorizontalHeaderItem(6, QTableWidgetItem(lm.translate("Radiation")))
            self.chem_table.setHorizontalHeaderItem(7, QTableWidgetItem(lm.translate("Oxygen")))
