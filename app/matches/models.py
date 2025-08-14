from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime


class MatchRequest(BaseModel):
    profile_id: int = Field(..., description="Profile ID to match")
    job_id: int = Field(..., description="Job ID to match against")


class MatchReason(BaseModel):
    skill: str
    category: str  # 'must_have' or 'nice_to_have'
    status: str    # 'matched' or 'missing'
    weight: float  # contribution to final score


class MatchSuggestion(BaseModel):
    type: str      # 'cv_improvement' or 'keyword'
    suggestion: str
    rationale: str
    priority: str  # 'high', 'medium', 'low'


class MatchResponse(BaseModel):
    profile_id: int
    job_id: int
    match_score: float = Field(..., ge=0, le=100, description="Match score from 0-100")
    reasons: List[MatchReason] = Field(..., description="Detailed matching reasons")
    suggestions: List[MatchSuggestion] = Field(..., description="Improvement suggestions")
    created_at: datetime