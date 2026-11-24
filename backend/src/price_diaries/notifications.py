"""Notes after each check: saved for the inbox, and shown as desktop notifications.

Everything stays on this computer. Each event is noted once: an alert's state is kept
in ``alert_states``, and a note is made only when its condition turns from false to true.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from price_diaries.analysis import (
    AlertKind,
    alert_signals,
    cheaper_elsewhere,
    fresh_alerts,
    next_low_mark,
)
from price_diaries.db import AlertState, Notification, Product, group_by_key, others_in_group
from price_diaries.parsers import store_name
from price_diaries.settings import Settings

log = logging.getLogger(__name__)

APP_NAME = "The Price Diaries"


# --- what to note ----------------------------------------------------------------------


def _cheaper(
    product: Product, others: Sequence[Product], use_member: bool, today: date
) -> tuple[str, float] | None:
    """The store that sells it for less today, and its price for this product's size.

    A product on its first check doesn't count yet, so adding a new listing never sets
    off a note right away; it can from its second check on.
    """
    here = product.offer(use_member)
    if here is None:
        return None
    offers = [
        offer
        for other in others
        if len(other.prices) > 1
        if (offer := other.offer(use_member)) is not None
    ]
    best = cheaper_elsewhere(here, offers, today)
    if best is None:
        return None
    there = next(p for p in others if p.id == best[0].product_id)
    price_there = float(Decimal(str(here.price)) - Decimal(str(best[1])))
    return there.store, price_there


def detect(
    session: Session, products: Iterable[Product], use_member: bool, today: date | None = None
) -> list[Notification]:
    """Save a note for every alert that just turned on for these products, and the new
    state of every alert. Call it after the products' new prices are committed."""
    today = today or date.today()
    session.expire_all()  # read the prices the check just saved
    products = list(products)
    ids = [p.id for p in products]
    states = {
        (s.product_id, s.kind): s
        for s in session.scalars(select(AlertState).where(AlertState.product_id.in_(ids)))
    }
    keys = {p.group_key for p in products if p.group_key}
    groups = group_by_key(
        session.scalars(select(Product).where(Product.group_key.in_(keys))) if keys else []
    )

    notes: list[Notification] = []
    for product in products:
        if not product.prices:
            continue
        readings = product.readings(use_member)
        cheaper = _cheaper(product, others_in_group(product, groups), use_member, today)
        lowest = states.get((product.id, "lowest"))
        low_mark = lowest.price if lowest else None
        signals = alert_signals(readings, product.target_price, cheaper, low_mark)
        previous: dict[AlertKind, bool] = {
            kind: state.active for (pid, kind), state in states.items() if pid == product.id
        }
        fired = fresh_alerts(signals, previous, first_check=len(readings) == 1)
        for kind in fired:
            signal = signals[kind]
            notes.append(
                Notification(
                    product_id=product.id,
                    kind=kind,
                    old_price=signal.old_price,
                    new_price=signal.new_price,
                    other_store=signal.other_store,
                )
            )
        for kind, signal in signals.items():
            state = states.get((product.id, kind))
            if state is None:
                state = AlertState(product_id=product.id, kind=kind)
                session.add(state)
            state.active = signal.active
            if kind == "lowest":
                state.price = next_low_mark(readings, low_mark, new_low="lowest" in fired)
    session.add_all(notes)
    session.commit()
    return notes


# --- how it reads ----------------------------------------------------------------------

TITLES: dict[str, str] = {
    "target": "At your alert price",
    "lowest": "Lowest price ever",
    "fake_sale": "Fake sale",
    "cheaper": "Cheaper at another store",
    "back_in_stock": "Back in stock",
}


def lira(value: float) -> str:
    """1299.9 -> "₺1.299,90", the way Turkish stores print prices."""
    amount = Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    whole, kurus = f"{amount:,.2f}".split(".")
    return f"₺{whole.replace(',', '.')},{kurus}"


