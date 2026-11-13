from datetime import datetime, timedelta

from price_diaries.analysis import UnitPrice, is_fake_sale, summarize, unit_price

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
