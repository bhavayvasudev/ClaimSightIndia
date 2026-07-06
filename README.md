# ClaimSight India

AI-assisted vehicle damage assessment and insurance claim triage.

ClaimSight India analyzes vehicle damage photos, identifies affected vehicle parts, estimates damage severity and repair cost ranges, flags uncertain detections for manual review, and generates structured claim reports.

The system combines computer vision, vehicle-aware pricing, policy document analysis, and a complete claim management workflow into a single platform.

---

## Overview

Traditional vehicle claim assessment involves multiple manual steps: collecting evidence, inspecting visible damage, identifying affected parts, estimating repair costs, reviewing policy information, and preparing a structured report.

ClaimSight provides an AI-assisted first-pass assessment workflow.

A user can:

1. Sign in securely with Google.
2. Select their vehicle manufacturer, model, and year.
3. Upload one or more vehicle damage photos.
4. Optionally attach an insurance policy document.
5. Run an AI-assisted damage assessment.
6. Review detected damaged parts and severity.
7. View estimated repair cost ranges.
8. Identify detections requiring manual inspection.
9. Review policy and risk analysis where available.
10. Access saved claims, timelines, notifications, and reports from the dashboard.

ClaimSight is designed as a decision-support and triage system. Uncertain detections are explicitly surfaced for manual review rather than being presented as definitive conclusions.

---

## Current MVP Features

### Vehicle Damage Analysis

- Multi-image vehicle damage assessment
- Vehicle presence validation before damage inference
- Damaged-part identification
- Damage severity classification
- Per-detection confidence handling
- Multi-image result merging
- Representative observation selection
- Explicit `Review Required` states for uncertain detections
- Manual inspection recommendations
- Rejection of non-vehicle image submissions

The current vision pipeline uses trained object detection models to analyze uploaded vehicle images and associate visible damage with detected vehicle parts.

---

### Vehicle-Aware Claim Intake

ClaimSight includes a structured Indian vehicle catalog with support for current and historical manufacturers and models.

The claim intake flow supports:

- Searchable manufacturer selection
- Dependent model selection
- Manufacture year validation
- Automatic vehicle category synchronization
- Support for discontinued and historical India-market vehicles

Vehicle categories are used by the repair estimation system to avoid applying identical repair assumptions across fundamentally different vehicle classes.

---

### Repair Cost Estimation

Repair estimates are generated using a backend-owned pricing service.

Estimation considers:

- Vehicle category
- Damaged part
- Severity
- Recommended repair action

Supported pricing categories include:

- Hatchback
- Sedan
- SUV
- Luxury Car
- Bus
- Truck
- Commercial Vehicle

The pricing layer is intentionally separated from the AI inference service.

The AI service determines visible damage characteristics. The backend applies business logic and pricing rules.

> Repair estimates are indicative ranges, not final workshop quotations. Actual costs may vary based on location, labour rates, parts availability, taxes, workshop selection, and vehicle condition.

---

### Multi-Image Claim Analysis

Multiple images of the same vehicle can be analyzed as a single claim.

For each damaged part, ClaimSight:

- Groups observations across images
- Tracks the images in which the part was detected
- Selects one representative observation
- Preserves severity, percentage, confidence, status, and action from the same observation
- Separately records aggregate confidence metadata

This avoids combining a damage percentage from one image with an unrelated confidence score from another.

---

### Insurance Policy Analysis

Users may optionally attach a supported insurance policy document during claim assessment.

The policy workflow supports:

- Document upload
- Text extraction
- Structured policy information extraction
- Policy processing states
- Coverage analysis
- Manual-review states for uncertain policy interpretation

Where available, the interface can surface information such as:

- Insurer
- Masked policy number
- Policy type
- Policy coverage dates
- Insured Declared Value
- Deductible information
- Extracted vehicle information
- Coverage interpretation
- Relevant policy notes

Policy upload is optional. Damage analysis can proceed without a policy document.

---

### Claim Management

Authenticated users can:

