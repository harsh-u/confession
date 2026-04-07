import hmac
import hashlib
import json
import logging
import os
from base64 import urlsafe_b64encode

from fastapi import APIRouter, Depends, Request, HTTPException, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Confession, PostStatus

router = APIRouter()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")

ADMIN_COOKIE_NAME = "admin_session"
ADMIN_COOKIE_MAX_AGE = 86400 * 7  # 7 days


def _admin_cookie_value() -> str:
    """Produce a signed value for the admin cookie."""
    raw = b"admin_verified"
    sig = hmac.new(
        settings.secret_key.encode(),
        raw,
        hashlib.sha256,
    ).hexdigest()
    return urlsafe_b64encode(sig.encode()).decode().rstrip("=")


def verify_admin_cookie(cookie: str | None) -> bool:
    if not cookie:
        return False
    try:
        expected = _admin_cookie_value()
        return hmac.compare_digest(cookie, expected)
    except Exception:
        return False


def require_admin(request: Request) -> None:
    cookie = request.cookies.get(ADMIN_COOKIE_NAME)
    if not verify_admin_cookie(cookie):
        raise HTTPException(status_code=401, detail="Admin authentication required")


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Serve admin UI: login form if not authenticated, otherwise pending list."""
    cookie = request.cookies.get(ADMIN_COOKIE_NAME)
    if not verify_admin_cookie(cookie):
        return templates.TemplateResponse(
            "admin.html",
            {"request": request, "logged_in": False},
        )
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "logged_in": True},
    )


@router.post("/admin/login")
async def admin_login(password: str = Form(...)):
    if not settings.admin_password:
        raise HTTPException(status_code=503, detail="Admin login not configured")
    if password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid password")
    value = _admin_cookie_value()
    resp = RedirectResponse(url="/admin", status_code=302)
    resp.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=value,
        max_age=ADMIN_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


@router.post("/admin/logout")
async def admin_logout(response: Response):
    resp = RedirectResponse(url="/admin", status_code=302)
    resp.delete_cookie(ADMIN_COOKIE_NAME, path="/")
    return resp


@router.get("/admin/api/pending")
async def admin_list_pending(
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    confessions = (
        db.query(Confession)
        .filter(Confession.posted_status == PostStatus.PENDING)
        .order_by(Confession.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "text": c.text,
            "image_path": c.image_path,
            "caption": c.caption or "",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in confessions
    ]


@router.post("/admin/api/approve/{confession_id}")
async def admin_approve(
    confession_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    confession = db.query(Confession).filter(Confession.id == confession_id).first()
    if not confession:
        raise HTTPException(status_code=404, detail="Confession not found")
    if confession.posted_status != PostStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Confession is not pending (status: {confession.posted_status})",
        )

    caption = confession.caption or ""
    
    # Use the stored image_path directly if it's an S3 URL (starts with http)
    if confession.image_path and confession.image_path.startswith("http"):
        image_url = confession.image_path
    else:
        base = (settings.public_base_url or "").strip().rstrip("/")
        path_segment = os.path.basename(confession.image_path)
        image_url = f"{base}/generated_images/{path_segment}" if base else None

    if settings.sqs_queue_url:
        if not image_url:
            raise HTTPException(
                status_code=503,
                detail="PUBLIC_BASE_URL not set; cannot build image URL for Instagram",
            )
        try:
            import boto3

            sqs = boto3.client("sqs", region_name=settings.aws_region)
            body = json.dumps({"image_url": image_url, "caption": caption})
            sqs.send_message(QueueUrl=settings.sqs_queue_url, MessageBody=body)
        except Exception as e:
            logger.exception("SQS send failed for confession %s", confession_id)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to queue post: {e!s}",
            )

        confession.posted_status = PostStatus.APPROVED_QUEUED
        db.add(confession)
        db.commit()
        return {"ok": True, "message": "Approved and queued for Instagram"}

    if not image_url:
        raise HTTPException(
            status_code=503,
            detail="PUBLIC_BASE_URL not set; cannot build image URL for Instagram",
        )

    try:
        from app.services import instagram_api

        instagram_api.post_image(image_url, caption)
    except Exception as e:
        logger.exception("Direct Instagram post failed for confession %s", confession_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to post to Instagram: {e!s}",
        )

    confession.posted_status = PostStatus.POSTED
    db.add(confession)
    db.commit()

    return {"ok": True, "message": "Approved and posted to Instagram"}
