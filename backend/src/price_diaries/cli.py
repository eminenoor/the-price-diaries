"""Command line: `price-diaries serve | check | migrate | demo | inspect | notify`."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from price_diaries import migrate
from price_diaries.db import Database
from price_diaries.settings import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="price-diaries")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the API and the daily scheduler")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="restart on code changes")
    serve.add_argument(
        "--demo", action="store_true", help="show the demo database on its day, with no checks"
    )
    sub.add_parser("check", help="check all prices once, now")
    sub.add_parser("migrate", help="create or update the database schema")
    demo = sub.add_parser("demo", help="add fake products with 180 days of history")
    demo.add_argument("--days", type=int, default=180)
    inspect = sub.add_parser("inspect", help="show what the tracker finds on a product page")
    inspect.add_argument("url")
    inspect.add_argument("--browser", action="store_true", help="also load the page in Chromium")
    inspect.add_argument("--save", metavar="FILE", help="save the downloaded HTML to a file")
    notify = sub.add_parser("notify", help="desktop notifications")
    notify_sub = notify.add_subparsers(dest="notify_command", required=True)
    notify_sub.add_parser("test", help="send one test notification")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = get_settings()

    if args.command == "serve":
        import uvicorn

        if args.demo:
            _use_demo(settings.demo_database_url)
        # 127.0.0.1 only: the app has no login, so it must not be reachable from the network.
        uvicorn.run("price_diaries.main:app", host="127.0.0.1", port=args.port, reload=args.reload)
        return 0

    if args.command == "inspect":
        return asyncio.run(_inspect(args.url, args.browser, args.save))

    if args.command == "notify":
        return asyncio.run(_notify_test(settings.desktop_notifications))

    if args.command == "demo":
        return _demo(args.days, settings.database_url, settings.demo_database_url)

    migrate.upgrade(settings.database_url)
    if args.command == "migrate":
        print("Database is up to date.")
    elif args.command == "check":
        from price_diaries.scheduler import run_daily_check

        asyncio.run(run_daily_check(Database(settings.database_url), settings))
    return 0


def _demo(days: int, real_url: str, demo_url: str) -> int:
    """Seed the demo into its own database, never the real one."""
    from sqlalchemy import func, select

    from price_diaries.db import Product
    from price_diaries.demo import DEMO_TODAY, seed_demo

    if _same_database(real_url, demo_url):
        print(
            "PD_DEMO_DATABASE_URL points at your real database, so the demo wasn't added. "
            "Give the demo a file of its own."
        )
        return 1
    migrate.upgrade(demo_url)
    shown = demo_url.removeprefix("sqlite:///")
    with Database(demo_url).session() as session:
        if session.scalar(select(func.count()).select_from(Product)):
            print(f"The demo is already in {shown}. Delete that file to start it again.")
            return 1
        count = seed_demo(session, days=days)
    day = f"{DEMO_TODAY.day} {DEMO_TODAY:%B %Y}"
    print(f"Added {count} demo products to {shown}, as they are on {day}.")
    print("See them with: uv run price-diaries serve --demo")
    return 0


def _same_database(a: str, b: str) -> bool:
    def where(url: str) -> str:
        if url.startswith("sqlite:///") and ":memory:" not in url:
            return str(Path(url.removeprefix("sqlite:///")).resolve()).casefold()
        return url

    return where(a) == where(b)


def _use_demo(demo_url: str) -> None:
    """`serve --demo`: the demo database, on the demo's day, without the daily check."""
    import os

    from price_diaries.demo import DEMO_TODAY

    os.environ["PD_DATABASE_URL"] = demo_url
    os.environ["PD_TODAY"] = DEMO_TODAY.isoformat()
    os.environ["PD_SCHEDULER_ENABLED"] = "false"
    get_settings.cache_clear()  # the app reads its settings again, with these


async def _inspect(url: str, browser: bool, save: str | None) -> int:
    from price_diaries.fetcher import Fetcher, FetchError
    from price_diaries.security import UnsupportedURLError, validate_product_url

    try:
        url, store = validate_product_url(url)
    except UnsupportedURLError as exc:
        print(f"error: {exc}")
        return 2

    parser = store.parser()
    member_found = False
    async with Fetcher(min_delay=0, max_delay=0) as fetcher:
        pages = [("page HTML", fetcher.get)]
        if browser:
            pages.append(("browser", fetcher.get_rendered))
        for label, load in pages:
            try:
                html = await load(url)
            except FetchError as exc:
                print(f"\n{label}: could not load ({exc})")
                continue
            if save:
                Path(save).write_text(html, encoding="utf-8")
                print(f"Saved {label} to {save}")
            print(f"\n{store.name}, {label}:")
            found = parser.explain(html)
            member_found = member_found or found["member price"] is not None
            for strategy, price in found.items():
                print(f"  {strategy:<16} {price if price is not None else '-'}")

    if store.member_labels and not browser and not member_found:
        print("\nNo member price? It may be added by JavaScript. Try again with --browser.")
    return 0


async def _notify_test(enabled: bool) -> int:
    from price_diaries import notifications

    if not enabled:
        print("Desktop notifications are off. Set PD_DESKTOP_NOTIFICATIONS=true to turn them on.")
        return 1
    sent = await notifications.DesktopNotifications().send(
        "Test notification", "Notes about your prices will appear like this."
    )
    if not sent:
        print("Couldn't show a desktop notification. The log above says why.")
        return 1
    print("Sent a test notification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
