"""Background jobs for PMS synchronization."""

import logging

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Hotel
from app.services.pms.sync_engine import sync_hotel

logger = logging.getLogger(__name__)


def run_pms_sync_for_all_hotels() -> None:
    """
    Sync all active hotels that have PMS configured.

    This is the main scheduled job that runs every 15 minutes.
    It queries all hotels with PMS credentials and syncs each one.
    """
    db: Session = SessionLocal()
    total_hotels = 0
    successful_syncs = 0
    failed_syncs = 0

    try:
        # Query all active hotels with PMS configured
        hotels = (
            db.query(Hotel)
            .filter(
                Hotel.is_active == True,  # noqa: E712
                Hotel.pms_type.isnot(None),
                Hotel.pms_api_key.isnot(None),
            )
            .all()
        )

        total_hotels = len(hotels)
        logger.info(f"Starting PMS sync for {total_hotels} hotels")

        for hotel in hotels:
            try:
                logger.info(f"Syncing hotel {hotel.id} ({hotel.name}) with {hotel.pms_type}")

                # Sync this hotel (24 hour window)
                stats = sync_hotel(hotel.id, time_window_hours=24)

                if stats.errors > 0:
                    logger.warning(
                        f"Hotel {hotel.id} sync completed with {stats.errors} errors: "
                        f"{stats.checkins_processed} check-ins, {stats.checkouts_processed} check-outs"
                    )
                    failed_syncs += 1
                else:
                    logger.info(
                        f"Hotel {hotel.id} sync successful: "
                        f"{stats.checkins_processed} check-ins, {stats.checkouts_processed} check-outs, "
                        f"{stats.guests_created} new guests, {stats.stays_created} new stays"
                    )
                    successful_syncs += 1

            except Exception as e:
                logger.error(f"Failed to sync hotel {hotel.id}: {e}", exc_info=True)
                failed_syncs += 1

        logger.info(
            f"PMS sync batch complete: {total_hotels} hotels, "
            f"{successful_syncs} successful, {failed_syncs} failed"
        )

    except Exception as e:
        logger.error(f"Fatal error in PMS sync batch: {e}", exc_info=True)
    finally:
        db.close()
