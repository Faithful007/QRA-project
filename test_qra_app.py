import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.ui.main_window import QRACalculatorApp, MainControlWindow
from src.database.connection import init_db, get_session, get_engine, Base, DATABASE_URL
from src.database.data_manager import DataManager
from src.models.tunnel_settings import TunnelConfiguration, VehicleClassification
from src.models import ALL_MODELS

# Set the platform to 'offscreen' for headless testing
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
# Ensure QApplication is initialized once
if not QApplication.instance():
    app = QApplication(sys.argv)

class TestQRACalculatorApp(unittest.TestCase):
    
    def setUp(self):
        # Use a temporary in-memory SQLite database for each test
        self.engine = create_engine("sqlite:///:memory:")
        
        # Ensure all models are registered with Base
        from src.models import ALL_MODELS
        Base.metadata.create_all(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Manually initialize DataManager with the test session
        self.data_manager = DataManager(session=self.session)
        
        # Pass the DataManager to the app for testing
        self.main_app = QRACalculatorApp(data_manager=self.data_manager)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.main_app.close()

    def test_tabs_initialization(self):
        """Test if all 5 tabs are present."""
        self.assertEqual(self.main_app.tabs.count(), 5)
        self.assertIn("tunnel", self.main_app.tab_instances)
        self.assertIn("traffic", self.main_app.tab_instances)
        self.assertIn("har_evac", self.main_app.tab_instances)
        self.assertIn("simulation", self.main_app.tab_instances)
        self.assertIn("mdb", self.main_app.tab_instances)

    def test_default_tunnel_config_in_db(self):
        """Test if the default tunnel configuration is created in the database."""
        tunnel = self.session.query(TunnelConfiguration).first()
        self.assertIsNotNone(tunnel)
        self.assertEqual(tunnel.name, "Default QRA Project")
        self.assertEqual(self.session.query(VehicleClassification).count(), 7)

    def test_tunnel_tab_data_binding(self):
        """Test if the Tunnel tab loads and saves data correctly."""
        tunnel_tab = self.main_app.tab_instances["tunnel"]
        
        # 1. Check initial load
        self.assertEqual(tunnel_tab.name_input.text(), "Default QRA Project")
        
        # 2. Change data and save
        new_name = "Test Tunnel Save"
        tunnel_tab.name_input.setText(new_name)
        tunnel_tab.save_data()
        
        # 3. Check database
        tunnel = self.session.query(TunnelConfiguration).first()
        self.assertEqual(tunnel.name, new_name)

    def test_simulation_button_calls_logic(self):
        """Test if the Simulation button calls the calculation logic."""
        main_control = self.main_app.main_control
        
        # Mock the save_all_tabs method to ensure it's called
        self.main_app.save_all_tabs = MagicMock()
        
        # Mock the calculator's run_simulation method
        with patch('src.logic.QRACalculator.run_simulation') as mock_run:
            mock_run.return_value = {
                "tunnel_name": "Test", "total_pcu": 100.0, "aset_s": 700.0, "rset_s": 400.0, 
                "safety_margin_s": 300.0, "is_safe": True, "accident_frequency_per_year": 1e-5,
                "fatalities_per_accident": 10.0, "risk_status": "ALARP", "improvement_required": True,
                "simulation_status": "Completed (Full QRA Procedure)"
            }
            
            # Click the simulation button
            main_control.sim_btn.click()
            
            # Assertions
            self.main_app.save_all_tabs.assert_called_once()
            mock_run.assert_called_once_with(self.data_manager.current_tunnel_id)
            self.assertEqual(main_control.status_label.text(), "Completed")
            self.assertEqual(main_control.risk_status_label.text(), "ALARP")
            self.assertEqual(main_control.improvement_label.text(), "YES")
