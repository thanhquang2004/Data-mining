"""
Dashboard API - Analytics endpoints for job data visualization.
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import get_db, Job, JobIT

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get overall dashboard statistics."""
    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    active_jobs = db.query(func.count(Job.id)).filter(Job.is_active == True).scalar() or 0
    
    sources = db.query(
        Job.source,
        func.count(Job.id).label('count')
    ).group_by(Job.source).all()
    
    jobs_by_source = {s.source or 'unknown': s.count for s in sources}
    
    remote_count = db.query(func.count(Job.id)).filter(Job.is_remote == True).scalar() or 0
    
    jobs_with_salary = db.query(func.count(Job.id)).filter(
        Job.salary_min.isnot(None)
    ).scalar() or 0
    
    avg_salary = db.query(
        func.avg((Job.salary_min + Job.salary_max) / 2)
    ).filter(
        Job.salary_min.isnot(None),
        Job.salary_max.isnot(None)
    ).scalar()
    
    return {
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "inactive_jobs": total_jobs - active_jobs,
        "jobs_by_source": jobs_by_source,
        "remote_jobs": remote_count,
        "onsite_jobs": total_jobs - remote_count,
        "jobs_with_salary": jobs_with_salary,
        "average_salary": round(avg_salary, 2) if avg_salary else None,
        "last_updated": datetime.now().isoformat()
    }


@router.get("/skills")
async def get_skills_analytics(
    limit: int = Query(20, ge=1, le=100, description="Number of top skills to return"),
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db)
):
    """Get top skills analytics from job postings."""
    query = db.query(Job.required_skills, Job.preferred_skills)
    
    if source:
        query = query.filter(Job.source == source)
    
    jobs = query.filter(Job.is_active == True).all()
    
    required_skills_counter = Counter()
    preferred_skills_counter = Counter()
    all_skills_counter = Counter()
    
    for job in jobs:
        if job.required_skills:
            skills = job.required_skills if isinstance(job.required_skills, list) else []
            for skill in skills:
                if skill:
                    skill_lower = skill.strip().lower()
                    required_skills_counter[skill_lower] += 1
                    all_skills_counter[skill_lower] += 1
        
        if job.preferred_skills:
            skills = job.preferred_skills if isinstance(job.preferred_skills, list) else []
            for skill in skills:
                if skill:
                    skill_lower = skill.strip().lower()
                    preferred_skills_counter[skill_lower] += 1
                    all_skills_counter[skill_lower] += 1
    
    return {
        "top_required_skills": [
            {"skill": skill, "count": count} 
            for skill, count in required_skills_counter.most_common(limit)
        ],
        "top_preferred_skills": [
            {"skill": skill, "count": count} 
            for skill, count in preferred_skills_counter.most_common(limit)
        ],
        "top_all_skills": [
            {"skill": skill, "count": count} 
            for skill, count in all_skills_counter.most_common(limit)
        ],
        "total_unique_skills": len(all_skills_counter)
    }


