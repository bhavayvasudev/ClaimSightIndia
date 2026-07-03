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
