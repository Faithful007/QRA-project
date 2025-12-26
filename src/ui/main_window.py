from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, QLabel, QLineEdit, QGridLayout, QGroupBox, QMenuBar, QMenu, QStatusBar, QComboBox
from PyQt6.QtCore import Qt, QSize
from src.ui.tabs.tunnel_settings import TunnelSettingsTab
from src.ui.tabs.traffic_management import TrafficManagementTab
from src.ui.tabs.har_evac import HAREVACAnalysisTab
from src.ui.tabs.simulation import SimulationSettingsTab
from src.ui.tabs.mdb_create import MDBDatabaseCreationTab
from src.database.data_manager import DataManager
from src.logic import QRACalculator
from src.database.connection import get_session
from src.language_manager import get_language_manager

class MainControlWindow(QMainWindow):
    """
    The separate Main Control panel as described in the specification.
    This is a separate QMainWindow instance.
    """
    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.language_manager = get_language_manager()
        
        # Connect to language change signal
        self.language_manager.language_changed.connect(self._on_language_changed)
        
        lm = self.language_manager
        self.setWindowTitle(lm.translate("QRA Main Control"))
        self.setGeometry(100, 100, 350, 450)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)
        
        # 1. Top Control Buttons
        top_group = QGroupBox(lm.translate("Top Controls"))
        top_layout = QHBoxLayout(top_group)
        self.sim_btn = QPushButton(lm.translate("Simulation"))
        self.result_btn = QPushButton(lm.translate("Result Analysis"))
        self.mdb_btn = QPushButton(lm.translate("Data_MDB File Set"))
        top_layout.addWidget(self.sim_btn)
        top_layout.addWidget(self.result_btn)
        top_layout.addWidget(self.mdb_btn)
        self.layout.addWidget(top_group)

        # Connect Simulation button
        self.sim_btn.clicked.connect(self._run_simulation)
        self.result_btn.clicked.connect(self._show_qra_results)
        self.mdb_btn.clicked.connect(self._show_main_window)

        # 2. Simulation Control
        sim_group = QGroupBox(lm.translate("Simulation Control"))
        sim_layout = QGridLayout(sim_group)
        sim_layout.addWidget(QLabel(lm.translate("Simulation Status:")), 0, 0)
        self.status_label = QLabel(lm.translate("Idle"))
        sim_layout.addWidget(self.status_label, 0, 1)
        
        # New QRA Result Display
        sim_layout.addWidget(QLabel(lm.translate("Risk Status:")), 3, 0)
        self.risk_status_label = QLabel(lm.translate("N/A"))
        sim_layout.addWidget(self.risk_status_label, 3, 1)
        sim_layout.addWidget(QLabel(lm.translate("Improvement Req.:")), 4, 0)
        self.improvement_label = QLabel(lm.translate("N/A"))
        sim_layout.addWidget(self.improvement_label, 4, 1)
        
        self.cancel_btn = QPushButton(lm.translate("Cancel"))
        self.result_local_btn = QPushButton(lm.translate("Result Analysis Local"))
        self.program_end_btn = QPushButton(lm.translate("Program End"))
        sim_layout.addWidget(self.cancel_btn, 1, 0)
        sim_layout.addWidget(self.result_local_btn, 1, 1)
        sim_layout.addWidget(self.program_end_btn, 2, 0, 1, 2)
        self.layout.addWidget(sim_group)

        # 3. Analysis Control
        analysis_group = QGroupBox(lm.translate("Analysis Control"))
        analysis_layout = QVBoxLayout(analysis_group)
        self.aset_analysis_btn = QPushButton(lm.translate("Local ASET Analysis"))
        analysis_layout.addWidget(self.aset_analysis_btn)
        self.layout.addWidget(analysis_group)

        # 4. Graph Control
        graph_group = QGroupBox(lm.translate("Graph Control"))
        graph_layout = QHBoxLayout(graph_group)
        self.graph1_btn = QPushButton(lm.translate("Graph 1 On/Off"))
        self.graph2_btn = QPushButton(lm.translate("Graph 2 On/Off"))
        self.graph3_btn = QPushButton(lm.translate("Graph 3 On/Off"))
        graph_layout.addWidget(self.graph1_btn)
        graph_layout.addWidget(self.graph2_btn)
        graph_layout.addWidget(self.graph3_btn)
        self.layout.addWidget(graph_group)

        # 5. Language Control
        language_group = QGroupBox(lm.translate("Language"))
        language_layout = QHBoxLayout(language_group)
        self.language_label = QLabel(lm.translate("Language") + ":")
        language_layout.addWidget(self.language_label)
        
        self.language_combo = QComboBox()
        
        # Populate language combo box
        languages = self.language_manager.get_available_languages()
        for lang_code, lang_name in languages.items():
            self.language_combo.addItem(lang_name, lang_code)
        
        # Set current language
        current_lang = self.language_manager.get_language()
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                break
        
        self.language_combo.currentIndexChanged.connect(self._on_language_changed_combo)
        language_layout.addWidget(self.language_combo)
        self.layout.addWidget(language_group)

        self.layout.addStretch(1)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage(lm.translate("Main Control Initialized"))

    def _on_language_changed(self, language_code: str):
        """Handle language change signal from language manager."""
        self._update_ui_text()
    
    def _on_language_changed_combo(self):
        """Handle language change from combo box."""
        language_code = self.language_combo.currentData()
        self.language_manager.set_language(language_code)
    
    def _update_ui_text(self):
        """Update all UI text based on current language."""
        lm = self.language_manager
        
        # Update window title and group boxes
        self.setWindowTitle(lm.translate("QRA Main Control"))
        
        # Get references to group boxes
        for i in range(self.layout.count()):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, QGroupBox):
                if "Top Controls" in widget.title() or widget.title() == lm.translate("Top Controls"):
                    widget.setTitle(lm.translate("Top Controls"))
                elif "Simulation Control" in widget.title() or widget.title() == lm.translate("Simulation Control"):
                    widget.setTitle(lm.translate("Simulation Control"))
                elif "Analysis Control" in widget.title() or widget.title() == lm.translate("Analysis Control"):
                    widget.setTitle(lm.translate("Analysis Control"))
                elif "Graph Control" in widget.title() or widget.title() == lm.translate("Graph Control"):
                    widget.setTitle(lm.translate("Graph Control"))
                elif "Language" in widget.title() or widget.title() == lm.translate("Language"):
                    widget.setTitle(lm.translate("Language"))
        
        # Update all buttons
        self.sim_btn.setText(lm.translate("Simulation"))
        self.result_btn.setText(lm.translate("Result Analysis"))
        self.mdb_btn.setText(lm.translate("Data_MDB File Set"))
        self.cancel_btn.setText(lm.translate("Cancel"))
        self.result_local_btn.setText(lm.translate("Result Analysis Local"))
        self.program_end_btn.setText(lm.translate("Program End"))
        self.aset_analysis_btn.setText(lm.translate("Local ASET Analysis"))
        self.graph1_btn.setText(lm.translate("Graph 1 On/Off"))
        self.graph2_btn.setText(lm.translate("Graph 2 On/Off"))
        self.graph3_btn.setText(lm.translate("Graph 3 On/Off"))
        
        # Update labels
        self.language_label.setText(lm.translate("Language") + ":")
        self.status_label.setText(lm.translate("Idle"))
        self.risk_status_label.setText(lm.translate("N/A"))
        self.improvement_label.setText(lm.translate("N/A"))
        
        # Update status bar
        self.statusBar().showMessage(lm.translate("Main Control Initialized"))

    def _show_main_window(self):
        """Brings the parent main window (tab view) to the front and switches to MDB Database Creation tab."""
        main_win = self.parent()
        if main_win:
            # Switch to the MDB Database Creation tab
            if hasattr(main_win, 'tabs'):
                lm = self.language_manager
                mdb_tab_name = lm.translate("MDB Database Creation")
                # Find the index of the MDB tab
                for i in range(main_win.tabs.count()):
                    if main_win.tabs.tabText(i) == mdb_tab_name:
                        main_win.tabs.setCurrentIndex(i)
                        break
            
            # Position the main window beside this control window (to the right), clamped to screen
            ctrl_geo = self.geometry()
            main_geo = main_win.geometry()
            screen_geo = self.screen().availableGeometry() if self.screen() else None

            target_x = ctrl_geo.x() + ctrl_geo.width() + 20
            target_y = ctrl_geo.y()

            if screen_geo:
                if target_x + main_geo.width() > screen_geo.right():
                    target_x = max(screen_geo.left(), screen_geo.right() - main_geo.width())
                if target_y + main_geo.height() > screen_geo.bottom():
                    target_y = max(screen_geo.top(), screen_geo.bottom() - main_geo.height())

            main_win.move(target_x, target_y)
            main_win.show()
            main_win.raise_()
            main_win.activateWindow()
    
    def _show_qra_results(self):
        """Shows detailed QRA results, including the F-N Curve status."""
        from src.models.qra_results import QRAResult # Import here to avoid circular dependency
        session = get_session()
        try:
            qra_result = session.query(QRAResult).filter_by(tunnel_config_id=self.data_manager.current_tunnel_id).first()
            calculator = QRACalculator(session)
            fn_data = calculator.generate_fn_curve_data()
            
            if qra_result:
                msg = f"--- QRA Analysis Results ---\n"
                msg += f"Risk Status: {qra_result.risk_status}\n"
                msg += f"Improvement Required: {'YES' if qra_result.improvement_required else 'NO'}\n"
                msg += f"Accident Frequency (F): {qra_result.accident_frequency_per_year:.2e} events/year\n"
                msg += f"Fatalities (N): {qra_result.fatalities_per_accident:.2f} persons\n"
                msg += f"\n--- F-N Curve Data ---\n"
                msg += f"N Values: {fn_data['N_values']}\n"
                msg += f"Unacceptable F: {[f'{f:.2e}' for f in fn_data['unacceptable_F']]}\n"
                msg += f"Acceptable F: {[f'{f:.2e}' for f in fn_data['acceptable_F']]}\n"
                
                # In a real app, this would generate a matplotlib plot
                print(msg)
                self.statusBar().showMessage("Detailed QRA results printed to console.")
            else:
                self.statusBar().showMessage("No QRA results found. Run simulation first.")
        except Exception as e:
            self.statusBar().showMessage(f"Error showing results: {e}")
        finally:
            session.close()

    def _run_simulation(self):
        lm = self.language_manager
        self.status_label.setText("Running...")
        self.statusBar().showMessage("Starting QRA Simulation...")
        
        # 1. Ensure all data is saved before running simulation
        if self.parent() and hasattr(self.parent(), 'save_all_tabs'):
            self.parent().save_all_tabs()
        
        # 2. Run Calculation
        session = get_session()
        calculator = QRACalculator(session)
        
        try:
            results = calculator.run_simulation(self.data_manager.current_tunnel_id)
            
            # 3. Display Results
            if "error" in results:
                self.status_label.setText("Error")
                self.statusBar().showMessage(f"Simulation Error: {results['error']}")
                self.risk_status_label.setText("Error")
                self.improvement_label.setText(lm.translate("N/A"))
            else:
                self.status_label.setText("Completed")
                self.statusBar().showMessage(f"Simulation Complete. Risk Status: {results['risk_status']}")
                
                # Update QRA Result Labels
                self.risk_status_label.setText(results['risk_status'])
                self.improvement_label.setText("YES" if results['improvement_required'] else "NO")
                
                # In a real app, this would open a detailed results window
                print(f"Simulation Results: {results}")
                
        except Exception as e:
            self.status_label.setText("Crash")
            self.statusBar().showMessage(f"Critical Simulation Crash: {e}")
        finally:
            session.close()


