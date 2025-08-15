from app.matches.repositories import MatchRepository
from app.db import get_database
from fastapi import Depends

async def invalidate_matches_for_profile(profile_id: int, db=Depends(get_database)):
    repo = MatchRepository(db)
    await repo.invalidate_matches_for_profile(profile_id)

async def invalidate_matches_for_job(job_id: int, db=Depends(get_database)):
    repo = MatchRepository(db)
    await repo.invalidate_matches_for_job(job_id)
