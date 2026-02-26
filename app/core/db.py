from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Connection pool configuration for concurrent load handling
engine = create_engine(
    settings.database_url,
    future=True,
    pool_size=20,  # Increased from default 5
    max_overflow=30,  # Increased from default 10
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=120,  # Recycle connections after 2 minutes (prevents Supabase stale SSL)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
