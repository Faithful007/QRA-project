from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from src.database.base import Base

class TrafficManagement(Base):
    __tablename__ = 'traffic_management'

    id = Column(Integer, primary_key=True)
    tunnel_config_id = Column(Integer, ForeignKey('tunnel_configurations.id'))
    
    # Traffic Flow Configuration
    max_speed = Column(Float, default=80.0) # Site Max Speed
    incident_traffic_volume = Column(Float, default=0.0) # Incident Traffic Volume
    
    # Speed Distribution (simplified to a single value for now)
    speed_distribution_factor = Column(Float, default=1.0)
    
    # Evacuation Zone Speed Distribution (simplified)
    evac_zone_speed = Column(Float, default=1.0)
    
    # Occupancy Calculation (derived from TunnelConfiguration, but stored here for management)
    occupancy_factor = Column(Float, default=1.0)
    
    # Relationships
    # Add relationships to detailed tables if necessary, e.g., SpeedDistributionTable
    
    def __repr__(self):
        return f"<TrafficManagement(max_speed={self.max_speed})>"
