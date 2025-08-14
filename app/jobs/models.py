from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime

class JobCreate(BaseModel):
    job_description: str = Field(..., min_length=100, description="Job description text")
    title: Optional[str] = Field(None, description="Job title", max_length=255)
    company: Optional[str] = Field(None, description="Company name", max_length=255)
    
    @field_validator('job_description')
    def validate_job_description(cls, v):
        if len(v.strip()) < 100:
            raise ValueError('Job description must be at least 100 characters long')
        return v.strip()


class JobResponse(BaseModel):
    id: int
    job_description: str
    title: Optional[str]
    company: Optional[str]
    must_have_skills: List[str]
    nice_to_have_skills: List[str]
    created_at: datetime