@router.get("/locations")
async def get_location_analytics(
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get job distribution by location."""
    query = db.query(
        Job.location,
        func.count(Job.id).label('count')
    ).filter(
        Job.is_active == True,
        Job.location.isnot(None)
    )
    
    if source:
        query = query.filter(Job.source == source)
    
    locations = query.group_by(Job.location).order_by(
        func.count(Job.id).desc()
    ).limit(limit).all()
    
    return {
        "locations": [
            {"location": loc.location, "count": loc.count}
            for loc in locations
        ],
        "total_locations": len(locations)
    }


@router.get("/companies")
async def get_company_analytics(
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get top hiring companies."""
    query = db.query(
        Job.company_name,
        func.count(Job.id).label('job_count'),
        func.avg(Job.company_rating).label('avg_rating')
    ).filter(
        Job.is_active == True,
        Job.company_name.isnot(None)
    )
    
    if source:
        query = query.filter(Job.source == source)
    
    companies = query.group_by(Job.company_name).order_by(
        func.count(Job.id).desc()
    ).limit(limit).all()
    
    return {
        "companies": [
            {
                "company": comp.company_name,
                "job_count": comp.job_count,
                "avg_rating": round(comp.avg_rating, 2) if comp.avg_rating else None
            }
            for comp in companies
        ]
    }


@router.get("/salary")
async def get_salary_analytics(
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get salary distribution analytics."""
    query = db.query(Job).filter(
        Job.is_active == True,
        Job.salary_min.isnot(None)
    )
    
    if source:
        query = query.filter(Job.source == source)
    
    jobs_with_salary = query.all()
    
    # Salary ranges distribution
    salary_ranges = {
        "0-500": 0,
        "500-1000": 0,
        "1000-2000": 0,
        "2000-3000": 0,
        "3000-5000": 0,
        "5000+": 0
    }
    
    salary_by_level = {}
    
    for job in jobs_with_salary:
        avg_salary = (job.salary_min + (job.salary_max or job.salary_min)) / 2
        
        # Categorize by salary range (assuming USD or converted values)
        if avg_salary < 500:
            salary_ranges["0-500"] += 1
        elif avg_salary < 1000:
            salary_ranges["500-1000"] += 1
        elif avg_salary < 2000:
            salary_ranges["1000-2000"] += 1
        elif avg_salary < 3000:
            salary_ranges["2000-3000"] += 1
        elif avg_salary < 5000:
            salary_ranges["3000-5000"] += 1
        else:
            salary_ranges["5000+"] += 1
        
        # Salary by level
        level = job.level or "Unknown"
        if level not in salary_by_level:
            salary_by_level[level] = {"total": 0, "count": 0}
        salary_by_level[level]["total"] += avg_salary
        salary_by_level[level]["count"] += 1
    
    # Calculate average salary by level
    avg_salary_by_level = {
        level: round(data["total"] / data["count"], 2) if data["count"] > 0 else 0
        for level, data in salary_by_level.items()
    }
    
    return {
        "salary_distribution": [
            {"range": range_name, "count": count}
            for range_name, count in salary_ranges.items()
        ],
        "average_salary_by_level": avg_salary_by_level,
        "total_jobs_with_salary": len(jobs_with_salary)
    }


@router.get("/trends")
async def get_job_trends(
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db)
):
    """Get job posting trends over time."""
    cutoff_date = datetime.now() - timedelta(days=days)
    
    daily_jobs = db.query(
        func.date(Job.created_at).label('date'),
        func.count(Job.id).label('count')
    ).filter(
        Job.created_at >= cutoff_date
    ).group_by(
        func.date(Job.created_at)
    ).order_by(
        func.date(Job.created_at)
    ).all()
    
    source_trends = db.query(
        func.date(Job.created_at).label('date'),
        Job.source,
        func.count(Job.id).label('count')
    ).filter(
        Job.created_at >= cutoff_date
    ).group_by(
        func.date(Job.created_at),
        Job.source
    ).order_by(
        func.date(Job.created_at)
    ).all()
    
    # Format source trends
    source_trends_formatted = {}
    for trend in source_trends:
        date_str = trend.date.isoformat() if trend.date else None
        source = trend.source or 'unknown'
        if source not in source_trends_formatted:
            source_trends_formatted[source] = []
        source_trends_formatted[source].append({
            "date": date_str,
            "count": trend.count
        })
    
    return {
        "daily_jobs": [
            {"date": job.date.isoformat() if job.date else None, "count": job.count}
            for job in daily_jobs
        ],
        "source_trends": source_trends_formatted,
        "period_days": days
    }


@router.get("/levels")
async def get_level_distribution(
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get job distribution by experience level."""
    query = db.query(
        Job.level,
        func.count(Job.id).label('count')
    ).filter(Job.is_active == True)
    
    if source:
        query = query.filter(Job.source == source)
    
    levels = query.group_by(Job.level).all()
    
    return {
        "levels": [
            {"level": level.level or "Not Specified", "count": level.count}
            for level in levels
        ]
    }


@router.get("/job-types")
async def get_job_types_distribution(
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get job distribution by job type (Full-time, Part-time, etc.)."""
    query = db.query(
        Job.job_type,
        func.count(Job.id).label('count')
    ).filter(Job.is_active == True)
    
    if source:
        query = query.filter(Job.source == source)
    
    job_types = query.group_by(Job.job_type).all()
    
    return {
        "job_types": [
            {"type": jt.job_type or "Not Specified", "count": jt.count}
            for jt in job_types
        ]
    }


@router.get("/jobs")
async def get_jobs_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    source: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get paginated list of jobs for dashboard table."""
    query = db.query(Job).filter(Job.is_active == True)
    
    if source:
        query = query.filter(Job.source == source)
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if level:
        query = query.filter(Job.level == level)
    if search:
        query = query.filter(
            (Job.title.ilike(f"%{search}%")) |
            (Job.company_name.ilike(f"%{search}%")) |
            (Job.description.ilike(f"%{search}%"))
        )
    
    total = query.count()
    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "jobs": [
            {
                "id": job.id,
                "title": job.title,
                "company_name": job.company_name,
                "location": job.location,
                "source": job.source,
                "level": job.level,
                "job_type": job.job_type,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "is_remote": job.is_remote,
                "required_skills": job.required_skills or [],
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "source_url": job.source_url
            }
            for job in jobs
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


# ===== JobsIT Endpoints =====

@router.get("/jobs-it/stats")
async def get_jobs_it_stats(db: Session = Depends(get_db)):
    """Get overall statistics for preprocessed IT jobs."""
    total_jobs = db.query(func.count(JobIT.id)).scalar() or 0
    active_jobs = db.query(func.count(JobIT.id)).filter(JobIT.is_active == True).scalar() or 0
    
    sources = db.query(
        JobIT.source,
        func.count(JobIT.id).label('count')
    ).group_by(JobIT.source).all()
    
    jobs_by_source = {s.source or 'unknown': s.count for s in sources}
    
    # Level distribution
    levels = db.query(
        JobIT.level,
        func.count(JobIT.id).label('count')
    ).group_by(JobIT.level).all()
    
    jobs_by_level = {l.level or 'unknown': l.count for l in levels}
    
    # Remote vs Onsite
    remote_count = db.query(func.count(JobIT.id)).filter(JobIT.is_remote == True).scalar() or 0
    
    # Prediction distribution
    pred_dist = db.query(
        JobIT.pred,
        func.count(JobIT.id).label('count')
    ).group_by(JobIT.pred).all()
    
    jobs_by_prediction = {p.pred: p.count for p in pred_dist}
    
    # Experience range stats
    avg_exp_min = db.query(func.avg(JobIT.experience_years_min)).filter(
        JobIT.experience_years_min.isnot(None)
    ).scalar()
    
    avg_exp_max = db.query(func.avg(JobIT.experience_years_max)).filter(
        JobIT.experience_years_max.isnot(None)
    ).scalar()
    
    return {
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "inactive_jobs": total_jobs - active_jobs,
        "jobs_by_source": jobs_by_source,
        "jobs_by_level": jobs_by_level,
        "jobs_by_prediction": jobs_by_prediction,
        "remote_jobs": remote_count,
        "onsite_jobs": total_jobs - remote_count,
        "avg_experience_min": round(avg_exp_min, 1) if avg_exp_min else None,
        "avg_experience_max": round(avg_exp_max, 1) if avg_exp_max else None,
        "last_updated": datetime.now().isoformat()
    }


@router.get("/jobs-it/skills")
async def get_jobs_it_skills(
    limit: int = Query(20, ge=1, le=100, description="Number of top skills to return"),
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db)
):
    """Get top skills analytics from preprocessed IT jobs."""
    query = db.query(JobIT.required_skills)
    
    if source:
        query = query.filter(JobIT.source == source)
    
    jobs = query.filter(JobIT.is_active == True).all()
    
    skills_counter = Counter()
    
    for job in jobs:
        if job.required_skills:
            try:
                # Parse JSON string
                skills = json.loads(job.required_skills) if isinstance(job.required_skills, str) else job.required_skills
                if isinstance(skills, list):
                    for skill in skills:
                        if skill:
                            skill_lower = str(skill).strip().lower()
                            if skill_lower and skill_lower != 'yes':  # Filter out generic terms
                                skills_counter[skill_lower] += 1
            except (json.JSONDecodeError, TypeError):
                pass
    
    return {
        "top_skills": [
            {"skill": skill, "count": count} 
            for skill, count in skills_counter.most_common(limit)
        ],
        "total_skills": len(skills_counter),
        "total_jobs_analyzed": len(jobs)
    }


@router.get("/jobs-it/locations")
async def get_jobs_it_locations(
    limit: int = Query(20, ge=1, le=100, description="Number of top locations to return"),
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db)
):
    """Get top locations for IT jobs."""
    query = db.query(
        JobIT.location,
        func.count(JobIT.id).label('count')
    ).filter(JobIT.location.isnot(None))
    
    if source:
        query = query.filter(JobIT.source == source)
    
    locations = query.filter(JobIT.is_active == True).group_by(JobIT.location).order_by(
        func.count(JobIT.id).desc()
    ).limit(limit).all()
    
    return {
        "top_locations": [
            {"location": loc.location, "count": loc.count}
            for loc in locations
        ]
    }


@router.get("/jobs-it/companies")
async def get_jobs_it_companies(
    limit: int = Query(20, ge=1, le=100, description="Number of top companies to return"),
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db)
):
    """Get top companies hiring for IT jobs."""
    query = db.query(
        JobIT.company_name,
        func.count(JobIT.id).label('count')
    ).filter(JobIT.company_name.isnot(None))
    
    if source:
        query = query.filter(JobIT.source == source)
    
    companies = query.filter(JobIT.is_active == True).group_by(JobIT.company_name).order_by(
        func.count(JobIT.id).desc()
    ).limit(limit).all()
    
    return {
        "top_companies": [
            {"company_name": company.company_name, "count": company.count}
            for company in companies
        ]
    }


@router.get("/jobs-it/levels")
async def get_jobs_it_levels(
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db)
):
    """Get job level distribution for IT jobs."""
    query = db.query(
        JobIT.level,
        func.count(JobIT.id).label('count')
    ).filter(JobIT.level.isnot(None))
    
    if source:
        query = query.filter(JobIT.source == source)
    
    levels = query.filter(JobIT.is_active == True).group_by(JobIT.level).order_by(
        func.count(JobIT.id).desc()
    ).all()
    
    return {
        "levels": [
            {"level": level.level, "count": level.count}
            for level in levels
        ]
    }


