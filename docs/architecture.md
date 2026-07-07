# Architecture

## Supervisor graph

```
                              ┌──────────────┐
                intake ──────▶│  Supervisor   │
                              └──────┬───────┘
                                     │ fan-out (parallel)
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
   Vehicle Verification         Policy Agent            Vision Agent
     (OCR + regex)          (LlamaIndex RAG over        (HF damage model
                              policy PDF, pgvector)       over photos)
              │                      │                      │
              └──────────────────────┼──────────────────────┘
                                     ▼
                            Cost Estimation Agent
                              (XGBoost regression)
                                     │
                                     ▼
                            Fraud Detection Agent
                         (weather API cross-check +
                          consistency check via Claude)
                                     │
                                     ▼
                         needs_human_review? ──yes──▶ Human Review Checkpoint
                                     │no                        │
                                     ▼                          │
                            Report Agent  ◀──────────────────────
                                     │
                                     ▼
                                COMPLETED
```

Vehicle Verification, Policy, and Vision run in parallel because they read
independent inputs (plate photo, policy PDF, damage photos respectively)
and don't depend on each other's output. Cost Estimation needs vehicle age
(from Vehicle Verification) and damage type/severity (from Vision), so it
waits for both. Fraud Detection needs the incident description, vehicle,
and vision output, so it runs after those. See `ClaimState.needs_human_review`
in `backend/app/schemas/claim_state.py` for the exact routing condition out
of Fraud Detection.

## Why Pydantic-as-LangGraph-state

LangGraph supports both `TypedDict` and Pydantic `BaseModel` as the state
schema. `TypedDict` is marginally faster (no validation per node), but this
project uses Pydantic throughout for structured Claude outputs anyway, and
per-node validation catches a malformed agent output at the node boundary
instead of three nodes later — worth the small perf cost for a
correctness-first solo build. See `ClaimState` module docstring for the
specific reducer rules (`operator.add` on `agent_runs`/`errors` for
concurrent fan-out writes).

## Data flow for a single claim

1. Frontend uploads vehicle photo, damage photos, policy PDF, and the
   description via `POST /claims` → `services/storage.py` persists files,
   returns storage ids → `ClaimIntakeInput` is built → `ClaimState.new(...)`.
2. The graph runs; each node returns a partial `ClaimState` update.
3. `ClaimState.agent_runs` accumulates one `AgentRun` per node (status,
   latency, token usage) — this is what Langfuse and the evaluation
   framework both read.
4. If `needs_human_review`, the graph interrupts at the Human Review node
   (LangGraph `interrupt()`) and the API surfaces a pending-review status;
   an adjuster approves/rejects via `POST /claims/{id}/review`, which
   resumes the graph.
5. Report Agent renders `ClaimTriageReport` (structured) and
   `.to_markdown()` (display) from whatever's populated in `ClaimState` —
   it must handle any per-agent field being `None` gracefully.

## Observability

Every node is wrapped so it logs to Langfuse as its own observation within
the claim's trace (`ClaimState.langfuse_trace_id`), and appends an
`AgentRun` with the same token/cost numbers. Two systems, one source of
truth per node execution — no duplicate instrumentation.

---

## Implemented claim workflow (this batch)

Everything above this line describes the originally-planned full
supervisor graph. Most of it — Vehicle Verification (plate OCR), the
weather-API fraud cross-check, the `interrupt()`-based human-review
resume flow — is still not built. What *is* real and running today is a
narrower graph over the actual working claim flow
(`POST /claims` → `POST /claims/{id}/analyze` → this graph):

```
Claim Intake (existing create/analyze flow, unchanged)
      │
Vehicle Validation + Damage Assessment  (app/graph/nodes/damage_assessment.py
      │                                   — wraps AIServiceClient; skips if
      │                                   ai_assessment already computed)
      ▼
Pricing  (app/graph/nodes/pricing.py — wraps cost_model.summarize_claim_costs)
      │
      ├── policy processed + chunks available ──▶ Policy Retrieval + Coverage
      │                                            Analysis (app/graph/nodes/
      │                                            coverage_analysis.py — RAG
      │                                            over the claimant's own
      │                                            uploaded policy text)
      │
      └── no policy / still processing / failed ─▶ skip straight through
                                                     (coverage_analysis stays
                                                     unset; never blocks
                                                     damage/pricing)
      ▼
Risk Signal Analysis  (app/graph/nodes/risk_signal.py — deterministic,
                        rule-based; always runs with whatever evidence
                        exists, never an LLM-scored guess)
      ▼
Final Report Generation  (app/graph/nodes/report_generation.py — pure
                           aggregation, see report_service.py)
```

Real typed state: `app/graph/workflow_state.py`'s `ClaimWorkflowState`
(a `TypedDict`), not the `ClaimState` above — that one is reserved for the
original intake shape (`vehicle_image_id`/`policy_pdf_id`/etc.) this
codebase doesn't actually collect. `app/graph/orchestrator.py` is the one
place that reads a `ClaimRecord`/`PolicyDocumentRecord` from the database,
builds the initial state, runs the compiled graph, and persists the
result back — called from `POST /claims/{id}/analyze` (after a fresh
assessment) and `POST /claims/{id}/policy` (after a policy finishes
processing), never on every read (`GET /claims/{id}/report` just renders
whatever was last persisted).

