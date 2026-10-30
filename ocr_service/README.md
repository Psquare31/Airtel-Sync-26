---
title: Udyam Digital OCR
emoji: 📄
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Udyam Digital document reader

The OCR service behind Smart KYC in the Udyam Digital prototype (YTL Hackathon 2026, Track A).
It reads GST/Udyam certificates, signatory IDs and utility bills with our own OCR pipeline,
so document images are never sent to an LLM provider.

- `POST /extract` (multipart: `doc_type`, `file`; header `X-OCR-Key`) returns the extracted fields.
- `GET /health` is for uptime pings.

Images are processed in memory only. Nothing is stored or logged. All documents in the
prototype are synthetic specimens.
