import pytest

from app.services.cities import find_in_text, resolve, tier_for
from app.services.profile import Profile


@pytest.mark.parametrize("name,city", [
    ("कोलकाता", "Kolkata"), ("கொல்கத்தா", "Kolkata"), ("কলকাতা", "Kolkata"), ("Kolkatta", "Kolkata"),
    ("Calcutta", "Kolkata"), ("मुंबई", "Mumbai"), ("मुम्बई", "Mumbai"), ("Bombay", "Mumbai"),
    ("रामपुर", None), ("पुणे", "Pune"), ("బెంగళూరు", "Bengaluru"), ("ಬೆಂಗಳೂರು", "Bengaluru"), ("Banglore", "Bengaluru"),
    ("சென்னை", "Chennai"), ("హైదరాబాద్", "Hyderabad"), ("અમદાવાદ", "Ahmedabad"), ("ਲੁਧਿਆਣਾ", "Ludhiana"),
    ("ଭୁବନେଶ୍ୱର", "Bhubaneswar"), ("കൊച്ചി", "Kochi"), ("विशाखापत्तनम", "Visakhapatnam"),
])
def test_resolves_any_script_or_spelling(name, city):
    hit = resolve(name)
    assert (hit[0] if hit else None) == city


def test_ordinary_words_are_not_cities_without_a_cue():
    assert find_in_text("we need पानी and an open shop") is None
    assert find_in_text("मेरा क्लिनिक कोलकाता में है") == "Kolkata"
    assert find_in_text("my shop is in Banglore") == "Bengaluru"
    assert find_in_text("சென்னையில் கடை") == "Chennai"


def test_unknown_cities_still_count():
    assert tier_for("Agartala") == 2  # not in our lists: served tier by default
    assert tier_for("Agartala", model_tier=2) == 2
    assert tier_for("Rampur", context="small village") == 3
    p = Profile().merge({"city": "रामपुर"})
    assert p.city == "रामपुर" and p.city_tier == 2 and "city" not in p.missing()
    p = Profile().merge({"city": "Kolkatta", "city_tier": 2})
    assert p.city == "Kolkata" and p.city_tier == 1  # known list beats the model


def test_unknown_city_is_never_tier_one():
    assert Profile().merge({"city": "Tirunelveli", "city_tier": 1}).city_tier == 2
    assert Profile().merge({"city": "Tirunelveli", "city_tier": 3}).city_tier == 3
