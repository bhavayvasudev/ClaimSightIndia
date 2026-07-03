# Evaluation framework

- `golden_dataset/` — hand-curated claim bundles (photos + policy PDF +
  description + `expected_output.json`). Start with ~15-20 claims covering
  each severity level, at least one flood-damage case, one total-loss case,
  and one deliberately inconsistent case (for fraud-detection recall).
- `metrics/` — per-agent scoring: OCR exact-match rate for the Vehicle
  Verification agent, damage-type/severity accuracy for the Vision agent,
  cost-estimate MAE against the golden range for the Cost Estimation agent,
  precision/recall on `fraud_risk` for the Fraud Detection agent.
- `run_regression.py` — replays the golden dataset through the graph and
  fails CI if agent-level accuracy regresses past a threshold. Reads
  `ClaimState.agent_runs` off each run for latency and
  `total_cost_usd` for cost — those fields exist specifically so this
  script doesn't need separate instrumentation.
- `reports/` — generated run output (gitignored).
