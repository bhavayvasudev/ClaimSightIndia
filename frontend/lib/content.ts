export const metrics = [
  { value: 80, suffix: "%", label: "Faster triage", detail: "From days of manual review to minutes of structured analysis." },
  { value: 60, suffix: "%", label: "Better fraud detection", detail: "Cross-modal signals surface inconsistencies humans miss." },
  { value: 100, suffix: "%", label: "Audit-ready reports", detail: "Every finding traced back to its evidence, every time." },
];

export const problemStats = [
  { value: "15–30", unit: "days", label: "Average motor claim settlement time in India" },
  { value: "1 in 10", unit: "claims", label: "Carry fraud signals that manual review misses" },
  { value: "4+", unit: "documents", label: "Photos, policies, RC numbers and narratives — reviewed by hand" },
];

export const workflowSteps = [
  {
    index: "01",
    title: "Upload claim",
    description: "Vehicle photos, policy PDF, registration number, and the accident narrative.",
  },
  {
    index: "02",
    title: "AI verification",
    description: "Registration OCR and policy details are cross-checked against the claim.",
  },
  {
    index: "03",
    title: "Risk & cost analysis",
    description: "Damage severity, fraud signals, and repair cost bands are estimated.",
  },
  {
    index: "04",
    title: "Generate report",
    description: "A structured triage report is compiled with every finding traced to evidence.",
  },
  {
    index: "05",
    title: "Human review",
    description: "An adjuster confirms or overrides the recommendation before payout.",
  },
];

export const agents = [
  {
    name: "Vehicle Verification",
    description: "Reads registration plates and confirms make, model, and ownership.",
    glyph: "plate",
  },
  {
    name: "Policy Analysis",
    description: "Retrieves coverage terms, exclusions, and limits from the policy PDF.",
    glyph: "document",
  },
  {
    name: "Damage Assessment",
    description: "Localizes and grades damage severity across submitted photos.",
    glyph: "scan",
  },
  {
    name: "Cost Estimation",
    description: "Predicts a repair cost band from damage extent and part pricing.",
    glyph: "rupee",
  },
  {
    name: "Fraud Detection",
    description: "Flags inconsistencies between narrative, imagery, and policy history.",
    glyph: "shield",
  },
  {
    name: "Report Generation",
    description: "Synthesizes every agent's findings into one audit-ready report.",
    glyph: "report",
  },
];
