from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.database.base import Base

class TunnelConfiguration(Base):
    __tablename__ = 'tunnel_configurations'

    id = Column(Integer, primary_key=True)
    name = Column(String, default="New Tunnel")
    
    # Tunnel Geometry
    mode = Column(String, default="One-Way") # One-Way or Two-Way
    length = Column(Float, default=410.0)
    entrance_length = Column(Float, default=29.21)
    slope = Column(Float, default=-3.0)
    area = Column(Float, default=54.11)
    height = Column(Float, default=5.9)
    lanes = Column(Integer, default=2)
    lane_width = Column(Float, default=3.25)
    shoulder_width = Column(Float, default=1.0)
    
    # Two-Way Traffic Ratios (if mode is Two-Way)
    forward_ratio = Column(Float, default=0.5)
    backward_ratio = Column(Float, default=0.5)
    forward_lanes = Column(Integer, default=0)
    backward_lanes = Column(Integer, default=0)

    # Relationships
    vehicle_classifications = relationship("VehicleClassification", back_populates="tunnel_config", cascade="all, delete-orphan")
    qra_results = relationship("QRAResult", back_populates="tunnel_config", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TunnelConfiguration(name='{self.name}', length={self.length})>"

class VehicleClassification(Base):
    __tablename__ = 'vehicle_classifications'

    id = Column(Integer, primary_key=True)
    tunnel_config_id = Column(Integer, ForeignKey('tunnel_configurations.id'))
    tunnel_config = relationship("TunnelConfiguration", back_populates="vehicle_classifications")

    # Vehicle Type (e.g., Passenger Car, Small Bus, Large Bus, etc.)
    vehicle_type = Column(String)
    
    # Traffic Volume (per direction, e.g., +Direction, -Direction)
    volume_plus = Column(Float, default=0.0)
    volume_minus = Column(Float, default=0.0)
    
    # Mixing Ratio (혼입율)
    mixing_ratio_plus = Column(Float, default=0.0)
    mixing_ratio_minus = Column(Float, default=0.0)
    
    # PCU (Passenger Car Unit)
    pcu = Column(Float, default=1.0)
    
    # Vehicle Length (차량길이)
    length = Column(Float, default=4.34)
    
    # Occupancy (탑승인원)
    occupancy = Column(Integer, default=3)

    def __repr__(self):
        return f"<VehicleClassification(type='{self.vehicle_type}', vol+={self.volume_plus})>"

# Initial data for the 8 vehicle types based on the screenshot
VEHICLE_TYPES = [
    {"vehicle_type": "Passenger Car (승용차)", "pcu": 1.0, "length": 4.34, "occupancy": 3},
    {"vehicle_type": "Small Bus (버스소형)", "pcu": 1.0, "length": 4.5, "occupancy": 8},
    {"vehicle_type": "Large Bus (버스대형)", "pcu": 1.5, "length": 10.77, "occupancy": 30},
    {"vehicle_type": "Small Truck (트럭소형)", "pcu": 1.0, "length": 4.52, "occupancy": 2},
    {"vehicle_type": "Medium Truck (트럭중형)", "pcu": 1.5, "length": 6.1, "occupancy": 2},
    {"vehicle_type": "Large Truck (트럭대형)", "pcu": 1.5, "length": 8.74, "occupancy": 1},
    {"vehicle_type": "Special (특수)", "pcu": 2.0, "length": 18.31, "occupancy": 1},
]
