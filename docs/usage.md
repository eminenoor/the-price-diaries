# Usage

## Commands

Run these from `backend/`.

- `uv run price-diaries serve`: runs the API, the daily check and the built UI on http://127.0.0.1:8000
- `uv run price-diaries check`: checks every product once, now
- `uv run price-diaries migrate`: creates or updates the database
- `uv run price-diaries demo`: adds demo products with fake history
- `uv run price-diaries notify test`: sends one test desktop notification
- `uv run price-diaries inspect <url>`: shows what each parsing strategy finds on a product page (`--browser` to render JavaScript, `--save page.html` to keep the HTML)
- `uv run pytest`: backend tests
- `npm test` (from `frontend/`): frontend tests
- `npm run build` (from `frontend/`): builds the UI that `serve` shows

## Settings

Copy `backend/.env.example` to `backend/.env`. All settings are optional.

- `PD_DATABASE_URL`: database location (default `sqlite:///./data/prices.db`)
- `PD_CHECK_HOUR`, `PD_CHECK_MINUTE`: daily check time (default 09:17)
- `PD_MIN_DELAY`, `PD_MAX_DELAY`: seconds between two pages of the same store (default 3 to 7)
- `PD_BROWSER_FALLBACK`: use a headless browser when the price isn't in the page HTML (default `true`)
- `PD_USE_MEMBER_PRICES`: track the loyalty-card price when a store shows one (default `true`)
- `PD_DESKTOP_NOTIFICATIONS`: show notes as desktop notifications (default `true`)

## Notifications

A note is left when:

- the price is at or under your alert price
- there is a new lowest price, at least ₺1 and 1% below the last new-low note
- a sale is fake
- the same product is cheaper at another store
- the product is back in stock

Each note is sent once. A product's first check never sends one.

## Adding a store

- Add one `Store(...)` entry in `backend/src/price_diaries/parsers/sites.py`: name, domains, and when needed price selectors, whether it needs a browser, and the loyalty-card price labels
- Run `uv run price-diaries inspect <url>` on a product page to see what each parsing strategy finds
- Add tests in `backend/tests/test_parsers.py`

## Development

Setup:

```bash
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..
uvx pre-commit install --hook-type pre-commit --hook-type commit-msg
```

The pre-commit hooks format Python code and check commit messages.

Tests and lint, before opening a pull request:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && npm run lint && npm test && npm run build
```
