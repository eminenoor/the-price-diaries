"""Fill the database with realistic fake price history.

For developing the UI and taking README screenshots, so real scraped data
never needs to be published. Every floor and every state the UI can show
(good deal, fake sale, no change, price up, blocked store, member price,
one check only, two days of checks, not checked yet, empty floor, with and without a brand,
the same product at two stores by barcode and by hand)
appears at least once, and the result is the same every run.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from price_diaries.analysis import paper_week
from price_diaries.checker import update_group, update_size
from price_diaries.db import Category, CheckFailure, Notification, PricePoint, Product
from price_diaries.fetcher import StoreBlockedError

Ending = Literal["deal", "fake", "steady", "up", "blocked", "first", "two_days", "waiting"]


@dataclass(frozen=True)
class DemoProduct:
    name: str
    store: str
    floor: str
    room: str
    base: float
    ending: Ending
    member_share: float | None = None  # loyalty-card price as a share of the shelf price
    brand: str | None = None
    gtin: str | None = None  # same barcode = same product at another store
    link: str | None = None  # linked by hand to others with the same link


TONER_GTIN = "08809598452350"

# Add new products at the END. Every product draws from one random stream in this
# order, so a product inserted in the middle changes the history of every product
# after it (and with it, which windows are lit).
DEMO_PRODUCTS = [
    DemoProduct(
        "AHA BHA PHA 30 Days Miracle Toner 150 ml",
        "gratis",
        "Skincare",
        "Toners",
        950,
        "deal",
        0.52,
        brand="Some By Mi",
        gtin=TONER_GTIN,
    ),
    DemoProduct("Niacinamide 10% Toner 200 ml", "trendyol", "Skincare", "Toners", 210, "steady"),
    DemoProduct(
        "Vitamin C 15% Serum 30 ml",
        "eveshop",
        "Skincare",
        "Vitamin C serums",
        399,
        "deal",
        brand="Lumen Lab",
    ),
    DemoProduct(
        "SPF 50+ Fluid Sunscreen 50 ml",
        "watsons",
        "Skincare",
        "Sun care",
        349,
        "fake",
        brand="Daylight Co.",
    ),
    DemoProduct(
        "Ceramide Barrier Cream 50 ml", "sephora", "Skincare", "Moisturizers", 645, "blocked"
    ),
    DemoProduct("Gentle Foaming Cleanser 150 ml", "rossmann", "Skincare", "Cleansers", 159, "up"),
    DemoProduct(
        "Rice Water Bright Cleansing Foam 150 ml",
        "watsons",
        "Skincare",
        "Cleansers",
        268.22,
        "first",
        brand="Lumen Lab",
    ),
    DemoProduct(
        "Centella Calming Cream 50 ml",
        "gratis",
        "Skincare",
        "Moisturizers",
        420,
        "two_days",
        brand="Kuzey Botanics",
    ),
    DemoProduct("Single-Origin Filter Coffee 500 g", "amazon", "Pantry", "Coffee", 420, "steady"),
    DemoProduct("Cold-Pressed Olive Oil 1 l", "trendyol", "Pantry", "Olive oil", 610, "deal"),
    DemoProduct(
        "Laundry Liquid 2.5 l", "rossmann", "Cleaning", "Laundry", 289, "fake", link="laundry"
    ),
    DemoProduct("Dishwasher Tablets 60 pcs", "amazon", "Cleaning", "Kitchen", 499, "waiting"),
    DemoProduct(
        "Vitamin D3 1000 IU, 90 tablets", "gratis", "Supplements", "Vitamins", 275, "steady"
    ),
    DemoProduct(
        "Magnesium Bisglycinate 120 caps", "watsons", "Supplements", "Minerals", 389, "deal"
    ),
    # The same toner at another store, found by its barcode: cheaper there today.
    DemoProduct(
        "Some By Mi AHA BHA PHA Miracle Toner 150 ml",
        "watsons",
        "Skincare",
        "Toners",
        340,
        "steady",
        brand="Some By Mi",
        gtin=TONER_GTIN,
    ),
    # A smaller bottle elsewhere, linked by hand: cheaper per ml, so cheaper for 2.5 l too.
    DemoProduct(
        "Laundry Liquid 1.5 l", "trendyol", "Cleaning", "Laundry", 165, "steady", link="laundry"
    ),
]

# A floor with nothing on it yet, to show the empty-floor state.
EMPTY_FLOOR = "Haircare"

_FLOOR_COLOR = "#D9D2C3"
_SCRIPTED_DAYS = 15  # the last two weeks are scripted so each ending is certain


def room_for(session: Session, floor_name: str, room_name: str) -> Category:
    """Find or create a room on a floor (and the floor, if needed)."""
    floor = session.scalar(
        select(Category).where(Category.name == floor_name, Category.parent_id.is_(None))
    )
    if floor is None:
        floor = Category(name=floor_name, color=_FLOOR_COLOR)
        session.add(floor)
        session.flush()
    room = session.scalar(
        select(Category).where(Category.name == room_name, Category.parent_id == floor.id)
    )
    if room is None:
        room = Category(name=room_name, parent_id=floor.id, color=floor.color)
        session.add(room)
        session.flush()
    return room


def _random_walk(rng: random.Random, base: float, days: int) -> list[float]:
    """Mostly the regular price, with occasional real sales and raise-then-'discount' tricks."""
    prices, price, trick_until = [], base, -1
    for day in range(days):
        roll = rng.random()
        if day == trick_until:  # the "sale" after an artificial raise
            price = base
        elif roll < 0.025:  # raise now, "discount" a few days later
            price = round(base * rng.uniform(1.15, 1.30), 2)
            trick_until = day + rng.randint(2, 5)
        elif roll < 0.06:  # a real sale
            price = round(base * rng.uniform(0.80, 0.92), 2)
        elif roll < 0.20 and trick_until < day:
            price = base
        prices.append(price)
    return prices


def _ending(ending: Ending, base: float, history: list[float]) -> list[float]:
    """The scripted last two weeks."""
    flat = [base] * (_SCRIPTED_DAYS - 1)
    if ending == "deal":  # a new all-time low today
        return [*flat, round(min([*history, base]) * 0.93, 2)]
    if ending == "fake":  # raised 25 % for four days, then "discounted" back to normal
        return [base] * 9 + [round(base * 1.25, 2)] * 4 + [base] * 2
    if ending == "up":
        return [*flat, round(base * 1.06, 2)]
    return [*flat, base]  # steady, blocked


# The latest Sunday paper's week has news in every section, so the paper isn't empty in
# screenshots. Changes there stop the day before today, so every product's state today
# (and the home page) stays as scripted above.
PAPER_RISE = "Gentle Foaming Cleanser 150 ml"
PAPER_FAKE = "Laundry Liquid 2.5 l"
PAPER_SOLD_OUT = "Vitamin D3 1000 IU, 90 tablets"
PAPER_SLOWED = "Vitamin C 15% Serum 30 ml"  # one check stopped by a "too many requests"


@dataclass
class PaperWeekScript:
    prices: dict[date, float] = field(default_factory=dict)
    sold_out: set[date] = field(default_factory=set)
    failed: dict[date, str] = field(default_factory=dict)  # no price that day, this error


def paper_week_script(demo: DemoProduct, low: float, today: date) -> PaperWeekScript:
    """One product's part in the paper week. ``low`` is its lowest price before the
    scripted days, which a deal's new low has to beat."""
    monday = paper_week(today)
    yesterday = today - timedelta(days=1)

    def day(k: int) -> date:
        return monday + timedelta(days=k)

    def until_yesterday(k: int) -> list[date]:
        return [day(k) + timedelta(days=i) for i in range((yesterday - day(k)).days + 1)]

    script = PaperWeekScript()
    if demo.ending == "deal":  # a drop to a new low on Wednesday; today's is lower still
        script.prices = {d: round(low * 0.965, 2) for d in until_yesterday(2)}
    elif demo.name == PAPER_RISE:  # up 3% on Thursday; today's 6% comes on top
        script.prices = {d: round(demo.base * 1.03, 2) for d in until_yesterday(3)}
    elif demo.name == PAPER_FAKE:  # raised Monday to Wednesday, "discounted" on Thursday
        script.prices = {day(k): round(demo.base * 1.25, 2) for k in range(3)}
    elif demo.name == PAPER_SOLD_OUT:
        script.sold_out = {day(4)}
    if demo.ending == "blocked":  # blocked since Friday
        host = f"www.{demo.store}.com.tr"
        script.failed = {d: str(StoreBlockedError(host, 403)) for d in until_yesterday(4)}
        script.failed[today] = str(StoreBlockedError(host, 403))
    if demo.name == PAPER_SLOWED:
        script.failed = {day(1): str(StoreBlockedError(f"www.{demo.store}.com.tr", 429))}
    return script


