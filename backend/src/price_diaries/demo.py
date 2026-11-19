"""Fill the database with half a year of realistic, made-up price history.

For developing the UI and taking README screenshots, so real scraped data never needs to
be published. The demo is always seen on one day, Tuesday 1 December 2026 (serve it with
PD_TODAY=2026-12-01), just after Efsane Cuma, and the result is the same on every run.

Prices behave the way Turkish online prices do: regular prices go up in steps (inflation),
stores run campaigns, a few products dip around paydays (the 1st and the 15th), the
marketplaces have 11.11 and everyone has a big Efsane Cuma sale. Some sales are fake: a
price raised and then "discounted" back, or a short spike just before a campaign. There
are out-of-stock gaps, failed checks, a store that blocks checks (Sephora) and loyalty-card
prices that come and go.

The last weeks of every product are scripted, so each one's state today is certain and
every UI state appears: good deal, fake sale, no change, price up, blocked store, failed
check, member price, one check only, two days of checks, not checked yet, an empty floor,
the same product at three stores and in two sizes. The inbox holds the notes the app
itself would have left over the last three weeks, and the latest Sunday paper (the week
of Efsane Cuma) has news in every section.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from price_diaries.checker import update_group, update_size
from price_diaries.db import Category, CheckFailure, Notification, PricePoint, Product
from price_diaries.fetcher import FetchError, StoreBlockedError
from price_diaries.notifications import detect
from price_diaries.parsers import STORES

# The day the demo is seen on: a Tuesday, four days after Efsane Cuma.
DEMO_TODAY = date(2026, 12, 1)
DEFAULT_DAYS = 180
CHECK_TIME = time(9, 17)

EFSANE_CUMA = date(2026, 11, 27)
# Most stores run Efsane Cuma from Thursday to Sunday; the marketplaces all week, and Monday too.
_EFSANE_DAYS = {
    "trendyol": (date(2026, 11, 23), date(2026, 11, 30)),
    "amazon": (date(2026, 11, 23), date(2026, 11, 30)),
}
_EFSANE_DEFAULT = (date(2026, 11, 26), date(2026, 11, 29))
_ELEVEN_ELEVEN = (date(2026, 11, 10), date(2026, 11, 12))  # 11.11, at the marketplaces
_MARKETPLACES = ("trendyol", "amazon")

Ending = Literal[
    "deal",  # a new lowest price today
    "fake",  # raised the week before Efsane Cuma, then "discounted" back to normal
    "spike",  # a short spike just before the campaign, then an Efsane "discount" back to it
    "steady",  # the same price as yesterday
    "up",  # dearer than yesterday
    "blocked",  # the store has refused checks since Friday
    "error",  # today's check failed
    "first",  # checked once, this morning
    "two_days",  # tracked since yesterday
    "waiting",  # not checked yet
]


@dataclass(frozen=True)
class DemoProduct:
    name: str
    store: str
    floor: str
    room: str
    price: float  # the regular shelf price today, as the store prints it
    ending: Ending
    member_share: float | None = None  # loyalty-card price as a share of the shelf price
    member_comes_and_goes: bool = False
    brand: str | None = None
    gtin: str | None = None  # same barcode = same product at another store
    link: str | None = None  # linked by hand to others with the same link
    tracked_days: int | None = None  # added later than the rest


TONER_GTIN = "08809598452350"

# Each product has its own random stream, so adding, removing or moving one never changes
# another's history. Floors appear in the order of their first product.
DEMO_PRODUCTS = [
    # --- Skincare ---
    DemoProduct(
        "AHA BHA PHA 30 Days Miracle Toner 150 ml",
        "gratis",
        "Skincare",
        "Toners",
        899.90,
        "deal",
        member_share=0.8,
        brand="Some By Mi",
        gtin=TONER_GTIN,
    ),
    # The same toner at two more stores, found by its barcode.
    DemoProduct(
        "Some By Mi AHA BHA PHA Miracle Toner 150 ml",
        "watsons",
        "Skincare",
        "Toners",
        849.95,
        "steady",
        brand="Some By Mi",
        gtin=TONER_GTIN,
    ),
    DemoProduct(
        "Some By Mi AHA-BHA-PHA 30 Days Miracle Toner 150ml",
        "trendyol",
        "Skincare",
        "Toners",
        879.90,
        "steady",
        brand="Some By Mi",
        gtin=TONER_GTIN,
    ),
    DemoProduct("Niacinamide 10% Toner 200 ml", "trendyol", "Skincare", "Toners", 289.90, "steady"),
    DemoProduct(
        "Vitamin C 15% Serum 30 ml",
        "eveshop",
        "Skincare",
        "Vitamin C serums",
        549.90,
        "deal",
        brand="Lumen Lab",
    ),
    DemoProduct(
        "Hyaluronic Acid Serum 30 ml",
        "trendyol",
        "Skincare",
        "Serums",
        319.90,
        "spike",
        brand="Lumen Lab",
    ),
    DemoProduct(
        "SPF 50+ Fluid Sunscreen 50 ml",
        "watsons",
        "Skincare",
        "Sun care",
        479.95,
        "fake",
        brand="Daylight Co.",
    ),
    DemoProduct(
        "Ceramide Barrier Cream 50 ml", "sephora", "Skincare", "Moisturizers", 899.00, "blocked"
    ),
    DemoProduct(
        "Retinol 0.3% Night Cream 50 ml",
        "gratis",
        "Skincare",
        "Moisturizers",
        649.90,
        "steady",
        member_share=0.85,
        member_comes_and_goes=True,
        brand="Kuzey Botanics",
        tracked_days=120,
    ),
    DemoProduct(
        "Centella Calming Cream 50 ml",
        "gratis",
        "Skincare",
        "Moisturizers",
        549.90,
        "two_days",
        brand="Kuzey Botanics",
    ),
    DemoProduct(
        "Gentle Foaming Cleanser 150 ml", "rossmann", "Skincare", "Cleansers", 229.95, "deal"
    ),
    DemoProduct(
        "Rice Water Bright Cleansing Foam 150 ml",
        "watsons",
        "Skincare",
        "Cleansers",
        349.95,
        "first",
        brand="Lumen Lab",
    ),
    # --- Haircare ---
    DemoProduct(
        "Argan Oil Repair Shampoo 400 ml",
        "gratis",
        "Haircare",
        "Shampoo",
        249.90,
        "deal",
        member_share=0.85,
        brand="Kuzey Botanics",
    ),
    DemoProduct("Anti-Dandruff Shampoo 300 ml", "watsons", "Haircare", "Shampoo", 189.95, "up"),
    DemoProduct(
        "Keratin Smooth Conditioner 350 ml", "rossmann", "Haircare", "Conditioner", 219.95, "up"
    ),
    DemoProduct("Bond Repair Hair Mask 250 ml", "amazon", "Haircare", "Masks", 459.99, "deal"),
    DemoProduct("Rosemary Hair Oil 100 ml", "eveshop", "Haircare", "Hair oil", 399.90, "error"),
    DemoProduct(
        "Heat Protect Spray 200 ml",
        "trendyol",
        "Haircare",
        "Styling",
        279.90,
        "steady",
        tracked_days=75,
    ),
    # --- Pantry ---
    DemoProduct(
        "Single-Origin Filter Coffee 500 g", "amazon", "Pantry", "Coffee", 529.99, "steady"
    ),
    DemoProduct(
        "Espresso Beans 1 kg", "amazon", "Pantry", "Coffee", 1099.99, "steady", tracked_days=40
    ),
    DemoProduct("Cold-Pressed Olive Oil 1 l", "trendyol", "Pantry", "Olive oil", 749.90, "deal"),
    DemoProduct("Rize Black Tea 1 kg", "trendyol", "Pantry", "Tea", 389.90, "up"),
    DemoProduct("Green Tea 100 pcs", "amazon", "Pantry", "Tea", 219.99, "steady"),
    DemoProduct("Raw Flower Honey 850 g", "trendyol", "Pantry", "Honey", 649.90, "steady"),
    # --- Cleaning ---
    # One laundry liquid in two sizes at two stores, linked by hand.
    DemoProduct(
        "Laundry Liquid 2.5 l", "rossmann", "Cleaning", "Laundry", 349.95, "fake", link="laundry"
    ),
    DemoProduct(
        "Laundry Liquid 1.5 l", "trendyol", "Cleaning", "Laundry", 219.90, "steady", link="laundry"
    ),
    DemoProduct("Fabric Softener 1440 ml", "watsons", "Cleaning", "Laundry", 159.95, "deal"),
    DemoProduct("Dishwasher Tablets 60 pcs", "amazon", "Cleaning", "Kitchen", 599.99, "waiting"),
    DemoProduct("Dish Soap 750 ml", "rossmann", "Cleaning", "Kitchen", 89.95, "steady"),
    DemoProduct(
        "Surface Cleaner Spray 500 ml",
        "gratis",
        "Cleaning",
        "Bathroom",
        119.90,
        "steady",
        tracked_days=25,
    ),
    # --- Supplements ---
    DemoProduct(
        "Vitamin D3 1000 IU, 90 tablets", "gratis", "Supplements", "Vitamins", 349.90, "steady"
    ),
    DemoProduct(
        "Vitamin C 1000 mg, 30 tablets", "eveshop", "Supplements", "Vitamins", 189.90, "up"
    ),
    DemoProduct(
        "Magnesium Bisglycinate 120 caps", "watsons", "Supplements", "Minerals", 489.95, "deal"
    ),
    DemoProduct("Zinc 25 mg, 100 tablets", "rossmann", "Supplements", "Minerals", 159.95, "steady"),
    DemoProduct("Omega-3 Fish Oil 60 caps", "amazon", "Supplements", "Fish oil", 429.99, "steady"),
    DemoProduct("Collagen Peptides 300 g", "trendyol", "Supplements", "Collagen", 899.90, "steady"),
]

# A floor with nothing on it yet, to show the empty-floor state.
EMPTY_FLOOR = "Fragrance"

# The latest Sunday paper (23 to 29 November, the week of Efsane Cuma) has news in every
# section. Most comes from Efsane Cuma itself; these make sure of the rest. Nothing here
# changes a product's state today.
PAPER_RISE = "Keratin Smooth Conditioner 350 ml"  # up 4% on Wednesday, before today's 6%
PAPER_SOLD_OUT = "Vitamin D3 1000 IU, 90 tablets"  # sold out on Friday, back on Saturday
PAPER_SLOWED = "Vitamin C 15% Serum 30 ml"  # one check stopped by a "too many requests"
PAPER_TIMEOUT = "Omega-3 Fish Oil 60 caps"  # one check timed out on Saturday
# Dearer per litre than the big bottle until Trendyol's Efsane week starts on Monday.
PAPER_CHEAPER = "Laundry Liquid 1.5 l"

_FLOOR_COLOR = "#D9D2C3"
_SCRIPTED_DAYS = 20  # the last 20 days of a scripted ending have no random events
_REPLAY_DAYS = 21  # the inbox holds the notes of the last three weeks
_HOSTS = {s.key: s.domains[0] for s in STORES}
# How each store prints a regular price: ₺349,90 at Gratis, ₺529,99 at Amazon.
_ENDINGS = {"amazon": 0.01, "watsons": 0.05, "rossmann": 0.05, "sephora": 0.0}


# --- one product's checks, without a database ----------------------------------------------


@dataclass
class Check:
    """One daily check: a price, or the error that stopped it."""

    at: datetime
    price: float | None = None  # None when the check failed
    member_price: float | None = None
    in_stock: bool = True
    error: FetchError | None = None


@dataclass(frozen=True)
class Campaign:
    start: date
    end: date
    depth: float  # the share taken off

    def __contains__(self, day: date) -> bool:
        return self.start <= day <= self.end


def shelf_price(value: float, store: str) -> float:
    """A regular price the way ``store`` prints it, near ``value``."""
    return round(round(value) - _ENDINGS.get(store, 0.10), 2)


def store_campaigns(store: str, seed: int, first: date) -> list[Campaign]:
    """A store's sales from ``first`` on: a few store-wide campaigns, 11.11 at the
    marketplaces and Efsane Cuma. Nothing else in the three weeks before Efsane Cuma."""
    rng = random.Random(f"{seed}:store:{store}")
    campaigns = []
    quiet_from = EFSANE_CUMA - timedelta(days=21)
    start = first + timedelta(days=rng.randint(8, 25))
    while start + timedelta(days=7) < quiet_from:
        length = rng.randint(3, 7)
        campaigns.append(
            Campaign(start, start + timedelta(days=length - 1), round(rng.uniform(0.10, 0.22), 2))
        )
        start += timedelta(days=rng.randint(24, 40))
    if store in _MARKETPLACES:
        campaigns.append(Campaign(*_ELEVEN_ELEVEN, round(rng.uniform(0.08, 0.14), 2)))
    efsane = _EFSANE_DAYS.get(store, _EFSANE_DEFAULT)
    campaigns.append(Campaign(*efsane, round(rng.uniform(0.18, 0.30), 2)))
    return campaigns


def _error(demo: DemoProduct, rng: random.Random) -> FetchError:
    host = _HOSTS.get(demo.store, demo.store)
    return rng.choice(
        [
            FetchError("Store answered 503."),
            FetchError("Network error: ReadTimeout."),
            StoreBlockedError(host, 429),
        ]
    )


@dataclass
class _Days:
    """One product's days, oldest first, while they're being made."""

    dates: list[date]
    price: list[float]  # shelf price
    member: list[bool]  # the store showed a card price that day
    in_stock: list[bool]
    errors: dict[int, FetchError] = field(default_factory=dict)

    def index(self, day: date) -> int:
        return len(self.dates) - 1 - (self.dates[-1] - day).days

    def between(self, first: date, last: date) -> range:
        return range(max(self.index(first), 0), self.index(last) + 1)


def _natural(
    demo: DemoProduct, rng: random.Random, days: list[date], campaigns: list[Campaign]
) -> _Days:
    """Inflation steps, campaigns, payday dips, the odd fake sale, stock gaps, failed checks
    and card prices that come and go."""
    n = len(days)

    # Regular prices: a step up every few weeks, ending at today's price.
    factors, factor, next_step = [], 1.0, rng.randint(5, 40)
    for i in range(n):
        if i == next_step:
            factor *= 1 + rng.uniform(0.025, 0.07)
            next_step = i + rng.randint(20, 45)
        factors.append(factor)
    regular = [
        demo.price if f == factors[-1] else shelf_price(demo.price * f / factors[-1], demo.store)
        for f in factors
    ]

    joins = {c: rng.random() < 0.7 for c in campaigns}  # not every product is in every sale
    own_depth = {c: c.depth * rng.uniform(0.8, 1.25) for c in campaigns}
    paydays: dict[tuple[int, int, bool], float] = {}
    out = _Days(days, [], [], [])
    trick_left = gap_left = 0
    trick_price = 0.0
    member_on = True
    recent = n - _REPLAY_DAYS  # random events stop before the last three weeks
    for i, day in enumerate(days):
        price = regular[i]
        sale = next((c for c in campaigns if day in c and joins[c]), None)
        if trick_left:  # a raised price, "discounted" back when it ends
            trick_left -= 1
            price = trick_price
        elif sale:
            price = round(regular[i] * (1 - own_depth[sale]), 2)
        elif day.day in (1, 2, 15, 16):  # around payday, a small dip at some stores
            key = (day.year, day.month, day.day > 2)
            if key not in paydays:
                paydays[key] = rng.uniform(0.03, 0.06) if rng.random() < 0.3 else 0.0
            if paydays[key]:
                price = round(regular[i] * (1 - paydays[key]), 2)
        elif i < recent - 10 and rng.random() < 0.008:
            trick_left = rng.randint(2, 5)
            trick_price = shelf_price(regular[i] * rng.uniform(1.15, 1.30), demo.store)
            price = trick_price
        out.price.append(price)

        if demo.member_comes_and_goes and i < recent and rng.random() < 0.07:
            member_on = not member_on
        out.member.append(demo.member_share is not None and (member_on or i >= recent))

        if gap_left:
            gap_left -= 1
        elif i < recent and rng.random() < 0.005:
            gap_left = rng.randint(2, 6)
        out.in_stock.append(gap_left == 0)
        if i < recent and rng.random() < 0.004:
            out.errors[i] = _error(demo, rng)
    return out


def _effective(d: _Days, i: int, share: float | None) -> float:
    return round(d.price[i] * share, 2) if d.member[i] and share else d.price[i]


def _script(demo: DemoProduct, d: _Days) -> None:
    """The scripted ending: today's state, and this product's part in the paper week."""
    n = len(d.dates)
    today = d.dates[-1]

    def flat(days: int) -> None:  # no sales, gaps or failures: just today's regular price
        for i in range(max(n - days, 0), n):
            d.price[i], d.in_stock[i] = demo.price, True
            d.errors.pop(i, None)

    def set_days(first: date, last: date, price: float) -> None:
        for i in d.between(first, last):
            d.price[i] = price

    if demo.ending == "fake":  # raised from Monday to Wednesday, "discounted" on Thursday
        flat(_SCRIPTED_DAYS)
        set_days(date(2026, 11, 23), date(2026, 11, 25), shelf_price(demo.price * 1.25, demo.store))
    elif demo.ending == "spike":  # up 20% the weekend before, then "18% off" all week
        flat(_SCRIPTED_DAYS)
        spike = shelf_price(demo.price * 1.2, demo.store)
        set_days(date(2026, 11, 20), date(2026, 11, 22), spike)
        set_days(date(2026, 11, 23), today, round(spike * 0.82, 2))
    elif demo.name == PAPER_RISE:  # up 4% on Wednesday, and 6% more today
        flat(_SCRIPTED_DAYS)
        set_days(date(2026, 11, 25), today, shelf_price(demo.price * 1.04, demo.store))
    elif demo.name == PAPER_CHEAPER:  # 20% off from Monday, still on today
        flat(_SCRIPTED_DAYS)
        set_days(date(2026, 11, 23), today, round(demo.price * 0.8, 2))

    if demo.ending == "deal":  # the Efsane price kept on Monday, and cut a little more today
        low = min(_effective(d, i, demo.member_share) for i in range(n - 2) if i not in d.errors)
        share = demo.member_share if d.member[-1] and demo.member_share else 1.0
        d.price[-2] = round(low * 0.99 / share, 2)
        d.price[-1] = round(low * 0.96 / share, 2)
        d.member[-2] = d.member[-1]
        d.errors.pop(n - 2, None)
    elif demo.ending == "steady":
        d.price[-1], d.member[-1] = d.price[-2], d.member[-2]
    elif demo.ending == "up":
        d.price[-1] = shelf_price(d.price[-2] * 1.06, demo.store)
    elif demo.ending == "error":
        d.errors[n - 1] = FetchError("Store answered 503.")
    elif demo.ending == "blocked":  # since Friday
        for i in d.between(EFSANE_CUMA, today):
            d.errors[i] = StoreBlockedError(_HOSTS[demo.store], 403)

    if demo.name == PAPER_SOLD_OUT:
        d.in_stock[d.index(date(2026, 11, 27))] = False
    if demo.name == PAPER_SLOWED:
        d.errors[d.index(date(2026, 11, 24))] = StoreBlockedError(_HOSTS[demo.store], 429)
    if demo.name == PAPER_TIMEOUT:
        d.errors[d.index(date(2026, 11, 28))] = FetchError("Network error: ReadTimeout.")


def demo_checks(
    demo: DemoProduct, days: int = DEFAULT_DAYS, seed: int = 7, today: date = DEMO_TODAY
) -> list[Check]:
    """Every check of one product, oldest first. The same arguments give the same checks."""
    at = datetime.combine(today, CHECK_TIME)
    if demo.ending == "waiting":
        return []
    if demo.ending == "first":
        return [Check(at, demo.price)]
    if demo.ending == "two_days":  # a little cheaper today
        return [Check(at - timedelta(days=1), demo.price), Check(at, round(demo.price * 0.9, 2))]

    n = min(days, demo.tracked_days or days)
    dates = [today - timedelta(days=n - 1 - i) for i in range(n)]
    rng = random.Random(f"{seed}:{demo.store}:{demo.name}")
    campaigns = store_campaigns(demo.store, seed, today - timedelta(days=days - 1))
    d = _natural(demo, rng, dates, campaigns)
    _script(demo, d)

    checks = []
    for i, day in enumerate(dates):
        when = datetime.combine(day, CHECK_TIME)
        if i in d.errors:
            checks.append(Check(when, error=d.errors[i]))
            continue
        member = _effective(d, i, demo.member_share) if d.member[i] else None
        checks.append(Check(when, d.price[i], member, d.in_stock[i]))
    return checks


# --- the database ------------------------------------------------------------------------------


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


def _target(demo: DemoProduct) -> float | None:
    """An alert price for most products, at a different distance for each."""
    rng = random.Random(f"target:{demo.store}:{demo.name}")
    share = rng.choice([None, 0.7, 0.75, 0.8, 0.85])
    return round(demo.price * share) if share else None


def _save(session: Session, product: Product, check: Check) -> None:
    if check.error is not None:
        session.add(
            CheckFailure(product_id=product.id, error=str(check.error), checked_at=check.at)
        )
        product.last_error = str(check.error)
        product.blocked = isinstance(check.error, StoreBlockedError) and check.error.status != 429
        return
    assert check.price is not None
    session.add(
        PricePoint(
            product_id=product.id,
            price=check.price,
            member_price=check.member_price,
            currency="TRY",
            in_stock=check.in_stock,
            checked_at=check.at,
        )
    )
    product.last_error, product.blocked = None, False


def seed_demo(session: Session, days: int = DEFAULT_DAYS, seed: int = 7) -> int:
    """Add the demo products and their history, as seen on ``DEMO_TODAY``."""
    days = max(days, 30)
    replay_from = DEMO_TODAY - timedelta(days=_REPLAY_DAYS - 1)

    products: list[tuple[Product, list[Check]]] = []
    for i, demo in enumerate(DEMO_PRODUCTS):
        checks = demo_checks(demo, days, seed)
        first = checks[0].at if checks else datetime.combine(DEMO_TODAY, CHECK_TIME)
        product = Product(
            url=f"https://demo.invalid/{demo.store}/{i}",
            name=demo.name,
            store=demo.store,
            category_id=room_for(session, demo.floor, demo.room).id,
            target_price=_target(demo),
            brand=demo.brand,
            created_at=first - timedelta(minutes=5),
        )
        update_size(product)  # from the name, like a new product
        update_group(product, demo.gtin)
        if demo.link:
            product.group_key, product.group_source = f"user:{demo.link}", "user"
        session.add(product)
        session.flush()
        products.append((product, checks))
    if session.scalar(select(Category).where(Category.name == EMPTY_FLOOR)) is None:
        session.add(Category(name=EMPTY_FLOOR, color=_FLOOR_COLOR))

    # Everything before the last three weeks at once; the app's alert states start there.
    for product, checks in products:
        for check in checks:
            if check.at.date() < replay_from:
                _save(session, product, check)
    session.commit()
    detect(session, [p for p, _ in products], True, replay_from - timedelta(days=1))

    # Then day by day, noting what the app would have noted after each morning's check.
    for offset in range(_REPLAY_DAYS):
        day = replay_from + timedelta(days=offset)
        checked = []
        for product, checks in products:
            for check in checks:
                if check.at.date() == day:
                    _save(session, product, check)
                    if check.error is None:
                        checked.append(product)
        session.commit()
        notes = detect(session, checked, True, day)
        if day.weekday() == 6:  # the Sunday paper, after the morning's check
            paper = Notification(kind="sunday_paper", week=day - timedelta(days=6))
            session.add(paper)
            notes.append(paper)
        _date_notes(notes, day)
        session.commit()
    return len(DEMO_PRODUCTS)


def _date_notes(notes: list[Notification], day: date) -> None:
    """Notes come a minute apart after the morning's check. Those from before today have
    been read, except the latest Sunday paper."""
    latest_paper = DEMO_TODAY - timedelta(days=DEMO_TODAY.weekday() + 1)
    for minute, note in enumerate(notes, start=1):
        note.created_at = datetime.combine(day, CHECK_TIME) + timedelta(minutes=minute)
        if day < DEMO_TODAY and not (note.kind == "sunday_paper" and day == latest_paper):
            note.read_at = note.created_at + timedelta(hours=2)
