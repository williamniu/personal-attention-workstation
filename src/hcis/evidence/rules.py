from __future__ import annotations

from dataclasses import dataclass

from hcis.evidence.schema import JDExtraction, TriState

NEGATIVE = (
    "do not sponsor",
    "does not sponsor",
    "will not sponsor",
    "unable to sponsor",
    "no visa sponsorship",
    "not eligible for sponsorship",
    "must not require sponsorship now or in the future",
    "must be authorized without current or future sponsorship",
)
TRANSFER_ONLY = (
    "h-1b transfer may be considered",
    "must already hold h-1b status",
    "existing h-1b holders only",
    "h-1b transfers only",
)
POSITIVE = (
    "visa sponsorship available",
    "h-1b sponsorship offered",
    "we sponsor opt",
    "we sponsor stem opt",
    "eligible for future h-1b sponsorship",
)


@dataclass(frozen=True)
class ExtractionOutcome:
    extraction: JDExtraction
    status: str
    conflicting_fields: tuple[str, ...] = ()


def extract_rules(text: str) -> JDExtraction:
    lowered = " ".join(text.lower().split())
    matched_negative = [phrase for phrase in NEGATIVE if phrase in lowered]
    matched_transfer = [phrase for phrase in TRANSFER_ONLY if phrase in lowered]
    matched_positive = [phrase for phrase in POSITIVE if phrase in lowered]
    extraction = JDExtraction(
        evidence_quotes=matched_negative + matched_transfer + matched_positive
    )
    if matched_negative:
        extraction.future_sponsorship = TriState.NO
        extraction.confidence = 0.99
    elif matched_transfer:
        extraction.first_time_h1b = TriState.NO
        extraction.h1b_transfer = TriState.YES
        extraction.confidence = 0.98
    elif matched_positive:
        extraction.future_sponsorship = TriState.YES
        if "h-1b sponsorship offered" in matched_positive:
            extraction.first_time_h1b = TriState.YES
        extraction.confidence = 0.95
    if "u.s. citizenship required" in lowered or "us citizenship required" in lowered:
        extraction.citizenship_required = TriState.YES
        extraction.evidence_quotes.append("U.S. citizenship required")
        extraction.confidence = max(extraction.confidence, 0.99)
    if "security clearance required" in lowered:
        extraction.security_clearance_required = TriState.YES
        extraction.evidence_quotes.append("security clearance required")
        extraction.confidence = max(extraction.confidence, 0.99)
    return extraction


def combine_rule_and_llm(rule: JDExtraction, llm: JDExtraction) -> ExtractionOutcome:
    fields = (
        "future_sponsorship",
        "first_time_h1b",
        "first_available_lottery",
        "h1b_transfer",
        "opt_supported",
        "stem_opt_supported",
        "citizenship_required",
        "security_clearance_required",
    )
    conflicts = tuple(
        field
        for field in fields
        if getattr(rule, field) != TriState.UNKNOWN
        and getattr(llm, field) != TriState.UNKNOWN
        and getattr(rule, field) != getattr(llm, field)
    )
    if conflicts:
        return ExtractionOutcome(rule, "CONFLICTING", conflicts)
    merged = rule.model_copy(deep=True)
    for field in fields:
        if getattr(merged, field) == TriState.UNKNOWN:
            setattr(merged, field, getattr(llm, field))
    merged.evidence_quotes = list(dict.fromkeys(rule.evidence_quotes + llm.evidence_quotes))
    merged.confidence = max(rule.confidence, llm.confidence)
    return ExtractionOutcome(merged, "CLASSIFIED")
