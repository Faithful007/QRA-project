from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, QLabel, QLineEdit, QGridLayout, QGroupBox, QMenuBar, QMenu, QStatusBar
from PyQt6.QtCore import Qt, QSize
from src.ui.tabs.tunnel_settings import TunnelBasicSettingsTab
from src.ui.tabs.traffic_management import TrafficManagementTab
from src.ui.tabs.har_evac import HAREVACAnalysisTab
from src.ui.tabs.simulation import SimulationSettingsTab
from src.ui.tabs.mdb_create import MDBDatabaseCreationTab
from src.database.data_manager import DataManager
from src.logic import QRACalculator
from src.database.connection import get_session

class MainControlWindow(QMainWindow):
    """
    The separate Main Control panel as described in the specification.
    This is a separate QMainWindow instance.
    """
    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle("QRA Main Control")
        self.setGeometry(100, 100, 350, 450)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)
        
        # 1. Top Control Buttons
        top_group = QGroupBox("Top Controls")
        top_layout = QHBoxLayout(top_group)
        self.sim_btn = QPushButton("Simulation")
        self.result_btn = QPushButton("Result Analysis")
        self.mdb_btn = QPushButton("Data_MDB File Set")
        top_layout.addWidget(self.sim_btn)
        top_layout.addWidget(self.result_btn)
        top_layout.addWidget(self.mdb_btn)
        self.layout.addWidget(top_group)

        # Connect Simulation button
        self.sim_btn.clicked.connect(self._run_simulation)
        self.result_btn.clicked.connect(self._show_qra_results)

        # 2. Simulation Control
        sim_group = QGroupBox("Simulation Control")
        sim_layout = QGridLayout(sim_group)
        sim_layout.addWidget(QLabel("Simulation Status:"), 0, 0)
        self.status_label = QLabel("Idle")
        sim_layout.addWidget(self.status_label, 0, 1)
        
        # New QRA Result Display
        sim_layout.addWidget(QLabel("Risk Status:"), 3, 0)
        self.risk_status_label = QLabel("N/A")
        sim_layout.addWidget(self.risk_status_label, 3, 1)
        sim_layout.addWidget(QLabel("Improvement Req.:"), 4, 0)
        self.improvement_label = QLabel("N/A")
        sim_layout.addWidget(self.improvement_label, 4, 1)
        sim_layout.addWidget(QPushButton("Cancel"), 1, 0)
        sim_layout.addWidget(QPushButton("Result Analysis Local"), 1, 1)
        sim_layout.addWidget(QPushButton("Program End"), 2, 0, 1, 2)
        self.layout.addWidget(sim_group)

        # 3. Analysis Control
        analysis_group = QGroupBox("Analysis Control")
        analysis_layout = QVBoxLayout(analysis_group)
        analysis_layout.addWidget(QPushButton("Local ASET Analysis"))
        self.layout.addWidget(analysis_group)

        # 4. Graph Control
        graph_group = QGroupBox("Graph Control")
        graph_layout = QHBoxLayout(graph_group)
        graph_layout.addWidget(QPushButton("Graph 1 On/Off"))
        graph_layout.addWidget(QPushButton("Graph 2 On/Off"))
        graph_layout.addWidget(QPushButton("Graph 3 On/Off"))
        self.layout.addWidget(graph_group)

        self.layout.addStretch(1)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Main Control Initialized")

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
                self.improvement_label.setText("N/A")
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
        self.setWindowTitle("QRA Program - Quantitative Risk Analysis")
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
        self.tab_instances["tunnel"] = TunnelBasicSettingsTab(self.data_manager)
        self.tab_instances["traffic"] = TrafficManagementTab(self.data_manager)
        self.tab_instances["har_evac"] = HAREVACAnalysisTab(self.data_manager)
        self.tab_instances["simulation"] = SimulationSettingsTab(self.data_manager)
        self.tab_instances["mdb"] = MDBDatabaseCreationTab(self.data_manager)
        
        self.tabs.addTab(self.tab_instances["tunnel"], "Tunnel Basic Settings")
        self.tabs.addTab(self.tab_instances["traffic"], "Traffic Management")
        self.tabs.addTab(self.tab_instances["har_evac"], "HAR EVAC Analysis")
        self.tabs.addTab(self.tab_instances["simulation"], "Simulation Settings")
        self.tabs.addTab(self.tab_instances["mdb"], "MDB Database Creation")

        # Make the selected tab label bold
        self.tabs.setStyleSheet(
            """
            QTabBar::tab { font-weight: normal; }
            QTabBar::tab:selected { font-weight: bold; }
            """
        )
        
        # The Main Control is a separate window
        self.main_control = MainControlWindow(self.data_manager, self)
        self.main_control.show()

        self._create_menu_bar()
        self.statusBar().showMessage("QRA Program Initialized")

    def _create_menu_bar(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Save All", self.save_all_tabs)
        file_menu.addAction("Exit", self.close)

        view_menu = menu_bar.addMenu("View")
        view_menu.addAction("Show Main Control", self.main_control.show)
        view_menu.addAction("Hide Main Control", self.main_control.hide)

    def save_all_tabs(self):
        """Iterates through all tabs and calls their save_data method."""
        for tab_name, tab_instance in self.tab_instances.items():
            if hasattr(tab_instance, 'save_data'):
                tab_instance.save_data()
        self.statusBar().showMessage("All tab data saved to database.")

    def closeEvent(self, event):
        """Handle closing of the main window and the control window."""
        self.main_control.close()
        event.accept()
