from __future__ import annotations

import hashlib
from typing import Protocol

from hcis.evidence.schema import JDExtraction


class StructuredJSONProvider(Protocol):
    provider: str
    model: str

    async def complete_json(
        self, prompt_name: str, prompt_version: str, input_text: str
    ) -> dict[str, object]: ...


class JDLLMExtractor:
    def __init__(
        self, provider: StructuredJSONProvider, prompt_version: str = "jd-sponsor-v1"
    ) -> None:
        self.provider = provider
        self.prompt_version = prompt_version
        self.cache: dict[str, JDExtraction] = {}

    async def extract(self, text: str) -> JDExtraction:
        key = hashlib.sha256(
            "|".join(
                [self.provider.provider, self.provider.model, self.prompt_version, text]
            ).encode()
        ).hexdigest()
        if key not in self.cache:
            payload = await self.provider.complete_json("jd_sponsorship", self.prompt_version, text)
            self.cache[key] = JDExtraction.model_validate(payload)
        return self.cache[key]
