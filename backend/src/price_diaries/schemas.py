"""Request and response models for the HTTP API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: int | None = None
    target_price: float | None = Field(default=None, gt=0)
    selector: str | None = Field(default=None, max_length=300)


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


class ProductOut(BaseModel):
    id: int
    url: str
    name: str
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


class ProductDetail(ProductOut):
    history: list[PricePointOut]
    anomalies: list[AnomalyOut]


class CheckResult(BaseModel):
    product_id: int
    ok: bool
    price: float | None = None
    error: str | None = None