@router.get("/jobs-it/predictions")
async def get_jobs_it_predictions(
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db)
):
    """Get prediction/classification distribution for IT jobs."""
    query = db.query(
        JobIT.pred,
        func.count(JobIT.id).label('count')
    )
    
    if source:
        query = query.filter(JobIT.source == source)
    
    predictions = query.filter(JobIT.is_active == True).group_by(JobIT.pred).order_by(
        JobIT.pred
    ).all()
    
    return {
        "predictions": [
            {"prediction": pred.pred, "count": pred.count}
            for pred in predictions
        ]
    }


@router.get("/jobs-it/experience")
async def get_jobs_it_experience(
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db)
):
    """Get experience requirements distribution for IT jobs."""
    query = db.query(JobIT)
    
    if source:
        query = query.filter(JobIT.source == source)
    
    jobs = query.filter(
        JobIT.is_active == True,
        JobIT.experience_years_min.isnot(None)
    ).all()
    
    # Group by experience ranges
    exp_ranges = {
        "0-1": 0,
        "1-3": 0,
        "3-5": 0,
        "5-7": 0,
        "7+": 0
    }
    
    for job in jobs:
        exp_min = job.experience_years_min or 0
        if exp_min < 1:
            exp_ranges["0-1"] += 1
        elif exp_min < 3:
            exp_ranges["1-3"] += 1
        elif exp_min < 5:
            exp_ranges["3-5"] += 1
        elif exp_min < 7:
            exp_ranges["5-7"] += 1
        else:
            exp_ranges["7+"] += 1
    
    return {
        "experience_ranges": [
            {"range": range_name, "count": count}
            for range_name, count in exp_ranges.items()
        ],
        "total_jobs": len(jobs)
    }


