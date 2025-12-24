from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.database.base import Base

class SimulationSettings(Base):
    __tablename__ = 'simulation_settings'

    id = Column(Integer, primary_key=True)
    tunnel_config_id = Column(Integer, ForeignKey('tunnel_configurations.id'))
    
    # Program Settings
    time_interval = Column(Float, default=5.0) # seconds
    total_simulation_time = Column(Float, default=3600.0) # seconds (1 hour)
    
    # Fire Point Configuration
    fire_point_count = Column(Integer, default=1)
    
    # Monitoring Points
    monitoring_point_count = Column(Integer, default=10)
    
    # Project Configuration
    project_name = Column(String, default="QRA_Simulation")
    
    # Relationships
    fire_points = relationship("FirePoint", back_populates="simulation_settings", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SimulationSettings(project='{self.project_name}', time={self.total_simulation_time})>"

class FirePoint(Base):
    __tablename__ = 'fire_points'

    id = Column(Integer, primary_key=True)
    simulation_settings_id = Column(Integer, ForeignKey('simulation_settings.id'))
    simulation_settings = relationship("SimulationSettings", back_populates="fire_points")
    
    name = Column(String)
    location_x = Column(Float)
    location_y = Column(Float)
    location_z = Column(Float)
    
    def __repr__(self):
        return f"<FirePoint(name='{self.name}', loc=({self.location_x}, {self.location_y}))>"
