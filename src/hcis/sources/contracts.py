from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

type NormalizedRecord = dict[str, str | int | float | bool | None]


@dataclass(frozen=True)
class SourceCheckpoint:
    cursor: str | None = None
    state: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveredItem:
    external_id: str
    partition: str
    uri: str
    media_type: str


@dataclass(frozen=True)
class DiscoveryBatch:
    items: list[DiscoveredItem]


@dataclass(frozen=True)
class RawArtifact:
    item: DiscoveredItem
    content: bytes
    content_type: str


@dataclass(frozen=True)
class SourceHealth:
    status: str
    details: str


class SourceAdapter(Protocol):
    source_id: str

    async def discover(self, checkpoint: SourceCheckpoint) -> DiscoveryBatch: ...

    async def fetch(self, item: DiscoveredItem) -> RawArtifact: ...

    async def normalize(self, artifact: RawArtifact) -> list[NormalizedRecord]: ...

    async def health_check(self) -> SourceHealth: ...
