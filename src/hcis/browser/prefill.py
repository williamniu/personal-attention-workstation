from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup

SENSITIVE_TERMS = (
    "authorization",
    "sponsorship",
    "citizenship",
    "nationality",
    "disability",
    "veteran",
    "demographic",
    "salary",
    "non-compete",
    "background check",
    "export control",
    "security clearance",
    "attestation",
)
SAFE_FIELDS = {"name", "first_name", "last_name", "email", "phone", "city", "state"}


@dataclass(frozen=True)
class FormField:
    name: str
    label: str
    field_type: str


@dataclass(frozen=True)
class ApplyPage:
    fields: list[FormField]
    has_mfa: bool
    has_captcha: bool


@dataclass(frozen=True)
class PrefillPlan:
    safe_values: dict[str, str]
    waiting_for_human: tuple[str, ...]
    status: str


def parse_apply_page(html: str) -> ApplyPage:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    fields = []
    for element in soup.select("input, textarea, select"):
        name = str(element.get("name") or element.get("id") or "")
        if not name:
            continue
        element_id = element.get("id")
        label = soup.find("label", attrs={"for": str(element_id)}) if element_id else None
        fields.append(
            FormField(
                name=name,
                label=label.get_text(" ", strip=True) if label else name.replace("_", " "),
                field_type=str(element.get("type", element.name)),
            )
        )
    return ApplyPage(
        fields=fields,
        has_mfa="multi-factor authentication" in text or "verification code" in text,
        has_captcha="captcha" in text or "recaptcha" in text,
    )


def build_prefill_plan(page: ApplyPage, profile_values: dict[str, str]) -> PrefillPlan:
    if page.has_mfa:
        return PrefillPlan({}, tuple(field.name for field in page.fields), "PAUSED_MFA")
    if page.has_captcha:
        return PrefillPlan({}, tuple(field.name for field in page.fields), "PAUSED_CAPTCHA")
    safe: dict[str, str] = {}
    waiting: list[str] = []
    for field in page.fields:
        description = f"{field.name} {field.label}".lower()
        if any(term in description for term in SENSITIVE_TERMS) or field.name not in SAFE_FIELDS:
            waiting.append(field.name)
        elif field.name in profile_values:
            safe[field.name] = profile_values[field.name]
    return PrefillPlan(safe, tuple(waiting), "WAITING_FOR_HUMAN" if waiting else "PREFILL_READY")
