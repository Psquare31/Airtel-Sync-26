# Udyam Digital: small businesses go digital in one sitting

Prototype for **YTL Hackathon 2026 · Enterprise Track A (Airtel SYNC)**. A small-business owner uses their phone, in their own language, to:

1. **Advisor**: chat or speak (English, Hindi, Hinglish, Tamil, Marathi…). An LLM collects the business profile, and a deterministic rules engine picks the bundle from `product_catalogue.csv`.
2. **Quote & checkout**: one transparent monthly price with GST shown. Add-ons toggle on and off, quantities can change, the price drops with a 24-month contract, and the setup fee can be spread into instalments.
3. **Smart KYC**:
   - consent screen with separate purposes (DPDP)
   - document photo upload with extraction (Groq vision on the hosted prototype; our own OCR is built and switches on with one setting), plus an optional DigiLocker pull
   - live mock GSTIN and Udyam registry lookups, and a GSTIN checksum
   - cross-document checks
4. **e-Sign & tracker**: OTP e-sign, an installation slot, a live order timeline, WhatsApp-style updates, and "ask about my order".
5. **Back-office (stretch)**:
   - leads the advisor couldn't close, ranked by a propensity model (AUC 0.72), with the next best action
   - assignment to field sales or a channel partner
   - partner-assisted sessions through `/?partner=CODE`
6. **Improvement loop**: with an optional consent, redacted advisor turns become prompt examples. 👎 conversations become draft test cases, and the lead model retrains on real journey outcomes. See [docs/architecture.md](docs/architecture.md#improvement-loop).

Accel Telecom is fictional and all data is synthetic (see [data/README.md](data/README.md)).

| Doc | |
|---|---|
| Architecture & data flows | [docs/architecture.md](docs/architecture.md) |
| Privacy & security note | [docs/privacy-note.md](docs/privacy-note.md) |
| 3-minute demo script | [docs/demo-script.md](docs/demo-script.md) |
| Business case deck | [docs/deck/](docs/deck/) |
| Funnel analysis | `python analysis/funnel.py` |

## Stack

- **Frontend**: React 19 + Vite + Tailwind v4. It is an installable PWA, with i18next for languages.
- **Backend**: FastAPI, with the onboarding journey as a **LangGraph** `StateGraph`. The graph uses interrupts and a Postgres or SQLite checkpointer.
- **LLM**: Groq via a cooldown-aware `ModelRouter`.
  - Chat rotates through `gpt-oss-120b → qwen3-32b → llama-3.3-70b → gpt-oss-20b`.
  - KYC documents: on the hosted prototype they are read by Groq vision (`qwen3.8-27b`, `KYC_VISION=true` in `render.yaml`), and the consent screen says so. Our own OCR (`ocr_local.py`, or `ocr_service/` as a separate service) is built and tested, and takes over automatically when it's installed or `OCR_SERVICE_URL` is set, so documents then never reach an AI provider.
  - Input screening uses `llama-prompt-guard-2-86m`.
  - Voice uses `whisper-large-v3-turbo`.
  - With no key, everything still works on rules plus local OCR.
- **Data**: SQLModel on Neon Postgres in production, SQLite locally.

## Run locally

```bash
# backend (Python 3.13)
cd backend
python -m venv .venv && .venv/Scripts/activate      # source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env                                  # add GROQ_API_KEY (optional)
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
cp .env.example .env.local                            # VITE_API_URL=http://localhost:8000
npm run dev                                           # http://localhost:5173
```

Back-office: http://localhost:5173/backoffice (key `demo` locally).

## Tests and self-checks

```bash
cd backend && pytest -q                       # 55 tests: rules, pricing, router rotation, advisor scenarios, KYC, graph paths, API
python -m scripts.kyc_batch --ocr             # runs Smart KYC on all 12 specimen applicants offline
# requirements-dev.txt includes the optional local OCR stack (requirements-ocr.txt).
# The Docker image leaves it out unless built with --build-arg WITH_OCR=true (needs > 512 MB RAM).
```

Current offline KYC result on the specimen pack:

| Applicant | Outcome | What we catch |
|---|---|---|
| K01 | blocked | GSTIN **cancelled** in registry; Udyam number blank |
| K02 | verified | skewed scan (auto-deskew); OCR `0`→`O` repaired via checksum |
| K03, K08, K09, K12 | verified | – |
| K04 | fixable | GST certificate photo too **blurry** |
| K05 | fixable | business is **Udyam-registered** but no certificate was uploaded; "Owner" can't sign for an **LLP** |
| K10 | fixable | "Owner" can't sign for an **LLP** |
| K06 | fixable | GSTIN **check digit wrong** (altered number) |
| K07 | blocked | legal name on certificate ≠ **GST registry** |
| K11 | fixable | address proof **257 days old**; "Owner" can't sign for a **Pvt Ltd** |

## Branches & deployment

- `dev` is for development and testing (the default branch). `prod` is production and only changes through a PR from `dev`.
- CI (`.github/workflows/ci.yml`) runs pytest, frontend lint and build, and a Docker build on every push and PR to either branch.

| | `dev` | `prod` |
|---|---|---|
| Frontend (Vercel, root `frontend/`) | Preview URL | Production URL |
| API (Render Docker, `render.yaml`) | `udyam-api-dev` (sleeps when idle) | `udyam-api`, kept awake by UptimeRobot |
| Database (Neon) | branch `dev` | branch `production` |

### One-time setup checklist

1. **GitHub**:
   - Push both branches.
   - Set `dev` as the default branch.
   - Add a branch-protection rule on `prod`: require a PR and require the CI checks to pass.
2. **Neon**:
   - Create a project. The default branch (`production`) is created automatically.
   - Create a branch called `dev`.
   - Copy both pooled connection strings.
3. **Render**:
   - New → Blueprint, pick the repo. This creates the two services from `render.yaml`.
   - For each service, set `DATABASE_URL` (its Neon branch) and `GROQ_API_KEY`.
   - Set `CORS_ORIGINS` to the matching Vercel URL.
4. **Vercel**:
   - Import the repo with root directory `frontend`.
   - Set Production Branch = `prod`.
   - Env `VITE_API_URL` = prod API URL (Production) and dev API URL (Preview).
5. **UptimeRobot**:
   - Add an HTTP(s) monitor on `https://<udyam-api>.onrender.com/health`, every 5 minutes, so the prod service doesn't cold-start during demos.
   - Render's free 750 h/month covers one always-on service.
