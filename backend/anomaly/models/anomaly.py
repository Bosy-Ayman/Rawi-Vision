from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from database import Base

class Anomaly(Base):
    __tablename__ = "anomalies"

    # TODO: Define primary key and unique identifier
    
    # TODO: Define camera and incident metadata columns
    
    # TODO: Define image storage and AI confidence columns
    
    # TODO: Define foreign key for employee involved
    pass
