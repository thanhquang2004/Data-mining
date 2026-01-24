"""
JobIT database model - Preprocessed jobs table.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float

from src.database.connection import Base


class JobIT(Base):
    """Preprocessed job posting model for IT jobs."""
    
    __tablename__ = "jobs_it"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Basic Info
    title = Column(String(500), nullable=False, index=True)
    company_name = Column(String(300), index=True)
    location = Column(String(200), index=True)
    source = Column(String(50), index=True)
    source_url = Column(String(500), index=True)
    
    # Job Details
    description = Column(Text)
    requirements_text = Column(Text)
    job_type = Column(String(100))
    level = Column(String(50), index=True)
    
    # Experience & Education
    experience_years_min = Column(Float)
    experience_years_max = Column(Float)
    education_level = Column(String(100))
    
    # Skills (stored as JSON strings)
    required_skills = Column(Text)
    preferred_skills = Column(Text)
    
    # Additional Info
    benefits = Column(Text)
    is_remote = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Preprocessed fields
    job_desc_lem = Column(Text)  # Lemmatized job description
    text = Column(Text)  # Processed text
    pred = Column(Integer, index=True)  # Prediction/classification result
    
    def __repr__(self) -> str:
        return f"<JobIT(id={self.id}, title='{self.title}', company='{self.company_name}', pred={self.pred})>"
