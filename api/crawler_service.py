"""
Crawler Service - Business logic for managing crawler jobs.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import CrawlRequest, CrawlJob, CrawlStatus
from src.crawlers import create_crawler
from src.database import get_db_session, job_crud
from src.schemas.job import JobCreate

logger = logging.getLogger(__name__)


class CrawlerService:
    """Service for managing crawler jobs."""
    
    def __init__(self):
        """Initialize the crawler service."""
        self.jobs: Dict[str, CrawlJob] = {}
        self.data_dir = Path("data/raw")
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_job(self, request: CrawlRequest) -> CrawlJob:
        """Create a new crawl job."""
        job_id = str(uuid.uuid4())
        
        job = CrawlJob(
            job_id=job_id,
            source=request.source,
            status=CrawlStatus.PENDING,
            keywords=request.keywords,
            location=request.location,
            pages=request.pages,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            duration=None,
            jobs_found=0,
            jobs_processed=0,
            error_message=None,
            results=None
        )
        
        self.jobs[job_id] = job
        logger.info(f"Created job {job_id} for source {request.source}")
        return job
    
    async def run_crawler(self, job_id: str, request: CrawlRequest):
        """Run the crawler for a job."""
        job = self.jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        try:
            job.status = CrawlStatus.RUNNING
            job.started_at = datetime.now()
            logger.info(f"Starting crawler for job {job_id}")
            
            crawler_kwargs = {"headless": request.headless}
            if request.cookies_path:
                crawler_kwargs["cookies_path"] = request.cookies_path
            
            crawler = create_crawler(request.source, **crawler_kwargs)
            
            crawl_kwargs = {
                "pages": request.pages,
                "max_jobs": request.max_jobs,
                "fetch_details": request.fetch_details,
                "store_to_db": request.store_to_db,
            }
            if request.keywords:
                crawl_kwargs["keywords"] = request.keywords
            if request.location:
                crawl_kwargs["location"] = request.location
            
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self._run_crawler_sync, crawler, crawl_kwargs
            )
            
            job.status = CrawlStatus.COMPLETED
            job.completed_at = datetime.now()
            job.duration = (job.completed_at - job.started_at).total_seconds()
            job.jobs_found = len(results)
            job.jobs_processed = len(results)
            job.results = results
            
            self._save_results(job_id, results, request.source)
            logger.info(f"Job {job_id} completed. Found {len(results)} jobs.")
            
        except Exception as e:
            logger.error(f"Error running crawler for job {job_id}: {e}", exc_info=True)
            job.status = CrawlStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()
            if job.started_at:
                job.duration = (job.completed_at - job.started_at).total_seconds()
    
    def _run_crawler_sync(self, crawler, kwargs) -> List[Dict[str, Any]]:
        """Run crawler synchronously (for use in executor)."""
        return list(crawler.crawl(**kwargs))
    
    def _save_results(self, job_id: str, results: List[Dict[str, Any]], source: str):
        """Save crawl results to JSON file and database."""
        # Save to JSON file
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{source}_{timestamp}_{job_id[:8]}.json"
            filepath = self.data_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'job_id': job_id,
                    'source': source,
                    'timestamp': timestamp,
                    'count': len(results),
                    'jobs': results
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(results)} jobs to {filepath}")
        except Exception as e:
            logger.error(f"Error saving results to file: {e}", exc_info=True)
        
        # Save to database
        self._save_to_database(results, source)
    
    def _save_to_database(self, results: List[Dict[str, Any]], source: str):
        """Save crawl results to the database."""
        saved_count = 0
        skipped_count = 0
        
        with get_db_session() as db:
            for job_data in results:
                try:
                    source_url = job_data.get('source_url') or job_data.get('url') or job_data.get('link')
                    if not source_url:
                        logger.warning(f"Job without source_url, skipping: {job_data.get('title', 'Unknown')}")
                        skipped_count += 1
                        continue
                    
                    existing_job = job_crud.get_by_source_url(db, source_url)
                    if existing_job:
                        logger.debug(f"Job already exists: {source_url}")
                        skipped_count += 1
                        continue
                    
                    job_create_data = {
                        'title': job_data.get('title', 'Unknown Title'),
                        'source_url': source_url,
                        'company_name': job_data.get('company_name') or job_data.get('company'),
                        'location': job_data.get('location'),
                        'source': source,
                        'description': job_data.get('description'),
                        'requirements_text': job_data.get('requirements_text') or job_data.get('requirements'),
                        'job_type': job_data.get('job_type') or job_data.get('employment_type'),
                        'level': job_data.get('level') or job_data.get('experience_level'),
                        'salary_min': job_data.get('salary_min'),
                        'salary_max': job_data.get('salary_max'),
                        'salary_currency': job_data.get('salary_currency', 'VND'),
                        'salary_text': job_data.get('salary_text') or job_data.get('salary'),
                        'experience_years_min': job_data.get('experience_years_min'),
                        'experience_years_max': job_data.get('experience_years_max'),
                        'required_skills': job_data.get('required_skills') or job_data.get('skills', []),
                        'preferred_skills': job_data.get('preferred_skills', []),
                        'benefits': job_data.get('benefits', []),
                        'is_remote': job_data.get('is_remote', False),
                        'is_active': True,
                    }
                    
                    job_create = JobCreate(**job_create_data)
                    job_crud.create(db, job_create)
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"Error saving job to database: {e}")
                    skipped_count += 1
                    continue
            
        logger.info(f"Database: Saved {saved_count} jobs, skipped {skipped_count} duplicates/errors")

    async def get_job(self, job_id: str) -> Optional[CrawlJob]:
        """Get a job by ID."""
        return self.jobs.get(job_id)
    
    async def list_jobs(
        self,
        limit: int = 20,
        offset: int = 0,
        source: Optional[str] = None,
        status: Optional[CrawlStatus] = None
    ) -> List[CrawlJob]:
        """List jobs with optional filtering."""
        jobs = list(self.jobs.values())
        
        if source:
            jobs = [j for j in jobs if j.source == source.lower()]
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[offset:offset + limit]
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [CrawlStatus.COMPLETED, CrawlStatus.FAILED, CrawlStatus.CANCELLED]:
            return False
        
        job.status = CrawlStatus.CANCELLED
        job.completed_at = datetime.now()
        if job.started_at:
            job.duration = (job.completed_at - job.started_at).total_seconds()
        
        logger.info(f"Cancelled job {job_id}")
        return True