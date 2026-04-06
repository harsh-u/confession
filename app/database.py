from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_caption_column():
    """Add caption column to confessions if missing (for existing DBs)."""
    if "sqlite" not in settings.database_url:
        return
    with engine.connect() as conn:
        r = conn.execute(text("PRAGMA table_info(confessions)"))
        rows = r.fetchall()
        # sqlite returns (cid, name, type, notnull, default, pk)
        names = [row[1] for row in rows]
        if "caption" not in names:
            conn.execute(text("ALTER TABLE confessions ADD COLUMN caption VARCHAR(1000)"))
            conn.commit()


def init_db():
    """Initialize database tables and add any missing columns."""
    Base.metadata.create_all(bind=engine)
    _ensure_caption_column()
