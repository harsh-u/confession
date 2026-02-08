import base64
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Confession, PostStatus
from app.schemas import ConfessionCreate, SubmissionResponse
from app.services import (
    moderate_content,
    image_generator,
    generate_caption,
    instagram_api,
    InstagramAPIError
)

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


def is_public_url(url: str) -> bool:
    """
    Return True if the URL is reachable from the internet (e.g. by Instagram's servers).
    localhost and private IPs are not public.
    """
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().strip("[]")
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        # Strip IPv6 zone and take first part for numeric checks
        host_for_check = hostname.split("%")[0]
        # Private / internal ranges (IPv4)
        if host_for_check.startswith("192.168.") or host_for_check.startswith("10."):
            return False
        if host_for_check.startswith("172."):
            parts = host_for_check.split(".")
            if len(parts) == 4 and 16 <= int(parts[1]) <= 31:
                return False
        return True
    except Exception:
        return False


def _check_image_url(image_url: str, timeout: int = 10) -> tuple[str, str]:
    """
    Check what the URL returns when fetched without browser headers (like Instagram does).
    Returns:
        ("ok", "") - URL returns a valid image, safe to send to Instagram.
        ("not_image", reason) - URL returns HTML etc. (e.g. ngrok warning). Skip Instagram.
        ("unreachable", reason) - Timeout/connection error from here. Still try Instagram
            (e.g. from Docker we may not reach the tunnel, but Instagram can).
    """
    try:
        resp = requests.get(
            image_url,
            timeout=timeout,
            stream=True,
            headers={"User-Agent": "FacebookPlatform/1.0"},
        )
        resp.raise_for_status()
        content_type = (resp.headers.get("Content-Type") or "").lower().split(";")[0].strip()
        if not content_type.startswith("image/"):
            return "not_image", (
                "URL returns non-image (Content-Type: %s). "
                "E.g. ngrok free tier shows an HTML warning to non-browser requests—Instagram "
                "cannot use it. Use Cloudflare Tunnel (cloudflared) or a paid ngrok plan."
            ) % (content_type or "unknown")
        return "ok", ""
    except requests.exceptions.RequestException as e:
        return "unreachable", str(e)


def upload_image_to_imgbb(file_path: str) -> Optional[str]:
    """
    Upload image to ImgBB and return the direct image URL.
    Returns None on failure. Use this URL for Instagram so they fetch from a fast CDN.
    """
    if not settings.imgbb_api_key:
        return None
    path = Path(file_path)
    if not path.is_file():
        return None
    try:
        with open(path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("ascii")
        r = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": settings.imgbb_api_key, "image": b64},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success") and data.get("data", {}).get("image", {}).get("url"):
            return data["data"]["image"]["url"]
    except Exception as e:
        logger.warning("ImgBB upload failed: %s", e)
    return None


@router.post("/api/submit", response_model=SubmissionResponse)
async def submit_confession(
    confession: ConfessionCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submit a new confession
    
    This endpoint:
    1. Validates and moderates the confession
    2. Checks rate limits
    3. Generates an image
    4. Creates a caption
    5. Posts to Instagram (if configured)
    6. Saves to database
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
        
        # Generate caption
        caption = generate_caption()
        
        # Create database entry
        db_confession = Confession(
            text=confession.text,
            image_path=image_path,
            posted_status=PostStatus.PENDING,
            ip_hash=ip_hash
        )
        db.add(db_confession)
        db.commit()
        db.refresh(db_confession)
        
        # Try to post to Instagram (only if image URL is publicly reachable)
        post_status = PostStatus.PENDING
        public_url = ""  # for error messages
        try:
            if settings.instagram_user_id and settings.instagram_access_token:
                # Prefer ImgBB: upload gives a direct CDN URL so Instagram never times out on tunnels
                image_url_for_instagram = None
                if settings.imgbb_api_key:
                    image_url_for_instagram = upload_image_to_imgbb(image_path)
                    if image_url_for_instagram:
                        logger.info("Using ImgBB URL for Instagram (avoids tunnel timeouts)")

                if not image_url_for_instagram:
                    # Fall back to public base URL or request host
                    if settings.public_base_url:
                        base = settings.public_base_url.rstrip("/")
                        public_url = f"{base}/{image_path}"
                    else:
                        scheme = request.url.scheme
                        host = request.headers.get("host", request.client.host)
                        public_url = f"{scheme}://{host}/{image_path}"

                    if not is_public_url(public_url):
                        logger.warning(
                            "Skipping Instagram post: image URL is not public (localhost/private). "
                            "Instagram's servers cannot reach %s. Set PUBLIC_BASE_URL or IMGBB_API_KEY.",
                            public_url,
                        )
                        post_status = PostStatus.FAILED
                    else:
                        check_status, check_reason = _check_image_url(public_url)
                        if check_status == "not_image":
                            logger.warning("Skipping Instagram post: %s", check_reason)
                            post_status = PostStatus.FAILED
                        else:
                            if check_status == "unreachable":
                                logger.warning(
                                    "Pre-check could not reach image URL (%s). Trying Instagram anyway.",
                                    check_reason,
                                )
                            image_url_for_instagram = public_url

                if image_url_for_instagram:
                    logger.info(f"Posting confession {db_confession.id} to Instagram")
                    logger.info(f"Using URL for Instagram: {image_url_for_instagram[:80]}...")
                    result = instagram_api.post_image(image_url_for_instagram, caption)
                    post_status = PostStatus.POSTED
                    logger.info(f"Successfully posted to Instagram: {result}")
            else:
                logger.warning("Instagram credentials not configured, skipping post")
                post_status = PostStatus.FAILED
        except InstagramAPIError as e:
            err_msg = str(e)
            logger.error(f"Failed to post to Instagram: {err_msg}")
            if "only photo or video" in err_msg.lower() and public_url and "ngrok" in public_url.lower():
                logger.warning(
                    "Instagram got HTML instead of your image. Ngrok free tier shows a warning page "
                    "to non-browser requests (like Instagram's). Use Cloudflare Tunnel instead: "
                    "run 'cloudflared tunnel --url http://localhost:8000' and set PUBLIC_BASE_URL to the *.trycloudflare.com URL."
                )
            post_status = PostStatus.FAILED
        except Exception as e:
            logger.error(f"Unexpected error posting to Instagram: {str(e)}")
            post_status = PostStatus.FAILED
        
        # Update post status
        db_confession.posted_status = post_status
        db.commit()
        
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
