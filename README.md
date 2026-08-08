# H-1B Career Intelligence System

HCIS is a local-first, two-candidate career intelligence system. The sole execution
specification is `H1B_Career_Intelligence_System_Codex_Spec_2026-08-07.md`.

## Quick start

```bash
uv sync
cp .env.example .env
./bin/jobintel start
./bin/jobintel status
```

Services bind to localhost by default. The system never sends outreach or submits an
application without a human action.

See `docs/STATUS.md` and `docs/OPERATIONS.md` for current capabilities and commands.

