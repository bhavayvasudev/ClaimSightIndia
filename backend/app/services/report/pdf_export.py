"""PDF claim report export (Task 11).

Renders exclusively from the already-persisted `UnifiedClaimReport` (see
`report_service.build_unified_report`) — never from anything a browser
client sends, and never anything beyond what that model exposes. That
model is itself already curated to only the fields safe to show a
claimant (no access tokens, no internal service URLs, no raw model
confidence thresholds, no stack traces) — see its docstring — so this
module has nothing further to filter; it only has to render.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fpdf import FPDF, XPos, YPos

from app.schemas.policy_state import TimelineStage, UnifiedClaimReport

_DISCLAIMER = (
    "Repair cost estimates in this report are preliminary and indicative, not a final "
    "insurer-approved figure. AI analysis assists claim triage; results depend on photo "
    "quality and available policy text, and uncertain findings are deliberately routed for "
    "manual inspection rather than guessed at. Policy coverage interpretation reflects "
    "retrieved policy wording only and is not the insurer's final adjudication of this claim."
)


class _ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "ClaimSight India", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 6, "Vehicle Claim Triage Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def section_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(240, 240, 245)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(1)
        self.set_font("Helvetica", "", 10)

    def kv(self, label: str, value: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self.cell(50, 6, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 10)
        available_width = self.w - self.r_margin - self.get_x()
        self.multi_cell(available_width, 6, value or "-", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def body_text(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def generate_claim_report_pdf(report: UnifiedClaimReport, timeline: list[TimelineStage]) -> bytes:
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.kv("Claim ID:", report.claim_id)
    pdf.kv("Generated:", datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"))
    pdf.ln(3)

    pdf.section_title("Vehicle Information")
    vehicle_line = " ".join(
        v for v in (report.vehicle.make, report.vehicle.model, str(report.vehicle.year or "")) if v
    ) or report.vehicle.category
    pdf.kv("Vehicle:", vehicle_line)
    pdf.kv("Category:", report.vehicle.category)
    pdf.ln(3)

    pdf.section_title("Damage Assessment")
    pdf.kv("Damaged parts:", str(report.damage.damaged_parts))
    pdf.kv("Automatically assessed:", str(report.damage.accepted))
    pdf.kv("Manual inspection required:", str(report.damage.review_required))
    if report.damage.overall_severity:
        pdf.kv("Overall severity:", report.damage.overall_severity)
    if report.damage.recommended_actions:
        pdf.kv("Recommended actions:", ", ".join(report.damage.recommended_actions))
    pdf.ln(3)

    pdf.section_title("Repair Estimate")
    if report.pricing.parts_priced > 0 and report.pricing.total_min_inr is not None:
        pdf.kv(
            "Estimated range:",
            f"Rs. {report.pricing.total_min_inr:,} - Rs. {report.pricing.total_max_inr:,} (indicative)",
        )
    else:
        pdf.kv("Estimated range:", "Pending manual inspection")
    if report.pricing.parts_pending_manual_inspection:
        pdf.kv("Parts pending manual inspection:", str(report.pricing.parts_pending_manual_inspection))
    pdf.ln(3)

    pdf.section_title("Policy Analysis")
    pdf.kv("Status:", report.policy.state.value.replace("_", " ").title())
    if report.policy.coverage:
        pdf.kv("Overall coverage interpretation:", report.policy.coverage.overall_status.value.replace("_", " ").title())
        pdf.body_text(report.policy.coverage.summary)
    if report.policy.deductible_inr is not None:
        pdf.kv("Deductible:", f"Rs. {report.policy.deductible_inr:,}")
    if report.policy.idv_inr is not None:
        pdf.kv("IDV:", f"Rs. {report.policy.idv_inr:,}")
    if report.policy.exclusions:
        pdf.kv("Exclusions on file:", "; ".join(report.policy.exclusions[:8]))
    pdf.ln(3)

    if report.policy.coverage and report.policy.coverage.part_assessments:
        pdf.section_title("Coverage Findings")
        for pa in report.policy.coverage.part_assessments:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(
                0, 6, f"{pa.part}: {pa.coverage_status.value.replace('_', ' ').title()}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, pa.reason, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            for clause in pa.relevant_clauses[:2]:
                loc = f"p.{clause.page}" if clause.page else ""
                sec = f" ({clause.section})" if clause.section else ""
                pdf.set_font("Helvetica", "I", 9)
                pdf.multi_cell(
                    0, 5, f"  {loc}{sec}: {clause.excerpt[:220]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT
                )
            pdf.ln(1)
        pdf.ln(2)

    pdf.section_title("Risk Signals")
    pdf.kv("Risk level:", report.risk.risk_level.value.replace("_", " ").title())
    if report.risk.signals:
        for signal in report.risk.signals:
            pdf.body_text(f"- [{signal.severity.value.upper()}] {signal.description}")
    else:
        pdf.body_text("No risk signals were raised.")
    pdf.ln(3)

    review_stages = [s for s in timeline if s.status.value == "needs_attention"]
    if review_stages:
        pdf.section_title("Review Required")
        for stage in review_stages:
            pdf.body_text(f"- {stage.label}: {stage.detail or 'Needs manual review.'}")
        pdf.ln(3)

    pdf.section_title("Claim Summary")
    pdf.body_text(report.summary)
    pdf.ln(4)

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 5, _DISCLAIMER, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
