"""
Job Crawler API - FastAPI application for managing web crawlers.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import CrawlRequest, CrawlJob, CrawlStatus, JobResponse, JobListResponse
from .crawler_service import CrawlerService
from .dashboard import router as dashboard_router
from src.database import init_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Initializing database...")
    init_database()
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="Job Crawler API",
    description="API to trigger and manage job crawlers for ITViec, TopDev, and LinkedIn",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

crawler_service = CrawlerService()
app.include_router(dashboard_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Job Crawler API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "crawl": "POST /api/v1/crawl",
            "get_job": "GET /api/v1/jobs/{job_id}",
            "list_jobs": "GET /api/v1/jobs",
            "sources": "GET /api/v1/sources",
            "dashboard": "/api/v1/dashboard/*",
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/sources")
async def get_sources():
    """Get list of available crawler sources."""
    return {
        "sources": [
            {"id": "itviec", "name": "ITViec", "url": "https://itviec.com"},
            {"id": "topdev", "name": "TopDev", "url": "https://topdev.vn"},
            {"id": "linkedin", "name": "LinkedIn", "url": "https://linkedin.com"},
        ]
    }



@app.post("/api/v1/crawl", response_model=JobResponse)
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    Start a new crawl job.
    
    Args:
        request: Crawl configuration (source, keywords, location, pages)
        
    Returns:
        Job information with job_id for tracking
    """
    try:
        logger.info(f"Received crawl request: {request.dict()}")
        
        # Create and start job
        job = await crawler_service.create_job(request)
        
        # Run crawler in background
        background_tasks.add_task(
            crawler_service.run_crawler,
            job.job_id,
            request
        )
        
        return JobResponse(
            job_id=job.job_id,
            status=job.status,
            source=job.source,
            created_at=job.created_at,
            message="Crawl job started successfully"
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting crawl: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start crawl: {str(e)}")


@app.get("/api/v1/jobs/{job_id}", response_model=CrawlJob)
async def get_job_status(job_id: str):
    """
    Get status and results of a crawl job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Job details including status and results
    """
    try:
        job = await crawler_service.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@app.get("/api/v1/jobs", response_model=JobListResponse)
async def list_jobs(
    limit: int = 20,
    offset: int = 0,
    source: str = None,
    status: CrawlStatus = None
):
    """
    List all crawl jobs with optional filtering.
    
    Args:
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip
        source: Filter by source (itviec, topdev, linkedin)
        status: Filter by status (pending, running, completed, failed)
        
    Returns:
        List of jobs with pagination info
    """
    try:
        jobs = await crawler_service.list_jobs(
            limit=limit,
            offset=offset,
            source=source,
            status=status
        )
        
        return JobListResponse(
            jobs=jobs,
            total=len(jobs),
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@app.delete("/api/v1/jobs/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel a running crawl job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Cancellation confirmation
    """
    try:
        success = await crawler_service.cancel_job(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or cannot be cancelled")
        
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancelled successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
