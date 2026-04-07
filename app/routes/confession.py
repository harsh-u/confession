import hashlib
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Confession, PostStatus
from app.schemas import ConfessionCreate, SubmissionResponse
from app.services import moderate_content, image_generator, generate_caption

router = APIRouter()
logger = logging.getLogger(__name__)


def get_ip_hash(request: Request) -> str:
    """Get hashed IP address for rate limiting"""
    ip = request.client.host
    return hashlib.sha256(ip.encode()).hexdigest()


def check_rate_limit(db: Session, ip_hash: str) -> bool:
    """
    Check if IP has exceeded rate limit

    Args:
        db: Database session
        ip_hash: Hashed IP address

    Returns:
        True if within rate limit, False otherwise
    """
    # Get submissions from this IP in the last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    recent_submissions = db.query(Confession).filter(
        Confession.ip_hash == ip_hash,
        Confession.created_at >= one_hour_ago
    ).count()

    return recent_submissions < settings.rate_limit_per_hour

import boto3
import os
from botocore.exceptions import NoCredentialsError

def get_s3_client():
    """Create S3 client using settings"""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region
    )

def upload_to_s3(file_path: str, object_name: str = None) -> str:
    try:
        s3_client = get_s3_client()
        if object_name is None:
            object_name = os.path.basename(file_path)

        s3_client.upload_file(
            file_path,
            settings.s3_bucket_name,
            object_name,
            ExtraArgs={
                "ContentType": "image/png",
                "ACL": "public-read"
            }
        )

        url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{object_name}"
        return url

    except NoCredentialsError:
        raise Exception("AWS credentials not configured")


@router.post("/api/submit", response_model=SubmissionResponse)
async def submit_confession(
    confession: ConfessionCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submit a new confession.

    Saves as PENDING; no Instagram post here. Admin approves in /admin → SQS → Lambda posts.
    1. Validates and moderates the confession
    2. Checks rate limits
    3. Generates an image and caption
    4. Saves to database with posted_status=PENDING
    """
    try:
        # Get IP hash for rate limiting
        ip_hash = get_ip_hash(request)
        
        # Check rate limit
        if not check_rate_limit(db, ip_hash):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {settings.rate_limit_per_hour} submissions per hour."
            )
        
        # Moderate content
        is_valid, error_message = moderate_content(confession.text)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)
        
        # Generate image
        logger.info("Generating image for confession")
        image_path = image_generator.generate_image(confession.text)

        s3_url = upload_to_s3(image_path)

        # ✅ Delete local file
        if os.path.exists(image_path):
            os.remove(image_path)
        
        # Generate caption (stored for admin approval → SQS → Lambda)
        caption = generate_caption()

        # Create database entry (pending admin approval; no Instagram post here)
        db_confession = Confession(
            text=confession.text,
            image_path=s3_url,
            caption=caption,
            posted_status=PostStatus.PENDING,
            ip_hash=ip_hash
        )
        db.add(db_confession)
        db.commit()
        db.refresh(db_confession)

        return SubmissionResponse(
            success=True,
            message="Confession submitted successfully!",
            confession_id=db_confession.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing confession: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred processing your confession")


@router.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "BeConversive Confession"}
