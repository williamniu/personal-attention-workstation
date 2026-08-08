# Privacy and Safety

- `.env`, `private/`, runtime data, browser state, reports, and exports are excluded from Git.
- Services bind to `127.0.0.1` by default.
- Work mail is local-only and folder-scoped when enabled.
- The mail adapter rejects every folder except `JobIntel-Intake`; non-whitelisted bodies are not
  stored, attachments are not downloaded, and work-confidential text is local-model-only.
- No automation may send outreach, accept legal attestations, bypass MFA/CAPTCHA, or submit an application.
- No missing public visa result is negative sponsorship evidence.
- Backups exclude `private/`, browser profiles, and secrets; PostgreSQL dump status must be explicit.
- Reset is recoverable and ordinary UI cannot delete the append-only audit log.
