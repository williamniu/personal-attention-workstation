from __future__ import annotations


def build_opportunity_alert(
    candidate: str,
    lane: str,
    title: str,
    company: str,
    location: str,
    apply_url: str,
    sponsorship: str,
    evidence: list[str],
) -> dict[str, object]:
    unknown = sponsorship in {"UNKNOWN_NEEDS_VERIFICATION", "UNVERIFIED_HIGH_POTENTIAL"}
    lines = [
        f"Role: {title} — {company} — {location}",
        f"Apply: {apply_url}",
        f"Action lane: {lane}",
        f"Sponsorship: {sponsorship}",
        "Evidence:",
        *[f"- {item}" for item in evidence],
    ]
    if unknown:
        lines.append("UNKNOWN — HUMAN VERIFICATION REQUIRED")
    return {
        "subject": f"[HCIS][{candidate.title()}][{lane.split('_', 1)[0]}] {title} — {company}",
        "body": "\n".join(lines),
    }
