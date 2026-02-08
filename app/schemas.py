from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional
from app.models import PostStatus


class ConfessionCreate(BaseModel):
    """Schema for creating a confession"""
    text: str = Field(..., min_length=1, max_length=500, description="Confession text")
    
    @validator('text')
    def validate_text(cls, v):
        """Validate confession text"""
        if not v or not v.strip():
            raise ValueError('Confession text cannot be empty')
        return v.strip()


class ConfessionResponse(BaseModel):
    """Schema for confession response"""
    id: int
    text: str
    image_path: str
    posted_status: PostStatus
    created_at: datetime
    
    class Config:
        from_attributes = True


class SubmissionResponse(BaseModel):
    """Schema for submission API response"""
    success: bool
    message: str
    confession_id: Optional[int] = None
