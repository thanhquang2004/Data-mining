"""
CRUD operations for Job model.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .job import Job
from src.schemas.job import JobCreate, JobUpdate, JobFilter


class JobCRUD:
    """CRUD operations for Job model."""
    
    def create(self, db: Session, job_data: JobCreate) -> Job:
        """Create a new job posting."""
        db_job = Job(**job_data.model_dump())
        db_job.crawled_at = datetime.utcnow()
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        return db_job
    
    def get_by_id(self, db: Session, job_id: int) -> Optional[Job]:
        """Get a job by ID."""
        return db.query(Job).filter(Job.id == job_id).first()
    
    def get_by_source_url(self, db: Session, source_url: str) -> Optional[Job]:
        """Get a job by source URL (for duplicate checking)."""
        return db.query(Job).filter(Job.source_url == source_url).first()
    
    def get_all(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[Job]:
        """Get all jobs with pagination."""
        query = db.query(Job)
        if is_active is not None:
            query = query.filter(Job.is_active == is_active)
        return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    def filter_jobs(self, db: Session, filters: JobFilter) -> List[Job]:
        """Filter jobs based on multiple criteria."""
        query = db.query(Job)
        
        if filters.title:
            query = query.filter(Job.title.ilike(f"%{filters.title}%"))
        if filters.company_name:
            query = query.filter(Job.company_name.ilike(f"%{filters.company_name}%"))
        if filters.location:
            query = query.filter(Job.location.ilike(f"%{filters.location}%"))
        if filters.source:
            query = query.filter(Job.source == filters.source)
        if filters.level:
            query = query.filter(Job.level == filters.level)
        if filters.is_remote is not None:
            query = query.filter(Job.is_remote == filters.is_remote)
        if filters.is_active is not None:
            query = query.filter(Job.is_active == filters.is_active)
        
        if filters.required_skills:
            for skill in filters.required_skills:
                query = query.filter(
                    Job.required_skills.cast(func.text).ilike(f"%{skill}%")
                )
        
        if filters.salary_min is not None:
            query = query.filter(
                or_(Job.salary_min >= filters.salary_min, Job.salary_max >= filters.salary_min)
            )
        if filters.salary_max is not None:
            query = query.filter(Job.salary_min <= filters.salary_max)
        
        return query.order_by(Job.created_at.desc()).offset(filters.skip).limit(filters.limit).all()
    
    def update(self, db: Session, job_id: int, job_data: JobUpdate) -> Optional[Job]:
        """Update an existing job."""
        db_job = self.get_by_id(db, job_id)
        if not db_job:
            return None
        
        for field, value in job_data.model_dump(exclude_unset=True).items():
            setattr(db_job, field, value)
        
        db_job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_job)
        return db_job
    
    def delete(self, db: Session, job_id: int) -> bool:
        """Delete a job (hard delete)."""
        db_job = self.get_by_id(db, job_id)
        if not db_job:
            return False
        db.delete(db_job)
        db.commit()
        return True
    
    def soft_delete(self, db: Session, job_id: int) -> Optional[Job]:
        """Soft delete a job (mark as inactive)."""
        db_job = self.get_by_id(db, job_id)
        if not db_job:
            return None
        db_job.is_active = False
        db_job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_job)
        return db_job
    
    def bulk_create(self, db: Session, jobs_data: List[JobCreate]) -> List[Job]:
        """Create multiple jobs at once."""
        db_jobs = [Job(**job_data.model_dump(), crawled_at=datetime.utcnow()) for job_data in jobs_data]
        db.add_all(db_jobs)
        db.commit()
        for db_job in db_jobs:
            db.refresh(db_job)
        return db_jobs
    
    def upsert(self, db: Session, job_data: JobCreate) -> Tuple[Job, bool]:
        """Create or update a job based on source_url. Returns (job, is_created)."""
        existing = self.get_by_source_url(db, job_data.source_url)
        if existing:
            for field, value in job_data.model_dump().items():
                setattr(existing, field, value)
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing, False
        return self.create(db, job_data), True
    
    def count(self, db: Session, is_active: Optional[bool] = None) -> int:
        """Count total jobs."""
        query = db.query(func.count(Job.id))
        if is_active is not None:
            query = query.filter(Job.is_active == is_active)
        return query.scalar() or 0
    
    def search_by_skills(self, db: Session, skills: List[str], skip: int = 0, limit: int = 100) -> List[Job]:
        """Search jobs by required or preferred skills."""
        query = db.query(Job).filter(Job.is_active == True)
        
        skill_conditions = [
            or_(
                Job.required_skills.cast(func.text).ilike(f"%{skill}%"),
                Job.preferred_skills.cast(func.text).ilike(f"%{skill}%")
            )
            for skill in skills
        ]
        if skill_conditions:
            query = query.filter(or_(*skill_conditions))
        
        return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_recent_jobs(self, db: Session, days: int = 7, limit: int = 100) -> List[Job]:
        """Get recently posted jobs."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return db.query(Job).filter(
            Job.created_at >= cutoff,
            Job.is_active == True
        ).order_by(Job.created_at.desc()).limit(limit).all()


# Singleton instance
job_crud = JobCRUD()

