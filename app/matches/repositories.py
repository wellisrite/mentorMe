from typing import Dict, Optional
import json
import logging
from databases import Database
from fastapi_cache.decorator import cache
from app.services.redis import cache_key_builder, FastAPICache

logger = logging.getLogger(__name__)

class MatchRepository:
    def __init__(self, db: Database):
        self.db = db

    @cache(expire=120, key_builder=cache_key_builder)
    async def get_existing_match(self, profile_id: int, job_id: int) -> Optional[Dict]:
        """Get existing match if it exists (cached for 2 minutes)."""
        logger.debug(f"🔍 DB QUERY: get_existing_match(profile_id={profile_id}, job_id={job_id})")
        query = """
            SELECT * FROM matches 
            WHERE profile_id = :profile_id AND job_id = :job_id
        """
        result = await self.db.fetch_one(
            query=query,
            values={"profile_id": profile_id, "job_id": job_id}
        )
        if result:
            logger.debug(f"📋 DB RESULT: found match with profile_id={result['profile_id']}, job_id={result['job_id']}")
        else:
            logger.debug(f"📋 DB RESULT: no match found for profile_id={profile_id}, job_id={job_id}")
        return result

    async def get_existing_match_from_db(self, profile_id: int, job_id: int) -> Optional[Dict]:
        """Get existing match directly from DB without cache (for duplicate handling)."""
        logger.debug(f"Fetching existing match for profile {profile_id}, job {job_id} directly from DB")
        query = """
            SELECT * FROM matches 
            WHERE profile_id = :profile_id AND job_id = :job_id
        """
        return await self.db.fetch_one(
            query=query,
            values={"profile_id": profile_id, "job_id": job_id}
        )

    @cache(expire=300, key_builder=cache_key_builder)  # Cache profiles for 5 minutes
    async def get_profile(self, profile_id: int) -> Optional[Dict]:
        """Get profile by ID."""
        query = "SELECT * FROM profiles WHERE id = :profile_id"
        return await self.db.fetch_one(
            query=query, 
            values={"profile_id": profile_id}
        )

    @cache(expire=300, key_builder=cache_key_builder)  # Cache jobs for 5 minutes
    async def get_job(self, job_id: int) -> Optional[Dict]:
        """Get job by ID."""
        query = "SELECT * FROM jobs WHERE id = :job_id"
        return await self.db.fetch_one(
            query=query, 
            values={"job_id": job_id}
        )

    async def create_match(self, 
                          profile_id: int, 
                          job_id: int, 
                          match_score: float, 
                          reasons: list, 
                          suggestions: list) -> Dict:
        """
        Create a new match and return its data.
        Invalidates relevant caches after creation.
        """
        query = """
            INSERT INTO matches (profile_id, job_id, match_score, reasons, suggestions)
            VALUES (:profile_id, :job_id, :match_score, :reasons, :suggestions)
            RETURNING id, profile_id, job_id, match_score, reasons, suggestions, created_at
        """
        
        result = await self.db.fetch_one(
            query=query,
            values={
                "profile_id": profile_id,
                "job_id": job_id,
                "match_score": match_score,
                "reasons": json.dumps([reason.dict() for reason in reasons]),
                "suggestions": json.dumps([suggestion.dict() for suggestion in suggestions])
            }
        )

        # Invalidate specific cache keys after creating a match
        await self._invalidate_match_cache(profile_id, job_id)
        await self._invalidate_report_cache(profile_id)

        return result

    async def _invalidate_match_cache(self, profile_id: int, job_id: int):
        """Invalidate the cache for the specific match that was just created."""
        try:
            # Build the cache key for the specific match
            cache_key = cache_key_builder(
                self.get_existing_match,
                self,  # This will be filtered out by cache_key_builder
                profile_id, 
                job_id
            )
            
            backend = FastAPICache.get_backend()
            if backend:
                full_key = f"mentorme_cache:{cache_key}"
                await backend.clear(full_key)
                logger.debug(f"Invalidated cache for match: profile {profile_id}, job {job_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate match cache: {e}")

    async def _invalidate_report_cache(self, profile_id: int):
        """Invalidate cached report for the profile."""
        try:
            backend = FastAPICache.get_backend()
            if backend:
                # Use pattern matching to clear all report-related cache keys for this profile
                pattern = f"mentorme_cache:*report*{profile_id}*"
                
                # Get Redis client from backend
                redis_client = backend.redis
                keys = await redis_client.keys(pattern)
                if keys:
                    await redis_client.delete(*keys)
                    logger.debug(f"Cleared {len(keys)} report cache entries for profile {profile_id}")
        except Exception as e:
            logger.warning(f"Failed to clear report cache for profile {profile_id}: {e}")