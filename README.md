# ClaimSight India

Multimodal AI-powered motor insurance claims triage copilot for Indian
insurers. Ingests vehicle damage photos, policy PDFs, registration numbers,
and free-text accident descriptions; produces a structured claim triage
report via a LangGraph supervisor of specialist agents.

Solo, one-month build. Prioritizes a working end-to-end pipeline over
polish, while staying honest about production concerns: structured
Pydantic contracts everywhere, graceful degradation when an agent fails,
human review checkpoints on high-risk claims, and cost/latency
observability built into the shared state from day one.

## Repository layout

```
backend/                   FastAPI + LangGraph + Pydantic
  app/
    main.py                FastAPI entrypoint
    config.py               Settings (env-driven, pydantic-settings)
    api/routes/              HTTP layer — claims intake, review, health
    schemas/
      claim_state.py         *** THE shared ClaimState — read this first ***
    graph/
      state.py                Re-exports ClaimState as the LangGraph state
      supervisor.py            Graph wiring + conditional routing (next)
      nodes/                   One file per agent (next)
    services/
      claude_client.py         Anthropic SDK wrapper, structured outputs
      ocr_service.py           EasyOCR/PaddleOCR wrapper
      vision_model.py          HF damage-detection model wrapper
      rag/                     LlamaIndex ingestion + retrieval over policy PDFs
      weather_api.py           Fraud cross-check
      cost_model/               XGBoost training + inference
      storage.py                Upload file persistence
    db/                        SQLAlchemy models, pgvector tables
    observability/              Langfuse client + tracing helpers
  tests/
    unit/test_claim_state.py    Schema contract tests — start here to see it run

evaluation/                 Golden dataset + regression harness + metrics
frontend/                   Next.js dashboard (upload, description, report view)
infra/                      docker-compose.yml, Postgres/pgvector init
docs/                       architecture.md, decision_log.md (ADRs)
scripts/                    dev_up.sh and one-off tooling
```

## Why this shape

- **`schemas/claim_state.py` is the contract every agent, the API, the
  frontend, and the evaluation harness all agree on.** It's written and
  tested before any agent logic exists, on purpose — get the shared state
  right first, and each agent becomes "read these fields, write that field."
- **`graph/nodes/` mirrors the six agents in the spec 1:1** (vehicle
  verification, policy, vision, cost estimation, fraud detection, report).
  Each node file will import only the `ClaimState` slice it needs.
- **`services/` holds anything that talks to the outside world** (Claude
  API, OCR models, vector search, weather API, the XGBoost model). Nodes
  stay thin — they call a service and map the result onto `ClaimState`.
- **`evaluation/` and `observability/` exist from the start**, not bolted
  on at the end, because `ClaimState.agent_runs` (latency, tokens, cost per
  node) is designed to feed both simultaneously.

See `docs/architecture.md` for the graph diagram and data flow, and
`docs/decision_log.md` for the reasoning behind specific schema choices
(e.g. why money is `int` rupees, not formatted strings).

## Quickstart

```bash
cp .env.example .env    # fill in ANTHROPIC_API_KEY at minimum
./scripts/dev_up.sh     # starts Postgres+pgvector, backend (:8000), frontend (:3000)
```

Backend health check: `curl http://localhost:8000/health`

Run the schema contract tests:

```bash
cd backend
pip install -e ".[dev]"
pytest tests/unit/test_claim_state.py -v
```

## Status

- [x] Repository structure
- [x] Shared `ClaimState` schema (Pydantic, tested, JSON round-trip verified)
- [ ] LangGraph supervisor wiring
- [ ] Vehicle Verification Agent (OCR)
- [ ] Policy Agent (RAG over policy PDF)
- [ ] Vision Agent (damage detection)
- [ ] Cost Estimation Agent (XGBoost)
- [ ] Fraud Detection Agent
- [ ] Report Agent
- [ ] Human review checkpoint + API
- [ ] Langfuse tracing
- [ ] Evaluation framework + golden dataset
- [ ] Frontend dashboard
