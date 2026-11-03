# H-1B Career Intelligence System

HCIS is a local-first career workbench with an existing two-candidate H-1B radar.
The original radar specification is `H1B_Career_Intelligence_System_Codex_Spec_2026-08-07.md`.

## Quick start

```bash
uv sync --reinstall
cp .env.example .env
uv run alembic upgrade head
./bin/jobintel start
./bin/jobintel status
```

Open `http://127.0.0.1:8501`. Services bind to localhost; startup is manual and no launchd item is
installed. Stop everything with `./bin/jobintel stop`. The system never sends outreach or submits
an application.

See `docs/STATUS.md` and `docs/OPERATIONS.md` for current capabilities and commands.

The active sources are MyVisaJobs, H1BData.info, H1BGrader, and official Careers validation.
Structured records and independent William/Rody state live in `data/hcis.sqlite3`. Direct DOL,
USCIS, PostgreSQL, and Docker runtime dependencies are disabled.

```bash
./bin/jobintel refresh-source h1bdata
./bin/jobintel refresh-plan
./bin/jobintel run-once
```

## Career workbench and daily review

Use `./bin/career-workbench start` to run only the local workbench, then open
`http://127.0.0.1:8501`. `status`, `stop`, `restart`, and `logs` manage this service.

The daily workflow reads the eight startup/VC entrances and their company/job pages through
Codex's in-app browser, combining those observations with existing employer jobs and local research.
The CLI imports browser evidence without HTTP/API fallbacks. It reads up to 20 companies per source
per round and prepares evidence for
a Codex review; the reviewed daily brief contains at most 10 recommendations across all sources.
Restricted and incomplete sources remain visible. Research, internships, current jobs, and
explicit co-founder invitations retain their separate evidence boundaries.

See [the daily workflow](docs/DAILY_CAREER_SCAN.md) for collection, review, and publishing commands.
Scheduling is owned by the existing local Codex heartbeat at 08:00 America/Chicago, configured
in the app rather than installed by this repository. Local databases, personal research,
relationships, reports, and automation state are not included in Git.
