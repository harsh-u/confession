from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Database
    database_url: str = "sqlite:///./confessions.db"
    
    # Instagram API
    instagram_user_id: Optional[str] = None
    instagram_access_token: Optional[str] = None
    # Public base URL for image links (e.g. https://abc123.ngrok.io when testing with ngrok)
    public_base_url: Optional[str] = None
    # Optional: ImgBB API key – upload images to ImgBB and use direct CDN URL for Instagram (avoids tunnel timeouts)
    imgbb_api_key: Optional[str] = None

    # Admin UI (approval flow → SQS → Lambda)
    admin_password: Optional[str] = None  # Required for /admin access
    sqs_queue_url: Optional[str] = None  # SQS queue URL for approved posts (Lambda consumes)
    aws_region: str = "eu-north-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    s3_bucket_name: str = "soothing-playlist"

    # Application
    max_confession_length: int = 500
    rate_limit_per_hour: int = 10
    secret_key: str = "change-this-in-production"
    environment: str = "development"
    
    # Image generation
    image_width: int = 1080
    image_height: int = 1080
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
