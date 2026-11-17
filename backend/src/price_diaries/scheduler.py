"""Daily automatic price check while the server is running."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from price_diaries.checker import check_all
from price_diaries.db import Database
from price_diaries.fetcher import Fetcher
from price_diaries.notifications import Notifier, make_notifier, notify_after_check
from price_diaries.paper import publish_paper
from price_diaries.settings import Settings

log = logging.getLogger(__name__)


async def run_daily_check(
    db: Database, settings: Settings, notifier: Notifier | None = None
) -> None:
    notifier = notifier or make_notifier(settings)
    async with Fetcher(settings.min_delay, settings.max_delay, settings.request_timeout) as f:
        with db.session() as session:
            outcomes = await check_all(session, f, settings.browser_fallback)
            checked = [o.product_id for o in outcomes if o.ok]
            notes = await notify_after_check(session, checked, settings, notifier)
            # On a Sunday, after the morning's prices are in: the week's paper is ready.
            try:
                await publish_paper(session, notifier)
            except Exception:
                session.rollback()
                log.exception("Couldn't publish the Sunday paper")
    failed = sum(not o.ok for o in outcomes)
    log.info(
        "Daily check finished: %d products, %d failed, %d new notes",
        len(outcomes),
        failed,
        len(notes),
    )


def build_scheduler(db: Database, settings: Settings, notifier: Notifier) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_daily_check,
        CronTrigger(hour=settings.check_hour, minute=settings.check_minute),
        args=[db, settings, notifier],
        id="daily-check",
        coalesce=True,  # if the laptop was asleep, run once, not once per missed day
        misfire_grace_time=12 * 60 * 60,
    )
    return scheduler
