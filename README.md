# Agentic Payment Assistant — Final Tech Stack & Infrastructure (Groq via OpenRouter + WhatsApp)

**Short summary**: an agentic pipeline that parses invoices (hosted files or forwarded email), sends masked data to Groq (Grok 4.1 Fast) via OpenRouter for structured validation and action-list generation, executes validated UI actions on a mock bank portal using Playwright (orchestrated via a Playwright executor service), and asks the human to approve via WhatsApp (Twilio sandbox or Cloud API). Final execution is simulated in the mock portal; all audits (parsed JSON, Groq request/response hashes, screenshots, action logs) are stored.

## 1 — High-level components (what runs and why)

*   **Frontend UI (React/Vite + Tailwind)** — upload UI, admin view, audit viewer.
*   **API & Orchestrator (Python 3.11+ + FastAPI)** — main server that receives uploads, enqueues jobs, calls OpenRouter/Groq, validates outputs, and issues Playwright steps.
*   **Task Worker(s) (Python workers)** — background workers that run OCR, call Groq via OpenRouter, run Playwright executor, handle WhatsApp webhooks.
*   **PostgreSQL (official Docker image)** — canonical relational DB for vendors, POs, invoices, payments, audit metadata.
*   **Redis (official Docker image or Redis cloud if you choose)** — job queue, ephemeral cache, locks, rate-limit counters. Use Redis as RQ or Celery broker.
*   **Blob store (MinIO or local filesystem)** — store invoice PDFs, screenshots and large artifacts. MinIO recommended if you want S3 semantics; local filesystem ok for hackathon.
*   **Playwright / Chromium** — deterministic browser executor that fills and screenshots the mock banking portal. Playwright can be run from a container worker or locally on your dev machine.
*   **Tesseract / OCR engine** — system-level binary (installed on host) used by OCR worker for scanned invoices.
*   **OpenRouter (external)** — API endpoint to call Groq model. You send masked payloads and receive JSON structured outputs.
*   **WhatsApp provider (Twilio Sandbox or WhatsApp Cloud API via Meta / BSP)** — send screenshot & action buttons for approval, receive webhook replies.
*   **Logging & audit store** — structured logs, SHA256 hashes of OpenRouter request/responses, stored screenshots, Playwright action logs.
*   **Optional local LLM** — fallback or future migration (llama.cpp / gpt4all) if you decide to stop sending data to OpenRouter.

## 2 — Why PostgreSQL + Redis (roles & why official Docker images)

### PostgreSQL (official image)
*   **Role**: persistent relational store for vendors, purchase orders, invoices, payments, audit metadata and long-term reports.
*   **Why Postgres**: strong JSONB support (store parsed_json & groq outputs), robust, ACID for financial records, widely supported in infra.
*   **How used (conceptually)**:
    *   `vendors`, `purchase_orders`, `invoices`, `payments`, `audits` tables.
    *   store `parsed_json` (invoice fields), `groq_validation_report`, `groq_action_list` (raw + validated), `groq_request_hash` & `groq_response_hash`.
    *   foreign keys: invoice → vendor/PO; payment → invoice.
*   **Persistence & backup**: run in Docker with a named volume mapped to host; backup via pg_dump or schedule exports to attach to MinIO/backups.

### Redis (official image or managed Redis)
*   **Role**: ephemeral job queue, worker coordination, caches, rate limits, locking and request dedup.
*   **Why Redis**: low-latency pub/sub and reliable broker for RQ/Celery; simple for hackathon.
*   **How used (conceptually)**:
    *   enqueue `ingest_job` when invoice uploaded.
    *   workers pop `groq_validation_job`, `playwright_exec_job`, `notify_job`.
    *   store per-job TTL keys for dedup, and short-lived cache for vendor name embeddings or PO lookup results.
    *   rate limiting OpenRouter calls (track counts per minute/hour).
*   **Persistence**: enable AOF/RDB persistence in config if you want to survive restarts; for hackathon default ephemeral is fine.

**Use official Docker images (Postgres & Redis)** — they’re maintained, predictable, and the easiest to configure in docker-compose for both development and local demo. If you want a managed production option later, switch Redis to a cloud provider or Postgres to a managed DB.

## 3 — What you installed already (how they fit)

You mentioned you already installed the following on your dev machine. Here’s what to keep in mind and how they integrate:

*   **Tesseract OCR (system binary)** — you installed it at `C:\Program Files\Tesseract-OCR` (Windows).
    *   **Use**: OCR worker invokes Tesseract to extract text from scanned pages when pdfplumber text extraction fails.
    *   **Important config**: Worker must be configured to point to the Tesseract binary path (no code shown here; just ensure env var or config contains that path). Keep language packs installed for any additional languages you need (see "additional language data" below).
