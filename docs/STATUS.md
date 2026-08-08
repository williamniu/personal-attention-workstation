# Project Status

Last updated: 2026-08-07

| Milestone | Status | Verification |
|---|---|---|
| M0 Repository and runtime skeleton | COMPLETE (Docker runtime blocked) | 3 tests; Ruff; Mypy; lifecycle smoke |
| M1 Candidate profiles and role taxonomy | COMPLETE | 6 cumulative tests; migration SQL compile |
| M2 Official visa data warehouse | COMPLETE (live manifests blocked) | 9 cumulative tests; 3 contract fixtures |
| M3 Company entity resolution | COMPLETE | 13 cumulative tests; deterministic/non-merge cases |
| M4 Realtime job collection | COMPLETE (live boards blocked) | 21 cumulative tests; 4 ATS + career fixture |
| M5 Sponsorship evidence engine | COMPLETE (live LLM blocked) | 28 cumulative tests; safety semantics |
| M6 Candidate scoring and reports | COMPLETE | 34 cumulative tests; isolated reports/exports |
| M7 Dashboard and human review | COMPLETE | 36 cumulative tests; token + durable audit |
| M8 Networking CRM | COMPLETE (external discovery blocked) | 41 cumulative tests; no send surface |
| M9–M11 | NOT STARTED | — |

## External constraints

- `BLOCKED_EXTERNAL`: Docker is not installed or not available on the current host. Compose and
  PostgreSQL wiring are implemented but the container path is not runtime-verified.
- No external data source or credential has been claimed as connected.
- `BLOCKED_EXTERNAL`: current official USCIS and DOL download manifest entries are not configured;
  fixture imports prove the contracts but do not represent a live import.
- `BLOCKED_EXTERNAL`: no verified company board tokens/site identifiers are configured. Four ATS
  contracts pass fixtures, but the “three ATS live” acceptance item is not claimed as successful.
- `BLOCKED_EXTERNAL`: no external LLM provider is configured. JSON schema and cache contracts pass
  a fixture provider; production extraction remains disabled until explicitly configured.
- `BLOCKED_EXTERNAL`: authenticated contact discovery sources are not configured. Manual discovery
  and CRM contracts work; no external profile research or outreach has run.

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

## M2 verification

- USCIS, LCA, and PERM contract fixtures each import to content-addressed Raw + Parquet.
- A second run discovers and inserts zero records due to persisted checkpoints.
- DuckDB reads Parquet and aggregates USCIS initial/continuing metrics.
- Source, checkpoint, raw artifact, case, and metrics migration compiles offline.

## M3 verification

- Exact domain and ATS identifiers auto-match.
- Same-name companies with different domains remain separate review candidates.
- Fuzzy names produce `POSSIBLE_MATCH`, never an automatic merge.
- Human-confirmed aliases can be added and split without rewriting the companies.

## M4 verification

- Greenhouse, Lever, Ashby, SmartRecruiters, and Career Page JSON-LD fixtures normalize.
- Official apply URLs are retained.
- Unchanged jobs create zero new versions; changed descriptions create one version.
- Jobs close only after consecutive missing reconciliations.

## M5 verification

- “Do not sponsor” maps to explicit negative; Transfer-only remains separate.
- No USCIS/LCA result remains coverage + `UNKNOWN_NEEDS_VERIFICATION`.
- Initial USCIS + LCA is `LIKELY`, never confirmed first-available.
- Rule/LLM conflicts require review; repeated structured inputs hit cache.
- Current human review remains authoritative; new conflicts set re-review without overwrite.

## M6 verification

- The same job produces different William and Girlfriend component sets and totals.
- Unknown high-fit jobs keep a nonzero identity score and enter `P1_APPLY_AND_VERIFY`.
- Explicit no-sponsorship jobs hard-reject before weighted scoring.
- Candidate reports/exports reject cross-candidate rows; couple bonus is capped at five.

## M7 verification

- Dashboard exposes all 18 specified navigation pages and working Evidence/Review/Control views.
- Protected API endpoints reject missing tokens.
- Human reviews persist locally when PostgreSQL is unavailable and emit append-only audit entries.
- Source health displays blockers rather than empty-success states.

## M8 verification

- Canonical profile URLs deduplicate contacts.
- Candidate/contact relationships remain candidate-scoped.
- CRM events are idempotent and manual discovery is company-scoped.
- Sponsorship drafts contain first-eligible-lottery and transfer distinctions, require human
  approval, and the service exposes no send method.
