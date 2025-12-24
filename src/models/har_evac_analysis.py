from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.database.base import Base

class HAREVACAnalysis(Base):
    __tablename__ = 'har_evac_analysis'

    id = Column(Integer, primary_key=True)
    tunnel_config_id = Column(Integer, ForeignKey('tunnel_configurations.id'))
    
    # Hazard Definition
    hazard_calculation_method = Column(String, default="FED") # e.g., FED, Fractional Effective Dose
    
    # Fire Characteristics
    heat_release_rate = Column(Float, default=10.0) # MW
    fire_growth_rate = Column(String, default="Medium") # e.g., Slow, Medium, Fast
    smoke_density = Column(Float, default=0.1) # m^-1
    
    # Evacuation Characteristics (ASET/RSET Criteria)
    visibility_limit = Column(Float, default=10.0) # m
    temperature_limit = Column(Float, default=60.0) # C
    CO_limit = Column(Float, default=1000.0) # ppm
    
    # Evacuation Timing (RSET components)
    reaction_time = Column(Float, default=60.0) # seconds
    hesitation_time = Column(Float, default=120.0) # seconds
    
    # Evacuation Speed Settings
    evac_speed_walking = Column(Float, default=1.0) # m/s
    evac_speed_running = Column(Float, default=2.0) # m/s
    
    # Early Start Conditions
    early_start_condition = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<HAREVACAnalysis(method='{self.hazard_calculation_method}', HRR={self.heat_release_rate})>"
