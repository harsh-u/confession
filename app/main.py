import os
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.exceptions import HTTPException

from app.config import settings
from app.database import init_db
from app.routes import confession_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="BeConversive Confession",
    description="Anonymous confession portal with Instagram integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Generated images: serve in one shot with Content-Length so Instagram gets full response before timeout
GENERATED_IMAGES_DIR = Path("generated_images").resolve()

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(confession_router)


@app.get("/generated_images/{path:path}")
async def serve_generated_image(path: str):
    """
    Serve generated confession images with full body + Content-Length so
    Instagram (and tunnels) get the complete response before timeout.
    """
    # Prevent path traversal
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    file_path = GENERATED_IMAGES_DIR / path
    if not file_path.is_file() or not file_path.suffix.lower() == ".png":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        file_path = file_path.resolve()
        base = GENERATED_IMAGES_DIR.resolve()
        if os.path.commonpath([file_path, base]) != str(base):
            raise HTTPException(status_code=404, detail="Not found")
    except (ValueError, OSError):
        raise HTTPException(status_code=404, detail="Not found")
    with open(file_path, "rb") as f:
        body = f.read()
    return Response(
        content=body,
        media_type="image/png",
        headers={
            "Content-Length": str(len(body)),
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")
    
    # Log configuration
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Max confession length: {settings.max_confession_length}")
    logger.info(f"Rate limit: {settings.rate_limit_per_hour} per hour")
    
    if settings.instagram_user_id and settings.instagram_access_token:
        logger.info("Instagram API configured")
    else:
        logger.warning("Instagram API not configured - posts will not be published")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render home page with confession form"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "max_length": settings.max_confession_length
        }
    )


@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    """Render success page"""
    return templates.TemplateResponse("success.html", {"request": request})


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    """Serve robots.txt so crawlers (e.g. Instagram) don't get 404."""
    return "User-agent: *\nAllow: /generated_images/\n"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
