# Architecture

HCIS keeps shared company, job, source, and sponsorship facts separate from candidate-specific
profiles, scores, CRM records, and applications. Raw inputs are content-addressed; canonical writes
use stable keys and content hashes. Human reviews are append-only overrides.

The first runtime slice is local API + dashboard + persistent desired state. Data modules are added
in milestone order and use adapters at external boundaries.

Company resolution is evidence-first. Group relationships are stored explicitly, and a parent's
facts are never copied to a child. Fuzzy names create review work rather than canonical merges.

Sponsor-first official adapters and job-first ATS/Career adapters converge only after independent
Raw, checkpoint, normalization, and company-resolution steps. Candidate scoring consumes shared
facts but writes candidate-specific versions. The notification and browser/application edges use
outboxes/tasks with human gates; no external write exists in the analytical cycle.

The local scheduler is one runtime-state writer and checks persisted desired state before each
cycle. Content hashes, stable keys, caches, and outboxes enforce idempotency independently of the
scheduler. A launchd Supervisor restores the desired state; it does not rewrite it.
