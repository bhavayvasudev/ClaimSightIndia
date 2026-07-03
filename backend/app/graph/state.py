"""
Re-exports ClaimState as the LangGraph state schema.

Kept as a separate one-line module (rather than importing
`app.schemas.claim_state.ClaimState` directly in every node) so that if the
graph ever needs a state shape that diverges from the API-facing schema
(e.g. extra internal-only routing fields), that divergence has one obvious
place to happen without touching every node file's imports.
"""

from app.schemas.claim_state import ClaimState

__all__ = ["ClaimState"]
