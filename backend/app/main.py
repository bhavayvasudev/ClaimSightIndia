"""
FastAPI entrypoint. Deliberately minimal at this stage of the build — this
step is repository structure + the shared ClaimState schema. The claim
intake route, the LangGraph supervisor wiring, and the agent nodes come in
the next steps.
"""

from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ClaimSight India",
    description="Multimodal AI claims triage copilot for Indian motor insurers",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
