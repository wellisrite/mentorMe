from typing import Dict, List, Optional
from databases import Database
import logging
import json
from app.services.cache import cache_service, build_cache_key, CacheConfig

logger = logging.getLogger(__name__)

class ProfileRepository:
    def __init__(self, db: Database):
        self.db = db
    
    async def create_profile(self, **profile_data) -> Dict:
        """Create profile and invalidate related caches"""
        # Insert into database
        query = """
            INSERT INTO profiles (cv_text, linkedin_url, skills)
            VALUES (:cv_text, :linkedin_url, :skills)
            RETURNING id, cv_text, linkedin_url, skills, created_at
        """
        
        result = await self.db.fetch_one(query=query, values=profile_data)
        result_dict = dict(result)
        
        # Cache the new profile
        cache_key = build_cache_key("profile", result_dict["id"])
        await cache_service.set(cache_key, result_dict, CacheConfig.PROFILE_TTL)
        
        # Invalidate profile list caches that might be affected
        await cache_service.delete_pattern("profile:list:*")
        await cache_service.delete_pattern("mentorme_cache:*profiles*")
        
        logger.info(f"Created profile {result_dict['id']} and invalidated related caches")
        
        return result_dict
    
    async def list_profiles(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """List all profiles with caching."""
        # Try cache first
        cache_key = build_cache_key("profile:list", limit=limit, offset=offset)
        cached_result = await cache_service.get(cache_key)
        
        if cached_result:
            logger.debug(f"Cache hit for profile list (limit={limit}, offset={offset})")
            return cached_result
        
        # Query database
        query = """
            SELECT id, cv_text, linkedin_url, skills, created_at 
            FROM profiles 
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        results = await self.db.fetch_all(
            query=query, 
            values={"limit": limit, "offset": offset}
        )
        
        # Convert to list of dicts
        results_list = [dict(row) for row in results]
        
        # Cache the results
        await cache_service.set(cache_key, results_list, CacheConfig.PROFILE_TTL)
        logger.debug(f"Cached profile list (limit={limit}, offset={offset})")
        
        return results_list
    
    async def get_profile_by_id(self, profile_id: int) -> Optional[Dict]:
        """Get profile by ID with caching"""
        # Try cache first
        cache_key = build_cache_key("profile", profile_id)
        cached_result = await cache_service.get(cache_key)
        
        if cached_result:
            logger.debug(f"Cache hit for profile {profile_id}")
            return cached_result
        
        # Query database
        query = """
            SELECT id, cv_text, linkedin_url, skills, created_at 
            FROM profiles 
            WHERE id = :profile_id
        """        
        result = await self.db.fetch_one(
            query=query,
            values={"profile_id": profile_id}
        )
        
        # Cache result if found
        if result:
            result_dict = dict(result)
            await cache_service.set(cache_key, result_dict, CacheConfig.PROFILE_TTL)
            logger.debug(f"Cached profile {profile_id}")
            return result_dict
        
        return None
    
    async def update_profile(self, profile_id: int, **updates) -> Optional[Dict]:
        """Update profile and invalidate cache"""
        # Update database
        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        query = f"""
            UPDATE profiles SET {set_clause} 
            WHERE id = :profile_id
            RETURNING id, cv_text, linkedin_url, skills, created_at
        """
        
        values = {**updates, "profile_id": profile_id}
        result = await self.db.fetch_one(query=query, values=values)
        
        if result:
            result_dict = dict(result)
            
            # Update cache
            cache_key = build_cache_key("profile", profile_id)
            await cache_service.set(cache_key, result_dict, CacheConfig.PROFILE_TTL)
            
            # Invalidate related caches
            await cache_service.delete_pattern("profile:list:*")
            await cache_service.delete_pattern(f"match:profile:{profile_id}:*")
            await cache_service.delete_pattern("mentorme_cache:*profiles*")
            
            return result_dict
        
        return None