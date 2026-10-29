from app.data.loader import get_dataset
from app.services.pricing import price_quote, unit_price
from app.services.profile import Profile
from app.services.rules_engine import recommend


def _rec(**kw):
    p = Profile(**kw).merge({})
    return p, recommend(p)


def selected(rec):
    return {l.product_id for l in rec.lines if l.selected}


def test_micro_without_gstin_locks_gst_products():
    _, rec = _rec(business_type="Kirana store", employees=2, sites=1, city_tier=2, has_gstin=False,
                  needs=["whatsapp", "pos_billing"])
    assert rec.segment == "micro"
    assert {"P01", "P07", "P19"} <= selected(rec)
    wa = next(l for l in rec.lines if l.product_id == "P15")
    assert wa.locked and not wa.selected and "GSTIN" in wa.lock_reason
    assert any("GSTIN" in n for n in rec.notes)


def test_every_selected_product_is_eligible_and_has_its_dependency():
    ds = get_dataset()
    profiles = [
        dict(business_type="Dental clinic", employees=8, sites=1, city_tier=1, has_gstin=True),
        dict(business_type="Restaurant chain", employees=40, sites=5, city_tier=2, has_gstin=True, needs=["cctv"]),
        dict(business_type="Textile unit", employees=30, sites=1, city_tier=2, has_gstin=True, needs=["iot_machines"]),
        dict(business_type="Salon", employees=3, sites=1, city_tier=2, has_gstin=False, needs=["cctv", "guest_wifi"]),
        dict(business_type="CA firm", employees=12, sites=1, city_tier=2, has_gstin=False),
    ]
    for kw in profiles:
        p, rec = _rec(**kw)
        chosen = selected(rec)
        for pid in chosen:
            prod = ds.products[pid]
            assert (p.city_tier or 2) in prod.city_tiers
            assert (p.employees or 1) >= prod.min_employees and (p.sites or 1) >= prod.min_sites
            assert not (prod.requires_gstin and not p.has_gstin), (kw, pid)
            if prod.requires_one_of:
                assert chosen & set(prod.requires_one_of), (kw, pid)


def test_multisite_gets_failover_and_sdwan_per_site():
    _, rec = _rec(business_type="Pharmacy chain", employees=30, sites=4, city_tier=1, has_gstin=True)
    lines = {l.product_id: l for l in rec.lines}
    assert rec.segment == "multi"
    assert lines["P09"].selected and lines["P09"].qty == 4
    assert lines["P10"].selected


def test_sdwan_locked_below_three_sites():
    _, rec = _rec(business_type="Bakery chain", employees=12, sites=2, city_tier=1, has_gstin=True,
                  needs=["central_mgmt"])
    assert next(l for l in rec.lines if l.product_id == "P10").locked


def test_manufacturer_gets_leased_line_only_with_gstin():
    _, rec = _rec(business_type="Auto-parts unit", employees=30, sites=1, city_tier=2, has_gstin=True)
    assert "P05" in selected(rec)
    _, rec = _rec(business_type="Auto-parts unit", employees=30, sites=1, city_tier=2, has_gstin=False)
    assert not selected(rec) & {"P05", "P06"}


def test_no_fibre_uses_airfiber():
    _, rec = _rec(business_type="Salon", employees=2, sites=1, city_tier=2, has_gstin=False, fibre_available=False)
    assert "P04" in selected(rec) and "P01" not in selected(rec)


def test_tier3_hands_off():
    _, rec = _rec(business_type="Kirana", employees=2, sites=1, city_tier=3, has_gstin=False)
    assert not rec.eligible and rec.handoff_reason == "city_not_served"


def test_budget_trims_optional_items():
    p, rec = _rec(business_type="Salon", employees=3, sites=1, city_tier=2, has_gstin=True,
                  needs=["cctv", "guest_wifi", "pos_billing"], budget_monthly=2000)
    assert price_quote(rec, p)["monthly_total"] <= 2000
    assert {"P01", "P07"} <= selected(rec)


def test_price_falls_with_longer_contract():
    p = get_dataset().products["P02"]
    assert unit_price(p, 24) < unit_price(p, 12) <= p.price_max
    assert unit_price(p, 24) >= p.price_min


def test_toggle_on_addon_updates_total_and_gst():
    p, rec = _rec(business_type="Salon", employees=3, sites=1, city_tier=2, has_gstin=False, needs=["cctv"])
    quote = price_quote(rec, p, toggles={"P22": True})
    assert next(i for i in quote["items"] if i["product_id"] == "P22")["selected"]
    total = sum(i["monthly"] for i in quote["items"] if i["selected"])
    assert quote["monthly_total"] == total
    assert quote["monthly_with_gst"] == total + round(total * 0.18)


def test_locked_items_cannot_be_toggled_on():
    p, rec = _rec(business_type="Kirana", employees=2, sites=1, city_tier=2, has_gstin=False, needs=["whatsapp"])
    quote = price_quote(rec, p, toggles={"P15": True})
    assert not next(i for i in quote["items"] if i["product_id"] == "P15")["selected"]


def test_core_items_cannot_be_toggled_off():
    p, rec = _rec(business_type="Kirana", employees=2, sites=1, city_tier=2, has_gstin=False)
    quote = price_quote(rec, p, toggles={"P01": False})
    assert next(i for i in quote["items"] if i["product_id"] == "P01")["selected"]


def test_setup_emi():
    p, rec = _rec(business_type="Kirana", employees=2, sites=1, city_tier=2, has_gstin=False, needs=["pos_billing"])
    q = price_quote(rec, p, setup_emi=True)
    assert q["setup_total"] == 2500 and q["setup_emi_monthly"] == 417