@router.get("/jobs-it")
async def get_jobs_it_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    pred: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get paginated list of preprocessed IT jobs."""
    query = db.query(JobIT).filter(JobIT.is_active == True)
    
    if source:
        query = query.filter(JobIT.source == source)
    if location:
        query = query.filter(JobIT.location.ilike(f"%{location}%"))
    if level:
        query = query.filter(JobIT.level == level)
    if pred is not None:
        query = query.filter(JobIT.pred == pred)
    if search:
        query = query.filter(
            (JobIT.title.ilike(f"%{search}%")) |
            (JobIT.company_name.ilike(f"%{search}%")) |
            (JobIT.description.ilike(f"%{search}%"))
        )
    
    total = query.count()
    jobs = query.order_by(JobIT.id.desc()).offset(skip).limit(limit).all()
    
    def parse_json_field(field_value):
        """Parse JSON string field safely."""
        if not field_value:
            return []
        try:
            if isinstance(field_value, str):
                return json.loads(field_value)
            return field_value if isinstance(field_value, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    return {
        "jobs": [
            {
                "id": job.id,
                "title": job.title,
                "company_name": job.company_name,
                "location": job.location,
                "source": job.source,
                "source_url": job.source_url,
                "level": job.level,
                "job_type": job.job_type,
                "experience_years_min": job.experience_years_min,
                "experience_years_max": job.experience_years_max,
                "education_level": job.education_level,
                "required_skills": parse_json_field(job.required_skills),
                "is_remote": job.is_remote,
                "pred": job.pred,
                "description": job.description[:200] + "..." if job.description and len(job.description) > 200 else job.description
            }
            for job in jobs
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }

