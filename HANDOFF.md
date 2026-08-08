# HCIS Handoff

## What we are building

HCIS is a local-first, two-candidate career intelligence system. It discovers current jobs through
job-first and sponsor-first lanes, stores auditable H-1B/OPT/E-Verify evidence, ranks independently
for William and Girlfriend, and prepares human-controlled research, networking, and applications.

The sole execution specification is
`H1B_Career_Intelligence_System_Codex_Spec_2026-08-07.md` in this repository.

## Completed milestones

M0–M11 are implemented and locally committed in milestone order. The code includes schemas and 11
migrations; official/ATS/mail/browser adapters; company resolution; Evidence/assessment; scoring and
reports; Dashboard/API; CRM; safe browser/application tasks; scheduler, backup, recovery, audit, and
notification outbox.

All integrations that need current external configuration are intentionally disabled. “Implemented”
does not mean live data was fetched.

## Current commands

```bash
cd /Users/williamniu/AI/projects/h1b-career-intelligence
uv sync
./bin/jobintel doctor
./bin/jobintel start
./bin/jobintel status
./bin/jobintel pause
./bin/jobintel resume
./bin/jobintel run-once
./bin/jobintel logs
./bin/jobintel backup
./bin/jobintel stop
```

Final verified desired state: `STOPPED`; API, Dashboard, and Scheduler all stopped.

## Data-source state

| Source | Code/contract | Live state |
|---|---|---|
| USCIS Employer Data | Adapter + fixture + Parquet/DuckDB | `BLOCKED_EXTERNAL`: manifest empty |
| DOL LCA/PERM | Adapters + fixtures + Parquet/DuckDB | `BLOCKED_EXTERNAL`: manifest empty |
| Greenhouse/Lever/Ashby/SmartRecruiters | Four adapters + fixtures | `BLOCKED_EXTERNAL`: no board IDs |
| Career Page JSON-LD | Parser + fixture | No company pages configured |
| E-Verify | Separate evidence model | No live query configured |
| External LLM | Strict schema + cache contract | `BLOCKED_EXTERNAL`: no provider |
| William Outlook/Himalaya | Read-only folder adapter + fixture | `BLOCKED_EXTERNAL`: account unconfigured |
| Girlfriend mail | Provider boundary | Disabled as specified |
| Dedicated Chrome Profile | Parser/tasks/prefill gates | `BLOCKED_EXTERNAL`: not created/signed in |
| Email notifications | Outbox/template/retry | `BLOCKED_EXTERNAL`: no sender |

## Test result

`60 passed`; Ruff passed; strict Mypy passed; all migrations compile offline. Lifecycle,
`SUCCESS_NO_ENABLED_SOURCES` run-once, launchd plist lint, and local backup creation passed. Docker is
absent, so PostgreSQL/Compose runtime health was not tested.

## Known limits

- No live opportunity, visa history, contact, email, or application data has been collected.
- Docker/PostgreSQL runtime and `pg_dump` backup are not connected.
- The native scheduler supplies three daily cycles; Prefect UI/workers are not activated.
- launchd is rendered and linted but not installed.
- Example reports under `examples/reports/` are deterministic fixtures, not live intelligence.

## User configuration still required

1. Set a strong `HCIS_API_TOKEN` in `.env`.
2. Install/start Docker or supply an approved PostgreSQL service, then run migrations.
3. Add current official USCIS/DOL manifest entries and verify hashes/columns.
4. Add at least three real target-company ATS identifiers and run a live canary scan.
5. Create the Outlook server-side `JobIntel-Intake` rule; configure Himalaya read-only for William.
6. Create/sign in to the dedicated HCIS Chrome Profile manually.
7. Configure an approved notification sender only after reviewing queued payloads.
8. Review and install the launchd plist manually if desired-state recovery is approved.

Credentials, resumes, email content, contacts, and browser data belong under ignored local paths or
macOS Keychain. Never commit them.

## Manual Outlook rule

Create `JobIntel-Intake` in Outlook and use server-side sender/subject criteria from the specification
for recruiter, interview, referral, immigration, visa, H-1B, OPT, STEM OPT, and CPT threads. Do not
route the general Inbox. Confirm that unrelated mail remains outside the folder before enabling sync.

## Manual browser setup

Create `~/Library/Application Support/HCIS-Chrome`, sign in manually, and handle MFA/CAPTCHA only on
the MacBook Pro/human side. Do not copy cookies/Profile data into the repository or containers.

## Recommended next gates

1. Verify Docker/PostgreSQL migration and restart recovery.
2. Canary one official USCIS file, one current LCA file, and one current PERM file.
3. Canary three public ATS boards; run twice and verify zero second-run versions/LLM/notices.
4. Import reviewed candidate resumes and confirm profile versions.
5. Enable William mail read-only and verify folder isolation with a harmless test message.
6. Install launchd only after all lifecycle checks pass from the final repository path.

Each gate requires a separate user approval; strategy approval is not external execution approval.

## Never repeat these mistakes

- No record is `UNKNOWN`, never “does not sponsor.”
- Continuing/transfer history is not first-time or first-available lottery proof.
- Company history never overrides a current job-specific restriction.
- Parent evidence never propagates automatically to every child/legal entity.
- Fuzzy names never auto-merge companies.
- Automatic jobs never overwrite a current human review.
- Never save hidden chain-of-thought; keep structured evidence, rules, tool calls, and score parts.
- Never read outside `JobIntel-Intake`, send outreach, bypass MFA/CAPTCHA, or click final Submit.
- Never call a fixture, snapshot, or blocked source “live.”
