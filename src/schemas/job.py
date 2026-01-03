from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List
from datetime import datetime


# Base schema with common fields
class JobBase(BaseModel):
    title: str = Field(..., max_length=500, description="Job title")
    company_name: Optional[str] = Field(None, max_length=300, description="Company name")
    location: Optional[str] = Field(None, max_length=200, description="Job location")
    source: Optional[str] = Field(None, max_length=50, description="Source platform (itviec, topdev, etc.)")
    source_url: Optional[str] = Field(None, max_length=1000, description="Original job posting URL")
    
    # Job Details
    description: Optional[str] = None
    requirements_text: Optional[str] = None
    job_type: Optional[str] = Field(None, max_length=100, description="Full-time, Part-time, etc.")
    level: Optional[str] = Field(None, max_length=50, description="Junior, Middle, Senior, etc.")
    
    # Salary
    salary_min: Optional[float] = Field(None, ge=0)
    salary_max: Optional[float] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, max_length=10, description="USD, VND, etc.")
    salary_text: Optional[str] = Field(None, max_length=200)
    
    # Experience & Education
    experience_years_min: Optional[int] = Field(None, ge=0)
    experience_years_max: Optional[int] = Field(None, ge=0)
    education_level: Optional[str] = Field(None, max_length=100)
    certifications: Optional[List[str]] = Field(default_factory=list)
    
    # Skills
    required_skills: Optional[List[str]] = Field(default_factory=list)
    preferred_skills: Optional[List[str]] = Field(default_factory=list)
    
    # Additional Info
    benefits: Optional[List[str]] = Field(default_factory=list)
    company_rating: Optional[float] = Field(None, ge=0, le=5)
    is_remote: Optional[bool] = False
    is_active: Optional[bool] = True

    @validator('salary_max')
    def validate_salary_range(cls, v, values):
        if v is not None and 'salary_min' in values and values['salary_min'] is not None:
            if v < values['salary_min']:
                raise ValueError('salary_max must be greater than or equal to salary_min')
        return v

    @validator('experience_years_max')
    def validate_experience_range(cls, v, values):
        if v is not None and 'experience_years_min' in values and values['experience_years_min'] is not None:
            if v < values['experience_years_min']:
                raise ValueError('experience_years_max must be greater than or equal to experience_years_min')
        return v


# Schema for creating a new job
class JobCreate(JobBase):
    title: str = Field(..., max_length=500, description="Job title (required)")
    source_url: str = Field(..., max_length=1000, description="Original job posting URL (required)")


# Schema for updating an existing job
class JobUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    company_name: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = Field(None, max_length=200)
    source: Optional[str] = Field(None, max_length=50)
    source_url: Optional[str] = Field(None, max_length=1000)
    
    description: Optional[str] = None
    requirements_text: Optional[str] = None
    job_type: Optional[str] = Field(None, max_length=100)
    level: Optional[str] = Field(None, max_length=50)
    
    salary_min: Optional[float] = Field(None, ge=0)
    salary_max: Optional[float] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, max_length=10)
    salary_text: Optional[str] = Field(None, max_length=200)
    
    experience_years_min: Optional[int] = Field(None, ge=0)
    experience_years_max: Optional[int] = Field(None, ge=0)
    education_level: Optional[str] = Field(None, max_length=100)
    certifications: Optional[List[str]] = None
    
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    
    benefits: Optional[List[str]] = None
    company_rating: Optional[float] = Field(None, ge=0, le=5)
    is_remote: Optional[bool] = None
    is_active: Optional[bool] = None


# Schema for reading/returning job data
class JobResponse(JobBase):
    id: int
    created_at: datetime
    updated_at: datetime
    crawled_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2 (use orm_mode = True for Pydantic v1)


# Schema for listing jobs (with minimal fields)
class JobListResponse(BaseModel):
    id: int
    title: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    level: Optional[str] = None
    salary_text: Optional[str] = None
    is_remote: Optional[bool] = False
    is_active: Optional[bool] = True
    created_at: datetime

    class Config:
        from_attributes = True


# Schema for filtering/searching jobs
class JobFilter(BaseModel):
    title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    level: Optional[str] = None
    is_remote: Optional[bool] = None
    is_active: Optional[bool] = None
    required_skills: Optional[List[str]] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)
