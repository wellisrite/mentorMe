from fastapi import APIRouter, HTTPException
import logging

from app.services import scoring
from app.jobs.routers import router as jobs_router
from app.profiles.routers import router as profiles_router
from app.matches.routers import router as matches_router
from app.health.routers import router as health_router
from app.services.cache import cache_service, CacheConfig, build_cache_key

logger = logging.getLogger(__name__)

# Create main router
main_router = APIRouter()

# Root endpoint
@main_router.get("/")
async def root():
    return {"message": "Career Mirror API - CV to Job Matching Service"}

# Enhanced Reports endpoint with better caching
@main_router.get("/reports/{profile_id}")
async def get_profile_report(profile_id: int):
    """Get aggregate matching report for a profile across all jobs with smart caching."""
    
    # Build cache key for this specific profile report
    # cache_key = build_cache_key("profile_report", profile_id)
    
    # # Try cache first with error handling
    # cached_report = None
    # try:
    #     cached_report = await cache_service.get(cache_key)
    #     if cached_report:
    #         logger.debug(f"Cache hit for profile report {profile_id}")
    #         return cached_report
    # except Exception as cache_error:
    #     logger.warning(f"Cache get failed for profile {profile_id}: {cache_error}")
    #     # Continue without cache - don't fail the request
    
    # Cache miss or cache error - generate report
    try:
        logger.debug(f"Cache miss for profile report {profile_id}")
        report = await scoring.get_profile_aggregate_report(profile_id)
        
        # Try to cache the report with error handling
        try:
            await cache_service.set(cache_key, report, CacheConfig.MATCH_TTL)
            logger.debug(f"Cached report for profile {profile_id}")
        except Exception as cache_error:
            logger.warning(f"Cache set failed for profile {profile_id}: {cache_error}")
            # Continue without caching - don't fail the request
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating profile report for profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")

# Cache invalidation helper for when matches are updated
async def invalidate_profile_report_cache(profile_id: int):
    """Invalidate cached report when profile's matches change."""
    try:
        cache_key = build_cache_key("profile_report", profile_id)
        await cache_service.delete(cache_key)
        logger.debug(f"Invalidated report cache for profile {profile_id}")
    except Exception as e:
        logger.error(f"Error invalidating report cache: {e}")

# Export all routers
__all__ = ['main_router', 'health_router', 'profiles_router', 'jobs_router', 'matches_router']