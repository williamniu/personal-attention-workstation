# Architecture

HCIS keeps shared company, job, source, and sponsorship facts separate from candidate-specific
profiles, scores, CRM records, and applications. Raw inputs are content-addressed; canonical writes
use stable keys and content hashes. Human reviews are append-only overrides.

The first runtime slice is local API + dashboard + persistent desired state. Data modules are added
in milestone order and use adapters at external boundaries.

