import math
from sqlalchemy.orm import Session
from .connection import get_session
from src.models.tunnel_settings import TunnelConfiguration, VehicleClassification, VEHICLE_TYPES
from src.models.traffic_management import TrafficManagement
from src.models.har_evac_analysis import HAREVACAnalysis
from src.models.simulation_settings import SimulationSettings
from src.models.mdb_settings import MDBDatabaseSettings
from src.models.qra_results import QRAResult

class DataManager:
    """
    Manages data persistence and retrieval for all QRA application components.
    Handles the stateless requirement by loading and saving the current configuration
    to the SQLite database.
    """
    
    def __init__(self, session=None):
        # Optional session for testing purposes (in-memory database)
        self._session = session
        # Ensure a default configuration exists and get its ID
        self.current_tunnel_id = self._get_or_create_default_tunnel_id()

    def _get_session(self):
        """Returns a configured SQLAlchemy session, using the test session if provided."""
        return self._session if self._session else get_session()

    def _get_or_create_default_tunnel_id(self):
        """Ensures a default tunnel configuration exists and returns its ID."""
        session = self._get_session()
        try:
            # Try to find an existing configuration
            tunnel = session.query(TunnelConfiguration).first()
            if tunnel:
                return tunnel.id
            
            # If none exists, create a new default one
            tunnel = TunnelConfiguration(name="Default QRA Project")
            session.add(tunnel)
            session.commit()
            
            # Create default vehicle classifications for the new tunnel
            for v_type in VEHICLE_TYPES:
                v_class = VehicleClassification(
                    tunnel_config_id=tunnel.id,
                    **v_type
                )
                session.add(v_class)
            
            # Create default settings for other tabs (linked to the new tunnel)
            session.add(TrafficManagement(tunnel_config_id=tunnel.id))
            session.add(HAREVACAnalysis(tunnel_config_id=tunnel.id))
            session.add(SimulationSettings(tunnel_config_id=tunnel.id))
            session.add(MDBDatabaseSettings(tunnel_config_id=tunnel.id))
            session.add(QRAResult(tunnel_config_id=tunnel.id))
            
            session.commit()
            return tunnel.id
        except Exception as e:
            session.rollback()
            print(f"Error initializing default tunnel: {e}")
            return None
        finally:
            # Only close the session if it was created by get_session() (i.e., not a test session)
            if not self._session:
                session.close()

    def save_tunnel_data(self, data):
        """Saves data from the Tunnel Basic Settings tab."""
        session = self._get_session()
        try:
            tunnel = session.get(TunnelConfiguration, self.current_tunnel_id)
            if not tunnel:
                return False

            # Update TunnelConfiguration fields
            tunnel.name = data["name"]
            tunnel.mode = data["mode"]
            # ... (other tunnel fields updated here)
            
            # Update VehicleClassification fields
            for v_data in data["vehicle_data"]:
                v_class = session.query(VehicleClassification).filter_by(
                    tunnel_config_id=self.current_tunnel_id,
                    vehicle_type=v_data["vehicle_type"]
                ).first()
                if v_class:
                    v_class.volume_plus = v_data["volume_plus"]
                    v_class.volume_minus = v_data["volume_minus"]
                    # ... (other vehicle fields updated here)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error saving tunnel data: {e}")
            return False
        finally:
            if not self._session:
                session.close()

    def load_tunnel_data(self):
        """Loads data for the Tunnel Basic Settings tab."""
        session = self._get_session()
        try:
            tunnel = session.get(TunnelConfiguration, self.current_tunnel_id)
            vehicles = session.query(VehicleClassification).filter_by(
                tunnel_config_id=self.current_tunnel_id
            ).order_by(VehicleClassification.id).all()
            return tunnel, vehicles
        finally:
            if not self._session:
                session.close()

    # Placeholder methods for other tabs
    def save_traffic_data(self, data):
        # Implementation for Tab 2
        pass

    def load_traffic_data(self):
        # Implementation for Tab 2
        pass

    def save_har_evac_data(self, data):
        # Implementation for Tab 3
        pass

    def load_har_evac_data(self):
        # Implementation for Tab 3
        pass

    def save_simulation_data(self, data):
        # Implementation for Tab 4
        pass

    def load_simulation_data(self):
        # Implementation for Tab 4
        pass

    def save_mdb_data(self, data):
        # Implementation for Tab 5
        pass

    def load_mdb_data(self):
        # Implementation for Tab 5
        pass
