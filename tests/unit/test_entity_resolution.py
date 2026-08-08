from __future__ import annotations

from hcis.entity_resolution import CompanyIdentity, CompanyQuery, EntityResolver


def companies() -> list[CompanyIdentity]:
    return [
        CompanyIdentity(
            company_id="example-us",
            canonical_name="Example AI",
            legal_name="Example AI Inc",
            official_domain="example.ai",
            address="New York NY",
            tax_id_last4="1234",
            naics="541512",
            ats_ids={"greenhouse:example"},
        ),
        CompanyIdentity(
            company_id="example-uk",
            canonical_name="Example AI",
            legal_name="Example AI Ltd",
            official_domain="example.co.uk",
            address="London UK",
        ),
    ]


def test_domain_and_ats_are_deterministic_matches() -> None:
    resolver = EntityResolver(companies())

    assert (
        resolver.resolve(
            CompanyQuery("Whatever", official_domain="https://example.ai/jobs")
        ).company_id
        == "example-us"
    )
    assert (
        resolver.resolve(CompanyQuery("Whatever", ats_id="greenhouse:example")).company_id
        == "example-us"
    )


def test_same_name_different_company_is_not_auto_merged() -> None:
    decision = EntityResolver(companies()).resolve(CompanyQuery("Example AI"))

    assert decision.status == "POSSIBLE_MATCH"
    assert decision.company_id is None
    assert set(decision.candidate_ids) == {"example-us", "example-uk"}


def test_fuzzy_name_only_requires_review() -> None:
    decision = EntityResolver(companies()).resolve(CompanyQuery("Exampel AI"))

    assert decision.status == "POSSIBLE_MATCH"
    assert decision.company_id is None


def test_human_alias_can_be_confirmed_and_split() -> None:
    resolver = EntityResolver(companies())
    resolver.confirm_alias("example-us", "Example Artificial Intelligence")
    assert (
        resolver.resolve(CompanyQuery("Example Artificial Intelligence")).company_id == "example-us"
    )

    resolver.split_alias("example-us", "Example Artificial Intelligence")
    assert resolver.resolve(CompanyQuery("Example Artificial Intelligence")).company_id is None
