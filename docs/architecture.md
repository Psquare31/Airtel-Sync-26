# Solution architecture

The owner uses a phone-first PWA. A FastAPI backend runs the onboarding journey as a **LangGraph state machine**. Only two steps use an LLM: the advisor conversation and document reading. Eligibility, bundle choice, pricing and order status are **deterministic code over `product_catalogue.csv`**, so prices and products are never invented.

![Architecture](architecture.png)

## Components and data flows

```mermaid
flowchart LR
  subgraph Client["Phone · PWA on Vercel"]
    UI["React PWA<br/>Advisor · Quote · Consent · KYC · e-Sign · Tracker"]
    MIC["Voice in/out<br/>MediaRecorder + speechSynthesis"]
    BO["Back-office<br/>(sales & partners)"]
  end

  subgraph API["API · FastAPI on Render"]
    J["/api/journeys<br/>start · resume · upload · DigiLocker"]
    G["LangGraph journey<br/>greet → advisor ⟲ → recommend → quote ⟲<br/>→ consent → kyc ⟲ → e-sign → order"]
    ADV["Advisor<br/>regex slot parser + LLM slot filling"]
    RULES["Rules engine<br/>eligibility · dependencies · budget"]
    PRICE["Pricing<br/>contract-based price · GST · setup EMI"]
    KYC["Smart KYC<br/>blur check · deskew OCR · GSTIN checksum<br/>registry + cross-document matching"]
    ORD["Order tracker<br/>state machine · WhatsApp notices"]
    PROP["Propensity model<br/>logistic regression (AUC 0.72)"]
    ROUTER["Groq ModelRouter<br/>cooldown-aware rotation"]
  end

  subgraph Groq["Groq Cloud"]
    GUARD["llama-prompt-guard-2-86m<br/>(input screening)"]
    CHAT["gpt-oss-120b → qwen3-32b →<br/>llama-3.3-70b → gpt-oss-20b"]
    VIS["llama-4-scout / maverick<br/>(document vision)"]
    STT["whisper-large-v3-turbo"]
  end

  subgraph Data["Data"]
    PG[("Neon Postgres<br/>checkpoints · journeys · consent ledger<br/>KYC fields · orders · audit log")]
    CSV[("Catalogue, mock GSTIN & Udyam<br/>registries, leads (CSV)")]
  end

  UI -- HTTPS JSON --> J
  MIC -- audio --> J
  BO -- X-Backoffice-Key --> API
  J --> G
  G --> ADV --> ROUTER
  G --> RULES --> PRICE
  G --> KYC --> ROUTER
  G --> ORD
  ROUTER --> GUARD & CHAT & VIS & STT
  G <--> PG
  KYC --> CSV
  RULES & PROP --> CSV
```

## The journey graph

Every human step is an `interrupt()`. The API resumes the graph with `Command(resume=...)`. A journey survives restarts and device changes, because its whole state is checkpointed in Postgres under `thread_id = journey_id`.

```mermaid
graph TD
  start([start]) --> greet --> advisor
  advisor -. "profile incomplete" .-> advisor
  advisor -. "6 slots filled" .-> recommend
  recommend -. "tier-3 city: partner hand-off" .-> advisor
  recommend -.-> quote
  quote -. "toggle / quantity / contract" .-> quote
  quote -. "change answers" .-> advisor
  quote -. accept .-> consent
  consent -. declined: partner KYC .-> stop([end])
  consent -.-> kyc
  kyc -. "fixable: re-upload" .-> kyc
  kyc -. "blocked: hand-off" .-> stop
  kyc -. verified .-> esign
  esign -. "bad OTP" .-> esign
  esign -.-> order --> stop
```

## Improvement loop

The advisor improves from consented real use, without retraining a model:

| Signal | What it improves |
|---|---|
| Redacted advisor turns, kept with the optional "improve the advisor" consent | Similar past turns in the same language are added to the prompt as examples of how answers map to slots |
| 👍/👎 on the plan, with a reason | 👎 conversations are left out of prompt examples and exported as draft test cases for review (`/api/backoffice/learning/scenarios.yaml`) |
| Reviewed draft test cases (`tests/learned_scenarios.yaml`) | Run with the advisor scenario suite, so a fixed mistake can't come back |
| Journey outcomes (ordered, handed off, or idle for a week) | The lead propensity model retrains on them with the historic leads, every 6 hours or on demand |

Fine-tuning a small Indic model on this data is a later step, once there is real volume.

## Key design choices

| Choice | Why |
|---|---|
| **LLM talks, code decides** | Judges run live scenarios; prices and eligibility must be reproducible. The LLM extracts slots and explains *reason codes*. It never picks products. |
| **Deterministic parser runs first** | Numbers, cities, GST yes/no and needs are parsed by regex (English, Hindi, Hinglish) before the LLM. The advisor still works with no API key or when every model is rate-limited. |
| **Groq model rotation** | On a 429 the router parks that model until its `retry-after` and moves to the next one. Malformed JSON also moves to the next model. When everything is exhausted, the scripted advisor takes over. |
| **Prompt Guard as a classifier** | `llama-prompt-guard-2-86m` scores each long user message for injection. It is not a chat fallback. A local regex catches the obvious cases offline. |
| **Two KYC extractors** | Groq vision (Llama 4) is the primary reader. The offline fallback removes the pink watermark by colour, deskews (projection-profile search), runs RapidOCR and pairs label/value boxes by geometry. |
| **Checks in code, not in the model** | GSTIN mod-36 checksum and PAN structure, O/0 OCR repair that is accepted only if the checksum then passes, registry status, fuzzy name/address match, signatory role by constitution, bill age ≤ 90 days, blur score. |
| **Hybrid LangGraph** | One graph gives a resumable state, conditional routing (fixable vs blocked KYC), human-in-the-loop interrupts and a clear hand-off path to people. |
| **PWA, not a native app** | One link works on any phone, can be added to the home screen, and needs no store review. API responses are never cached by the service worker. |

## Deployment

| Piece | `dev` branch | `prod` branch |
|---|---|---|
| Frontend | Vercel preview URL | Vercel production URL |
| API | Render `udyam-api-dev` (may sleep) | Render `udyam-api`, kept warm by UptimeRobot on `/health` |
| Database | Neon branch `dev` | Neon branch `production` |

GitHub Actions runs pytest, the frontend lint and build, and a Docker build on every push or PR. A PR merges `dev → prod`.
