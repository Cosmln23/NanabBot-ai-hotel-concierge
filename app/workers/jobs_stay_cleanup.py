"""Background job for cleaning up expired stays."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Stay
from app.models.models import StayStatus

logger = logging.getLogger(__name__)


def run_stay_cleanup_for_all_hotels() -> dict:
    """
    Cleanup stays with checkout_date in past but still IN_HOUSE.

    This is a fallback mechanism for when PMS sync fails to detect checkouts.
    Runs every 30 minutes.

    Returns:
        dict with stats: {"expired_stays_closed": int, "errors": int}
    """
    db: Session = SessionLocal()
    stats = {"expired_stays_closed": 0, "hotels_affected": 0, "errors": 0}

    try:
        now = datetime.now(timezone.utc)

        # Find stays with checkout_date < now but status == IN_HOUSE
        # No grace period - PMS should handle late checkouts
        expired_stays = (
            db.query(Stay)
            .filter(
                Stay.status == StayStatus.IN_HOUSE,
                Stay.checkout_date < now,
            )
            .all()
        )

        if not expired_stays:
            logger.debug("Stay cleanup: No expired stays found")
            return stats

        hotels_affected = set()

        for stay in expired_stays:
            try:
                logger.warning(
                    f"[STAY-CLEANUP] Found expired stay {stay.id} for hotel {stay.hotel_id}: "
                    f"checkout_date={stay.checkout_date}, now={now} - marking POST_STAY"
                )

                stay.status = StayStatus.POST_STAY
                db.add(stay)
                stats["expired_stays_closed"] += 1
                hotels_affected.add(stay.hotel_id)

            except Exception as e:
                logger.error(f"[STAY-CLEANUP] Error processing stay {stay.id}: {e}")
                stats["errors"] += 1

        if stats["expired_stays_closed"] > 0:
            db.commit()
            stats["hotels_affected"] = len(hotels_affected)
            logger.info(
                f"[STAY-CLEANUP] Completed: {stats['expired_stays_closed']} expired stays closed "
                f"across {stats['hotels_affected']} hotels"
            )

    except Exception as e:
        db.rollback()
        logger.error(f"[STAY-CLEANUP] Fatal error: {e}", exc_info=True)
        stats["errors"] += 1
    finally:
        db.close()

    return stats
