from app.services.kyc import repair_gstin
from app.services.validators import (gstin_checksum, legal_parts, mask, name_similarity, validate_gstin,
                                     validate_udyam)


def test_registry_gstins_pass_checksum():
    from app.data.loader import get_dataset

    assert all(not validate_gstin(g) for g in get_dataset().gstin)


def test_checksum_detects_altered_digit():
    assert not validate_gstin("08YKZXS5189L1ZO")
    assert any("check digit" in p for p in validate_gstin("08YKZXS8189L1ZO"))


def test_checksum_value():
    assert gstin_checksum("37IHKXV5167L1Z") == "S"


def test_pan_with_x_entity_is_accepted():
    assert not validate_gstin("37NBLXS1145E1ZU")


def test_bad_length_and_state():
    assert validate_gstin("123")
    assert any("state code" in p for p in validate_gstin("99NBLXS1145E1ZU"))


def test_repair_ocr_zero_for_o():
    fixed, changed = repair_gstin("19E0GXH4115Y1ZL")
    assert changed and fixed == "19EOGXH4115Y1ZL"
    assert repair_gstin("19E0GXH4115Y12L") == ("19EOGXH4115Y1ZL", True)  # Z read as 2
    fixed, _ = repair_gstin("08YKZXS8189L1Z0")  # a real alteration stays invalid
    assert validate_gstin(fixed)


def test_udyam_format():
    assert not validate_udyam("UDYAM-KR-00-0687054")
    assert validate_udyam("")
    assert validate_udyam("UDYAM-KL-0-12345")


def test_names_and_mask():
    assert legal_parts("Neha Kaur (Prop. Vindhya Tours & Travels)") == ("Neha Kaur", "Vindhya Tours & Travels")
    assert name_similarity("VindhyaTours&Travels", "Vindhya Tours & Travels") == 100
    assert name_similarity("Shri Physio Clinic", "Neelgiri Physio Clinic") < 85
    assert mask("37IHKXV5167L1ZS") == "37" + "•" * 10 + "1ZS"
