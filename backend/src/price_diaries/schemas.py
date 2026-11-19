"""Request and response models for the HTTP API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class AppInfo(BaseModel):
    # The day the app treats as today when PD_TODAY is set (the demo), else None.
    set_date: date | None


class StoreOut(BaseModel):
    key: str
    name: str
    domains: list[str]


HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


class CategoryOut(BaseModel):
    id: int
    name: str
    parent_id: int | None = Field(description="None for a floor; the floor's id for a room.")
    color: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    parent_id: int | None = Field(default=None, description="Set to a floor's id to add a room.")
    color: str | None = Field(
        default=None, pattern=HEX_COLOR, description="Defaults to the floor's."
    )


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=HEX_COLOR)


class ProductCreate(BaseModel):
    url: str = Field(max_length=2048, examples=["https://www.gratis.com/urun-p-12345"])
    name: str = Field(min_length=1, max_length=200)
    category_id: int | None = Field(default=None, description="A room or a floor.")
    target_price: float | None = Field(default=None, gt=0)
    selector: str | None = Field(default=None, max_length=300)


class ProductUpdate(BaseModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=200, description="The store's name for it."
    )
    display_name: str | None = Field(
        default=None,
        max_length=200,
        description="The name shown for it at every store in its group. "
        '"" or null goes back to the most complete store name.',
    )
    brand: str | None = Field(
        default=None, max_length=100, description='"" means no brand; checks won\'t fill it in.'
    )
    category_id: int | None = None
    target_price: float | None = Field(default=None, gt=0)
    selector: str | None = Field(default=None, max_length=300)
    size: str | None = Field(
        default=None,
        max_length=50,
        examples=["150 ml", "1,5 L", "500 g", "60 adet"],
        description='The pack size as written on the pack. "" or null removes it; '
        "checks won't fill it in again.",
    )


SizeUnit = Literal["ml", "g", "pcs"]


class SizeOut(BaseModel):
    amount: float = Field(description="In millilitres, grams or pieces.")
    unit: SizeUnit
    source: Literal["name", "page", "user"]


class UnitPriceOut(BaseModel):
    price: float = Field(description="The price of `per` of `unit`, e.g. 2.53 for 10 ml.")
    per: int
    unit: SizeUnit


class Summary(BaseModel):
    current: float
    previous: float | None
    lowest: float
    lowest_at: datetime
    highest: float
    highest_at: datetime
    lowest_30d: float
    change_pct: float | None
    is_all_time_low: bool
    fake_sale: bool


class ElsewhereNote(BaseModel):
    """The same product is cheaper at another store today."""

    product_id: int
    store: str
    store_name: str
    saving: float = Field(description="How much less it costs there, for this product's size.")


class ProductOut(BaseModel):
    id: int
    url: str
    name: str = Field(
        description="The name to show: the user's, or the most complete store name in its group."
    )
    listing_name: str = Field(description="This store's own name for it.")
    brand: str | None = Field(
        default=None, description="From the store page or set by the user; None if unknown."
    )
    store: str
    category_id: int | None
    target_price: float | None
    image_url: str | None = Field(default=None, description="Product photo from the store.")
    last_error: str | None
    blocked: bool = Field(default=False, description="The store refuses automated checks.")
    created_at: datetime
    summary: Summary | None
    regular_price: float | None = Field(
        default=None, description="Latest shelf price, when a member price is shown instead."
    )
    sparkline: list[float] = Field(description="Up to the last 30 prices, oldest first.")
    size: SizeOut | None = Field(default=None, description="Pack size, if known.")
    unit_price: UnitPriceOut | None = Field(
        default=None, description="Current price (the card price when shown) per unit of size."
    )
    gtin: str | None = Field(default=None, description="Barcode, 14 digits, if the store shows it.")
    cheaper_elsewhere: ElsewhereNote | None = Field(
        default=None, description="The biggest saving at another store, from today's checks."
    )


class PricePointOut(BaseModel):
    checked_at: datetime
    price: float
    member_price: float | None
    currency: str
    in_stock: bool


class AnomalyOut(BaseModel):
    checked_at: datetime
    price: float
    change_pct: float
    score: float


class OfferOut(BaseModel):
    """The same product at another store."""

    product_id: int
    name: str
    store: str
    store_name: str
    price: float = Field(description="The price you'd pay there (the card price when shown).")
    unit_price: UnitPriceOut | None
    checked_at: datetime
    in_stock: bool
    saving: float | None = Field(
        description="How much less it costs there than here, for this product's size. "
        "Negative when it costs more; None when the sizes can't be compared."
    )


class ProductDetail(ProductOut):
    history: list[PricePointOut]
    anomalies: list[AnomalyOut]
    elsewhere: list[OfferOut] = Field(
        default_factory=list, description="The same product at other stores, cheapest first."
    )


class LinkCreate(BaseModel):
    other_id: int = Field(description="A product to group this one with.")


NoteKind = Literal["target", "lowest", "fake_sale", "cheaper", "back_in_stock", "sunday_paper"]


class NoteOut(BaseModel):
    """A note in the inbox: about one product, or the Sunday paper (no product)."""

    id: int
    kind: NoteKind
    product_id: int | None
    product_name: str | None
    store: str | None
    store_name: str | None
    old_price: float | None = Field(
        description="The price at the check before; for cheaper, the price here."
    )
    new_price: float | None = Field(
        description="The new price; for cheaper, the other store's price for this size."
    )
    other_store_name: str | None = Field(description="For cheaper: the store that sells it.")
    week: date | None = Field(
        default=None, description="For sunday_paper: the Monday of the week it's about."
    )
    created_at: datetime
    read: bool


class NotesOut(BaseModel):
    unread: int
    notes: list[NoteOut] = Field(description="The latest notes, newest first.")


class PaperItem(BaseModel):
    """One product in the Sunday paper."""

    product_id: int
    name: str
    store_name: str


class PaperMove(PaperItem):
    """The price before the week against the last price in it."""

    old_price: float
    new_price: float
    change_pct: float


class PaperLow(PaperItem):
    price: float = Field(description="The week's lowest price.")
    at: datetime
    previous_low: float = Field(description="The lowest price before the week.")


class PaperFakeSale(PaperItem):
    price: float = Field(description="The 'sale' price.")
    peak: float = Field(description="The raised price before it.")
    at: datetime


class PaperCheaper(PaperItem):
    other_store_name: str
    price_here: float
    price_there: float = Field(description="The other store's price for this product's size.")
    at: datetime


class PaperTrouble(PaperItem):
    failed_checks: int = Field(description="Checks that couldn't get a price this week.")
    last_error: str | None
    out_of_stock_at: datetime | None = Field(description="When it went out of stock this week.")


class PaperOut(BaseModel):
    """One week, Monday to Sunday. Every list may be empty."""

    week_start: date
    week_end: date
    previous_week: date | None = Field(description="None before the first check.")
    next_week: date | None = Field(description="None when the next paper isn't out yet.")
    products_checked: int = Field(description="Products checked at least once this week.")
    drops: list[PaperMove] = Field(description="Biggest drop first.")
    new_lows: list[PaperLow]
    fake_sales: list[PaperFakeSale]
    cheaper: list[PaperCheaper] = Field(description="Biggest saving first.")
    rises: list[PaperMove] = Field(description="Biggest rise first.")
    trouble: list[PaperTrouble] = Field(description="Failed checks or out of stock.")


class CheckResult(BaseModel):
    product_id: int
    ok: bool
    price: float | None = None
    error: str | None = None
