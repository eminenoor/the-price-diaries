"""HTTP API used by the React dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from price_diaries import migrate
from price_diaries.analysis import (
    Offer,
    cheaper_elsewhere,
    pick_display_name,
    price_anomalies,
    rank_offers,
    saving,
    summarize,
    unit_price,
)
from price_diaries.checker import check_all, check_product, update_size
from price_diaries.db import Category, Database, Product
from price_diaries.fetcher import Fetcher
from price_diaries.parsers import STORES, Size, parse_size, with_size
from price_diaries.scheduler import build_scheduler
from price_diaries.schemas import (
    AnomalyOut,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    CheckResult,
    ElsewhereNote,
    LinkCreate,
    OfferOut,
    PricePointOut,
    ProductCreate,
    ProductDetail,
    ProductOut,
    ProductUpdate,
    SizeOut,
    StoreOut,
    Summary,
    UnitPriceOut,
)
from price_diaries.security import UnsupportedURLError, validate_product_url
from price_diaries.settings import Settings, get_settings

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    db = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        migrate.upgrade(settings.database_url)
        scheduler = build_scheduler(db, settings) if settings.scheduler_enabled else None
        if scheduler:
            scheduler.start()
        yield
        if scheduler:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="The Price Diaries", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _register_routes(app)
    if settings.frontend_dir and Path(settings.frontend_dir, "index.html").exists():
        _serve_frontend(app, Path(settings.frontend_dir).resolve())
    return app


def _serve_frontend(app: FastAPI, root: Path) -> None:
    """Serve the built React app, so daily use needs one process and one port."""

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        file = (root / path).resolve()
        # Stay inside the build folder (no ../ tricks), and let the React
        # router handle any other path such as /products/3.
        if path and file.is_relative_to(root) and file.is_file():
            return FileResponse(file)
        return FileResponse(root / "index.html")


# --- dependencies ------------------------------------------------------------


def get_session(request: Request):
    yield from request.app.state.db.session_scope()


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def _get_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found.")
    return product


DEFAULT_FLOOR_COLOR = "#D9D2C3"


def _get_category(session: Session, category_id: int) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Floor or room not found.")
    return category


def _require_unique_name(session: Session, name: str, parent_id: int | None) -> None:
    siblings = session.scalars(
        select(Category.name).where(
            Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id
        )
    )
    if name.casefold() in {s.casefold() for s in siblings}:
        where = "floor" if parent_id is None else "room on this floor"
        raise HTTPException(status.HTTP_409_CONFLICT, f"There's already a {where} called {name}.")


def _category_out(category: Category) -> CategoryOut:
    return CategoryOut(
        id=category.id, name=category.name, parent_id=category.parent_id, color=category.color
    )


def _require_category(session: Session, category_id: int | None) -> None:
    if category_id is not None and session.get(Category, category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That floor or room is gone.")


# --- serialization -------------------------------------------------------------


def _history(product: Product, use_member: bool) -> list[tuple]:
    """Price history using the price you would actually pay."""
    return [(p.checked_at, p.effective_price(use_member)) for p in product.prices]


_STORE_NAMES = {s.key: s.name for s in STORES}


def _store_name(key: str) -> str:
    return _STORE_NAMES.get(key, key)


def _offer(product: Product, use_member: bool) -> Offer | None:
    """The latest price you'd pay at this store, or None before the first check."""
    if not product.prices:
        return None
    latest = product.prices[-1]
    return Offer(
        product_id=product.id,
        price=latest.effective_price(use_member),
        checked_at=latest.checked_at,
        in_stock=latest.in_stock,
        size_amount=product.size_amount,
        size_unit=product.size_unit,
    )


def _group(session: Session, product: Product) -> list[Product]:
    """The same product at other stores (not this one)."""
    if product.group_key is None:
        return []
    return list(
        session.scalars(
            select(Product).where(Product.group_key == product.group_key, Product.id != product.id)
        )
    )


def _unit_price_out(price: float, product: Product) -> UnitPriceOut | None:
    if product.size_amount is None or product.size_unit is None:
        return None
    found = unit_price(price, product.size_amount, product.size_unit)
    return UnitPriceOut(**vars(found)) if found else None


def _cheaper_elsewhere(
    product: Product, others: Sequence[Product], use_member: bool
) -> ElsewhereNote | None:
    here = _offer(product, use_member)
    if here is None:
        return None
    offers = [o for o in (_offer(p, use_member) for p in others) if o is not None]
    best = cheaper_elsewhere(here, offers, date.today())
    if best is None:
        return None
    there = next(p for p in others if p.id == best[0].product_id)
    return ElsewhereNote(
        product_id=there.id, store=there.store, store_name=_store_name(there.store), saving=best[1]
    )


