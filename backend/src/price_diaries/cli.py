"""Command line: `price-diaries serve | check | migrate | demo`."""

from __future__ import annotations

import argparse
import asyncio
import logging

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


if __name__ == "__main__":
    raise SystemExit(main())
