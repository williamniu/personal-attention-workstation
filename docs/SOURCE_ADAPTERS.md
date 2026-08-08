# Source Adapters

Every source exposes discover, fetch, normalize, and health-check operations. Discovery consumes a
source-specific checkpoint. Fetching writes immutable content-addressed Raw artifacts; normalization
writes Parquet only when the content hash is new; the checkpoint advances after the durable write.

Official USCIS, DOL LCA, and DOL PERM adapters are manifest-driven and do not hard-code a fiscal
year or quarter. `config/sources/official.yaml` intentionally has no live entries until current
official download URLs are verified. Contract fixtures under `tests/fixtures/official/` preserve the
required column contracts. A successful fixture test is not a live-source success claim.

No-result queries belong in coverage observations, never negative sponsorship evidence.

Public job adapters support Greenhouse, Lever, Ashby, SmartRecruiters, and structured Career Page
JSON-LD. Their live identifiers are intentionally empty in `config/sources/ats.yaml`. Job content is
hashed before version creation; absence requires consecutive reconciliations before soft-closing.