- Create claims
- Analyze uploaded damage images
- View saved assessments
- Reopen previous claims
- Track claim status
- View claim timelines
- Receive application notifications
- Access structured reports
- Generate PDF reports

Claims are associated with persisted user profiles and protected by server-side ownership checks.

---

### Authentication

The current MVP supports Google OAuth authentication.

On first sign-in, ClaimSight creates or updates a backend user profile using the authenticated identity.

Stored profile information includes only the information required by the application, such as:

- Name
- Email
- Profile image
- Provider identity reference

OAuth tokens are not stored as user profile data.

Protected claim operations require authenticated backend authorization.

---

## Assessment Statuses

### Analysis Complete

The automated assessment completed and the current detections did not require additional manual review.

### Review Required

The assessment completed successfully, but one or more detected areas require manual inspection.

This is not a system failure.

ClaimSight intentionally separates uncertain observations from accepted detections instead of forcing low-confidence results into definitive classifications.

### Processing

The claim is currently moving through one or more assessment stages.

### Failed

The assessment could not be completed because of a processing or service error.

---

## System Architecture

```text
┌─────────────────────┐
│    Next.js Client   │
│                     │
│  Auth · Dashboard   │
│  Claims · Reports   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   FastAPI Backend   │
│                     │
│  Auth Verification  │
│  Claim Management   │
│  Pricing            │
│  Policy Processing  │
│  Reports            │
│  Notifications      │
│  Persistence        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  AI Inference API   │
│                     │
│  Vehicle Validation │
│  Damage Detection   │
│  Part Detection     │
│  Severity Analysis  │
│  Result Merging     │
└─────────────────────┘
```

The architecture deliberately separates inference from application business logic.

### Frontend

Responsible for:

- Authentication experience
- Claim intake
- Image upload
- Dashboard
- Assessment visualization
- Policy analysis presentation
- Timeline and report interfaces

### Backend

Responsible for:

- Authenticated API access
- User persistence
- Claim ownership
- Claim orchestration
- Vehicle catalog
- Pricing logic
- Policy processing
- Reporting
- Notifications
- Persistent application state

### AI Service

Responsible for:

- Vehicle presence validation
- Vehicle damage detection
- Vehicle part detection
- Part-to-damage matching
- Severity assessment
- Multi-image result aggregation

The AI service does not own repair pricing business logic.

---

## Technology Stack

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Framer Motion
- Auth.js

### Backend

- FastAPI
- Python
- Pydantic
- SQLAlchemy
- PostgreSQL
- SQLite for lightweight local development and testing
- Alembic

### AI and Computer Vision

- Python
- Ultralytics YOLO
- OpenCV
- Custom damage-analysis pipeline

### Testing and Quality

- Pytest
- Backend integration tests
- Schema contract tests
- AI merge regression tests
- TypeScript type checking
- ESLint
- Production build verification
- Frontend secret-pattern scanning

---

## Repository Structure

```text
ClaimSight-India/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── public/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── data/
│   │   ├── db/
│   │   ├── schemas/
│   │   └── services/
│   ├── migrations/
│   └── tests/
│
├── ai-service/
│   ├── main.py
│   ├── pipeline.py
│   └── tests/
│
├── evaluation/
│
└── README.md
```

---

## Local Development

### 1. Clone the repository

```bash
git clone github.com/bhavayvasudev/ClaimSightIndia
cd ClaimSightIndia
```

### 2. Start the AI Service

```bash
cd ai-service
python -m venv .venv
```

Activate the environment.

#### Windows

```bash
.venv\Scripts\activate
```

#### macOS/Linux

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the service:

```bash
uvicorn main:app --reload --port 8500
```

### 3. Start the Backend

Open another terminal:

```bash
cd backend
python -m venv .venv
```

Activate the environment and install dependencies according to the backend project configuration.

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

The backend communicates with the AI service through a server-side service URL.

### 4. Start the Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs locally on port `3000` by default.

---

## Environment Variables

Use the provided environment example files as templates.

Do not commit real secrets.