def _display_name(product: Product, others: Sequence[Product]) -> str:
    """One name for the product at every store: the user's, or the most complete store name."""
    members = sorted([product, *others], key=lambda p: p.id)
    chosen = [p.display_name for p in members if p.display_name]
    name = chosen[0] if chosen else pick_display_name([p.name for p in members])
    # Stores in a group can sell different sizes: keep this one's own size in the name.
    size = None
    if product.size_amount is not None and product.size_unit is not None:
        size = Size(product.size_amount, product.size_unit)  # type: ignore[arg-type]
    return with_size(name, size, product.name)


def _to_out(product: Product, use_member: bool, others: Sequence[Product] = ()) -> ProductOut:
    history = _history(product, use_member)
    summary = summarize(history)
    latest = product.prices[-1] if product.prices else None
    shows_member = bool(latest and use_member and latest.member_price is not None)
    size = per_unit = None
    if product.size_amount is not None and product.size_unit is not None:
        size = SizeOut(
            amount=product.size_amount, unit=product.size_unit, source=product.size_source
        )
        if summary is not None:
            per_unit = _unit_price_out(summary.current, product)
    return ProductOut(
        id=product.id,
        url=product.url,
        name=_display_name(product, others),
        listing_name=product.name,
        brand=product.brand or None,  # "" (removed by the user) is no brand too
        store=product.store,
        category_id=product.category_id,
        target_price=product.target_price,
        image_url=product.image_url,
        last_error=product.last_error,
        blocked=product.blocked,
        created_at=product.created_at,
        summary=Summary(**vars(summary)) if summary else None,
        regular_price=latest.price if shows_member else None,
        sparkline=[price for _, price in history[-30:]],
        size=size,
        unit_price=per_unit,
        gtin=product.gtin,
        cheaper_elsewhere=_cheaper_elsewhere(product, others, use_member),
    )


def _elsewhere(product: Product, others: Sequence[Product], use_member: bool) -> list[OfferOut]:
    """The same product at other stores, cheapest first. Unchecked listings are left out."""
    here = _offer(product, use_member)
    by_id = {p.id: p for p in others}
    offers = [o for o in (_offer(p, use_member) for p in others) if o is not None]
    return [
        OfferOut(
            product_id=offer.product_id,
            name=by_id[offer.product_id].name,
            store=by_id[offer.product_id].store,
            store_name=_store_name(by_id[offer.product_id].store),
            price=offer.price,
            unit_price=_unit_price_out(offer.price, by_id[offer.product_id]),
            checked_at=offer.checked_at,
            in_stock=offer.in_stock,
            saving=saving(here, offer) if here else None,
        )
        for offer in rank_offers(offers)
    ]


def _to_detail(session: Session, product: Product, use_member: bool) -> ProductDetail:
    history = _history(product, use_member)
    others = _group(session, product)
    return ProductDetail(
        **_to_out(product, use_member, others).model_dump(),
        history=[PricePointOut.model_validate(p, from_attributes=True) for p in product.prices],
        anomalies=[AnomalyOut(**vars(a)) for a in price_anomalies(history)],
        elsewhere=_elsewhere(product, others, use_member),
    )


# --- routes ----------------------------------------------------------------------


