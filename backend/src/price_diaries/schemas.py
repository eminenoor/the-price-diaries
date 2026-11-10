"""Request and response models for the HTTP API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StoreOut(BaseModel):
    key: str
    name: str
    domains: list[str]


class ProductCreate(BaseModel):
    url: str = Field(max_length=2048, examples=["https://www.gratis.com/urun-p-12345"])
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    target_price: float | None = Field(default=None, gt=0)
    selector: str | None = Field(default=None, max_length=300)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=50)
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
    category: str | None
    target_price: float | None
    last_error: str | None
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
