from fastapi import APIRouter, HTTPException, Depends
from app.matches.repositories import MatchRepository
from app.profiles.repositories import ProfileRepository
from app.jobs.repositories import JobRepository
import logging
import json

from app.matches.models import MatchRequest, MatchResponse
from app.db import get_database
from app.services.scoring import calculate_match_score

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_match_repository(db=Depends(get_database)) -> MatchRepository:
    """Dependency to get match repository."""
    return MatchRepository(db)

async def get_profile_repository(db=Depends(get_database)) -> ProfileRepository:
    """Dependency to get profile repository."""
    return ProfileRepository(db)

async def get_job_repository(db=Depends(get_database)) -> JobRepository:
    """Dependency to get job repository."""
    return JobRepository(db)

@router.post("/", response_model=MatchResponse)
async def create_match(
    match_request: MatchRequest, 
    match_repo: MatchRepository = Depends(get_match_repository),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    job_repo: JobRepository = Depends(get_job_repository)
):
    """Generate match analysis between a profile and job."""
    try:
        logger.info(f"Creating match for profile {match_request.profile_id} and job {match_request.job_id}")
        
        # Check existing match
        existing_match = await match_repo.get_existing_match(
            match_request.profile_id, 
            match_request.job_id
        )
        
        if existing_match:
            logger.info("Returning existing match result")
            return MatchResponse(
                profile_id=existing_match["profile_id"],
                job_id=existing_match["job_id"],
                match_score=existing_match["match_score"],
                reasons=json.loads(existing_match["reasons"]),
                suggestions=json.loads(existing_match["suggestions"]),
                created_at=existing_match["created_at"]
            )
        
        # Get profile data from profile repository
        profile = await profile_repo.get_profile_by_id(match_request.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Get job data from job repository
        job = await job_repo.get_job_by_id(match_request.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Calculate match score
        match_result = calculate_match_score(
            profile_skills=json.loads(profile["skills"]) if profile["skills"] else [],
            profile_text=profile["cv_text"],
            must_have_skills=json.loads(job["must_have_skills"]) if job["must_have_skills"] else [],
            nice_to_have_skills=json.loads(job["nice_to_have_skills"]) if job["nice_to_have_skills"] else [],
            job_description=job["job_description"]
        )
        
        # Store match result
        stored_match = await match_repo.create_match(
            profile_id=match_request.profile_id,
            job_id=match_request.job_id,
            match_score=match_result["match_score"],
            reasons=match_result["reasons"],
            suggestions=match_result["suggestions"]
        )
        
        logger.info(f"Match created with score: {match_result['match_score']}")
        
        return MatchResponse(
            profile_id=stored_match["profile_id"],
            job_id=stored_match["job_id"],
            match_score=stored_match["match_score"],
            reasons=json.loads(stored_match["reasons"]),
            suggestions=json.loads(stored_match["suggestions"]),
            created_at=stored_match["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating match: {e}")
        raise HTTPException(status_code=500, detail="Failed to create match")