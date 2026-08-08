from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import StrEnum


def normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    return value.lower().removeprefix("https://").removeprefix("http://").split("/")[0]


def normalize_name(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


class ResolutionStatus(StrEnum):
    MATCHED = "MATCHED"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NEW_COMPANY = "NEW_COMPANY"


@dataclass
class CompanyIdentity:
    company_id: str
    canonical_name: str
    brand_name: str | None = None
    official_domain: str | None = None
    legal_name: str | None = None
    address: str | None = None
    tax_id_last4: str | None = None
    naics: str | None = None
    ats_ids: set[str] = field(default_factory=set)
    human_aliases: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class CompanyQuery:
    name: str
    official_domain: str | None = None
    legal_name: str | None = None
    address: str | None = None
    tax_id_last4: str | None = None
    naics: str | None = None
    ats_id: str | None = None


@dataclass(frozen=True)
class ResolutionDecision:
    status: ResolutionStatus
    company_id: str | None
    reason: str
    candidate_ids: tuple[str, ...] = ()


class EntityResolver:
    def __init__(self, companies: list[CompanyIdentity], fuzzy_threshold: float = 0.86) -> None:
        self.companies = {company.company_id: company for company in companies}
        self.fuzzy_threshold = fuzzy_threshold

    def resolve(self, query: CompanyQuery) -> ResolutionDecision:
        domain = normalize_domain(query.official_domain)
        for company in self.companies.values():
            if domain and domain == normalize_domain(company.official_domain):
                return ResolutionDecision(
                    ResolutionStatus.MATCHED, company.company_id, "DOMAIN_EXACT"
                )
            if query.ats_id and query.ats_id in company.ats_ids:
                return ResolutionDecision(
                    ResolutionStatus.MATCHED, company.company_id, "ATS_ID_EXACT"
                )
            if normalize_name(query.name) in {normalize_name(x) for x in company.human_aliases}:
                return ResolutionDecision(
                    ResolutionStatus.MATCHED, company.company_id, "HUMAN_ALIAS_EXACT"
                )
            if (
                query.legal_name
                and company.legal_name
                and normalize_name(query.legal_name) == normalize_name(company.legal_name)
                and query.address
                and company.address
                and normalize_name(query.address) == normalize_name(company.address)
            ):
                return ResolutionDecision(
                    ResolutionStatus.MATCHED, company.company_id, "LEGAL_NAME_ADDRESS_EXACT"
                )
            if (
                query.tax_id_last4
                and query.tax_id_last4 == company.tax_id_last4
                and query.address == company.address
                and query.naics == company.naics
            ):
                return ResolutionDecision(
                    ResolutionStatus.MATCHED, company.company_id, "TAX_ADDRESS_NAICS_EXACT"
                )

        candidates = tuple(
            company.company_id
            for company in self.companies.values()
            if SequenceMatcher(
                None, normalize_name(query.name), normalize_name(company.canonical_name)
            ).ratio()
            >= self.fuzzy_threshold
        )
        if candidates:
            return ResolutionDecision(
                ResolutionStatus.POSSIBLE_MATCH,
                None,
                "NAME_SIMILARITY_REQUIRES_REVIEW",
                candidates,
            )
        return ResolutionDecision(ResolutionStatus.NEW_COMPANY, None, "NO_DETERMINISTIC_MATCH")

    def confirm_alias(self, company_id: str, alias: str) -> None:
        self.companies[company_id].human_aliases.add(alias)

    def split_alias(self, company_id: str, alias: str) -> None:
        self.companies[company_id].human_aliases.discard(alias)
