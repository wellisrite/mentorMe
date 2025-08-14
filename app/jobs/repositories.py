from typing import Dict, List, Optional
from databases import Database
import json
import logging

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
        
        return await self.db.fetch_one(
            query=query,
            values={
                "job_description": job_description,
                "title": title,
                "company": company,
                "must_have_skills": json.dumps(must_have_skills),
                "nice_to_have_skills": json.dumps(nice_to_have_skills)
            }
        )

    async def list_jobs(self, page: int = 1, page_size: int = 10) -> List[Dict]:
        """List jobs with pagination."""
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
        """Get a specific job by ID."""
        query = """
            SELECT id, job_description, title, company, must_have_skills, nice_to_have_skills, created_at 
            FROM jobs WHERE id = :job_id
        """
        return await self.db.fetch_one(query=query, values={"job_id": job_id})