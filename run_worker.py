#!/usr/bin/env python
"""
Production RQ worker entrypoint.

- Loads environment (.env)
- Imports worker modules to ensure jobs can be deserialized
- Optionally starts PMS sync scheduler thread

Run with: python run_worker.py
"""

import logging
import threading
import time

from dotenv import load_dotenv
from redis import Redis
from rq import Queue, SimpleWorker, Worker

load_dotenv(override=True)

import sentry_sdk  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402

# Initialize Sentry for worker error monitoring
_settings = get_settings()
if _settings.sentry_dsn:
    sentry_sdk.init(
        dsn=_settings.sentry_dsn,
        send_default_pii=False,
        environment=_settings.environment,
    )
from app.workers import (  # noqa: F401,E402
    jobs,
    jobs_cleanup,
    jobs_gdpr_cleanup,
    jobs_journey,
    jobs_pms,
    jobs_stay_cleanup,
    jobs_trial,
)


def _start_pms_scheduler() -> None:
    """Background thread that runs PMS sync every 15 minutes."""
    settings = get_settings()

    def _loop():
        # small delay to allow app to start
        time.sleep(120)
        while True:
            try:
                jobs_pms.run_pms_sync_for_all_hotels()
            except Exception as exc:  # pragma: no cover - scheduler best-effort
                logging.getLogger("hotelbot.worker").exception("PMS scheduler error: %s", exc)
            time.sleep(900)

    if settings.environment != "test":
        t = threading.Thread(target=_loop, daemon=True, name="PMS-Scheduler")
        t.start()
        logging.getLogger("hotelbot.worker").info("PMS scheduler started (every 15 minutes)")


def _start_cleanup_scheduler() -> None:
    """Background thread that runs task cleanup every 60 minutes."""
    settings = get_settings()

    def _loop():
        time.sleep(180)
        while True:
            try:
                jobs_cleanup.run_cleanup_for_all_hotels()
            except Exception as exc:  # pragma: no cover - scheduler best-effort
                logging.getLogger("hotelbot.worker").exception("Cleanup scheduler error: %s", exc)
            time.sleep(3600)

    if settings.environment != "test":
        t = threading.Thread(target=_loop, daemon=True, name="Cleanup-Scheduler")
        t.start()
        logging.getLogger("hotelbot.worker").info("Cleanup scheduler started (every 60 minutes)")


def _start_journey_scheduler() -> None:
    """Background thread that runs journey processor every 60 seconds."""
    settings = get_settings()

    def _loop():
        # Small delay to allow app to start
        time.sleep(30)
        while True:
            try:
                jobs_journey.process_pending_journeys()
            except Exception as exc:  # pragma: no cover - scheduler best-effort
                logging.getLogger("hotelbot.worker").exception("Journey scheduler error: %s", exc)
            time.sleep(60)

    if settings.environment != "test":
        t = threading.Thread(target=_loop, daemon=True, name="Journey-Scheduler")
        t.start()
        logging.getLogger("hotelbot.worker").info("Journey scheduler started (every 60 seconds)")


def _start_aggregation_scheduler() -> None:
    """Background thread that runs usage aggregation every 6 hours."""
    settings = get_settings()

    def _loop():
        time.sleep(300)  # Wait 5 min before first run
        while True:
            try:
                jobs.aggregate_daily_usage(days_back=2)
                logging.getLogger("hotelbot.worker").info("Usage aggregation completed")
            except Exception as exc:
                logging.getLogger("hotelbot.worker").exception(
                    "Aggregation scheduler error: %s", exc
                )
            time.sleep(21600)  # Every 6 hours

    if settings.environment != "test":
        t = threading.Thread(target=_loop, daemon=True, name="Aggregation-Scheduler")
        t.start()
        logging.getLogger("hotelbot.worker").info("Aggregation scheduler started (every 6 hours)")


