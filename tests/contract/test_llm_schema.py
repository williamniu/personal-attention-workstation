from __future__ import annotations

import json
from pathlib import Path

import pytest

from hcis.evidence import TriState
from hcis.llm import JDLLMExtractor

FIXTURE = Path(__file__).parents[1] / "fixtures" / "llm" / "jd_positive.json"


class FixtureProvider:
    provider = "fixture"
    model = "fixture-v1"

    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(
        self, prompt_name: str, prompt_version: str, input_text: str
    ) -> dict[str, object]:
        self.calls += 1
        return json.loads(FIXTURE.read_text())  # type: ignore[no-any-return]


@pytest.mark.asyncio
async def test_llm_output_schema_and_cache() -> None:
    provider = FixtureProvider()
    extractor = JDLLMExtractor(provider)

    first = await extractor.extract("Sponsorship wording")
    second = await extractor.extract("Sponsorship wording")

    assert first.future_sponsorship == TriState.YES
    assert second == first
    assert provider.calls == 1
