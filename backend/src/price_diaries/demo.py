"""Fill the database with realistic fake price history.

For developing the UI and taking README screenshots, so real scraped data
never needs to be published.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from price_diaries.db import PricePoint, Product

DEMO_PRODUCTS = [
    ("Hyaluronic Acid Serum 30 ml", "gratis", "Serum", 289.0),
    ("SPF 50+ Fluid Sunscreen 50 ml", "watsons", "Sun care", 349.0),
    ("Gentle Foaming Cleanser 150 ml", "rossmann", "Cleanser", 159.0),
    ("Niacinamide 10% Toner 200 ml", "trendyol", "Toner", 210.0),
    ("Ceramide Barrier Cream 50 ml", "sephora", "Moisturizer", 645.0),
    ("Retinol 0.3% Night Serum", "eveshop", "Serum", 399.0),
    ("Micellar Water 400 ml", "amazon", "Cleanser", 189.0),
]


def seed_demo(session: Session, days: int = 90, seed: int = 7) -> int:
    rng = random.Random(seed)
    start = datetime.now().replace(hour=9, minute=17, second=0, microsecond=0)
    start -= timedelta(days=days)

    for i, (name, store, category, base) in enumerate(DEMO_PRODUCTS):
        product = Product(
            url=f"https://demo.invalid/{store}/{i}",
            name=name,
            store=store,
            category=category,
            target_price=round(base * 0.85),
        )
        session.add(product)
        session.flush()

        price, trick_until = base, -1
        for day in range(days + 1):
            roll = rng.random()
            if day == trick_until:  # the "sale" after an artificial raise
                price = base
            elif roll < 0.025:  # raise now, "discount" a few days later
                price = round(base * rng.uniform(1.15, 1.30), 2)
                trick_until = day + rng.randint(2, 5)
            elif roll < 0.06:  # a real sale
                price = round(base * rng.uniform(0.75, 0.92), 2)
            elif roll < 0.20 and trick_until < day:
                price = base
            session.add(
                PricePoint(
                    product_id=product.id,
                    price=price,
                    currency="TRY",
                    in_stock=rng.random() > 0.02,
                    checked_at=start + timedelta(days=day),
                )
            )
    session.commit()
    return len(DEMO_PRODUCTS)