def seed_demo(session: Session, days: int = 90, seed: int = 7, now: datetime | None = None) -> int:
    rng = random.Random(seed)
    today = (now or datetime.now()).replace(hour=9, minute=17, second=0, microsecond=0)
    days = max(days, _SCRIPTED_DAYS)

    created: dict[str, Product] = {}
    for i, demo in enumerate(DEMO_PRODUCTS):
        product = created[demo.name] = Product(
            url=f"https://demo.invalid/{demo.store}/{i}",
            name=demo.name,
            store=demo.store,
            category_id=room_for(session, demo.floor, demo.room).id,
            target_price=round(demo.base * 0.85),
            brand=demo.brand,
        )
        update_size(product)  # from the name, like a new product
        update_group(product, demo.gtin)
        if demo.link:
            product.group_key, product.group_source = f"user:{demo.link}", "user"
        if demo.ending == "blocked":
            error = StoreBlockedError(f"www.{demo.store}.com.tr", 403)
            product.last_error, product.blocked = str(error), True
        session.add(product)
        session.flush()
        if demo.ending == "waiting":
            continue
        if demo.ending == "first":  # checked once, this morning
            session.add(PricePoint(product_id=product.id, price=demo.base, checked_at=today))
            continue
        if demo.ending == "two_days":  # tracked since yesterday, a little cheaper today
            yesterday = today - timedelta(days=1)
            session.add(PricePoint(product_id=product.id, price=demo.base, checked_at=yesterday))
            session.add(
                PricePoint(product_id=product.id, price=round(demo.base * 0.9, 2), checked_at=today)
            )
            continue

        history = _random_walk(rng, demo.base, days + 1 - _SCRIPTED_DAYS)
        ending = _ending(demo.ending, demo.base, history)
        if demo.name == PAPER_FAKE:  # its raise moves into the paper week
            ending = [demo.base] * _SCRIPTED_DAYS
        prices = history + ending
        script = paper_week_script(demo, min([*history, demo.base]), today.date())
        start = today - timedelta(days=len(prices) - 1)
        for day, price in enumerate(prices):
            checked_at = start + timedelta(days=day)
            # Draw from the random stream for every day, scripted or not, so the products
            # after this one keep their history.
            in_stock = day == len(prices) - 1 or rng.random() > 0.02
            if checked_at.date() in script.failed:
                error = script.failed[checked_at.date()]
                session.add(CheckFailure(product_id=product.id, error=error, checked_at=checked_at))
                continue
            price = script.prices.get(checked_at.date(), price)
            member = round(price * demo.member_share, 2) if demo.member_share else None
            session.add(
                PricePoint(
                    product_id=product.id,
                    price=price,
                    member_price=member,
                    currency="TRY",
                    in_stock=in_stock and checked_at.date() not in script.sold_out,
                    checked_at=checked_at,
                )
            )
    if session.scalar(select(Category).where(Category.name == EMPTY_FLOOR)) is None:
        session.add(Category(name=EMPTY_FLOOR, color=_FLOOR_COLOR))
    session.flush()
    _add_notes(session, created, today)
    session.commit()
    return len(DEMO_PRODUCTS)


