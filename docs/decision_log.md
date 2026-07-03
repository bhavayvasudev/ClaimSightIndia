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

## 2026-07-03 — Fixed `DamageType` enum, not open vocabulary

The Vision Agent's underlying HF model may output free-text labels, but
`DamageType` is a closed enum matching the spec's five categories plus
`OTHER`. Cost Estimation feeds `damage_type` into XGBoost as a categorical
feature — an open vocabulary would make that feature useless without a
separate mapping layer, so the mapping happens once, at the Vision Agent
boundary, not downstream.
