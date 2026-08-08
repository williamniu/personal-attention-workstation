# Test Plan

Each milestone adds the narrowest regression tests for its contracts. The final suite covers:

- no-record sponsorship semantics;
- entity-resolution non-merges;
- incremental idempotency and checkpoint recovery;
- human-review precedence;
- two-candidate data isolation;
- browser, mail, notification, and application safety gates;
- lifecycle persistence and backup/restore.

Run all checks with `make check`.
