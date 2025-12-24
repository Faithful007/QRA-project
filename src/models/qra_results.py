from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.database.base import Base

class QRAResult(Base):
    __tablename__ = 'qra_results'

    id = Column(Integer, primary_key=True)
    tunnel_config_id = Column(Integer, ForeignKey('tunnel_configurations.id'))

    # QRA Procedure Outputs
    accident_frequency_per_year = Column(Float, default=0.0, comment="F: Accident Frequency (events/year)")
    fatalities_per_accident = Column(Float, default=0.0, comment="N: Average Fatalities per Accident (persons)")
    
    # Risk Evaluation
    risk_status = Column(String, default="Not Evaluated", comment="Risk status: Acceptable, ALARP, Unacceptable")
    improvement_required = Column(Boolean, default=False, comment="True if risk is Unacceptable or ALARP")
    
    # Relationship
    tunnel_config = relationship("TunnelConfiguration", back_populates="qra_results")

    def __repr__(self):
        return f"<QRAResult(id={self.id}, risk_status='{self.risk_status}')>"
