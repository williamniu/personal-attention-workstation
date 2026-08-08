# Test Plan and Evidence

Run the complete local gate:

```bash
make check
uv run alembic upgrade head --sql > /tmp/hcis-migrations.sql
```

Verified on Python 3.12.13:

- 60 tests pass across unit, contract, integration, and E2E suites;
- Ruff passes;
- strict Mypy passes;
- all 11 PostgreSQL migrations compile in offline mode;
- local API/Dashboard/Scheduler lifecycle smoke passes and finishes fully stopped;
- launchd output passes `plutil -lint`;
- a local backup archive is created and the tested restore requires confirmation.

Coverage includes no-record semantics, exact/fuzzy company resolution, three official-data
contracts, four ATS contracts, job/evidence/LLM/notification idempotency, checkpoint recovery, human
review precedence, candidate isolation, mail-folder privacy, browser/application gates,
desired-state recovery, backup/restore, logging redaction, and repeat-cycle zero side effects.

Not yet executable on this host: Docker/PostgreSQL integration, live official downloads, live ATS
boards, live mailbox, signed-in browser, external LLM, LaunchAgent installation, and email delivery.
Each remains an explicit acceptance gate in `docs/STATUS.md`.
