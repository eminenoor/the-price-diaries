"""Daily automatic price check while the server is running."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from price_diaries.checker import check_all
from price_diaries.db import Database
from price_diaries.fetcher import Fetcher
from price_diaries.settings import Settings

log = logging.getLogger(__name__)


async def run_daily_check(db: Database, settings: Settings) -> None:
    async with Fetcher(settings.min_delay, settings.max_delay, settings.request_timeout) as f:
        with db.session() as session:
            outcomes = await check_all(session, f, settings.browser_fallback)
    failed = sum(not o.ok for o in outcomes)
    log.info("Daily check finished: %d products, %d failed", len(outcomes), failed)


def build_scheduler(db: Database, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_daily_check,
        CronTrigger(hour=settings.check_hour, minute=settings.check_minute),
        args=[db, settings],
        id="daily-check",
        coalesce=True,  # if the laptop was asleep, run once, not once per missed day
        misfire_grace_time=12 * 60 * 60,
    )
    return scheduler