def note_text(note: Notification, name: str, store: str) -> tuple[str, str]:
    """The title and sentence for a desktop notification. The inbox says the same."""
    new = lira(note.new_price) if note.new_price is not None else "?"
    # "(was ₺420,00)" next to "now ₺420,00" says nothing, so leave it out.
    changed = note.old_price is not None and note.old_price != note.new_price
    was = f" (was {lira(note.old_price)})" if changed and note.old_price is not None else ""
    if note.kind == "target":
        text = f"{name} at {store} is now {new}{was}, at or under your alert price."
    elif note.kind == "lowest":
        text = f"{name} at {store} is now {new}{was}, the lowest since you started tracking."
    elif note.kind == "fake_sale":
        text = (
            f"{name} at {store} is now {new}{was}, but only after a recent price rise. "
            "Not really cheaper."
        )
    elif note.kind == "cheaper":
        here = lira(note.old_price) if note.old_price is not None else "?"
        other = store_name(note.other_store or "")
        text = f"{name} is {new} at {other} for the same amount, {here} at {store}."
    else:
        text = f"{name} is back in stock at {store}, now {new}{was}."
    return TITLES.get(note.kind, "Note"), text


# --- desktop notifications ---------------------------------------------------------------


class Notifier(Protocol):
    async def send(self, title: str, message: str) -> bool:
        """Show one notification. Never raises; False when it couldn't be shown."""
        ...


class NoDesktopNotifications:
    """PD_DESKTOP_NOTIFICATIONS=false: notes go to the inbox only."""

    async def send(self, title: str, message: str) -> bool:
        return False


class DesktopNotifications:
    """Desktop notifications through desktop-notifier (Windows toasts, also macOS and Linux).

    If the system can't show them, that's logged once and notes go to the inbox only.
    """

    def __init__(self) -> None:
        self._notifier: Any = None
        self._unavailable = False

    async def _get(self) -> Any:
        if self._unavailable:
            return None
        if self._notifier is None:
            try:
                from desktop_notifier import DesktopNotifier
                from desktop_notifier.backends.dummy import DummyNotificationCenter
                from desktop_notifier.main import get_backend_class

                if get_backend_class() is DummyNotificationCenter:
                    raise RuntimeError("this system has no notification service")
                notifier = DesktopNotifier(app_name=APP_NAME)
                if not await notifier.request_authorisation():
                    raise RuntimeError("they're turned off for this app in the system settings")
            except Exception as exc:
                self._unavailable = True
                log.warning(
                    "Desktop notifications aren't available (%s). Notes still go to the inbox.",
                    exc,
                )
                return None
            self._notifier = notifier
        return self._notifier

    async def send(self, title: str, message: str) -> bool:
        notifier = await self._get()
        if notifier is None:
            return False
        try:
            await notifier.send(title=title, message=message)
        except Exception as exc:
            log.warning("Couldn't show a desktop notification: %s", exc)
            return False
        return True


def make_notifier(settings: Settings) -> Notifier:
    return DesktopNotifications() if settings.desktop_notifications else NoDesktopNotifications()


async def send_desktop(session: Session, notes: Sequence[Notification], notifier: Notifier) -> None:
    """One desktop notification per note. A failure is logged and never stops the rest."""
    for note in notes:
        try:
            if note.product_id is None:
                continue
            product = session.get(Product, note.product_id)
            if product is None:
                continue
            title, message = note_text(
                note, product.display_name or product.name, store_name(product.store)
            )
            await notifier.send(title, message)
        except Exception:
            log.exception("Couldn't show a desktop notification")


async def notify_after_check(
    session: Session, product_ids: Iterable[int], settings: Settings, notifier: Notifier
) -> list[Notification]:
    """Note what changed for the products a check just updated. Prices are already saved,
    so nothing here can undo or fail the check."""
    ids = list(product_ids)
    if not ids:
        return []
    try:
        products = session.scalars(select(Product).where(Product.id.in_(ids))).all()
        notes = detect(session, products, settings.use_member_prices)
    except Exception:
        session.rollback()
        log.exception("Couldn't work out the notes after the check")
        return []
    await send_desktop(session, notes, notifier)
    return notes