class QRACalculatorApp(QMainWindow):
    """
    The main window containing the tabbed interface.
    """
    def __init__(self, data_manager=None):
        super().__init__()
        self.data_manager = data_manager if data_manager else DataManager()
        self.language_manager = get_language_manager()
        
        # Connect to language change signal
        self.language_manager.language_changed.connect(self._on_language_changed_main)
        
        lm = self.language_manager
        self.setWindowTitle(lm.translate("QRA Program - Quantitative Risk Analysis"))
        self.setGeometry(100, 100, 1200, 800)
        
        # Central Widget and Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Add Tabs
        self.tab_instances = {}
        self.tab_instances["tunnel"] = TunnelSettingsTab(self.language_manager)
        self.tab_instances["traffic"] = TrafficManagementTab(self.data_manager)
        self.tab_instances["har_evac"] = HAREVACAnalysisTab(self.data_manager)
        self.tab_instances["simulation"] = SimulationSettingsTab(self.data_manager)
        self.tab_instances["mdb"] = MDBDatabaseCreationTab(self.data_manager)
        
        self.tabs.addTab(self.tab_instances["tunnel"], lm.translate("Tunnel Basic Settings"))
        self.tabs.addTab(self.tab_instances["traffic"], lm.translate("Traffic Management"))
        self.tabs.addTab(self.tab_instances["har_evac"], lm.translate("HAR EVAC Analysis"))
        self.tabs.addTab(self.tab_instances["simulation"], lm.translate("Simulation Settings"))
        self.tabs.addTab(self.tab_instances["mdb"], lm.translate("MDB Database Creation"))

        # Make the selected tab label bold
        self.tabs.setStyleSheet(
            """
            QTabBar::tab { font-weight: normal; }
            QTabBar::tab:selected { font-weight: bold; }
            """
        )
        
        # Bottom control buttons
        bottom_layout = QHBoxLayout()
        self.simulation_btn = QPushButton(lm.translate("Simulation"))
        self.result_btn = QPushButton(lm.translate("Result Analysis"))
        self.print_btn = QPushButton(lm.translate("Print"))
        self.save_btn = QPushButton(lm.translate("Save"))
        self.status_btn = QPushButton(lm.translate("Status"))
        self.table_btn = QPushButton(lm.translate("Table"))
        
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.simulation_btn)
        bottom_layout.addWidget(self.result_btn)
        bottom_layout.addWidget(self.print_btn)
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(self.status_btn)
        bottom_layout.addWidget(self.table_btn)
        
        main_layout.addLayout(bottom_layout)
        
        # Status bar message
        self.status_label_main = QLabel(lm.translate("!!! Simulation End !!!"))
        main_layout.addWidget(self.status_label_main)
        
        # The Main Control is a separate window
        self.main_control = MainControlWindow(self.data_manager, self)
        self.main_control.show()
        
        # Keep the tabbed window hidden on startup; it will be shown from Main Control
        self.hide()

        self._create_menu_bar()
        self.statusBar().showMessage(lm.translate("QRA Program Initialized"))
    
    def _on_language_changed_main(self, language_code: str):
        """Handle language change event - update tab titles and buttons."""
        lm = self.language_manager
        
        # Update window title
        self.setWindowTitle(lm.translate("QRA Program - Quantitative Risk Analysis"))
        
        # Update tab titles
        self.tabs.setTabText(0, lm.translate("Tunnel Basic Settings"))
        self.tabs.setTabText(1, lm.translate("Traffic Management"))
        self.tabs.setTabText(2, lm.translate("HAR EVAC Analysis"))
        self.tabs.setTabText(3, lm.translate("Simulation Settings"))
        self.tabs.setTabText(4, lm.translate("MDB Database Creation"))
        
        # Update bottom buttons
        self.simulation_btn.setText(lm.translate("Simulation"))
        self.result_btn.setText(lm.translate("Result Analysis"))
        self.print_btn.setText(lm.translate("Print"))
        self.save_btn.setText(lm.translate("Save"))
        self.status_btn.setText(lm.translate("Status"))
        self.table_btn.setText(lm.translate("Table"))
        
        # Update status label
        self.status_label_main.setText(lm.translate("!!! Simulation End !!!"))
        
        # Update status bar
        self.statusBar().showMessage(lm.translate("QRA Program Initialized"))

    def _create_menu_bar(self):
        lm = self.language_manager
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(lm.translate("Save"), self.save_all_tabs)
        file_menu.addAction("Exit", self.close)

        view_menu = menu_bar.addMenu("View")
        view_menu.addAction("Show Main Control", self.main_control.show)
        view_menu.addAction("Hide Main Control", self.main_control.hide)

    def save_all_tabs(self):
        """Iterates through all tabs and calls their save_data method."""
        lm = self.language_manager
        for tab_name, tab_instance in self.tab_instances.items():
            if hasattr(tab_instance, 'save_data'):
                tab_instance.save_data()
        self.statusBar().showMessage(lm.translate("Save"))

    def closeEvent(self, event):
        """Hide the tabbed window instead of closing the Main Control."""
        self.hide()
        # Keep Main Control running so the user can reopen the tabs from there
        event.ignore()
        if self.main_control:
            self.main_control.raise_()
            self.main_control.activateWindow()
