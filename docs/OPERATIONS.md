# Operations

## First setup

```bash
cd /Users/williamniu/AI/projects/h1b-career-intelligence
uv sync
cp .env.example .env
./bin/jobintel doctor
```

Replace `HCIS_API_TOKEN` before any private-network access. Services bind to localhost by default.
Do not enable a source until its current official URL/identifier, terms, and scope are verified.

## Lifecycle controls

```bash
./bin/jobintel start
./bin/jobintel stop
./bin/jobintel pause
./bin/jobintel resume
./bin/jobintel run-once
./bin/jobintel status
./bin/jobintel health
./bin/jobintel logs
./bin/jobintel doctor
```

`start` launches API, Dashboard, and Scheduler as independently tracked background processes.
`pause` keeps API/Dashboard available; the Scheduler process remains alive but starts no new cycle.
`resume` restores `SCHEDULED`. `stop` terminates all three and persists `STOPPED`.

The default scheduler interval is eight hours (three scans/day). A manual `run-once` is allowed in
any desired state. With all sources blocked it writes an auditable
`SUCCESS_NO_ENABLED_SOURCES` run containing zero activity.

## Local endpoints

- API health: `http://127.0.0.1:8080/health`
- Dashboard: `http://127.0.0.1:8501`

All API endpoints except health require `Authorization: Bearer <HCIS_API_TOKEN>` or
`X-API-Token`. Do not bind to a public interface. Use a private Tailnet/Headscale path and host
firewall if remote access is later approved.

## Logs and diagnosis

```bash
./bin/jobintel logs --service api
./bin/jobintel logs --service dashboard
./bin/jobintel logs --service scheduler
./bin/jobintel doctor
./bin/jobintel status
```

Runtime logs and job-run records are under ignored `data/logs/` and `data/job_runs/`. JSON logging
redacts passwords, cookies, authorization headers, API tokens, and message bodies. Failures retain a
visible error; adapters must not silently return an empty success.

## Backup, restore, and reset

```bash
./bin/jobintel backup
./bin/jobintel stop
./bin/jobintel restore data/backups/hcis-YYYYMMDDTHHMMSSZ.tar.gz --confirm-restore
./bin/jobintel reset --confirm-delete-all-data
```

Backups include configuration, runtime/analytical data, reports, and exports. They exclude
`private/`, browser data, secrets, and the backup directory itself. The backup manifest records
PostgreSQL as `BLOCKED_EXTERNAL` until a real database dump is wired and verified.

Restore and reset refuse to run while services are active. Reset is recoverable: it moves `data/` to
`data.trash-<timestamp>/` and creates a new empty data directory rather than deleting recursively.

## launchd recovery

Render and inspect the template:

```bash
./bin/render-launchd > /tmp/com.hcis.supervisor.plist
plutil -lint /tmp/com.hcis.supervisor.plist
```

After user review, the user may copy it to `~/Library/LaunchAgents/com.hcis.supervisor.plist` and
bootstrap it with `launchctl`. Installation is intentionally not automated here. The Supervisor
reconciles every minute:

- `SCHEDULED`: restore services + Scheduler and plan checkpoint catch-up;
- `PAUSED`: restore API/Dashboard but do not start a new scan;
- `STOPPED`: remain stopped.

## Docker/PostgreSQL

`docker-compose.yml` defines localhost PostgreSQL, API, Dashboard, and Scheduler with CPU/memory
limits. Docker is not installed on the verified host, so do not treat Compose as runtime-tested.
Once Docker exists, validate in this order:

```bash
docker compose config
docker compose up -d postgres
uv run alembic upgrade head
docker compose up -d api dashboard scheduler
./bin/jobintel health
```

Do not enable `restart` behavior as a substitute for the persisted desired state.

## Source activation gates

- Official visa data: add only verified USCIS/DOL manifest entries; run contract tests first.
- ATS: add verified company board tokens/site IDs; preserve official Apply URLs.
- Mail: user creates Outlook server-side `JobIntel-Intake`; configure William only; test folder
  rejection before live sync.
- Browser: user creates/signs in to the dedicated HCIS Chrome Profile; MFA/CAPTCHA stay manual.
- Notifications: configure an approved email sender, then dispatch existing outbox rows once.

Never infer sponsorship from a zero-result query, send outreach, accept meetings, or submit an
application from an automated task.
