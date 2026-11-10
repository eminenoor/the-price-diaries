from datetime import datetime, timedelta

from price_diaries.analysis import is_fake_sale, summarize

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
