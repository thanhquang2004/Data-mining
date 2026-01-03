"""
API Models - Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class CrawlStatus(str, Enum):
    """Status of a crawl job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlRequest(BaseModel):
    """Request model for starting a crawl job."""
    source: str = Field(..., description="Crawler source (itviec, topdev, linkedin)")
    keywords: Optional[List[str]] = Field(None, description="Search keywords")
    location: Optional[str] = Field(None, description="Location filter")
    pages: int = Field(1, ge=1, le=100, description="Number of pages to crawl (1-100)")
    max_jobs: int = Field(1000, ge=1, le=5000, description="Maximum jobs to collect")
    fetch_details: bool = Field(True, description="Fetch detailed info for each job (complete data)")
    store_to_db: bool = Field(True, description="Store jobs directly to database")
    headless: bool = Field(True, description="Run browser in headless mode")
    cookies_path: Optional[str] = Field(None, description="Path to cookies file for authentication")
    
    @validator('source')
    def validate_source(cls, v):
        """Validate that source is supported."""
        allowed_sources = ['itviec', 'topdev', 'linkedin']
        if v.lower() not in allowed_sources:
            raise ValueError(f"Source must be one of: {', '.join(allowed_sources)}")
        return v.lower()
    
    @validator('keywords')
    def validate_keywords(cls, v):
        """Validate keywords list."""
        if v is not None and len(v) == 0:
            return None
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "source": "linkedin",
                "keywords": ["python", "developer"],
                "location": "United States",
                "pages": 2,
                "headless": True
            }
        }


class CrawlJob(BaseModel):
    """Model representing a crawl job."""
    job_id: str = Field(..., description="Unique job identifier")
    source: str = Field(..., description="Crawler source")
    status: CrawlStatus = Field(..., description="Current job status")
    keywords: Optional[List[str]] = Field(None, description="Search keywords used")
    location: Optional[str] = Field(None, description="Location filter used")
    pages: int = Field(..., description="Number of pages to crawl")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    duration: Optional[float] = Field(None, description="Job duration in seconds")
    jobs_found: int = Field(0, description="Number of jobs found")
    jobs_processed: int = Field(0, description="Number of jobs processed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="Crawled job results")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "source": "linkedin",
                "status": "completed",
                "keywords": ["python", "developer"],
                "location": "United States",
                "pages": 2,
                "created_at": "2026-01-02T12:00:00",
                "started_at": "2026-01-02T12:00:01",
                "completed_at": "2026-01-02T12:05:30",
                "duration": 329.5,
                "jobs_found": 50,
                "jobs_processed": 50,
                "error_message": None,
                "results": [
                    {
                        "job_id": "123456",
                        "title": "Senior Python Developer",
                        "company_name": "Tech Corp",
                        "location": "San Francisco, CA"
                    }
                ]
            }
        }


class JobResponse(BaseModel):
    """Response model for job creation."""
    job_id: str
    status: CrawlStatus
    source: str
    created_at: datetime
    message: str = "Job created successfully"


class JobListResponse(BaseModel):
    """Response model for job listing."""
    jobs: List[CrawlJob]
    total: int
    limit: int
    offset: int
