# Usage

Installing, starting the app and the demo are in the README under "Run it".

## Commands

Run these from `backend/`.

- `uv run price-diaries check`: checks every product once, now
- `uv run price-diaries migrate`: creates or updates the database
- `uv run price-diaries notify test`: sends one test desktop notification
- `uv run price-diaries inspect <url>`: shows what each parsing strategy finds on a product page (`--browser` to render JavaScript, `--save page.html` to keep the HTML)

The demo has 36 products with half a year of made-up history, as they are on 1 December 2026, just after Efsane Cuma. Run `demo` once; to start over, delete `data/demo.db`.

To use the app without the dev server, run `npm run build` in `frontend/`. Then `serve` shows the UI on http://127.0.0.1:8000.

## Settings

Copy `backend/.env.example` to `backend/.env`. Every setting is described in that file, and all of them are optional.

## Notifications

A note is left when:

- the price is at or under your alert price
- there is a new lowest price, at least ₺1 and 1% below the last new-low note
- a sale is fake
- the same product is cheaper at another store
- the product is back in stock
- it's Sunday morning: the Sunday paper is ready (once a week; if the app didn't run that Sunday, at the next check)

Each note is sent once. A product's first check never sends one.

## Adding a store

- Add one `Store(...)` entry in `backend/src/price_diaries/parsers/sites.py`: name, domains, and when needed price selectors, whether it needs a browser, and the loyalty-card price labels
- Run `inspect` (above) on a product page to see what each parsing strategy finds
- Add tests in `backend/tests/test_parsers.py`

## Development

Setup:

```bash
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..
uvx pre-commit install
```

The pre-commit hooks lint and format the Python code and check commit messages.

Tests and lint, before opening a pull request:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && npm run lint && npm test && npm run build
```
