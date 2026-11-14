from datetime import datetime, timedelta

from price_diaries.analysis import (
    MIN_SAVING,
    Offer,
    UnitPrice,
    cheaper_elsewhere,
    is_fake_sale,
    pick_display_name,
    rank_offers,
    saving,
    summarize,
    unit_price,
)

START = datetime(2026, 1, 1, 9)


def series(*prices):
    return [(START + timedelta(days=i), p) for i, p in enumerate(prices)]


def test_summary_basic_numbers():
    s = summarize(series(300, 280, 320, 290))
    assert s.current == 290
    assert s.previous == 320
    assert s.lowest == 280
    assert s.lowest_at == START + timedelta(days=1)
    assert s.highest == 320
    assert s.change_pct == -9.38
    assert s.is_all_time_low is False


def test_all_time_low():
    assert summarize(series(300, 290, 250)).is_all_time_low is True


def test_empty_history():
    assert summarize([]) is None


def test_fake_sale_raise_then_discount_back_to_normal():
    # Normal 300 -> raised to 360 -> "sale" back to 300
    assert is_fake_sale(series(300, 300, 360, 360, 300)) is True


def test_real_sale_is_not_flagged():
    # Raised to 360, then dropped well below the old price
    assert is_fake_sale(series(300, 300, 360, 250)) is False


def test_plain_drop_is_not_flagged():
    assert is_fake_sale(series(300, 300, 300, 270)) is False


def test_still_at_peak_is_not_flagged():
    assert is_fake_sale(series(300, 300, 360)) is False


def test_old_raise_outside_window_is_ignored():
    history = [(START, 300.0), (START + timedelta(days=1), 360.0)]
    history += [(START + timedelta(days=30 + i), 300.0) for i in range(3)]
    assert is_fake_sale(history, window_days=14) is False


def test_anomaly_on_stable_product():
    from price_diaries.analysis import price_anomalies

    history = series(300, 300, 301, 300, 300, 390, 300, 300)
    [spike] = price_anomalies(history)  # the drop back to 300 is good news, not flagged
    assert spike.price == 390 and spike.change_pct == 30.0


def test_noisy_product_needs_bigger_jump():
    from price_diaries.analysis import price_anomalies

    noisy = series(300, 320, 290, 315, 295, 325, 300, 330)
    assert price_anomalies(noisy) == []


def test_too_little_history():
    from price_diaries.analysis import price_anomalies

    assert price_anomalies(series(300, 400)) == []


def test_unit_price_per_10_ml():
    # ₺379,50 for 150 ml -> ₺25,30 per 10 ml
    assert unit_price(379.5, 150, "ml") == UnitPrice(25.3, 10, "ml")


def test_unit_price_per_100_g():
    # ₺62 for 500 g -> ₺12,40 per 100 g
    assert unit_price(62, 500, "g") == UnitPrice(12.4, 100, "g")


def test_unit_price_per_piece():
    assert unit_price(499, 60, "pcs") == UnitPrice(8.32, 1, "pcs")


def test_unit_price_of_a_big_pack_is_rounded_to_kurus():
    # ₺253 for 1 L -> ₺2,53 per 10 ml
    assert unit_price(253, 1000, "ml") == UnitPrice(2.53, 10, "ml")
    assert unit_price(100, 3000, "ml") == UnitPrice(0.33, 10, "ml")


def test_bigger_pack_with_same_price_per_ml_compares_equal():
    assert unit_price(150, 250, "ml") == unit_price(600, 1000, "ml")


def test_no_unit_price_without_a_usable_size():
    assert unit_price(100, 0, "ml") is None
    assert unit_price(100, -5, "g") is None
    assert unit_price(100, 50, "oz") is None


def test_unit_price_rounds_half_a_kurus_up():
    # 289,90 / 200 ml * 10 = 14,495
    assert unit_price(289.9, 200, "ml") == UnitPrice(14.5, 10, "ml")


TODAY = START + timedelta(days=10)


def offer(product_id, price, amount=None, unit=None, checked_at=TODAY, in_stock=True):
    return Offer(product_id, price, checked_at, in_stock, amount, unit)


def test_saving_for_the_same_pack():
    assert saving(offer(1, 378.89, 150, "ml"), offer(2, 340, 150, "ml")) == 38.89


def test_saving_is_negative_when_it_costs_more_there():
    assert saving(offer(1, 340), offer(2, 378.89)) == -38.89


def test_saving_scales_a_different_size_to_this_pack():
    # 1,5 L for ₺165 is ₺275 for 2,5 L, so ₺14 less than ₺289.
    assert saving(offer(1, 289, 2500, "ml"), offer(2, 165, 1500, "ml")) == 14
    # The other way round, the big bottle is dearer for 1,5 L: 289 / 2500 * 1500 = 173,40.
    assert saving(offer(2, 165, 1500, "ml"), offer(1, 289, 2500, "ml")) == -8.4


def test_saving_assumes_the_same_pack_when_a_size_is_missing():
    assert saving(offer(1, 300, 150, "ml"), offer(2, 280)) == 20


def test_no_saving_between_different_units():
    assert saving(offer(1, 300, 500, "g"), offer(2, 280, 500, "ml")) is None


def test_rank_by_unit_price_when_every_size_is_known():
    big = offer(1, 289, 2500, "ml")  # 11,56 per 100 ml
    small = offer(2, 165, 1500, "ml")  # 11,00 per 100 ml
    assert rank_offers([big, small]) == [small, big]


def test_rank_by_price_when_a_size_is_missing():
    big = offer(1, 289, 2500, "ml")
    unknown = offer(2, 165)
    assert rank_offers([big, unknown]) == [unknown, big]


def test_rank_ties_go_to_the_latest_check():
    old = offer(1, 100, checked_at=TODAY - timedelta(days=1))
    new = offer(2, 100)
    assert rank_offers([old, new]) == [new, old]


def test_cheaper_elsewhere_picks_the_biggest_saving():
    here = offer(1, 400)
    best = offer(3, 340)
    assert cheaper_elsewhere(here, [offer(2, 380), best], TODAY.date()) == (best, 60)


def test_cheaper_elsewhere_only_counts_todays_checks_in_stock():
    here = offer(1, 400)
    stale = offer(2, 300, checked_at=TODAY - timedelta(days=1))
    sold_out = offer(3, 300, in_stock=False)
    assert cheaper_elsewhere(here, [stale, sold_out], TODAY.date()) is None


def test_cheaper_elsewhere_ignores_tiny_savings_and_itself():
    here = offer(1, 400)
    tiny = offer(2, 400 - MIN_SAVING / 2)
    assert cheaper_elsewhere(here, [here, tiny], TODAY.date()) is None


def test_cheaper_elsewhere_skips_what_costs_more():
    assert cheaper_elsewhere(offer(1, 300), [offer(2, 320)], TODAY.date()) is None


def test_display_name_with_the_most_words_wins():
    names = ["AHA BHA PHA Miracle Toner", "Some By Mi AHA BHA PHA Miracle Toner 150 ml"]
    assert pick_display_name(names) == names[1]


def test_display_name_counts_distinct_words_then_length():
    # Repeated words and punctuation don't make a name more complete.
    assert pick_display_name(["Toner toner, TONER 150 ml", "Calming Toner 150 ml"]) == (
        "Calming Toner 150 ml"
    )
    assert pick_display_name(["Rice Foam 150 ml", "Rice Foams 150 ml"]) == "Rice Foams 150 ml"


def test_display_name_ties_go_to_the_first():
    assert pick_display_name(["Serum 30 ml", "Serum 30 mL"]) == "Serum 30 ml"
