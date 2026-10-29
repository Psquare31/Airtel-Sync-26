"""Runs Smart KYC over every specimen applicant in data/kyc_documents.

usage: python -m scripts.kyc_batch [--ocr] [--out results.json]
--ocr forces the local OCR extractor (no Groq calls).
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from app.config import get_settings
from app.services import kyc, ocr
from app.services.llm import ModelRouter, set_router


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="", help="comma-separated applicant ids, e.g. K01,K02")
    args = ap.parse_args()
    only = {a.strip().upper() for a in args.only.split(",") if a.strip()}
    if args.ocr:
        router = ModelRouter()
        router.available = lambda: False  # type: ignore[method-assign]
        set_router(router)

    folder = get_settings().data_dir / "kyc_documents"
    applicants: dict[str, dict] = defaultdict(dict)
    for path in sorted(folder.glob("*.png")):
        m = re.match(r"(K\d+)_(.+)\.png", path.name)
        if not m:
            continue
        applicant, doc_type = m.groups()
        if only and applicant not in only:
            continue
        data = path.read_bytes()
        ext = ocr.extract(data, doc_type)
        ext["checks"] = [c.to_dict() for c in kyc.document_checks(doc_type, ext, data)]
        applicants[applicant][doc_type] = ext
        print(f"{path.name}: {ext.get('extractor')} {json.dumps(ext.get('fields'), ensure_ascii=False)}", file=sys.stderr)

    results = {}
    for applicant, docs in applicants.items():
        res = kyc.verify(docs)
        results[applicant] = res
        issues = [c["message"] for c in res["checks"] if c["status"] != "pass"]
        print(f"{applicant}: {res['outcome'].upper():9} {' | '.join(issues) or 'all checks passed'}")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
