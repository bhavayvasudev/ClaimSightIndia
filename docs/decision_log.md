# Decision log

Short-form ADRs. Add an entry whenever a choice isn't obvious from the code.

## 2026-07-03 — Money as `int` rupees, not `float` or `str`

The spec's example outputs show `"deductible": ""` and
`"estimated_cost_range": "₹30,000 - ₹45,000"` as strings. Storing computed
money as a formatted string makes it unusable for arithmetic (deductible
netting, payout calculation) and unsortable. `CostEstimate`/`PolicyDetails`
store whole-rupee `int` fields and expose `display_range` /
`deductible_display` properties that format on demand. The Report Agent
renders the display strings; nothing else should re-derive them.

## 2026-07-03 — Single `claim_state.py` file, not one file per agent

Considered splitting into `vehicle.py`, `policy.py`, `vision.py`, etc. to
mirror the agent boundaries. For a solo one-month build the extra import
indirection isn't worth it yet — one file is easier to keep consistent
while the schema is still moving. Revisit if it passes ~600 lines.

## 2026-07-03 — Pydantic BaseModel as the LangGraph state, not TypedDict

See `docs/architecture.md` § Why Pydantic-as-LangGraph-state.

## 2026-07-03 — Fixed `DamageType` enum, not open vocabulary (superseded)

Superseded by the 2026-07-04 entry below — there is no HF Vision Agent or
XGBoost Cost Estimation Agent anymore, so `DamageType` doesn't exist.
Kept here for history; see `PartDamageAssessment` for the current
part-centric shape.

## 2026-07-04 — Replaced HF Vision Agent + XGBoost pricing with the
## working ai-service pipeline + category-heuristic pricing

The original plan (HF vision model output mapped to a `DamageType` enum,
XGBoost regression for cost) predates a working YOLO car-parts +
damage-segmentation pipeline (`ai-service/`) that was already built,
tested against five sample images, and tuned (candidate vs trusted mask
thresholds, part-group severity cutoffs). Building a second, redundant
vision model made no sense once one existed and worked. `VisionAssessment`
now wraps `PartDamageAssessment` — a 1:1 mirror of the ai-service's
per-part JSON — instead of a generic damage-type taxonomy, and cost
estimation is a small, explicitly-labelled MVP heuristic
(`services/cost_model/pricing_config.py`: base cost range per part group
× vehicle-category multiplier) rather than a trained regression model,
since no real repair-cost training data exists yet. `basis` on every
`PartCostEstimate` says `"category_heuristic_v0"` so it's obvious in the
data itself that this isn't a fitted model — swap the config table for
real pricing data later without changing the interface
(`estimate_cost`/`summarize_claim_costs`).

## 2026-07-04 — ai-service stays inference-only; no pricing fields in its
## response contract

`estimated_cost` was removed from every ai-service response
(`/analyze`, `/analyze-claim`) and from `pipeline.py`'s
`get_cost_estimate` entirely. Pricing needs vehicle category, which is
claimant-submitted metadata the ai-service never receives (and shouldn't
guess — the YOLO models aren't vehicle classifiers). Keeping cost
estimation in the ai-service would mean pricing without knowing the
vehicle category, or duplicating category logic in two services. The
backend's `services/cost_model` is now the only place a repair-cost
estimate is computed.

## 2026-07-04 — Claim persistence: JSONB for AI/pricing assessments,
## normalized columns for vehicle metadata + status

`ClaimRecord` (`app/db/models/claim.py`) normalizes `vehicle_type`,
`vehicle_make/model/year`, and `status` — fixed-shape fields already
present at intake, and exactly what a claims dashboard would filter/sort
on. `ai_assessment` and `pricing_assessment` are JSONB: both are nested,
variable-length structures with an already-tested Pydantic contract
(`PartDamageAssessment`, `ClaimCostSummary`), and nothing yet needs to
query across individual parts — normalizing into a `claim_parts` table
now would be relational complexity with no current payoff. No
`registration_number` column: the current `ClaimIntakeInput` doesn't
collect one (it's OCR-derived by the not-yet-built Vehicle Verification
agent) — a column nothing writes to isn't worth adding yet.

Async SQLAlchemy engine (`app/db/session.py`) because the same process
also makes async HTTP calls to the ai-service (`app/services/ai_client.py`);
mixing sync DB calls into async routes would risk blocking the event
loop. `postgresql+psycopg` (psycopg 3) is the one SQLAlchemy driver that
supports both sync and async under one URL scheme, so `settings.database_url`
is reused unchanged for Alembic's sync migration engine
(`migrations/env.py`) — no separate "migration URL" to maintain.

## 2026-07-05 — Policy upload/OCR/extraction did not actually exist;
## built as a prerequisite for Policy RAG

A batch of work assumed policy document upload, OCR, PDF extraction, and
structured field extraction were already implemented ("already DONE").
They weren't: no policy-related route, model, or service existed
anywhere in `backend/app/`; `/docs` even stated outright that the API
"covers claim intake and retrieval, not policy documents". What *did*
exist was an aspirational, unwired `PolicyDetails`/`PolicyType` contract
in `claim_state.py` and already-declared-but-not-installed dependencies
(`easyocr`, `llama-index`, `pgvector`, `anthropic`) — scaffolding for this
work, never the work itself. Built the real thing
(`app/services/policy/`) as a prerequisite rather than skip Policy
RAG/Coverage/Risk/Report entirely, since all of those depend on it.

## 2026-07-05 — Feature-hashing embeddings, not a hosted embedding API

Policy clause retrieval (`app/services/rag/embeddings.py`) needs vectors
to do similarity search over. No embedding-model credential is configured
anywhere in this project — `ANTHROPIC_API_KEY` is the only LLM secret,
and Anthropic doesn't serve embeddings (they recommend Voyage AI, not
configured here either). Rather than silently require a new paid
API key the deployment hasn't provisioned, or pull in a heavy local model
(sentence-transformers/torch — the ai-service already carries that
weight for YOLO; the backend doesn't), used a deterministic feature-
hashing vectorizer: real cosine-similarity math, no network call, no GPU,
reasonable for the fairly lexical vocabulary of insurance policy clauses.
Explicitly swappable later — `retrieval.py`/`vector_store.py` only
consume fixed-length float vectors, so replacing `embed_text()` with a
hosted embedding call is a one-file change.

## 2026-07-05 — LangGraph nodes wrap existing services; damage
## assessment/pricing are idempotent no-ops when already computed

The claim workflow graph (`app/graph/`) never reimplements vehicle
validation, damage detection, multi-image merge, or pricing — those
already work (`AIServiceClient`, `cost_model.pricing_service`) and are
already tested. Graph nodes for those stages check whether the result is
already on the incoming state and skip all I/O if so — the graph runs
after `POST /claims/{id}/analyze` has already produced `ai_assessment`/
`pricing_assessment` the normal way, so re-running the workflow (e.g.
once more after a policy finishes processing) never re-triggers YOLO
inference or an extra ai-service call.

## 2026-07-05 — No public review-item resolution endpoint yet

The manual review queue (`app/db/models/review_item.py`) has no HTTP
route that resolves an item. There is no reviewer/admin role system in
this codebase — only claimant Google accounts — so exposing a resolve
endpoint now would be an unauthenticated (or, worse, claimant-authenticated)
write into another user's claim's review state. Built the clean
data/service boundary (`ReviewItemRepository.resolve()`) for whenever a
real reviewer role exists, without the insecure public surface.
