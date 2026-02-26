"""Background jobs for task auto-cleanup."""

import logging

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.tasks_cleanup import run_auto_cleanup

logger = logging.getLogger(__name__)


def run_cleanup_for_all_hotels() -> None:
    db: Session = SessionLocal()
    try:
        summary = run_auto_cleanup(db)
        logger.info("Task cleanup summary: %s", summary)
    except Exception as exc:
        logger.error("Task cleanup failed: %s", exc, exc_info=True)
    finally:
        db.close()
