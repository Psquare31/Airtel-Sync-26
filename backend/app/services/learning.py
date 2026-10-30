"""The improvement loop: consented, redacted advisor turns become prompt examples
and test material; owner feedback flags the conversations that went wrong."""
from __future__ import annotations

import time
from collections import Counter
from datetime import timedelta

import yaml
from rapidfuzz import fuzz
from sqlmodel import select

from app.db import Feedback, LearnedTurn, audit, now, session
from app.services.llm import redact

RETENTION = timedelta(days=365)
_cache: dict[str, tuple[float, list[LearnedTurn]]] = {}
CACHE_S = 300


def turn_entry(text: str, before: dict, after: dict, model: str | None) -> dict | None:
    """What this message contributed: the slots it changed."""
    changed = {k: v for k, v in after.items() if v not in (None, [], "") and before.get(k) != v}
    if not changed:
        return None
    return {"text": redact(text)[:500], "updates": changed, "model": model}


def persist(journey_id: str, lang: str, segment: str | None, turns: list[dict]) -> int:
    flagged = has_negative_feedback(journey_id)
    with session() as s:
        for t in turns:
            s.add(LearnedTurn(journey_id=journey_id, lang=lang, user_text=t["text"], updates=t["updates"],
                              segment=segment, model=t.get("model"), flagged=flagged,
                              purge_after=now() + RETENTION))
        s.commit()
    _cache.clear()
    audit("system", "learning_turns_saved", journey_id, count=len(turns))
    return len(turns)


def has_negative_feedback(journey_id: str) -> bool:
    with session() as s:
        return s.exec(select(Feedback).where(Feedback.journey_id == journey_id, Feedback.rating < 0)).first() is not None


def record_feedback(journey_id: str, rating: int, reason: str | None, comment: str | None, stage: str = "quote") -> None:
    with session() as s:
        s.add(Feedback(journey_id=journey_id, stage=stage, rating=1 if rating > 0 else -1,
                       reason=(reason or None) and reason[:80], comment=(comment or None) and redact(comment)[:300]))
        if rating < 0:
            for t in s.exec(select(LearnedTurn).where(LearnedTurn.journey_id == journey_id)).all():
                t.flagged = True
                s.add(t)
        s.commit()
    _cache.clear()
    audit("owner", "feedback", journey_id, rating=rating, reason=reason)


def _pool(lang: str) -> list[LearnedTurn]:
    hit = _cache.get(lang)
    if hit and time.monotonic() - hit[0] < CACHE_S:
        return hit[1]
    with session() as s:
        rows = s.exec(select(LearnedTurn).where(LearnedTurn.lang == lang, LearnedTurn.flagged == False)  # noqa: E712
                      .order_by(LearnedTurn.created_at.desc()).limit(300)).all()
    _cache[lang] = (time.monotonic(), rows)
    return rows


def examples(lang: str, text: str, k: int = 2, min_score: int = 45) -> list[dict]:
    """Most similar past turns in the same language, as few-shot examples."""
    query = redact(text)
    scored = sorted(((fuzz.token_set_ratio(query, r.user_text), r) for r in _pool(lang)), key=lambda x: -x[0])
    out, seen = [], set()
    for score, r in scored:
        if score < min_score or r.user_text in seen:
            continue
        seen.add(r.user_text)
        out.append({"text": r.user_text, "updates": r.updates})
        if len(out) == k:
            break
    return out


def stats() -> dict:
    with session() as s:
        fb = s.exec(select(Feedback)).all()
        turns = s.exec(select(LearnedTurn)).all()
    flagged_ids = sorted({f.journey_id for f in fb if f.rating < 0})
    by_journey: dict[str, list[LearnedTurn]] = {}
    for t in turns:
        by_journey.setdefault(t.journey_id, []).append(t)
    flagged = []
    for jid in flagged_ids[-20:]:
        reasons = [f.reason for f in fb if f.journey_id == jid and f.rating < 0 and f.reason]
        comments = [f.comment for f in fb if f.journey_id == jid and f.comment]
        flagged.append({"journey_id": jid, "reasons": reasons, "comments": comments,
                        "turns": [{"text": t.user_text, "updates": t.updates} for t in by_journey.get(jid, [])],
                        "consented": jid in by_journey})
    return {
        "feedback_up": sum(1 for f in fb if f.rating > 0),
        "feedback_down": sum(1 for f in fb if f.rating < 0),
        "top_reasons": Counter(f.reason for f in fb if f.rating < 0 and f.reason).most_common(5),
        "learned_turns": len(turns),
        "learned_by_lang": dict(Counter(t.lang for t in turns)),
        "flagged": list(reversed(flagged)),
    }


def export_scenarios() -> str:
    """Thumbs-down conversations as draft advisor test cases for a developer to correct."""
    items = []
    for f in stats()["flagged"]:
        if not f["turns"]:
            continue
        last = {}
        for t in f["turns"]:
            last.update(t["updates"])
        items.append({
            "name": f"learned {f['journey_id']}: {', '.join(f['reasons']) or 'thumbs down'}",
            "status": "needs_review",
            "messages": [t["text"] for t in f["turns"]],
            "observed": {k: last[k] for k in ("segment", "employees", "sites", "city", "has_gstin",
                                              "current_internet", "needs") if k in last},
            "expect": {},
        })
    header = ("# Draft scenarios from conversations owners rated thumbs-down.\n"
              "# Fill in `expect`, remove `status: needs_review`, and move them to advisor_scenarios.yaml.\n")
    return header + yaml.safe_dump(items, allow_unicode=True, sort_keys=False)
