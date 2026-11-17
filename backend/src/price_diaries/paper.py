"""The Sunday paper: one page about one week (Monday to Sunday), and its Sunday note.

Price moves, new lows, fake sales and stock come from each product's checks, so any past
week can be read again. Cheaper-elsewhere finds come from that week's notes (they depend
on other stores' prices on the day), and failed checks from ``check_failures``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from price_diaries.analysis import Reading, paper_week, week_story
from price_diaries.db import CheckFailure, Notification, PricePoint, Product
from price_diaries.notifications import Notifier, store_name
from price_diaries.schemas import (
    PaperCheaper,
    PaperFakeSale,
    PaperItem,
    PaperLow,
    PaperMove,
    PaperOut,
    PaperTrouble,
)

log = logging.getLogger(__name__)


class About(TypedDict):
    """Which product a line in the paper is about."""

    product_id: int
    name: str
    store_name: str


PAPER_TITLE = "Your Sunday paper is ready"
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def week_words(monday: date) -> str:
    """ "9 to 15 Nov", or "27 Oct to 2 Nov" across two months."""
    sunday = monday + timedelta(days=6)
    first = str(monday.day) if monday.month == sunday.month else _day_month(monday)
    return f"{first} to {_day_month(sunday)}"


def _day_month(day: date) -> str:
    return f"{day.day} {_MONTHS[day.month - 1]}"


def build_paper(
    session: Session,
    monday: date,
    use_member: bool,
    today: date,
    name_of: Callable[[Product], str],
) -> PaperOut:
    """The paper for the week starting ``monday``. ``name_of`` gives a product's shown name."""
    start = datetime.combine(monday, time.min)
    end = start + timedelta(days=7)
    products = session.scalars(select(Product)).all()
    by_id = {p.id: p for p in products}

    def about(product: Product) -> About:
        return About(
            product_id=product.id, name=name_of(product), store_name=store_name(product.store)
        )

    drops: list[PaperMove] = []
    rises: list[PaperMove] = []
    lows: list[PaperLow] = []
    fakes: list[PaperFakeSale] = []
    stock: dict[int, datetime] = {}
    checked = 0
    for product in products:
        readings = [
            Reading(p.checked_at, p.effective_price(use_member), p.in_stock)
            for p in product.prices
            if p.checked_at < end
        ]
        story = week_story(readings, monday)
        checked += story.checked
        if story.move:
            move = PaperMove(**about(product), **vars(story.move))
            (drops if story.move.change_pct < 0 else rises).append(move)
        if story.new_low:
            lows.append(PaperLow(**about(product), **vars(story.new_low)))
        if story.fake_sale:
            fakes.append(PaperFakeSale(**about(product), **vars(story.fake_sale)))
        if story.out_of_stock_at:
            stock[product.id] = story.out_of_stock_at

    cheaper: dict[int, PaperCheaper] = {}
    notes = session.scalars(
        select(Notification)
        .where(
            Notification.kind == "cheaper",
            Notification.created_at >= start,
            Notification.created_at < end,
        )
        .order_by(Notification.created_at)
    )
    for note in notes:
        product = by_id.get(note.product_id or 0)
        if product is None or note.old_price is None or note.new_price is None:
            continue
        cheaper[product.id] = PaperCheaper(  # the latest find for each product
            **about(product),
            other_store_name=store_name(note.other_store or ""),
            price_here=note.old_price,
            price_there=note.new_price,
            at=note.created_at,
        )

    failed: dict[int, tuple[int, str]] = {}  # product -> (failed checks, the latest error)
    for failure in session.scalars(
        select(CheckFailure)
        .where(CheckFailure.checked_at >= start, CheckFailure.checked_at < end)
        .order_by(CheckFailure.checked_at)
    ):
        count = failed.get(failure.product_id, (0, ""))[0]
        failed[failure.product_id] = (count + 1, failure.error)
    trouble = [
        PaperTrouble(
            **about(by_id[pid]),
            failed_checks=failed[pid][0] if pid in failed else 0,
            last_error=failed[pid][1] if pid in failed else None,
            out_of_stock_at=stock.get(pid),
        )
        for pid in failed.keys() | stock.keys()
        if pid in by_id
    ]

    first = session.scalar(select(func.min(PricePoint.checked_at)))
    latest = paper_week(today)

    def by_name(item: PaperItem) -> str:
        return item.name.casefold()

    return PaperOut(
        week_start=monday,
        week_end=monday + timedelta(days=6),
        previous_week=(
            monday - timedelta(days=7) if first is not None and first.date() < monday else None
        ),
        next_week=monday + timedelta(days=7) if monday < latest else None,
        products_checked=checked,
        drops=sorted(drops, key=lambda m: (m.change_pct, by_name(m))),
        new_lows=sorted(lows, key=lambda low: (low.at, by_name(low))),
        fake_sales=sorted(fakes, key=lambda f: (f.at, by_name(f))),
        cheaper=sorted(cheaper.values(), key=lambda c: (c.price_there - c.price_here, by_name(c))),
        rises=sorted(rises, key=lambda m: (-m.change_pct, by_name(m))),
        trouble=sorted(trouble, key=by_name),
    )


# --- the Sunday note ------------------------------------------------------------------------


def paper_note_text(monday: date) -> tuple[str, str]:
    """The desktop notification's title and sentence. The inbox says the same."""
    return PAPER_TITLE, f"The week of {week_words(monday)}, on one page."


async def publish_paper(
    session: Session, notifier: Notifier, now: datetime | None = None
) -> Notification | None:
    """Pin "Your Sunday paper is ready" to the inbox and show it on the desktop, once per
    week: on Sunday for this week, or, if the app didn't run that Sunday, at the next check
    later in the week. A late note is only sent for a week that had checks, so a new
    install doesn't start with an empty paper."""
    now = now or datetime.now()
    monday = paper_week(now.date())
    exists = session.scalar(
        select(Notification.id).where(
            Notification.kind == "sunday_paper", Notification.week == monday
        )
    )
    if exists is not None:
        return None
    if now.weekday() != 6:
        start = datetime.combine(monday, time.min)
        checked = session.scalar(
            select(PricePoint.id).where(
                PricePoint.checked_at >= start, PricePoint.checked_at < start + timedelta(days=7)
            )
        )
        if checked is None:
            return None
    note = Notification(kind="sunday_paper", week=monday, created_at=now)
    session.add(note)
    try:
        session.commit()
    except IntegrityError:  # another check (the CLI and the server, say) got there first
        session.rollback()
        return None
    try:
        await notifier.send(*paper_note_text(monday))
    except Exception:
        log.exception("Couldn't show the Sunday paper notification")
    return note