*   **Playwright + Chromium** — you installed the Playwright Python package and ran `playwright install`, which downloaded Chromium and other browsers.
    *   **Use**: Playwright executor runs headful/headless browser sessions to fill mock bank pages, capture screenshots and optionally generate video for demo.
    *   **Important config**: Decide whether Playwright runs inside a worker container or runs on your host machine in dev. Both are valid: containerized Playwright ensures reproducibility; local Playwright is easier while developing.
*   **Python packages (pytesseract, pillow, playwright, etc.)** — used by OCR and automation workers; ensure your Python virtual environment or Docker image contains the same versions you tested with.

## 4 — WhatsApp choice and limits (why WhatsApp/Twilio sandbox)

*   **Recommendation for hackathon**: use Twilio WhatsApp Sandbox (fastest) or WhatsApp Cloud API (Meta) if you already have dev access. Twilio sandbox is easier to set up quickly — supports media and interactive replies for demo.
*   **Limits to know**: 24-hour messaging window rules and template requirements for proactive messages. For hackathon, Twilio sandbox is permissive; for production you must register templates or ensure user-initiated flow.
*   **Integration model**: server sends a message with screenshot + masked Groq explanation + two buttons (Approve / Reject). Buttons invoke a webhook back to your backend, which resumes Playwright execution. Always log full payload.

## 5 — OpenRouter & Groq integration (what to send, what to guard)

*   **What you send to OpenRouter/Groq**: always mask sensitive fields before outbound (send account_last4, vendor name, PO id, amount, payment date). Avoid sending full account numbers.
*   **Expected response**: Groq returns `validation_report` and `action_list` JSON. Your server must validate the schema strictly.
*   **Server responsibilities (MANDATORY)**:
    *   enforce schema validation (reject anything outside allowed ops).
    *   run additional rule-engine checks (amount thresholds, unknown beneficiary, IFSC mismatch).
    *   compute & store SHA256 hashes of request and response for each OpenRouter call.
    *   log and store Groq raw response only after validation.
*   **Rate control**: use Redis to throttle OpenRouter calls to prevent accidental overuse of the OpenRouter account.

## 6 — Where each service runs (recommended Docker layout)

Note: you asked for no code. Below is a conceptual service map you run via Docker Compose for dev + local demo.

### Core container services (recommended)
*   **app** — FastAPI API server (contains API routes, admin UI backend).
*   **worker** — background worker process that runs ingestion, OCR (using Tesseract binary mapped in), Groq call wrapper (OpenRouter client), and orchestrates tasks. You can run multiple worker processes for concurrency.
*   **playwright-worker** — isolated worker that runs Playwright and executes validated action lists against the mock bank portal. Playwright browsers can run inside this container, or you can mount the host’s Playwright/browser install (dev mode).
*   **postgres** — official Postgres image (persistent named volume).
*   **redis** — official Redis image (used by RQ/Celery). Use password/ACL and named volume if persistence needed.
*   **minio (optional)** — for object storage of PDFs and screenshots (S3-like). Or use a mounted host directory for file storage.
*   **mock-bank** — mock banking portal (simple HTML/React) running on an internal domain used only for demos (restrict Playwright to it).
*   **admin-frontend** — React app served statically (or via dev server) for upload/admin UI.

### Where Tesseract & Playwright live:
*   **Tesseract binary**: typically installed on the host. If you prefer containerized Tesseract, include a worker image that installs the Tesseract binary; otherwise mount host path into worker container (Windows nuances: prefer containerized Linux worker on Docker Desktop).
*   **Playwright browsers**: can be installed in the `playwright-worker` container (recommended) or used from the host for quick dev runs; containerized Playwright ensures consistency.

## 7 — Environment variables & secrets (what to set)

Set these in your environment / Docker Compose env file — server will read these:

