from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi_cache.decorator import cache
from app.services.redis import cache_key_builder, FastAPICache
from typing import List
import logging
import json

from app.jobs.models import JobCreate, JobResponse
from app.jobs.repositories import JobRepository
from app.db import get_database
from app.services.scoring import extract_job_requirements

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_repository(db=Depends(get_database)) -> JobRepository:
    """Dependency to get job repository."""
    return JobRepository(db)

@router.post("/", response_model=JobResponse)
async def create_job(job_data: JobCreate, repo: JobRepository = Depends(get_repository)):
    """Create a new job description and invalidate cache."""
    try:
        logger.info(f"Creating job with description length: {len(job_data.job_description)}")
        
        must_have_skills, nice_to_have_skills = extract_job_requirements(job_data.job_description)
        logger.info(f"Extracted {len(must_have_skills)} must-have and {len(nice_to_have_skills)} nice-to-have skills")
        
        result = await repo.create_job(
            job_description=job_data.job_description,
            title=job_data.title,
            company=job_data.company,
            must_have_skills=must_have_skills,
            nice_to_have_skills=nice_to_have_skills
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create job")
        
        job_response = JobResponse(
            id=result["id"],
            job_description=result["job_description"],
            title=result["title"],
            company=result["company"],
            must_have_skills=json.loads(result["must_have_skills"]),
            nice_to_have_skills=json.loads(result["nice_to_have_skills"]),
            created_at=result["created_at"]
        )
        
        await FastAPICache.clear()
        return job_response
        
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job")

@router.get("/", response_model=List[JobResponse])
@cache(expire=300, key_builder=cache_key_builder)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    repo: JobRepository = Depends(get_repository)
):
    """List jobs with pagination and caching."""
    try:
        results = await repo.list_jobs(page, page_size)
        return [
            JobResponse(
                id=row["id"],
                job_description=row["job_description"],
                title=row["title"],
                company=row["company"],
                must_have_skills=json.loads(row["must_have_skills"]) if row["must_have_skills"] else [],
                nice_to_have_skills=json.loads(row["nice_to_have_skills"]) if row["nice_to_have_skills"] else [],
                created_at=row["created_at"]
            )
            for row in results
        ]
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list jobs")

@router.get("/{job_id}", response_model=JobResponse)
@cache(expire=300, key_builder=cache_key_builder)  # Cache for 5 minutes
async def get_job(job_id: int, repo: JobRepository = Depends(get_repository)):
    """Get a specific job by ID with caching."""
    try:
        result = await repo.get_job_by_id(job_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobResponse(
            id=result["id"],
            job_description=result["job_description"],
            title=result["title"],
            company=result["company"],
            must_have_skills=json.loads(result["must_have_skills"]) if result["must_have_skills"] else [],
            nice_to_have_skills=json.loads(result["nice_to_have_skills"]) if result["nice_to_have_skills"] else [],
            created_at=result["created_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job")