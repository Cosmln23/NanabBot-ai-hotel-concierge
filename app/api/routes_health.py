from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.workers.queue import redis_conn

router = APIRouter()


@router.get("/health")
def healthcheck():
    """Basic liveness check - returns 200 if API is running."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check - verifies all dependencies are available.
    Returns 200 if DB and Redis are responsive, 503 otherwise.
    """
    errors = []

    # Check database
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = "failed"
        errors.append(f"Database: {str(e)}")

    # Check Redis
    try:
        redis_conn.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = "failed"
        errors.append(f"Redis: {str(e)}")

    # Return 503 if any dependency failed
    if errors:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "db": db_status,
                "redis": redis_status,
                "errors": errors,
            },
        )

    return {"status": "ready", "db": db_status, "redis": redis_status}
