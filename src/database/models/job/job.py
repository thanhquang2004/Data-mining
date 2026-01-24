"""
Job database model.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, Float

from src.database.connection import Base


class Job(Base):
    """Job posting model."""
    
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Basic Info
    title = Column(String(500), nullable=False, index=True)
    company_name = Column(String(300), index=True)
    location = Column(String(200), index=True)
    source = Column(String(50), index=True)
    source_url = Column(String(500), unique=True, index=True)
    
    # Job Details
    description = Column(Text)
    requirements_text = Column(Text)
    job_type = Column(String(100))
    level = Column(String(50))
    
    # Salary
    salary_min = Column(Float)
    salary_max = Column(Float)
    salary_currency = Column(String(10))
    salary_text = Column(String(200))
    
    # Experience & Education
    experience_years_min = Column(Integer)
    experience_years_max = Column(Integer)
    education_level = Column(String(100))
    certifications = Column(JSON, default=list)
    
    # Skills
    required_skills = Column(JSON, default=list)
    preferred_skills = Column(JSON, default=list)
    
    # Additional Info
    benefits = Column(JSON, default=list)
    company_rating = Column(Float)
    is_remote = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    crawled_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company_name}')>"
