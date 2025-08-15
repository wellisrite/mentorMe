from fastapi import APIRouter, HTTPException, Depends
from fastapi_cache.decorator import cache
from app.services.redis import cache_key_builder, FastAPICache
from app.services.linkedinscraper import extract_linkedin_profile
from typing import List
import logging
import json

from app.profiles.models import ProfileCreate, ProfileResponse
from app.profiles.repositories import ProfileRepository
from app.db import get_database
from app.services.scoring import extract_skills_from_text

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_repository(db=Depends(get_database)) -> ProfileRepository:
    """Dependency to get profile repository."""
    return ProfileRepository(db)

@router.post("/", response_model=ProfileResponse)
async def create_profile(profile_data: ProfileCreate, repo: ProfileRepository = Depends(get_repository)):
    """Create a new candidate profile from CV text or LinkedIn URL."""
    try:
        # Handle LinkedIn URL case
        if profile_data.linkedin_url and not profile_data.cv_text:
            try:
                logger.info(f"Extracting profile from LinkedIn URL: {profile_data.linkedin_url}")
                cv_text = await extract_linkedin_profile(profile_data.linkedin_url)
                profile_data.cv_text = cv_text
                logger.info(f"Successfully extracted CV text from LinkedIn: {len(cv_text)} chars")
            except NotImplementedError:
                raise HTTPException(
                    status_code=400,
                    detail="LinkedIn profile extraction is not supported in V1. Please provide CV text directly."
                )
            except Exception as e:
                logger.error(f"LinkedIn extraction failed: {e}")
                raise HTTPException(status_code=400, detail=str(e))

        # Validate CV text exists
        if not profile_data.cv_text:
            raise HTTPException(
                status_code=400,
                detail="Either CV text or a valid LinkedIn URL must be provided"
            )

        logger.info(f"Creating profile with CV length: {len(profile_data.cv_text)}")
        
        # Extract skills from CV text
        skills = extract_skills_from_text(profile_data.cv_text)
        logger.info(f"Extracted {len(skills)} skills from CV")
        
        try:
            result = await repo.create_profile(
                cv_text=profile_data.cv_text,
                linkedin_url=profile_data.linkedin_url,
                skills=skills
            )
        except Exception as db_error:
            logger.error(f"Database error while creating profile: {db_error}")
            raise HTTPException(status_code=500, detail="Database error while creating profile")
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create profile")
        
        profile_response = ProfileResponse(
            id=result["id"],
            cv_text=result["cv_text"],
            linkedin_url=result["linkedin_url"],
            skills=json.loads(result["skills"]),
            created_at=result["created_at"]
        )
        
        # Invalidate cache after creating new profile
        try:
            await FastAPICache.clear()
        except Exception as cache_error:
            logger.warning(f"Cache invalidation failed: {cache_error}")
            
        return profile_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[ProfileResponse])
# @cache(expire=300, key_builder=cache_key_builder)
async def list_profiles(repo: ProfileRepository = Depends(get_repository)):
    """List all profiles."""
    try:
        results = await repo.list_profiles()
        return [
            ProfileResponse(
                id=row["id"],
                cv_text=row["cv_text"],
                linkedin_url=row["linkedin_url"],
                skills=json.loads(row["skills"]) if row["skills"] else [],
                created_at=row["created_at"]
            )
            for row in results
        ]
    except Exception as e:
        logger.error(f"Error listing profiles: {e}")
        raise HTTPException(status_code=500, detail="Failed to list profiles")

@router.get("/{profile_id}", response_model=ProfileResponse)
# @cache(expire=300, key_builder=cache_key_builder)
async def get_profile(profile_id: int, repo: ProfileRepository = Depends(get_repository)):
    """Get a specific profile by ID."""
    try:
        result = await repo.get_profile_by_id(profile_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        return ProfileResponse(
            id=result["id"],
            cv_text=result["cv_text"],
            linkedin_url=result["linkedin_url"],
            skills=json.loads(result["skills"]) if result["skills"] else [],
            created_at=result["created_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")