The frontend may contain public configuration such as the backend API base URL.

Private credentials must remain server-side.

Examples of values that must never be exposed through `NEXT_PUBLIC_*` variables include:

- OAuth client secrets
- Authentication signing secrets
- Backend JWT signing secrets
- Database credentials
- Private AI provider keys
- Private storage credentials

The intended trust boundary is:

```text
Browser
   │
   ▼
ClaimSight Backend
   │
   ▼
Private External Services
```

The browser should never receive private service credentials.

---

## API Overview

The platform exposes APIs for:

- Users
- Claims
- Claim analysis
- Vehicle catalog
- Policy processing
- Reports
- Timelines
- Notifications

Protected claim resources require authentication and server-side ownership validation.

For detailed development schemas and current endpoint contracts, use the API documentation exposed by the running backend development environment.

---

## Validation Philosophy

ClaimSight does not treat every model prediction equally.

The pipeline distinguishes between:

- Accepted detections
- Uncertain observations
- Manual-review candidates

Low-confidence observations can still be useful for triage, but they should not automatically become definitive claim conclusions.

The system therefore preserves uncertainty as part of the product workflow.

---

## Security Principles

The MVP follows several security boundaries:

- Google OAuth authentication
- Backend authorization for private resources
- Server-side claim ownership validation
- Restricted file types
- Vehicle-image validation
- Bounded external service calls
- Backend-only private credentials
- No private API keys in frontend bundles
- No OAuth token persistence in user profile records
- Controlled error responses
- Temporary file cleanup

Security is treated as part of the application architecture rather than a frontend-only concern.

---

## Limitations

ClaimSight is an AI-assisted assessment and triage system.

Current limitations include:

- Visible damage may differ from internal mechanical or structural damage
- Image quality and camera angle affect detection quality
- Repair estimates are indicative ranges
- Unusual vehicle modifications may affect part recognition
- Uncertain detections may require manual inspection
- Policy interpretation depends on document quality and available policy information

The platform is not a replacement for qualified surveyors, repair professionals, insurers, or legally binding claim decisions.

---

## Future Roadmap

The following items are planned research and development directions and are not presented as current MVP functionality.

### Computer Vision

- Number plate OCR
- Broader damage taxonomy
- Improved segmentation-based damage measurement
- Larger multi-condition evaluation datasets
- Model drift monitoring
- Expanded vehicle-part coverage

### Policy Intelligence

- Richer retrieval-augmented policy analysis
- Clause-level evidence and citations
- Improved policy comparison
- Structured coverage conflict detection

### Repair Intelligence

- Repair-cost models trained on real repair datasets
- Workshop-aware pricing
- Region-aware labour pricing
- Parts availability signals
- Insurer-specific estimation workflows

### Claim Intelligence

- Advanced fraud signal analysis
- Duplicate damage detection
- Historical claim pattern analysis
- Richer external risk signals

### Human Review

- Surveyor review workspace
- Assignment and escalation workflows
- AI-to-human review queues
- Reviewer feedback loops
- Model evaluation from reviewer corrections

### Platform Engineering

- Advanced workflow orchestration
- Production model monitoring
- Inference performance analytics
- Larger automated benchmark suites
- Expanded observability and tracing

---

## Disclaimer

ClaimSight India is currently an AI-assisted claim assessment and triage platform.

Damage assessments, severity classifications, policy interpretations, and repair estimates are generated for assistance and preliminary evaluation. They should not be considered final insurance decisions, legal interpretations, or guaranteed repair quotations.

Human inspection may be required where the system identifies uncertainty or where physical inspection is necessary.

---

## Contributing

Contributions, issue reports, and technical discussions are welcome.

Before contributing, please review the repository structure and avoid mixing application business logic into the AI inference service.

Keep changes focused, tested, and consistent with the separation between:

- Inference
- Business logic
- Application state
- Presentation

Built as an exploration of practical AI-assisted vehicle claim assessment, with a focus on uncertainty-aware automation rather than replacing human judgment.
