import logging
from datetime import datetime, timedelta, timezone

import redis
from rq import Queue
from rq.job import Job

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("hotelbot.queue")

redis_conn = redis.from_url(settings.redis_url)


def get_queue(name: str = "default") -> Queue:
    return Queue(name, connection=redis_conn)


def enqueue_aggregate_daily(days_back: int = 2):
    from app.workers.jobs import aggregate_daily_usage

    q = get_queue()
    q.enqueue(aggregate_daily_usage, days_back)


def schedule_trial_check():
    """
    Schedule the trial expiration check job to run daily at 09:00 UTC.
    This function should be called on app startup.
    """
    from app.workers.jobs_trial import check_trial_expirations

    q = get_queue()
    job_id = "trial_check_daily"

    # Check if job already exists
    try:
        existing_job = Job.fetch(job_id, connection=redis_conn)
        if existing_job.get_status() in ["queued", "scheduled", "started"]:
            logger.debug("Trial check job already scheduled")
            return
    except Exception:
        pass  # Job doesn't exist

    # Schedule to run at next 09:00 UTC
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)

    q.enqueue_at(next_run, check_trial_expirations, job_id=job_id)
    logger.info(f"Trial check job scheduled for {next_run.isoformat()}")
