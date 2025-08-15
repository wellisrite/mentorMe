from fastapi import APIRouter, HTTPException, Depends
from fastapi_cache.decorator import cache
from app.services.redis import cache_key_builder
from app.matches.repositories import MatchRepository
import logging
import json
import asyncpg

from app.matches.models import MatchRequest, MatchResponse
from app.db import get_database
from app.services.scoring import calculate_match_score

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_repository(db=Depends(get_database)) -> MatchRepository:
    return MatchRepository(db)

@router.post("/", response_model=MatchResponse)
async def create_match(
    match_request: MatchRequest, 
    repo: MatchRepository = Depends(get_repository)
):
    """Generate match analysis between a profile and job."""
    try:
        profile_id = match_request.profile_id
        job_id = match_request.job_id
        logger.info(f"🔍 RECEIVED REQUEST: profile_id={profile_id}, job_id={job_id}")

        # STEP 1 — Try to get existing match (this will use cache automatically)
        existing_match = await repo.get_existing_match(profile_id, job_id)
        if existing_match:
            logger.info(f"📋 FOUND EXISTING MATCH: profile_id={existing_match['profile_id']}, job_id={existing_match['job_id']}")
            return MatchResponse(
                profile_id=existing_match["profile_id"],
                job_id=existing_match["job_id"],
                match_score=existing_match["match_score"],
                reasons=json.loads(existing_match["reasons"]),
                suggestions=json.loads(existing_match["suggestions"]),
                created_at=existing_match["created_at"]
            )

        # STEP 2 — Get profile & job
        logger.info(f"🔍 FETCHING profile_id={profile_id}, job_id={job_id}")
        profile = await repo.get_profile(profile_id)
        if not profile:
            logger.error(f"❌ Profile {profile_id} not found")
            raise HTTPException(status_code=404, detail="Profile not found")

        job = await repo.get_job(job_id)
        if not job:
            logger.error(f"❌ Job {job_id} not found")
            raise HTTPException(status_code=404, detail="Job not found")
        
        logger.info(f"✅ FOUND profile_id={profile['id']}, job_id={job['id']}")

        # STEP 3 — Calculate match score
        match_result = calculate_match_score(
            profile_skills=json.loads(profile["skills"]) if profile["skills"] else [],
            profile_text=profile["cv_text"],
            must_have_skills=json.loads(job["must_have_skills"]) if job["must_have_skills"] else [],
            nice_to_have_skills=json.loads(job["nice_to_have_skills"]) if job["nice_to_have_skills"] else [],
            job_description=job["job_description"]
        )

        # STEP 4 — Try to insert match
        try:
            stored_match = await repo.create_match(
                profile_id=profile_id,
                job_id=job_id,
                match_score=match_result["match_score"],
                reasons=match_result["reasons"],
                suggestions=match_result["suggestions"]
            )
        except asyncpg.exceptions.UniqueViolationError:
            logger.warning("Duplicate insert detected — fetching existing")
            existing_match = await repo.get_existing_match_from_db(profile_id, job_id)
            if not existing_match:
                raise HTTPException(status_code=500, detail="Duplicate detected but match not found")
            return MatchResponse(
                profile_id=existing_match["profile_id"],
                job_id=existing_match["job_id"],
                match_score=existing_match["match_score"],
                reasons=json.loads(existing_match["reasons"]),
                suggestions=json.loads(existing_match["suggestions"]),
                created_at=existing_match["created_at"]
            )

        # STEP 5 — Return newly created match
        logger.info(f"Match created successfully — score: {match_result['match_score']}")
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
        logger.exception("Unexpected error creating match")
        raise HTTPException(status_code=500, detail="Failed to create match")
