from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any
from datetime import datetime

class ProfileCreate(BaseModel):
    cv_text: Optional[str] = Field(None, min_length=50, description="CV text content")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    
    @field_validator('cv_text')
    @classmethod
    def validate_cv_text(cls, v, values):
        # Use values.data for Pydantic v2
        linkedin_url = values.data.get('linkedin_url') if hasattr(values, "data") else values.get('linkedin_url')
        if not v and not linkedin_url:
            raise ValueError('Either CV text or LinkedIn URL must be provided')
        if v and len(v.strip()) < 50:
            raise ValueError('CV text must be at least 50 characters long')
        return v.strip() if v else v
    
    @field_validator('linkedin_url')
    @classmethod
    def validate_linkedin_url(cls, v):
        if v:
            if not v.startswith(('http://linkedin.com/', 'https://linkedin.com/',
                               'http://www.linkedin.com/', 'https://www.linkedin.com/')):
                raise ValueError('Invalid LinkedIn URL format')
        return v

class ProfileResponse(BaseModel):
    id: int
    cv_text: str
    linkedin_url: Optional[str]
    skills: List[str]
    created_at: datetime

class ProfileReportResponse(BaseModel):
    profile_id: int
    total_jobs_analyzed: int
    average_match_score: float
    top_skills: List[Dict[str, Any]]
    common_gaps: List[Dict[str, Any]]
    recommendations: List[str]
    last_updated: datetime