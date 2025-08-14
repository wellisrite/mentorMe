from fastapi import APIRouter, HTTPException
import logging

from app.services import scoring
from app.jobs.routers import router as jobs_router
from app.profiles.routers import router as profiles_router
from app.matches.routers import router as matches_router
from app.health.routers import router as health_router

logger = logging.getLogger(__name__)

# Create main router
main_router = APIRouter()

# Root endpoint
@main_router.get("/")
async def root():
    return {"message": "Career Mirror API - CV to Job Matching Service"}

# Reports endpoint
@main_router.get("/reports/{profile_id}")
async def get_profile_report(profile_id: int):
    """Get aggregate matching report for a profile across all jobs."""
    try:
        report = await scoring.get_profile_aggregate_report(profile_id)
        return report
    except Exception as e:
        logger.error(f"Error generating profile report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")

# Export all routers
__all__ = ['main_router', 'health_router', 'profiles_router', 'jobs_router', 'matches_router']