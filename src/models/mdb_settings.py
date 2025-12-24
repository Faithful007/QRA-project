from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.database.base import Base

class MDBDatabaseSettings(Base):
    __tablename__ = 'mdb_database_settings'

    id = Column(Integer, primary_key=True)
    tunnel_config_id = Column(Integer, ForeignKey('tunnel_configurations.id'))
    
    # Database Type Selection
    database_type = Column(String, default="SQLite") # e.g., SQLite, MySQL, FDS
    
    # Chemical Properties Table (Simplified)
    chemical_properties_soot = Column(Float, default=0.01) # Soot Yield
    chemical_properties_co = Column(Float, default=0.01) # CO Yield
    chemical_properties_temp = Column(Float, default=1000.0) # Max Temperature (K)
    
    # FDS File Settings
    fds_file_path = Column(String, default="/path/to/fds/file.fds")
    fds_slf_time = Column(Float, default=5.0) # SLF Output Time Interval
    fds_id = Column(String, default="QRA_FDS_001") # Project ID for FDS
    
    def __repr__(self):
        return f"<MDBDatabaseSettings(type='{self.database_type}', fds_id='{self.fds_id}')>"