# Example notes, so the inbox isn't empty in screenshots: (product, kind, already read),
# oldest first. They're written straight to the database; the demo never sends a desktop
# notification.
DEMO_NOTES: list[tuple[str, str, bool]] = [
    ("Single-Origin Filter Coffee 500 g", "back_in_stock", True),
    ("Magnesium Bisglycinate 120 caps", "target", True),
    ("AHA BHA PHA 30 Days Miracle Toner 150 ml", "cheaper", False),
    ("SPF 50+ Fluid Sunscreen 50 ml", "fake_sale", False),
    ("Vitamin C 15% Serum 30 ml", "lowest", False),
]


def _add_notes(session: Session, products: dict[str, Product], today: datetime) -> None:
    def prices(product: Product) -> list[PricePoint]:
        return list(
            session.scalars(
                select(PricePoint)
                .where(PricePoint.product_id == product.id)
                .order_by(PricePoint.checked_at)
            )
        )

    for minute, (name, kind, read) in enumerate(DEMO_NOTES):
        product = products[name]
        points = prices(product)
        old, new = (p.effective_price(True) for p in points[-2:])
        other_store = None
        if kind == "cheaper":  # the same toner at Watsons, the same size
            other = next(p for p in products.values() if p.store == "watsons" and p.gtin)
            old, new, other_store = new, prices(other)[-1].price, other.store
        elif kind == "target":  # an alert price the new price just reached
            product.target_price = float(math.ceil(new / 10) * 10)
        elif kind == "fake_sale":  # the raised price before the "discount"
            old = next(p.price for p in reversed(points) if p.price != new)
        elif kind == "back_in_stock":
            points[-2].in_stock = False
        created_at = today + timedelta(minutes=minute)
        session.add(
            Notification(
                product_id=product.id,
                kind=kind,
                old_price=old,
                new_price=new,
                other_store=other_store,
                created_at=created_at,
                read_at=created_at + timedelta(hours=1) if read else None,
            )
        )

    # In the paper week: the big laundry bottle was cheaper per litre at Trendyol on Friday.
    monday = paper_week(today.date())
    friday = datetime.combine(monday + timedelta(days=4), today.time()) + timedelta(minutes=3)
    laundry, smaller = products[PAPER_FAKE], products["Laundry Liquid 1.5 l"]
    per_ml = prices(smaller)[-1].price / (smaller.size_amount or 1)
    session.add(
        Notification(
            product_id=laundry.id,
            kind="cheaper",
            old_price=next(
                p.price for p in prices(laundry) if p.checked_at.date() == friday.date()
            ),
            new_price=round(per_ml * (laundry.size_amount or 1), 2),
            other_store=smaller.store,
            created_at=friday,
            read_at=friday + timedelta(hours=2),
        )
    )
    # And the paper itself, out on that week's Sunday morning.
    if session.scalar(select(Notification).where(Notification.week == monday)) is None:
        sunday = datetime.combine(monday + timedelta(days=6), today.time()) + timedelta(minutes=5)
        session.add(Notification(kind="sunday_paper", week=monday, created_at=sunday))
