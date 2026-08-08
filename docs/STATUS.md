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
| M9 Mail and ICS intake | COMPLETE (live mailbox blocked) | 45 cumulative tests; read-only folder contract |
| M10 Browser prefill and applications | COMPLETE (browser login blocked) | 52 cumulative tests; submit gate |
| M11 Operations and full acceptance | COMPLETE (runtime integrations blocked) | 60 tests; lifecycle/backup/launchd smoke |

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
- `BLOCKED_EXTERNAL`: William's Himalaya/Outlook account is not configured. The read-only folder
  and manual import contracts pass; no live mailbox was accessed. Girlfriend mail remains disabled.
- `BLOCKED_EXTERNAL`: the dedicated Air Chrome profile is not configured or signed in. Apply-page
  parsing and safe plans pass fixtures; no browser was launched and no form was submitted.
- `BLOCKED_EXTERNAL`: notification email delivery is not configured. Outbox/template/retry contracts
  pass; no email was sent.
- `BLOCKED_EXTERNAL`: the launchd template validates but was not installed into the user LaunchAgents
  directory from this sandbox.

## Known implementation limits

- Docker is absent, so PostgreSQL and container recovery remain configuration-verified only.
- The local three-times-daily scheduler is implemented with the Python standard library. Prefect UI
  and worker services are not activated; add them only if operational visibility justifies the cost.
- Fixture reports are examples, not current jobs or live sponsorship facts.

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

## M9 verification

- Requests outside `JobIntel-Intake` fail before any mail command runs.
- UIDVALIDITY/UID keys deduplicate repeat syncs.
- Only whitelisted recruiting mail stores a local body; normal mail body is discarded.
- Manual `.eml` and `.ics` fixtures parse; calendar output requires human confirmation.
- Mail may create William-scoped CRM events; providers expose no send method.

## M10 verification

- Apply-page parsing separates safe identity fields from sponsorship, authorization, salary, and
  other mandatory human fields.
- CAPTCHA and MFA halt before any prefill.
- Automation cannot record `SUBMITTED`; only an explicit user actor can.
- Duplicate candidate/job applications fail while the other candidate remains independent.
- Browser-task completion requires a user actor; no submit method exists.

## M11 verification

- `start`, `health`, `pause`, `resume`, and `stop` passed with API, Dashboard, and Scheduler; final
  desired state and all service processes are `STOPPED`.
- `run-once` returned `SUCCESS_NO_ENABLED_SOURCES` with zero inserts/calls instead of claiming live
  ingestion.
- Consecutive identical E2E cycles produce zero new jobs, versions, Evidence, LLM calls, or notices.
- Backup creation and confirmed restore pass; reset moves data to a recoverable trash directory.
- launchd template passes `plutil -lint`; desired-state recovery plans cover scheduled/paused/stopped.
- Notification retry failure remains visible and a successful retry is not sent twice.
- 60 tests, Ruff, Mypy, and the full PostgreSQL offline migration chain pass.
