from sqlalchemy import Column, Integer, String, DateTime, Enum
from datetime import datetime
import enum
from app.database import Base


class PostStatus(str, enum.Enum):
    """Status of Instagram post"""
    PENDING = "pending"
    POSTED = "posted"
    FAILED = "failed"


class Confession(Base):
    """Confession model for database"""
    __tablename__ = "confessions"
    
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(500), nullable=False)
    image_path = Column(String(255), nullable=False)
    posted_status = Column(Enum(PostStatus), default=PostStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_hash = Column(String(64), nullable=False)  # Hashed IP for rate limiting
    
    def __repr__(self):
        return f"<Confession(id={self.id}, status={self.posted_status}, created_at={self.created_at})>"
