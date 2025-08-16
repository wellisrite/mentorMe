from typing import Optional
import logging
from .repositories import MatchRepository
from ..db import get_database
from fastapi import Depends

logger = logging.getLogger(__name__)

class MatchService:
    """Service layer for match operations"""
    
    def __init__(self, repo: MatchRepository):
        self.repo = repo
    
    async def invalidate_matches_for_profile(self, profile_id: int) -> int:
        """Invalidate (delete) all matches for a profile from both DB and cache"""
        try:
            rows_affected = await self.repo.invalidate_matches_for_profile(profile_id)
            logger.info(f"Service: Invalidated {rows_affected} matches for profile {profile_id}")
            return rows_affected
        except Exception as e:
            logger.error(f"Service error invalidating matches for profile {profile_id}: {e}")
            raise
    
    async def invalidate_matches_for_job(self, job_id: int) -> int:
        """Invalidate (delete) all matches for a job from both DB and cache"""
        try:
            rows_affected = await self.repo.invalidate_matches_for_job(job_id)
            logger.info(f"Service: Invalidated {rows_affected} matches for job {job_id}")
            return rows_affected
        except Exception as e:
            logger.error(f"Service error invalidating matches for job {job_id}: {e}")
            raise