def _start_stay_cleanup_scheduler() -> None:
    """Background thread that runs stay cleanup every 30 minutes."""
    settings = get_settings()

    def _loop():
        time.sleep(120)  # Wait 2 min after startup
        while True:
            try:
                logger = logging.getLogger("hotelbot.worker")
                logger.info("[SCHEDULER] Running stay cleanup job...")
                stats = jobs_stay_cleanup.run_stay_cleanup_for_all_hotels()
                if stats.get("expired_stays_closed", 0) > 0:
                    logger.info(f"[SCHEDULER] Stay cleanup completed: {stats}")
            except Exception as exc:
                logging.getLogger("hotelbot.worker").exception(
                    "[SCHEDULER] Stay cleanup error: %s", exc
                )
            time.sleep(1800)  # Every 30 minutes

    if settings.environment != "test":
        t = threading.Thread(target=_loop, daemon=True, name="StayCleanup-Scheduler")
        t.start()
        logging.getLogger("hotelbot.worker").info(
            "[SCHEDULER] Stay cleanup scheduler started (interval=30min)"
        )


def _start_gdpr_cleanup_scheduler() -> None:
    """Background thread that runs GDPR data retention cleanup once daily."""
    settings = get_settings()

    def _loop():
        time.sleep(600)  # Wait 10 min after startup
        while True:
            try:
                logger = logging.getLogger("hotelbot.worker")
                logger.info("[SCHEDULER] Running GDPR cleanup job...")
                stats = jobs_gdpr_cleanup.run_gdpr_cleanup()
                if stats.get("messages_deleted", 0) > 0 or stats.get("guests_anonymized", 0) > 0:
                    logger.info("[SCHEDULER] GDPR cleanup completed: %s", stats)
            except Exception as exc:
                logging.getLogger("hotelbot.worker").exception(
                    "[SCHEDULER] GDPR cleanup error: %s", exc
                )
            time.sleep(86400)  # Every 24 hours

    if settings.environment != "test":
        t = threading.Thread(target=_loop, daemon=True, name="GDPR-Cleanup-Scheduler")
        t.start()
        logging.getLogger("hotelbot.worker").info(
            "[SCHEDULER] GDPR cleanup scheduler started (interval=24h)"
        )


def _start_trial_check_scheduler() -> None:
    """Background thread that runs trial expiration check every 24 hours."""
    settings = get_settings()

    def _loop():
        time.sleep(300)  # Wait 5 min after startup
        while True:
            try:
                logger = logging.getLogger("hotelbot.worker")
                logger.info("[SCHEDULER] Running trial expiration check...")
                jobs_trial.check_trial_expirations()
                logger.info("[SCHEDULER] Trial expiration check completed")
            except Exception as exc:
                logging.getLogger("hotelbot.worker").exception(
                    "[SCHEDULER] Trial check error: %s", exc
                )
            time.sleep(86400)  # Every 24 hours

    if settings.environment != "test":
        t = threading.Thread(target=_loop, daemon=True, name="Trial-Check-Scheduler")
        t.start()
        logging.getLogger("hotelbot.worker").info(
            "[SCHEDULER] Trial check scheduler started (interval=24h)"
        )


def main() -> None:
    setup_logging("INFO")
    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)

    # Start all scheduler threads
    _start_journey_scheduler()
    _start_pms_scheduler()
    _start_cleanup_scheduler()
    _start_aggregation_scheduler()
    _start_stay_cleanup_scheduler()
    _start_gdpr_cleanup_scheduler()
    _start_trial_check_scheduler()

    # Start RQ worker (default queue)
    # Use SimpleWorker on macOS to avoid fork() issues
    import platform

    queue = Queue("default", connection=redis_conn)
    if platform.system() == "Darwin":
        worker = SimpleWorker([queue], connection=redis_conn)
        logging.getLogger("hotelbot.worker").info(
            "RQ SimpleWorker started on queue 'default' (macOS no-fork mode)"
        )
    else:
        worker = Worker([queue], connection=redis_conn)
        logging.getLogger("hotelbot.worker").info("RQ Worker started on queue 'default'")
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
