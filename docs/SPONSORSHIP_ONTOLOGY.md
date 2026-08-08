# Sponsorship Ontology

Evidence is scoped to company, department, location, job, and optionally candidate. It records the
source, verbatim excerpt, dates, authority, confidence, and separate first-time, first-available,
transfer, OPT, STEM OPT, and E-Verify fields.

`coverage_observations` record that a query ran and returned a count. They are not Evidence and can
never produce `CONFIRMED_NO_SPONSORSHIP`. Explicit current negative wording is required for a
negative classification. Continuing approvals alone indicate transfer/continuing capability, not a
first cap-subject registration.

Rules run before structured LLM extraction. A disagreement creates human-review work. Current human
reviews remain authoritative; automation may only flag a newer conflicting fact for re-review.
E-Verify evidence is a separate STEM OPT signal and never means H-1B sponsorship by itself.

