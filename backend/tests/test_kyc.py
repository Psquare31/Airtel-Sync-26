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
