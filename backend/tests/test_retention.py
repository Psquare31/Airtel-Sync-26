from datetime import timedelta

from sqlmodel import select

from app.db import ConsentRecord, Journey, KycDocument, now, session
from app.services.retention import purge_expired, withdraw


def test_withdraw_kyc_erases_documents():
    with session() as s:
        s.add(ConsentRecord(journey_id="J1", notice_version="v", lang="en",
                            purposes={"kyc_verification": True, "service_activation": True, "marketing": True}))
        s.add(KycDocument(journey_id="J1", doc_type="gst_certificate", sha256="x", fields={}))
        s.commit()
    assert withdraw("J1", ["marketing"])["documents_erased"] == 0
    assert withdraw("J1", ["kyc_verification"])["documents_erased"] == 1
    with session() as s:
        rec = s.exec(select(ConsentRecord)).one()
        assert rec.purposes == {"kyc_verification": False, "service_activation": True, "marketing": False}


def test_purge_keeps_ordered_journeys(graph):
    old = now() - timedelta(days=200)
    with session() as s:
        s.add(Journey(id="JOLD", updated_at=old))
        s.add(Journey(id="JORD", updated_at=old, order_id="AB1"))
        s.add(KycDocument(journey_id="JOLD", doc_type="x", sha256="x", fields={}, purge_after=old))
        s.add(KycDocument(journey_id="JORD", doc_type="x", sha256="x", fields={}, purge_after=old))
        s.commit()
    assert purge_expired() == {"documents": 1, "journeys": 1}
    with session() as s:
        assert s.get(Journey, "JORD") and not s.get(Journey, "JOLD")
