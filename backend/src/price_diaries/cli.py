"""Command line: `price-diaries serve | check | migrate | demo`."""

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
    sub.add_parser("check", help="check all prices once, now")
    sub.add_parser("migrate", help="create or update the database schema")
    demo = sub.add_parser("demo", help="add fake products with 90 days of history")
    demo.add_argument("--days", type=int, default=90)
    inspect = sub.add_parser("inspect", help="show what the tracker finds on a product page")
    inspect.add_argument("url")
    inspect.add_argument("--browser", action="store_true", help="also load the page in Chromium")
    inspect.add_argument("--save", metavar="FILE", help="save the downloaded HTML to a file")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = get_settings()

    if args.command == "serve":
        import uvicorn

        # 127.0.0.1 only: the app has no login, so it must not be reachable from the network.
        uvicorn.run("price_diaries.main:app", host="127.0.0.1", port=args.port, reload=args.reload)
        return 0

    if args.command == "inspect":
        return asyncio.run(_inspect(args.url, args.browser, args.save))

    migrate.upgrade(settings.database_url)
    if args.command == "migrate":
        print("Database is up to date.")
    elif args.command == "check":
        from price_diaries.scheduler import run_daily_check

        asyncio.run(run_daily_check(Database(settings.database_url), settings))
    elif args.command == "demo":
        from price_diaries.demo import seed_demo

        with Database(settings.database_url).session() as session:
            count = seed_demo(session, days=args.days)
        print(f"Added {count} demo products.")
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
