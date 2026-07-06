# ClaimSight India

AI-assisted motor insurance claims triage for the Indian market. A
claimant signs in with Google, enters vehicle details, and uploads damage
photos; ClaimSight validates the photos, detects damaged parts with a
YOLO-based vision pipeline, estimates severity and an indicative INR
repair range, optionally reads the claimant's policy document, and
produces a structured claim report (in-app and PDF). Anything the system
isn't confident about is routed for manual review instead of guessed at.

Solo build. Prioritizes a working, honest end-to-end pipeline: structured
Pydantic contracts everywhere, graceful degradation when a stage fails,
and human review checkpoints on uncertain findings.

## Current MVP features

These work today, end to end:

- **Google OAuth sign-in** (Auth.js/NextAuth on the frontend, exchanged
  server-side for a backend-issued JWT; the only active auth provider)
- **Persisted user profiles** and server-side claim ownership — every
  claim route is authenticated, and users can only ever see their own claims
- **Claim intake**: manufacturer → model → year, backed by a versioned
  India passenger-vehicle catalog (category is derived from the model)
- **Damage photo upload** with MIME/size/decode validation, and
  **vehicle-presence validation** that rejects non-vehicle photos with
  the exact filename and reason
- **Real YOLO-based damage analysis** (separate FastAPI ai-service):
  damaged-part detection, severity classification, confidence handling,
  multi-image result merging, and Accepted / Review Required statuses
- **Category-aware repair pricing** in INR — unpriced parts show
  "Manual Inspection Required", never a fake ₹0
- **Optional policy upload** (PDF/photo) with OCR/extraction, structured
  policy facts (insurer, type, coverage dates, IDV, deductible,
  exclusions — policy number always masked), and clause-grounded
  coverage findings per damaged part
- **Risk assessment** with neutral, explainable signals
- **Claim timeline, notifications, claim history dashboard**
- **Unified claim report** in-app and as a **PDF export** with the same
  fields
- **Reference vehicle images**: resolved per make/model via the
  Wikimedia API (no API key), downloaded once, validated, stored and
  served by the backend itself; a neutral category illustration is the
  deliberate fallback. Never the claimant's own photos, never used in
  analysis.

Deliberate MVP behaviors:

- Damage photos are processed for analysis and **not retained** — old
  claims re-display their stored results, not the original photos.
- Policy documents **are retained** so policy analysis can be re-displayed.
- Repair figures are indicative estimates, not quotations, and coverage
  findings reflect the uploaded policy's wording, not an insurer decision.

## Future roadmap

Documented, not implemented:

- Number plate OCR and registration cross-checks
- Richer policy RAG with clause-level citations in the UI
- Advanced fraud intelligence beyond the current risk signals
- Improved repair-cost models trained on real repair data
- Workshop/region-aware pricing
- Human surveyor review workflow (assignment, queues, sign-off)
- Advanced agent orchestration
- Model monitoring and drift analysis
- Larger benchmark/evaluation datasets

## Repository layout

```
backend/                    FastAPI application backend (:8000)
  app/
    main.py                 Entrypoint, middleware, CORS, security headers
    config.py               Settings (env-driven, pydantic-settings)
    api/routes/             claims, policy, reports, notifications,
                            users, vehicle_catalog, vehicle_images
    core/                   Auth (Google OIDC verify, backend JWT), rate limits
    schemas/                Pydantic contracts (claim_state.py is the core one)
    graph/                  Claim workflow orchestration + one node per stage
    services/               ai_client, claim_service, policy (OCR/RAG),
                            pricing (cost_model), risk, report (incl. PDF),
                            vehicle_catalog, vehicle_reference, notifications
    db/                     SQLAlchemy models + repositories
  data/                     Persisted uploads (policies/) and vehicle_images/
  tests/                    Unit + route-level integration tests

ai-service/                 YOLO vision pipeline (FastAPI, :8500)
frontend/                   Next.js 15 app (:3000) — Auth.js, dashboard,
                            claim intake, claim report, docs
scripts/                    dev_up.sh, check_frontend_secrets.py
infra/                      docker-compose for Postgres/pgvector (optional;
                            dev runs on SQLite out of the box)
docs/                       architecture and decision notes
evaluation/                 evaluation harness scaffolding
```

## Quickstart (development)

Three processes run side by side: backend (:8000), ai-service (:8500) and
frontend (:3000). The backend proxies claim analysis to the ai-service
(`AI_SERVICE_URL`, default `http://localhost:8500`) — if the ai-service
isn't running, `POST /claims/{id}/analyze` returns
503 "AI service is currently unavailable" while everything else keeps
working. Start the ai-service before exercising claim analysis.

Backend (SQLite by default, no external DB needed):

```bash
cd backend
pip install -e ".[dev]"
cp .env.example .env        # set AUTH_GOOGLE_ID + BACKEND_JWT_SECRET at minimum
uvicorn app.main:app --port 8000
```

ai-service (YOLO models under ai-service/models/ — run from inside
ai-service/, the model paths are relative to it):

```bash
cd ai-service
pip install -r requirements.txt
uvicorn main:app --port 8500
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env.local  # AUTH_SECRET, AUTH_GOOGLE_ID/SECRET, NEXT_PUBLIC_API_BASE_URL
npm run dev                 # http://localhost:3000
```

Health checks: `GET :8000/health` (liveness), `GET :8000/ready`
(DB reachability).

## Tests and checks

```bash
cd backend && pytest                 # backend unit + integration tests
cd frontend && npm test              # auth-callback regression tests (vitest)
cd frontend && npx tsc --noEmit      # typecheck
cd frontend && npm run lint
cd frontend && npm run build
python scripts/check_frontend_secrets.py   # no secrets in frontend source
```

## Notes

- Secrets live in `backend/.env` / `frontend/.env.local` only. The single
  `NEXT_PUBLIC_*` variable is the backend base URL, which is public by
  design. The ai-service URL is backend-only.
- No accuracy guarantees, regulatory approvals, or insurer partnerships
  are claimed. ClaimSight assists triage; it does not adjudicate claims.
