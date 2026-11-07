"""KYC rules against field values transcribed from the specimen documents."""
from app.services.kyc import verify


def gst(gstin, legal, trade, constitution="Proprietorship", address=""):
    return {"fields": {"gstin": gstin, "legal_name": legal, "trade_name": trade, "constitution": constitution,
                       "address": address}, "detected_type": "gst_certificate", "checks": []}


def sig(name, role, biz, valid="2028-01-01"):
    return {"fields": {"name": name, "designation": role, "business_name": biz, "valid_till": valid},
            "detected_type": "signatory_id", "checks": []}


def bill(billed, address, date):
    return {"fields": {"billed_to": billed, "address": address, "bill_date": date},
            "detected_type": "address_proof", "checks": []}


def udyam(number, name):
    return {"fields": {"udyam_number": number, "enterprise_name": name},
            "detected_type": "udyam_certificate", "checks": []}


def failed(res):
    return {c["id"] for c in res["checks"] if c["status"] == "fail"}


K02_ADDR = "Shop/Unit 199, Station Road, Kolkata, West Bengal - 347550"


def test_clean_applicant_with_ocr_zero_verifies():  # K02
    res = verify({
        "gst_certificate": gst("19E0GXH4115Y1ZL", "Joseph Shah (Prop. Harmony Dental Care)", "Harmony Dental Care",
                               address=K02_ADDR),
        "udyam_certificate": udyam("UDYAM-WB-00-5053330", "Harmony Dental Care"),
        "signatory_id": sig("JosephShah", "Manager", "Harmony Dental Care"),
        "address_proof": bill("Harmony Dental Care", K02_ADDR, "2026-05-22"),
    })
    assert res["outcome"] == "verified", failed(res)


def test_cancelled_gstin_and_blank_udyam_blocked():  # K01
    addr = "Shop/Unit 1, Tech Park Road, Visakhapatnam, Andhra Pradesh - 118383"
    res = verify({
        "gst_certificate": gst("37IHKXV5167L1ZS", "Neha Kaur (Prop. Vindhya Tours & Travels)",
                               "Vindhya Tours & Travels", address=addr),
        "udyam_certificate": udyam("", "Vindhya Tours & Travels"),
        "signatory_id": sig("Neha Kaur", "Office admin", "Vindhya Tours & Travels"),
        "address_proof": bill("Vindhya Tours & Travels", addr, "2026-06-26"),
    })
    assert res["outcome"] == "blocked"
    assert {"gstin_status", "udyam_format"} <= failed(res)


def test_altered_gstin_fails_checksum():  # K06
    addr = "Shop/Unit 71, Market Yard, Jaipur, Rajasthan - 194057"
    res = verify({
        "gst_certificate": gst("08YKZXS8189L1Z0", "Pooja Shah (Prop. Saffron Unisex Salon)", "Saffron Unisex Salon",
                               address=addr),
        "signatory_id": sig("Pooja Shah", "Owner", "Saffron Unisex Salon"),
        "address_proof": bill("Saffron Unisex Salon", addr, "2026-06-11"),
    })
    assert "gstin_format" in failed(res)


def test_legal_name_mismatch_blocked():  # K07
    addr = "Shop/Unit 52, Transport Nagar, Delhi, Delhi - 334596"
    res = verify({
        "gst_certificate": gst("07CPCXN0398P1ZT", "Neha Banerjee (Prop. Shri Physio Clinic)",
                               "Neelgiri Physio Clinic", address=addr),
        "signatory_id": sig("Neha Banerjee", "Manager", "Neelgiri Physio Clinic"),
        "address_proof": bill("Neelgiri Physio Clinic", addr, "2026-07-05"),
    })
    assert res["outcome"] == "blocked" and "gst_legal_name" in failed(res)


def test_stale_address_proof_and_owner_of_company():  # K11
    addr = "Shop/Unit 188, Industrial Area Phase 2, Ludhiana, Punjab - 541498"
    res = verify({
        "gst_certificate": gst("03KGZXT1320R1ZZ", "Trinity Bake House Pvt Ltd", "Trinity Bake House Pvt Ltd",
                               "Private Limited Company", addr),
        "signatory_id": sig("Vikram Pillai", "Owner", "Trinity Bake House Pvt Ltd"),
        "address_proof": bill("Trinity Bake House Pvt Ltd", addr, "2025-10-31"),
    })
    assert res["outcome"] == "fixable"
    assert {"address_date", "signatory_role"} <= failed(res)


