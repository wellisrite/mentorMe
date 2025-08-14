from typing import Dict, List, Optional
from databases import Database
import logging
import json

logger = logging.getLogger(__name__)

class ProfileRepository:
    def __init__(self, db: Database):
        self.db = db
    
    async def create_profile(self, cv_text: str, linkedin_url: Optional[str], skills: List[str]) -> Dict:
        """Create a new profile and return its data."""
        query = """
            INSERT INTO profiles (cv_text, linkedin_url, skills) 
            VALUES (:cv_text, :linkedin_url, :skills) 
            RETURNING id, cv_text, linkedin_url, skills, created_at
        """
        
        return await self.db.fetch_one(
            query=query,
            values={
                "cv_text": cv_text,
                "linkedin_url": linkedin_url,
                "skills": json.dumps(skills)
            }
        )
    
    async def list_profiles(self) -> List[Dict]:
        """List all profiles."""
        query = """
            SELECT id, cv_text, linkedin_url, skills, created_at 
            FROM profiles 
            ORDER BY created_at DESC
        """
        return await self.db.fetch_all(query)
    
    async def get_profile_by_id(self, profile_id: int) -> Optional[Dict]:
        """Get a specific profile by ID."""
        query = """
            SELECT id, cv_text, linkedin_url, skills, created_at 
            FROM profiles 
            WHERE id = :profile_id
        """
        return await self.db.fetch_one(query=query, values={"profile_id": profile_id})