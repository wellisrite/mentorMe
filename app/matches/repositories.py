from typing import Dict, Optional
import json
import logging
from databases import Database

logger = logging.getLogger(__name__)

class MatchRepository:
    def __init__(self, db: Database):
        self.db = db
    
    async def get_existing_match(self, profile_id: int, job_id: int) -> Optional[Dict]:
        """Get existing match if it exists."""
        query = """
            SELECT * FROM matches 
            WHERE profile_id = :profile_id AND job_id = :job_id
        """
        return await self.db.fetch_one(
            query=query,
            values={"profile_id": profile_id, "job_id": job_id}
        )
    
    async def get_profile(self, profile_id: int) -> Optional[Dict]:
        """Get profile by ID."""
        query = "SELECT * FROM profiles WHERE id = :profile_id"
        return await self.db.fetch_one(
            query=query, 
            values={"profile_id": profile_id}
        )
    
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
        """Create a new match and return its data."""
        query = """
            INSERT INTO matches (profile_id, job_id, match_score, reasons, suggestions)
            VALUES (:profile_id, :job_id, :match_score, :reasons, :suggestions)
            RETURNING id, profile_id, job_id, match_score, reasons, suggestions, created_at
        """
        
        return await self.db.fetch_one(
            query=query,
            values={
                "profile_id": profile_id,
                "job_id": job_id,
                "match_score": match_score,
                "reasons": json.dumps([reason.dict() for reason in reasons]),
                "suggestions": json.dumps([suggestion.dict() for suggestion in suggestions])
            }
        )