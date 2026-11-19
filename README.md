# The Price Diaries

I kept losing track of skincare prices. A serum would go up one week and come back "on sale" the next, at the same price as before. So I built this: it checks the products I follow every morning, keeps every price, and tells me when a sale isn't real.

![The Price Diaries at night](docs/screenshots/home.png)

| Product detail | The Sunday paper | On a phone |
| --- | --- | --- |
| ![Product page: a lit window, the price on mustard paper, the same toner at two other stores and a chart on torn paper](docs/screenshots/detail.png) | ![The Sunday paper for the week of Efsane Cuma: drops, new lows, fake sales caught, a cheaper store, price rises and failed checks on one printed page](docs/screenshots/paper.png) | ![Quiet mode on a phone: a daylight poster with red pencil circles around good deals](docs/screenshots/mobile.png) |

It runs on my own computer, and nothing is sent anywhere. The screenshots use demo data.

## What it does

- Checks Gratis, Trendyol, Amazon, Watsons, Rossmann, Eve Shop and Sephora once a day
- Flags fake sales, where a price goes up and then "drops" back to where it was
- Flags unusual price jumps using the modified z-score on daily price changes, so a product that changes price often needs a bigger jump
- Tracks loyalty-card prices, like Gratis Özel Fiyat
- Compares the same product across stores per ml or gram
- Says when each product has usually been cheapest, from its own history, and only if waiting for that time would have paid off in the past
- Leaves a note in the app and on the desktop when something changes
- Puts each week on one printable page every Sunday: drops, new lows, fake sales, cheaper stores, price rises and failed checks

Sephora blocks automated checks, and the app doesn't try to get around that.

## How it works

```mermaid
flowchart LR
    UI["React dashboard<br/>(Vite, TanStack Query)"] -- REST --> API["FastAPI"]
    API --> DB[("SQLite<br/>SQLAlchemy + Alembic")]
    Scheduler["APScheduler<br/>every morning"] --> Checker
    API -- check now --> Checker["Checker"]
    Checker --> Fetcher["Fetcher<br/>httpx, Playwright fallback"]
    Fetcher --> Stores(("Store websites"))
    Checker --> Parsers["Store parsers<br/>JSON-LD, meta tags, CSS"]
    Checker --> DB
    API --> Analysis["Analysis<br/>fake sales, anomalies"]
```

Details in [docs/how-it-works.md](docs/how-it-works.md).

## Run it

You need [uv](https://docs.astral.sh/uv/) and Node.js 22+.

```
cd backend
uv sync
uv run playwright install chromium
uv run price-diaries serve

cd ../frontend
npm install
npm run dev                   # http://127.0.0.1:5173
```

To try it with demo data first, run `uv run price-diaries demo` and then `uv run price-diaries serve --demo`. The demo has its own database (`data/demo.db`), so it never touches your real prices.

More commands and settings are in [docs/usage.md](docs/usage.md).

Built with Python (FastAPI, SQLAlchemy, Playwright) and React with TypeScript.

MIT license