def _register_routes(app: FastAPI) -> None:
    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/stores")
    def list_stores() -> list[StoreOut]:
        return [StoreOut(key=s.key, name=s.name, domains=list(s.domains)) for s in STORES]

    @app.get("/api/categories")
    def list_categories(session: SessionDep) -> list[CategoryOut]:
        """Floors in the order they were added, each followed by its rooms A to Z."""
        floors = session.scalars(
            select(Category).where(Category.parent_id.is_(None)).order_by(Category.id)
        ).all()
        return [_category_out(c) for floor in floors for c in (floor, *floor.rooms)]

    @app.post("/api/categories", status_code=status.HTTP_201_CREATED)
    def create_category(body: CategoryCreate, session: SessionDep) -> CategoryOut:
        name = body.name.strip()
        color = body.color or DEFAULT_FLOOR_COLOR
        if body.parent_id is not None:
            parent = session.get(Category, body.parent_id)
            if parent is None or parent.parent_id is not None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, "Rooms can only be added to a floor."
                )
            color = body.color or parent.color
        _require_unique_name(session, name, body.parent_id)
        category = Category(name=name, parent_id=body.parent_id, color=color.upper())
        session.add(category)
        session.commit()
        return _category_out(category)

    @app.patch("/api/categories/{category_id}")
    def update_category(category_id: int, body: CategoryUpdate, session: SessionDep) -> CategoryOut:
        category = _get_category(session, category_id)
        if body.name is not None and body.name.strip() != category.name:
            _require_unique_name(session, body.name.strip(), category.parent_id)
            category.name = body.name.strip()
        if body.color is not None:
            category.color = body.color.upper()
        session.commit()
        return _category_out(category)

    @app.delete("/api/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_category(category_id: int, session: SessionDep) -> None:
        """Deleting a floor deletes its rooms. Products stay, without a category."""
        session.delete(_get_category(session, category_id))
        session.commit()

    @app.get("/api/products")
    def list_products(session: SessionDep, settings: SettingsDep) -> list[ProductOut]:
        products = session.scalars(select(Product).order_by(Product.name)).all()
        groups: dict[str, list[Product]] = {}
        for p in products:
            if p.group_key is not None:
                groups.setdefault(p.group_key, []).append(p)
        outs = [
            _to_out(
                p,
                settings.use_member_prices,
                [o for o in groups.get(p.group_key or "", []) if o.id != p.id],
            )
            for p in products
        ]
        return sorted(outs, key=lambda o: o.name.casefold())

    @app.post("/api/products", status_code=status.HTTP_201_CREATED)
    def create_product(
        body: ProductCreate, session: SessionDep, settings: SettingsDep
    ) -> ProductOut:
        try:
            url, store = validate_product_url(body.url)
        except UnsupportedURLError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        _require_category(session, body.category_id)

        product = Product(
            url=url,
            name=body.name.strip(),
            store=store.key,
            category_id=body.category_id,
            target_price=body.target_price,
            selector=body.selector,
        )
        update_size(product)
        session.add(product)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "This link is already tracked.") from exc
        session.refresh(product)
        return _to_out(product, settings.use_member_prices)

    @app.get("/api/products/{product_id}")
    def get_product(product_id: int, session: SessionDep, settings: SettingsDep) -> ProductDetail:
        return _to_detail(session, _get_product(session, product_id), settings.use_member_prices)

    @app.patch("/api/products/{product_id}")
    def update_product(
        product_id: int, body: ProductUpdate, session: SessionDep, settings: SettingsDep
    ) -> ProductOut:
        product = _get_product(session, product_id)
        changes = body.model_dump(exclude_unset=True)
        _require_category(session, changes.get("category_id"))
        if "brand" in changes:
            # A blank brand is kept as "", so the next check doesn't fill it in again.
            changes["brand"] = " ".join((changes["brand"] or "").split())
        if "display_name" in changes:
            # Shared by the whole group; "" goes back to the most complete store name.
            display_name = " ".join((changes.pop("display_name") or "").split()) or None
            for member in [product, *_group(session, product)]:
                member.display_name = display_name
        size_text = (changes.pop("size", None) or "").strip()
        if "size" in body.model_fields_set:
            size = parse_size(size_text)
            if size_text and size is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "Write the size with a unit, like 150 ml, 1,5 L, 500 g or 60 adet.",
                )
            # Removing it is kept too (source "user"), so checks don't fill it in again.
            product.size_amount = size.amount if size else None
            product.size_unit = size.unit if size else None
            product.size_source = "user"
        for field, value in changes.items():
            setattr(product, field, value)
        if "name" in changes:
            update_size(product)
        session.commit()
        return _to_out(product, settings.use_member_prices, _group(session, product))

    @app.post("/api/products/{product_id}/link")
    def link_product(
        product_id: int, body: LinkCreate, session: SessionDep, settings: SettingsDep
    ) -> ProductDetail:
        """Group this product with another one: the same product at another store.

        It joins the other product's group (leaving its own). Checks won't move it
        again, even if the barcodes differ.
        """
        product = _get_product(session, product_id)
        other = session.get(Product, body.other_id)
        if other is None or other.id == product.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick another tracked product to link."
            )
        if other.group_key is None:
            other.group_key, other.group_source = f"user:{other.id}", "user"
        product.group_key, product.group_source = other.group_key, "user"
        product.display_name = None  # take the new group's name
        session.commit()
        return _to_detail(session, product, settings.use_member_prices)

    @app.delete("/api/products/{product_id}/link", status_code=status.HTTP_204_NO_CONTENT)
    def unlink_product(product_id: int, session: SessionDep) -> None:
        """Take this product out of its group. Checks won't put it back by barcode."""
        product = _get_product(session, product_id)
        product.group_key, product.group_source = None, "user"
        product.display_name = None  # the group's name stays with the group
        session.commit()

    @app.delete("/api/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_product(product_id: int, session: SessionDep) -> None:
        session.delete(_get_product(session, product_id))
        session.commit()

    @app.post("/api/products/{product_id}/check")
    async def check_one(product_id: int, session: SessionDep, settings: SettingsDep) -> CheckResult:
        product = _get_product(session, product_id)
        async with Fetcher(0, 0, settings.request_timeout) as fetcher:
            outcome = await check_product(session, product, fetcher, settings.browser_fallback)
        return CheckResult(**vars(outcome))

    @app.post("/api/check")
    async def check_everything(session: SessionDep, settings: SettingsDep) -> list[CheckResult]:
        async with Fetcher(settings.min_delay, settings.max_delay, settings.request_timeout) as f:
            outcomes = await check_all(session, f, settings.browser_fallback)
        return [CheckResult(**vars(o)) for o in outcomes]
