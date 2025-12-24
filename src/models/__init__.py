from .tunnel_settings import TunnelConfiguration, VehicleClassification, VEHICLE_TYPES
from .traffic_management import TrafficManagement
from .har_evac_analysis import HAREVACAnalysis
from .simulation_settings import SimulationSettings, FirePoint
from .mdb_settings import MDBDatabaseSettings
from .qra_results import QRAResult

# List all models for easy import and database creation
ALL_MODELS = [
    TunnelConfiguration,
    VehicleClassification,
    TrafficManagement,
    HAREVACAnalysis,
    SimulationSettings,
    FirePoint,
    MDBDatabaseSettings,
    QRAResult
]
