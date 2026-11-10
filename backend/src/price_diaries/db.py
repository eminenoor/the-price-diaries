"""Database models and session handling (SQLAlchemy 2.0)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sqlalchemy import Float, ForeignKey, Index, String, create_engine, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    store: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str | None] = mapped_column(String(50))
    selector: Mapped[str | None] = mapped_column(String(300))
    target_price: Mapped[float | None] = mapped_column(Float)
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    prices: Mapped[list[PricePoint]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="PricePoint.checked_at",
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
