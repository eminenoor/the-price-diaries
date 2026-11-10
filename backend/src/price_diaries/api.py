"""HTTP API used by the React dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from price_diaries import migrate
from price_diaries.analysis import price_anomalies, summarize
from price_diaries.checker import check_all, check_product
from price_diaries.db import Database, Product
from price_diaries.fetcher import Fetcher
from price_diaries.parsers import STORES
from price_diaries.scheduler import build_scheduler
from price_diaries.schemas import (
    AnomalyOut,
    CheckResult,
    PricePointOut,
    ProductCreate,
    ProductDetail,
    ProductOut,
    ProductUpdate,
    StoreOut,
    Summary,
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


# --- serialization -------------------------------------------------------------


def _to_out(product: Product) -> ProductOut:
    history = [(p.checked_at, p.price) for p in product.prices]
    summary = summarize(history)
    return ProductOut(
        id=product.id,
        url=product.url,
        name=product.name,
        store=product.store,
        category=product.category,
        target_price=product.target_price,
        last_error=product.last_error,
        created_at=product.created_at,
        summary=Summary(**vars(summary)) if summary else None,
        sparkline=[price for _, price in history[-30:]],
    )


def _to_detail(product: Product) -> ProductDetail:
    history = [(p.checked_at, p.price) for p in product.prices]
    return ProductDetail(
        **_to_out(product).model_dump(),
        history=[PricePointOut.model_validate(p, from_attributes=True) for p in product.prices],
        anomalies=[AnomalyOut(**vars(a)) for a in price_anomalies(history)],
    )


# --- routes ----------------------------------------------------------------------


def _register_routes(app: FastAPI) -> None:
    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/stores")
    def list_stores() -> list[StoreOut]:
        return [StoreOut(key=s.key, name=s.name, domains=list(s.domains)) for s in STORES]

    @app.get("/api/products")
    def list_products(session: SessionDep) -> list[ProductOut]:
        products = session.scalars(select(Product).order_by(Product.name)).all()
        return [_to_out(p) for p in products]

    @app.post("/api/products", status_code=status.HTTP_201_CREATED)
    def create_product(body: ProductCreate, session: SessionDep) -> ProductOut:
        try:
            url, store = validate_product_url(body.url)
        except UnsupportedURLError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

        product = Product(
            url=url,
            name=body.name.strip(),
            store=store.key,
            category=body.category,
            target_price=body.target_price,
            selector=body.selector,
        )
        session.add(product)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "This link is already tracked.") from exc
        session.refresh(product)
        return _to_out(product)

    @app.get("/api/products/{product_id}")
    def get_product(product_id: int, session: SessionDep) -> ProductDetail:
        return _to_detail(_get_product(session, product_id))

    @app.patch("/api/products/{product_id}")
    def update_product(product_id: int, body: ProductUpdate, session: SessionDep) -> ProductOut:
        product = _get_product(session, product_id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        session.commit()
        return _to_out(product)

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
