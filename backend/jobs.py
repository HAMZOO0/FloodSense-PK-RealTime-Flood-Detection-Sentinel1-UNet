"""Background job runner for slow analyses (GEE + U-Net take tens of seconds).

POST /api/analysis/{district} returns a job_id immediately; the analysis runs
on a small thread pool and writes its status/result to the Mongo `jobs`
collection, which GET /api/jobs/{job_id} polls.
"""

import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Callable

from .db import require_db, serialize
from .errors import conflict, not_found

logger = logging.getLogger("floodsense.jobs")

# GEE + torch are heavyweight — keep concurrency low.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="floodsense-job")
_submit_lock = threading.Lock()

# Jobs stuck in "running" longer than this are reported as failed (e.g. the
# server restarted mid-job).
STALE_AFTER = timedelta(minutes=30)


def shutdown() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)


def submit_analysis_job(district: str, runner: Callable[[str, str], dict]) -> dict:
    """Queue `runner(district, job_id)` and return the created job document."""
    db = require_db()

    with _submit_lock:
        # One active job per district — avoids duplicate expensive GEE work.
        active = db.jobs.find_one(
            {
                "district_query": district.lower().strip(),
                "status": {"$in": ["queued", "running"]},
                "updated_at": {"$gte": datetime.now(timezone.utc) - STALE_AFTER},
            }
        )
        if active:
            raise conflict(
                "ANALYSIS_ALREADY_RUNNING",
                f"An analysis for '{district}' is already {active['status']} "
                f"(job_id: {active['job_id']}). Poll GET /api/jobs/{active['job_id']}.",
            )

        job_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        job = {
            "job_id": job_id,
            "type": "district_analysis",
            "district_query": district.lower().strip(),
            "district": district,
            "status": "queued",
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        db.jobs.insert_one(job)

    _executor.submit(_run_job, job_id, district, runner)
    return serialize(job)


def _run_job(job_id: str, district: str, runner: Callable[[str, str], dict]) -> None:
    db = require_db()
    db.jobs.update_one(
        {"job_id": job_id},
        {"$set": {"status": "running", "updated_at": datetime.now(timezone.utc)}},
    )
    try:
        result = runner(district, job_id)
        db.jobs.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "complete",
                    "result": result,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        logger.info("Job %s complete (%s).", job_id, district)
    except Exception as e:
        logger.error("Job %s failed: %s\n%s", job_id, e, traceback.format_exc())
        message = getattr(e, "message", None) or str(e)
        try:
            db.jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": message,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception as db_err:
            logger.error("Could not record job failure: %s", db_err)


def get_job(job_id: str) -> dict:
    db = require_db()
    job = db.jobs.find_one({"job_id": job_id})
    if job is None:
        raise not_found("JOB_NOT_FOUND", f"No job with id '{job_id}'.")

    # Detect jobs orphaned by a server restart.
    updated_at = job.get("updated_at")
    if (
        job.get("status") in ("queued", "running")
        and updated_at is not None
        and updated_at.replace(tzinfo=timezone.utc)
        < datetime.now(timezone.utc) - STALE_AFTER
    ):
        job["status"] = "failed"
        job["error"] = "Job went stale (server may have restarted). Submit a new one."

    return serialize(job)