### Policy RAG (Task 2)

```
extracted policy text (app/services/policy/extraction.py:
  pypdf for text-layer PDFs; easyocr for photographed/scanned pages,
  gracefully degrading to a clear "processing failed" state if easyocr
  isn't installed — see that module's docstring)
      │
      ▼
chunks, page/section-tagged (app/services/rag/chunking.py — never crosses
  a page boundary, so every chunk's citation is accurate)
      │
      ▼
embeddings (app/services/rag/embeddings.py — a deterministic feature-
  hashing vectorizer; no embedding-model API key is configured anywhere
  in this project, so this avoids introducing a new paid dependency for
  an MVP. Swappable later for a hosted embedding model.)
      │
      ▼
vector storage (app/db/models/policy_chunk.py — a real `pgvector`
  column in Postgres; the exact same JSON-on-non-Postgres fallback
  `app/db/models/claim.py` already established, since this environment
  has no Postgres/pgvector available to exercise the real column type)
      │
      ▼
retrieval (app/services/rag/retrieval.py — brute-force cosine similarity;
  correct at this scale, since retrieval is always scoped to one claim's
  one policy document, never a cross-claim corpus)
      │
      ▼
coverage analysis (app/services/policy/coverage_analysis.py — keyword
  classification over the *retrieved* excerpts only, never the full
  document; produces likely_covered / unclear / potential_exclusion /
  manual_review, never "approved"/"rejected")
```

## Production readiness

Not deployed by this batch — preparing for a later deployment.

**Environment variables** — every field documented once in
`backend/app/config.py` (`Settings`) and mirrored in
`backend/.env.example`; `frontend/.env.example` for the Next.js side. New
in this batch: `ANTHROPIC_API_KEY`/`CLAUDE_MODEL` (optional — policy
structured extraction degrades to a deterministic heuristic without it),
`UPLOAD_DIR` (now actually used, by policy document storage).

**Service startup** — three independent processes, no orchestration
between them yet: `uvicorn app.main:app` (backend), the ai-service's own
FastAPI process (YOLO models loaded at startup — budget real RAM for
this, see below), `npm run dev` / `next start` (frontend). See root
`README.md` for exact commands; `infra/docker-compose.yml` currently
defines `postgres`/`backend`/`frontend` only — the ai-service has no
container defined yet, a pre-existing gap this batch didn't add scope to
close.

**Health / readiness** — `GET /health` (liveness — process is up, no I/O)
and `GET /ready` (readiness — verifies the database is actually
reachable) on the backend; the ai-service exposes its own `/health` (see
`ai-service/main.py`). Point a load balancer / orchestrator's readiness
probe at `/ready`, not `/health`.

**Database migrations** — `alembic upgrade head` against a real Postgres
`DATABASE_URL`. Known gap, not introduced by this batch: Alembic's sync
engine can't run migrations 0001+ against `sqlite+aiosqlite` (the sandbox
substitute this project's dev environment uses, per `backend/.env`'s own
inline note) — migration 0001 already hardcodes `postgresql.JSONB` in its
DDL. This has never worked against SQLite via Alembic; local/test dev
uses `Base.metadata.create_all()` instead (see `tests/conftest.py`
pattern). Not a regression from this batch's migration 0004, which
follows the same JSONB convention for consistency.

**Model storage** — the ai-service's YOLO weights (`ai-service/models/`)
must be present on whatever host runs it; they are not fetched at
runtime. Budget for both weight files being resident plus PyTorch's own
runtime overhead.

**AI-service memory** — loads two YOLO models (car-parts, damage
segmentation) into memory at process startup, held for the process
lifetime. Size the container/VM accordingly; a scale-to-zero or
per-request cold-start deployment reloads both models every time.
`AI_SERVICE_TIMEOUT_SECONDS` defaults to 120s to cover that cold start,
and the frontend reconciles a lost/timed-out analyze response against
real claim status rather than treating it as a failure.

**Persistent storage for policy documents** — `app/services/policy/storage.py`
writes to local disk (`UPLOAD_DIR`). Not safe as the only copy in a
multi-instance deployment (each instance only sees its own disk) or
without its own backup/retention policy — migrate to an S3/GCS-compatible
object store before running more than one backend instance.

**Vector database** — `policy_chunks.embedding` is a plain JSON column in
this sandbox (no pgvector extension available here) and a real `pgvector`
column in Postgres once the extension is enabled
(`CREATE EXTENSION vector;`). No separate vector-database service is
required — pgvector lives inside the existing Postgres instance.

**CORS** — `CORS_ALLOWED_ORIGINS` must list the real deployed frontend
origin(s) in production; never `*` (see `app/main.py` — `allow_origins`
always reads this list, there is no wildcard path in the code at all).
