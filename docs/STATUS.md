# Project Status

Last updated: 2026-08-07

| Milestone | Status | Verification |
|---|---|---|
| M0 Repository and runtime skeleton | COMPLETE (Docker runtime blocked) | 3 tests; Ruff; Mypy; lifecycle smoke |
| M1 Candidate profiles and role taxonomy | COMPLETE | 6 cumulative tests; migration SQL compile |
| M2–M11 | NOT STARTED | — |

## External constraints

- `BLOCKED_EXTERNAL`: Docker is not installed or not available on the current host. Compose and
  PostgreSQL wiring are implemented but the container path is not runtime-verified.
- No external data source or credential has been claimed as connected.

## M0 verification

- `uv run pytest`: 3 passed.
- `uv run ruff check .`: passed.
- `uv run mypy`: passed.
- Lifecycle smoke: `start`, `health`, `status`, `pause`, `resume`, `stop`; final state `STOPPED`.

## M1 verification

- Candidate configs preserve unknown degree titles and unknown DeepWisdom details as null/empty.
- Candidate document imports use separate private paths.
- `/candidates` returns two independent profiles.
- Alembic candidate migration compiles in offline PostgreSQL mode.
