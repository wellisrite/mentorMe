from typing import Dict, List, Optional
from databases import Database
import json
import logging

from app.services.cache import cache_service, CacheConfig, cached

logger = logging.getLogger(__name__)

class JobRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create_job(self, 
                        job_description: str,
                        title: str,
                        company: str,
                        must_have_skills: List[str],
                        nice_to_have_skills: List[str]) -> Dict:
        """Create a new job and return its data."""
        query = """
            INSERT INTO jobs (job_description, title, company, must_have_skills, nice_to_have_skills) 
            VALUES (:job_description, :title, :company, :must_have_skills, :nice_to_have_skills) 
            RETURNING id, job_description, title, company, must_have_skills, nice_to_have_skills, created_at
        """
        
        result = await self.db.fetch_one(
            query=query,
            values={
                "job_description": job_description,
                "title": title,
                "company": company,
                "must_have_skills": json.dumps(must_have_skills),
                "nice_to_have_skills": json.dumps(nice_to_have_skills)
            }
        )
        
        # Clear individual job cache patterns after creation
        if result:
            await self._invalidate_job_caches(result["id"])
        
        return result

    @cached(ttl=CacheConfig.JOB_TTL, prefix="job_list")
    async def list_jobs(self, page: int = 1, page_size: int = 10) -> List[Dict]:
        """List jobs with pagination and caching."""
        offset = (page - 1) * page_size
        query = """
            SELECT id, job_description, title, company, must_have_skills, nice_to_have_skills, created_at 
            FROM jobs 
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        return await self.db.fetch_all(
            query=query,
            values={"limit": page_size, "offset": offset}
        )

    async def get_job_by_id(self, job_id: int) -> Optional[Dict]:
        """Get a specific job by ID - caching handled at router level."""
        query = """
            SELECT id, job_description, title, company, must_have_skills, nice_to_have_skills, created_at 
            FROM jobs WHERE id = :job_id
        """
        return await self.db.fetch_one(query=query, values={"job_id": job_id})

    @cached(ttl=CacheConfig.JOB_TTL, prefix="job_exists")
    async def job_exists(self, job_id: int) -> bool:
        """Check if a job exists by ID."""
        query = "SELECT 1 FROM jobs WHERE id = :job_id LIMIT 1"
        result = await self.db.fetch_one(query=query, values={"job_id": job_id})
        return result is not None

    @cached(ttl=CacheConfig.JOB_TTL, prefix="job_count")
    async def get_total_jobs_count(self) -> int:
        """Get total count of jobs for pagination metadata."""
        query = "SELECT COUNT(*) as count FROM jobs"
        result = await self.db.fetch_one(query=query)
        return result["count"] if result else 0

    async def update_job(self,
                        job_id: int,
                        job_description: str = None,
                        title: str = None,
                        company: str = None,
                        must_have_skills: List[str] = None,
                        nice_to_have_skills: List[str] = None) -> Optional[Dict]:
        """Update an existing job and invalidate related caches."""
        
        # Build dynamic update query
        updates = []
        values = {"job_id": job_id}
        
        if job_description is not None:
            updates.append("job_description = :job_description")
            values["job_description"] = job_description
            
        if title is not None:
            updates.append("title = :title")
            values["title"] = title
            
        if company is not None:
            updates.append("company = :company")
            values["company"] = company
            
        if must_have_skills is not None:
            updates.append("must_have_skills = :must_have_skills")
            values["must_have_skills"] = json.dumps(must_have_skills)
            
        if nice_to_have_skills is not None:
            updates.append("nice_to_have_skills = :nice_to_have_skills")
            values["nice_to_have_skills"] = json.dumps(nice_to_have_skills)
        
        if not updates:
            # No updates provided, return current job
            return await self.get_job_by_id(job_id)
        
        query = f"""
            UPDATE jobs 
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = :job_id 
            RETURNING id, job_description, title, company, must_have_skills, nice_to_have_skills, created_at, updated_at
        """
        
        result = await self.db.fetch_one(query=query, values=values)
        
        if result:
            await self._invalidate_job_caches(job_id)
        
        return result

    async def delete_job(self, job_id: int) -> bool:
        """Delete a job and invalidate related caches."""
        query = "DELETE FROM jobs WHERE id = :job_id"
        
        try:
            result = await self.db.execute(query=query, values={"job_id": job_id})
            
            if result:
                await self._invalidate_job_caches(job_id)
                return True
                
        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {e}")
            
        return False

    async def search_jobs(self, 
                         search_term: str = None,
                         company: str = None,
                         page: int = 1,
                         page_size: int = 10) -> List[Dict]:
        """Search jobs with optional filters and caching."""
        
        # Build cache key based on search parameters
        cache_key = f"job_search:{search_term or 'all'}:{company or 'all'}:{page}:{page_size}"
        
        # Try cache first
        cached_result = await cache_service.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for job search: {cache_key}")
            return cached_result
        
        # Build dynamic search query
        conditions = []
        values = {"limit": page_size, "offset": (page - 1) * page_size}
        
        if search_term:
            conditions.append("""
                (job_description ILIKE :search_term 
                 OR title ILIKE :search_term 
                 OR must_have_skills ILIKE :search_term 
                 OR nice_to_have_skills ILIKE :search_term)
            """)
            values["search_term"] = f"%{search_term}%"
        
        if company:
            conditions.append("company ILIKE :company")
            values["company"] = f"%{company}%"
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT id, job_description, title, company, must_have_skills, nice_to_have_skills, created_at 
            FROM jobs 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        
        result = await self.db.fetch_all(query=query, values=values)
        
        # Cache the result
        await cache_service.set(cache_key, result, CacheConfig.SEARCH_TTL)
        logger.debug(f"Cached job search result: {cache_key}")
        
        return result

    async def _invalidate_job_caches(self, job_id: int):
        """Invalidate all caches related to a specific job."""
        try:
            patterns = [
                f"job:{job_id}",              # Individual job cache
                "job_list:*",                 # List jobs cache
                "job_exists:*",               # Job existence checks
                "job_count:*",                # Job count cache
                "job_search:*",               # Search results
                "mentorme_cache:*"            # FastAPI-Cache patterns
            ]
            await cache_service.clear_by_patterns(patterns)
            logger.debug(f"Invalidated caches for job {job_id}")
        except Exception as e:
            logger.error(f"Error invalidating job caches: {e}")