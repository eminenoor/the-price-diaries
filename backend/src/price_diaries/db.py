"""Database models and session handling (SQLAlchemy 2.0)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sqlalchemy import Float, ForeignKey, Index, String, create_engine, event, false, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from price_diaries.analysis import Offer


class Base(DeclarativeBase):
    pass


class Category(Base):
    """A "floor" (top level, e.g. Skincare) or a "room" inside one (e.g. Toners).

    Only two levels: a room's parent is always a floor.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    color: Mapped[str] = mapped_column(String(7))  # "#RRGGBB"

    rooms: Mapped[list[Category]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="Category.name"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    # From the store page; the user can correct it. "" means "no brand, don't fill it in".
    brand: Mapped[str | None] = mapped_column(String(100))
    store: Mapped[str] = mapped_column(String(32), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    selector: Mapped[str | None] = mapped_column(String(300))
    target_price: Mapped[float | None] = mapped_column(Float)
    image_url: Mapped[str | None] = mapped_column(String(2048))  # from the store page
    last_error: Mapped[str | None] = mapped_column(String(500))
    # The store refused the last check (403 or an "Access Denied" page).
    blocked: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Pack size in "ml", "g" or "pcs", for the unit price. size_source says where it came
    # from: "name", "page" or "user". Checks never change a size the user set or removed.
    size_amount: Mapped[float | None] = mapped_column(Float)
    size_unit: Mapped[str | None] = mapped_column(String(3))
    size_source: Mapped[str | None] = mapped_column(String(4))
    # Barcode from the store page, as 14 digits (GTIN-14; EAN-13 and UPC padded with zeros).
    gtin: Mapped[str | None] = mapped_column(String(14))
    # The same product at other stores shares a group_key: "gtin:<barcode>" when grouped by
    # barcode, "user:<id>" when linked by hand. group_source "user" means the user linked or
    # unlinked it, so checks leave the group alone.
    group_key: Mapped[str | None] = mapped_column(String(24), index=True)
    group_source: Mapped[str | None] = mapped_column(String(7))
    # A name the user gave this product, shared by every product in its group. None means
    # the app picks the most complete store name in the group.
    display_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    prices: Mapped[list[PricePoint]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="PricePoint.checked_at",
    )

    def offer(self, use_member_prices: bool) -> Offer | None:
        """The latest price you'd pay at this store, or None before the first check."""
        if not self.prices:
            return None
        latest = self.prices[-1]
        return Offer(
            product_id=self.id,
            price=latest.effective_price(use_member_prices),
            checked_at=latest.checked_at,
            in_stock=latest.in_stock,
            size_amount=self.size_amount,
            size_unit=self.size_unit,
        )


class PricePoint(Base):
    __tablename__ = "price_points"
    __table_args__ = (Index("ix_price_points_product_time", "product_id", "checked_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    price: Mapped[float] = mapped_column(Float)  # regular shelf price
    member_price: Mapped[float | None] = mapped_column(Float)  # loyalty-card price, if any
    currency: Mapped[str] = mapped_column(String(3), default="TRY")
    in_stock: Mapped[bool] = mapped_column(default=True)
    checked_at: Mapped[datetime] = mapped_column(default=datetime.now)

    product: Mapped[Product] = relationship(back_populates="prices")

    def effective_price(self, use_member_prices: bool) -> float:
        """The price you would actually pay."""
        if use_member_prices and self.member_price is not None:
            return self.member_price
        return self.price


class Notification(Base):
    """A note in the inbox: something worth knowing about a product after a check."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    # "target", "lowest", "fake_sale", "cheaper" or "back_in_stock"
    kind: Mapped[str] = mapped_column(String(16))
    old_price: Mapped[float | None] = mapped_column(Float)
    new_price: Mapped[float | None] = mapped_column(Float)
    # For "cheaper": the store that sells it for less (new_price is its price for this size).
    other_store: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    read_at: Mapped[datetime | None] = mapped_column()


class AlertState(Base):
    """Whether an alert's condition held at the last check, so each event is sent once.

    A note goes out only when the condition turns from false to true: the alert-price
    note again only after the price went back above the alert price and came down again.
    """

    __tablename__ = "alert_states"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    active: Mapped[bool] = mapped_column()
    # For "lowest": the price the next new-low note is measured from. The price of the last
    # new-low note, or the lowest price when notes started for this product.
    price: Mapped[float | None] = mapped_column(Float)


def ensure_sqlite_dir(url: str) -> None:
    """SQLite creates the file but not its folder, so create the folder first."""
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


def make_engine(url: str) -> Engine:
    ensure_sqlite_dir(url)
    engine = create_engine(url, connect_args={"check_same_thread": False})

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_conn, _):  # SQLite ignores FKs unless asked
            dbapi_conn.execute("PRAGMA foreign_keys = ON")

    return engine


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = make_engine(url)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self._sessions()

    def session_scope(self) -> Iterator[Session]:
        """FastAPI dependency: one session per request."""
        with self._sessions() as session:
            yield session
