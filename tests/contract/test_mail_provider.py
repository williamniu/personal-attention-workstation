from __future__ import annotations

from pathlib import Path

import pytest

from hcis.mail import MailCatalog, mail_to_crm_event, sync_mail
from hcis.sources.himalaya import HimalayaFolderProvider
from hcis.sources.manual import ManualMailProvider

FIXTURES = Path(__file__).parents[1] / "fixtures" / "mail"


class FixtureRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> str:
        self.commands.append(command)
        if command[1:3] == ["envelope", "list"]:
            return (FIXTURES / "envelopes.json").read_text()
        return "Recruiting body with interview details"


@pytest.mark.asyncio
async def test_folder_scope_uid_dedup_and_body_whitelist(tmp_path: Path) -> None:
    runner = FixtureRunner()
    provider = HimalayaFolderProvider("work-outlook", "uidvalidity-1", runner)
    catalog = MailCatalog()

    first = await sync_mail(provider, "JobIntel-Intake", 0, catalog, tmp_path / "mail")
    second = await sync_mail(provider, "JobIntel-Intake", 0, catalog, tmp_path / "mail")

    assert first.inserted == 2
    assert first.bodies_saved == 1
    assert second.inserted == 0 and second.skipped == 2
    assert len(list((tmp_path / "mail").glob("*.txt"))) == 1
    assert not hasattr(provider, "send")


@pytest.mark.asyncio
async def test_other_folder_is_rejected_before_command() -> None:
    runner = FixtureRunner()
    provider = HimalayaFolderProvider("work-outlook", "uidvalidity-1", runner)
    with pytest.raises(PermissionError, match="JobIntel-Intake"):
        await provider.list_envelopes("Inbox", 0)
    assert runner.commands == []


@pytest.mark.asyncio
async def test_manual_eml_import_and_mail_to_crm(tmp_path: Path) -> None:
    provider = ManualMailProvider(FIXTURES)
    envelopes = await provider.list_envelopes("JobIntel-Intake", 0)
    message = await provider.read_message(envelopes[0])

    event = mail_to_crm_event(message)
    assert event is not None
    assert event["candidate_id"] == "william"
    assert event["external_event_id"] == "<manual-recruiter-1@example.com>"
