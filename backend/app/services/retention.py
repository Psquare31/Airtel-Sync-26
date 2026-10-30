"""Retention jobs and consent withdrawal (see docs/privacy-note.md)."""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlmodel import select

from app.db import ConsentRecord, Journey, KycDocument, LearnedTurn, audit, now, session

log = logging.getLogger("retention")

ABANDONED_AFTER = timedelta(days=90)


def _delete_checkpoint(journey_id: str) -> None:
    from app.graph.journey import get_graph

    saver = get_graph().checkpointer
    try:
        saver.delete_thread(journey_id)
    except Exception as err:  # noqa: BLE001 - best effort, older savers lack it
        log.warning("checkpoint delete failed for %s: %s", journey_id, err)


def purge_expired() -> dict:
    """Drops KYC fields past purge_after (unless ordered) and abandoned journeys."""
    t = now()
    removed_docs = removed_journeys = 0
    with session() as s:
        ordered = {j.id for j in s.exec(select(Journey).where(Journey.order_id.is_not(None))).all()}
        for doc in s.exec(select(KycDocument)).all():
            purge_after = doc.purge_after
            if purge_after and purge_after.tzinfo is None:
                purge_after = purge_after.replace(tzinfo=t.tzinfo)
            if purge_after and purge_after < t and doc.journey_id not in ordered:
                s.delete(doc)
                removed_docs += 1
        for turn in s.exec(select(LearnedTurn)).all():
            purge_after = turn.purge_after
            if purge_after and purge_after.tzinfo is None:
                purge_after = purge_after.replace(tzinfo=t.tzinfo)
            if purge_after and purge_after < t:
                s.delete(turn)
        stale = []
        for j in s.exec(select(Journey).where(Journey.order_id.is_(None))).all():
            updated = j.updated_at if j.updated_at.tzinfo else j.updated_at.replace(tzinfo=t.tzinfo)
            if updated < t - ABANDONED_AFTER:
                stale.append(j.id)
                s.delete(j)
        removed_journeys = len(stale)
        s.commit()
    for jid in stale:
        _delete_checkpoint(jid)
    if removed_docs or removed_journeys:
        audit("system", "retention_purge", None, documents=removed_docs, journeys=removed_journeys)
    return {"documents": removed_docs, "journeys": removed_journeys}


def withdraw(journey_id: str, purposes: list[str]) -> dict:
    """Marks consent withdrawn; withdrawing KYC consent erases extracted KYC fields."""
    with session() as s:
        records = s.exec(select(ConsentRecord).where(ConsentRecord.journey_id == journey_id,
                                                     ConsentRecord.withdrawn_at.is_(None))).all()
        if not records:
            return {"withdrawn": [], "documents_erased": 0}
        erased = 0
        for rec in records:
            updated = dict(rec.purposes)
            for p in purposes:
                if p in updated:
                    updated[p] = False
            rec.purposes = updated
            if not any(updated.values()):
                rec.withdrawn_at = now()
            s.add(rec)
        if "improvement" in purposes:
            for turn in s.exec(select(LearnedTurn).where(LearnedTurn.journey_id == journey_id)).all():
                s.delete(turn)
        if "kyc_verification" in purposes:
            for doc in s.exec(select(KycDocument).where(KycDocument.journey_id == journey_id)).all():
                s.delete(doc)
                erased += 1
        s.commit()
    audit("owner", "consent_withdrawn", journey_id, purposes=purposes, documents_erased=erased)
    return {"withdrawn": purposes, "documents_erased": erased}
