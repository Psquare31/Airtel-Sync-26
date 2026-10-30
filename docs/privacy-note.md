# Data privacy and security note: Udyam Digital prototype

**Scope.** This covers the owner-facing journey (advisor → quote → consent → KYC → e-sign → tracker) and the back-office. Accel Telecom is the *data fiduciary* under the DPDP Act, 2023. All data in the prototype is synthetic, but it is handled as if it were real.

**1. Consent before KYC (DPDP s.6).** Nothing identity-related is collected until the owner sees a plain-language notice in their language. Consent is **split by purpose**:

- verification (required)
- service activation (required)
- marketing (optional, unticked by default)

Each purpose shows what is used, why, and how long it is kept. Every grant is written to an append-only `consent_ledger` with the notice version, language, timestamp and the purposes granted. If the owner declines, the journey routes to a partner for in-person KYC rather than forcing consent. Withdrawal is offered on the tracker and by replying STOP.

**2. Purpose limitation.**
- The advisor stores only business-profile slots: type, size, sites, city tier, GST yes/no, current tools and needs. It stores no identity data.
- KYC fields are used only to verify and provision.
- Back-office scoring uses only lead-time attributes (segment, size, source, GST status). It never uses KYC documents.

**3. Data minimisation.**
- **Document images are never stored.** An upload is read in memory, passed to the extractor and discarded. We keep only the extracted fields plus a SHA-256 of the file, so tampering or replacement can be proven later.
- An optional DigiLocker pull can stand in for the GST and Udyam uploads. It carries issuer-signed data, so no image is processed at all.
- The Udyam certificate is asked for only when the registry shows the business is Udyam-registered.

**4. Masking.** GSTIN, Udyam, ID and consumer numbers are masked (e.g. `37••••••••••1ZS`) in API responses, the UI, back-office lists and logs. The audit log records actions, never raw identifiers.

**5. What leaves our boundary (processors).**
- Before chat text reaches the LLM, a redactor strips GSTIN, PAN, Udyam, Aadhaar-like numbers, phone numbers and emails.
- Only document images go to the vision model. That transfer is named in the consent notice, and the processor contract must prohibit retention and training.
- Voice audio is sent once for transcription and is not stored.
- Prompt Guard screens inputs for injection attempts.

**6. Retention.**

| Data | Kept for |
|---|---|
| Raw images | 0 days |
| Extracted KYC fields (pending orders) | `purge_after` = 30 days |
| Extracted KYC fields (activated customers) | Account life + 8 years (telecom licence / KYC record-keeping) |
| Abandoned journeys | Purged after 90 days |
| Consent records | Kept as evidence for as long as the data they cover |

**7. Security controls.**
- TLS everywhere: Vercel and Render.
- Postgres on Neon, encrypted at rest.
- Secrets only in platform environment variables, never in git.
- Strict CORS allow-list.
- Upload limits: 6 MB, JPG/PNG/WebP magic-byte check.
- The service worker never caches API responses.
- The back-office needs a staff key. Production would use SSO with roles: partners see only leads assigned to them.
- Every consent, document, KYC result, assignment and order is written to `audit_log`.
- The demo-only endpoint (order advance) is gated by `DEMO_MODE`.

**8. Data principal rights.** The owner can access their journey by ID, correct details by re-uploading, withdraw consent, and use a named grievance contact (shown on the consent screen, reply within 7 days). Erasure purges KYC fields and the journey checkpoint, but keeps the consent and audit records the law requires.

**9. Known gaps before production.**
- A real DigiLocker / e-Sign ASP integration.
- Liveness and face match for signatory ID.
- KMS-backed field-level encryption for KYC fields.
- Formal DPIA.
- Processor DPAs.
- Rate limiting per IP.
