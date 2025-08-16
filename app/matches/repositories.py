from typing import Dict, Optional
import json
import logging
from databases import Database
from ..services.cache import cache_service, build_cache_key, CacheConfig

logger = logging.getLogger(__name__)

class MatchRepository:
    def __init__(self, db: Database):
        self.db = db

    async def get_existing_match(self, profile_id: int, job_id: int) -> Optional[Dict]:
        """Get existing match with caching"""
        cache_key = build_cache_key("match", profile_id, job_id)
        cached_result = await cache_service.get(cache_key)
        
        if cached_result:
            return cached_result
        
        query = """
            SELECT * FROM matches 
            WHERE profile_id = :profile_id AND job_id = :job_id
        """
        result = await self.db.fetch_one(
            query=query,
            values={"profile_id": profile_id, "job_id": job_id}
        )
        
        if result:
            result_dict = dict(result)
            await cache_service.set(cache_key, result_dict, CacheConfig.MATCH_TTL)
            return result_dict
        
        return None

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

    async def create_match(self, profile_id: int, job_id: int, 
                          match_score: float, reasons: list, suggestions: list) -> Dict:
        """Create match and manage cache"""
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
        
        result_dict = dict(result)
        
        # Cache the new match
        cache_key = build_cache_key("match", profile_id, job_id)
        await cache_service.set(cache_key, result_dict, CacheConfig.MATCH_TTL)
        
        # Invalidate related list caches
        await cache_service.delete_pattern(f"matches:profile:{profile_id}:*")
        await cache_service.delete_pattern(f"matches:job:{job_id}:*")
        
        return result_dict

    async def invalidate_matches_for_profile(self, profile_id: int) -> int:
        """Delete all matches for a profile from database and cache"""
        try:
            # Delete from database first
            query = "DELETE FROM matches WHERE profile_id = :profile_id"
            rows_affected = await self.db.execute(
                query=query,
                values={"profile_id": profile_id}
            )
            
            # Clear all match-related cache for this profile
            await self._clear_all_profile_matches_cache(profile_id)
            await self._clear_report_cache_only(profile_id)
            
            logger.info(f"Invalidated {rows_affected} matches for profile {profile_id}")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Error invalidating matches for profile {profile_id}: {e}")
            # Still try to clear cache
            await self._clear_all_profile_matches_cache(profile_id)
            await self._clear_report_cache_only(profile_id)
            return 0
    
    async def invalidate_matches_for_job(self, job_id: int) -> int:
        """Delete all matches for a job from database and cache"""
        try:
            # Get all profile IDs that have matches with this job (for cache clearing)
            profile_query = "SELECT DISTINCT profile_id FROM matches WHERE job_id = :job_id"
            profiles = await self.db.fetch_all(
                query=profile_query,
                values={"job_id": job_id}
            )
            
            # Delete from database
            delete_query = "DELETE FROM matches WHERE job_id = :job_id"
            rows_affected = await self.db.execute(
                query=delete_query,
                values={"job_id": job_id}
            )
            
            # Clear cache for all affected profiles
            for profile in profiles:
                profile_id = profile["profile_id"]
                await self._clear_match_cache_only(profile_id, job_id)
                await self._clear_report_cache_only(profile_id)
            
            # Clear job-related match lists
            await cache_service.delete_pattern(f"matches:job:{job_id}:*")
            
            logger.info(f"Invalidated {rows_affected} matches for job {job_id}")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Error invalidating matches for job {job_id}: {e}")
            # Still try to clear cache
            await cache_service.delete_pattern(f"matches:job:{job_id}:*")
            return 0
    
    async def _clear_all_profile_matches_cache(self, profile_id: int):
        """Clear all match-related cache entries for a specific profile"""
        patterns_to_clear = [
            f"match:{profile_id}:*",
            f"match:*:{profile_id}:*", 
            f"matches:profile:{profile_id}:*",
            f"mentorme_cache:*match*{profile_id}*",
            f"existing_match:{profile_id}:*"
        ]
        
        for pattern in patterns_to_clear:
            await cache_service.delete_pattern(pattern)
        
        logger.debug(f"Cleared all match cache entries for profile {profile_id}")
    
    async def _clear_match_cache_only(self, profile_id: int, job_id: int):
        """Clear cache only for the specific match (used during match creation)."""
        try:
            # Build the cache key for the specific match using the same pattern as get_existing_match
            cache_key = build_cache_key("existing_match", profile_id, job_id)
            
            # Clear the specific match cache
            await cache_service.delete(cache_key)
            
            # Also clear any FastAPI-Cache style keys if using mentorme_cache prefix
            fastapi_cache_key = f"mentorme_cache:{cache_key}"
            await cache_service.delete(fastapi_cache_key)
            
            # Clear related match list patterns
            await cache_service.delete_pattern(f"matches:profile:{profile_id}:*")
            await cache_service.delete_pattern(f"matches:job:{job_id}:*")
            await cache_service.delete_pattern(f"*match*{profile_id}*{job_id}*")
            
            logger.debug(f"Cleared cache for match: profile {profile_id}, job {job_id}")
            
        except Exception as e:
            logger.warning(f"Failed to clear match cache: {e}")
    
    async def _clear_report_cache_only(self, profile_id: int):
        """Clear cached report for the profile (cache only, no DB operations)."""
        try:
            # Clear all report-related cache keys for this profile using pattern matching
            patterns_to_clear = [
                f"*report*{profile_id}*",
                f"mentorme_cache:*report*{profile_id}*",
                f"profile_report:{profile_id}*",
                f"report:profile:{profile_id}*"
            ]
            
            for pattern in patterns_to_clear:
                await cache_service.delete_pattern(pattern)
            
            logger.debug(f"Cleared report cache entries for profile {profile_id}")
            
        except Exception as e:
            logger.warning(f"Failed to clear report cache for profile {profile_id}: {e}")