*   `OPENROUTER_API_KEY` — OpenRouter API key (used to call Groq).
*   `OPENROUTER_URL` — OpenRouter base URL (e.g., https://api.openrouter.ai/v1).
*   `GROQ_MODEL` — Groq model id as available in OpenRouter (pin exact name).
*   `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` — Twilio credentials if using Twilio sandbox.
*   `TWILIO_WHATSAPP_NUMBER` — Twilio sandbox from number for WhatsApp.
*   `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL` — Postgres connection.
*   `REDIS_URL`, `REDIS_PASSWORD` — Redis connection string for worker & queue.
*   `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` — if using MinIO.
*   `OPENROUTER_MOCK` — boolean flag to enable mock Groq responses during development.
*   `PLAYWRIGHT_EXECUTOR_MODE` — run mode for Playwright (container or host).
*   `TESSERACT_PATH` — path to tesseract binary on host if worker uses host binary.

**Security note**: keep these secrets out of source control; use local `.env` or Docker secrets in production.

## 8 — Data flow & audit chain (short)

1.  User uploads invoice → API saves PDF to blob store & writes invoice record in Postgres.
2.  API enqueues `ingest_job` in Redis.
3.  Worker runs extraction (pdfplumber → Tesseract fallback) → parsed JSON stored in Postgres.
4.  Worker constructs masked payload and sends it to OpenRouter (Groq). Save request SHA256.
5.  Receive Groq JSON → validate schema → save response SHA256 & `groq_validation_report` + `groq_action_list` in Postgres.
6.  If `action_list` approved by server rules, enqueue Playwright execution. Playwright runs only against mock bank; screenshot saved.
7.  Server sends WhatsApp message with screenshot + Groq explanation (masked) asking for Approve/Reject. Message arrives via Twilio / WhatsApp API.
8.  When user approves (via button), webhook triggers Execution Agent to resume Playwright (OTP simulation) and mark payment simulated-complete. All steps logged in audit table with timestamps and hashes.

## 9 — Additional installation notes (you asked about extra languages / script data & Tesseract)

*   **Tesseract language packs**: if you need extra script/language OCR (e.g., Devanagari / Marathi / Gujarati), download and install the relevant trained data (.traineddata) into Tesseract’s tessdata directory. On Windows with UB Mannheim builds, place them in `C:\Program Files\Tesseract-OCR\tessdata`. Then configure worker to pass `--lang` parameter or equivalent via your OCR wrapper.
*   **Why install extra languages**: invoices or vendor documents sometimes contain local-language text (addresses, vendor names). Additional language packs improve accuracy for those fields.
*   **Playwright/Chromium**: you already installed Playwright and Chromium — that is sufficient. For production-like containerized Playwright, use a worker container that includes Playwright and its browsers (or use official Playwright Docker images).

## 10 — Safety, limits & operational policies (Groq/OpenRouter & WhatsApp)

*   **Never send full account numbers to OpenRouter** — use `account_last4` or hashed forms. Only the server should possess full account numbers and use them exclusively when filling the mock portal.
*   **Strict action_list schema** — server rejects any action list containing navigations outside mock-bank domain or any submit op without `approved:true`.
*   **Rate-limiting Groq calls via Redis counters** to avoid exceeding OpenRouter quotas. Use `OPENROUTER_MOCK=true` while developing to avoid real requests.
*   **WhatsApp 24-hour window**: design so messages are user-initiated where possible or use pre-approved templates if sending proactively outside the 24-hour window. For the hackathon Twilio sandbox, this is flexible.
*   **Audit everything** — retain request/response hashes, screenshots, Playwright logs, and approval records; these protect you if a judge/tester questions behavior.

## 11 — Practical installation checklist (what you and the team must have ready)

(Do these before you start wiring flows)

### System-level / host installs
*   [x] Docker & Docker Compose (latest).
*   [x] Python 3.11+ and venv for local dev (or Docker-only flow).
*   [x] Node.js + npm/yarn (for frontend if building React).
*   [x] Tesseract OCR installed on host (you already did). Install any extra tessdata language packs you need.
*   [x] Playwright Python package installed and browsers installed (you already did `playwright install`). Confirm Chromium download OK.

### Service credentials & accounts
*   [ ] OpenRouter account + API key (Groq enabled) — store key in env.
*   [ ] Twilio account with WhatsApp Sandbox enabled, or WhatsApp Cloud API access and a dev phone number (choose one).
*   [ ] Optional: MinIO credentials (if using MinIO).
*   [ ] Prepare demo/test phone numbers and opt-in for Twilio sandbox.

### Docker services to run
*   [x] Postgres container (official).
*   [x] Redis container (official).
*   [ ] MinIO container (optional) OR ensure a host directory for file blobs.
*   [x] app, worker, playwright-worker containers built from your Dockerfiles.

### Repository & scaffolding
*   [x] Create repo with docker-compose definitions (no code shown here).
*   [x] Prepare configuration documentation for all env vars listed earlier.

## 12 — Audit & demo readiness checklist (what to show judges)

*   [ ] Upload a PDF and show parsed fields (text & confidence).
*   [ ] Show Groq validation report and action_list (both masked). Explain that full account numbers were never sent to OpenRouter.
*   [ ] Show Playwright filling the mock-bank fields, pausing at confirm, and screenshot capture.
*   [ ] Show WhatsApp message with screenshot and Groq explanation (masked). Approve via button.
*   [ ] Show final simulated success and audit entries with request/response hashes.
