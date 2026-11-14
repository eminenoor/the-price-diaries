import pytest

from price_diaries.parsers import Size, parse_size, with_size


@pytest.mark.parametrize(
    ("text", "amount", "unit"),
    [
        # Volumes, normalised to ml
        ("Tonik 150 ml", 150, "ml"),
        ("Tonik 150ml", 150, "ml"),
        ("TONİK 150 ML", 150, "ml"),
        ("Zeytinyağı 1 L", 1000, "ml"),
        ("Zeytinyağı 1 lt", 1000, "ml"),
        ("Şampuan 1,5 L", 1500, "ml"),  # Turkish decimal comma
        ("Laundry Liquid 2.5 l", 2500, "ml"),  # English decimal point
        ("Su 0,75 litre", 750, "ml"),
        ("Water 1 liter", 1000, "ml"),
        ("Parfüm 5 cl", 50, "ml"),
        ("Deterjan 1.000 ml", 1000, "ml"),  # Turkish thousands
        # Weights, normalised to g
        ("Kahve 500 g", 500, "g"),
        ("Kahve 500 gr", 500, "g"),
        ("Coffee 250 gram", 250, "g"),
        ("Pirinç 1 kg", 1000, "g"),
        ("Pirinç 2,5 kg", 2500, "g"),
        ("Rice 1.5kg", 1500, "g"),
        # Pieces
        ("Bulaşık Tableti 60 adet", 60, "pcs"),
        ("Dishwasher Tablets 60 pcs", 60, "pcs"),
        ("Vitamin D3 1000 IU, 90 tablets", 90, "pcs"),
        ("Omega 3 60 Kapsül", 60, "pcs"),
        ("Magnesium 120 caps", 120, "pcs"),
        # Multipacks
        ("Duş Jeli 2 x 250 ml", 500, "ml"),
        ("Shower Gel 3x400ml", 1200, "ml"),
        ("Islak Mendil 3 × 72 adet", 216, "pcs"),
    ],
)
def test_reads_size(text, amount, unit):
    assert parse_size(text) == Size(amount, unit)


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "Niacinamide 10% Serum",
        "SPF50 Sunscreen",  # a number glued to a word isn't a size
        "Vitamin C 1000 mg",  # milligrams are a dose, not the pack size
        "Lip Balm 1 Lip",  # "L" only counts on its own
        "100 gece kremi",  # "g" followed by more letters
        "Krem 0 ml",
    ],
)
def test_no_size(text):
    assert parse_size(text) is None


def test_takes_the_first_size():
    assert parse_size("Şampuan 400 ml + Saç Kremi 200 ml") == Size(400, "ml")


def test_skips_a_dose_before_the_pack_size():
    assert parse_size("Omega-3 1000 mg 60 kapsül") == Size(60, "pcs")


def test_with_size_swaps_in_this_stores_size():
    assert with_size("Laundry Liquid 2.5 l", Size(1500, "ml"), "Laundry Liquid 1.5 l") == (
        "Laundry Liquid 1.5 l"
    )


def test_with_size_writes_the_size_when_the_store_name_has_none():
    assert with_size("Deterjan 2,5 L", Size(1500, "ml")) == "Deterjan 1.5 l"
    assert with_size("Krem 50 ml", Size(30, "ml")) == "Krem 30 ml"
    assert with_size("Tablet 60 adet", Size(30, "pcs")) == "Tablet 30 pcs"


def test_with_size_leaves_matching_or_sizeless_names_alone():
    assert with_size("Tonik 150 ml", Size(150, "ml"), "Toner 150ML") == "Tonik 150 ml"
    assert with_size("My toner", Size(150, "ml")) == "My toner"
    assert with_size("Tonik 150 ml", None) == "Tonik 150 ml"