def test_missing_documents():
    res = verify({"signatory_id": sig("A", "Owner", "B")})
    assert "missing_gst_certificate" in failed(res)
    assert res["outcome"] != "verified"


def test_reader_busy_when_vision_down_and_local_ocr_off(monkeypatch):
    from app.config import get_settings
    from app.services import kyc, ocr

    monkeypatch.setattr(get_settings(), "local_ocr", False)
    data = (get_settings().data_dir / "kyc_documents" / "K02_signatory_id.png").read_bytes()
    ext = ocr.extract(data, "signatory_id")
    checks = kyc.document_checks("signatory_id", ext, data)
    assert ext["extractor"] == "unavailable" and checks[0].id == "reader_busy"


def test_busy_document_only_asks_for_retry():
    busy = {"fields": {}, "detected_type": None, "checks": [
        {"id": "reader_busy", "status": "fail", "message": "busy", "doc": "address_proof"}]}
    res = verify({
        "gst_certificate": gst("19EOGXH4115Y1ZL", "Joseph Shah (Prop. Harmony Dental Care)", "Harmony Dental Care",
                               address=K02_ADDR),
        "signatory_id": sig("Joseph Shah", "Owner", "Harmony Dental Care"),
        "udyam_certificate": udyam("UDYAM-WB-00-5053330", "Harmony Dental Care"),
        "address_proof": busy,
    })
    assert res["outcome"] == "fixable"
    assert {c["id"] for c in res["checks"] if c["status"] == "fail"} == {"reader_busy"}


def test_registered_business_must_upload_udyam():  # K05
    addr = "Shop/Unit 38, Civil Lines, Kochi, Kerala - 752083"
    res = verify({
        "gst_certificate": gst("32TZAXB5481U1Z1", "Balaji Realty LLP", "Balaji Realty LLP", "Limited Liability Partnership", addr),
        "signatory_id": sig("Anita Shah", "Partner", "Balaji Realty LLP"),
        "address_proof": bill("Balaji Realty LLP", addr, "2026-06-11"),
    })
    assert res["outcome"] == "fixable" and failed(res) == {"missing_udyam_certificate"}


def test_udyam_registration_lookup():
    from app.data.loader import get_dataset
    from app.services.kyc import _registered_udyam

    assert _registered_udyam(get_dataset().gstin["32TZAXB5481U1Z1"])["udyam_number"] == "UDYAM-KL-00-5521886"
    assert _registered_udyam(get_dataset().gstin["37IHKXV5167L1ZS"]) is None  # K01: no Udyam registration


def test_typed_udyam_of_another_business_is_flagged():  # K02's Udyam typed with a different GSTIN
    from app.data.loader import get_dataset

    rec = get_dataset().gstin["27XUIXG0767D1ZP"]
    res = verify({
        "gst_certificate": gst("27XUIXG0767D1ZP", rec["legal_name"], rec["trade_name"], rec["constitution"],
                               rec["principal_place_of_business"]),
        "signatory_id": sig("Owner", "Proprietor", rec["trade_name"]),
        "address_proof": bill(rec["trade_name"], rec["principal_place_of_business"], "2026-06-01"),
    }, {"udyam_number": "UDYAM-WB-00-5053330"})
    assert "udyam_typed_vs_gst" in failed(res) and res["outcome"] != "verified"


def test_udyam_certificate_of_another_business_blocks():
    res = verify({
        "gst_certificate": gst("19E0GXH4115Y1ZL", "Joseph Shah (Prop. Harmony Dental Care)", "Harmony Dental Care",
                               address=K02_ADDR),
        "udyam_certificate": udyam("UDYAM-KL-00-5521886", "Balaji Realty LLP"),
        "signatory_id": sig("JosephShah", "Manager", "Harmony Dental Care"),
        "address_proof": bill("Harmony Dental Care", K02_ADDR, "2026-05-22"),
    })
    assert "udyam_vs_gst" in failed(res) and res["outcome"] == "blocked"
