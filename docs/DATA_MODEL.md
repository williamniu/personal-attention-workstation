# Data Model

All durable records use UUID-compatible string keys, timestamps, and source provenance. Candidate
tables are private-scope: candidates, documents, experiences, skills, and versioned preferences.
Candidate documents are content-addressed under separate ignored private directories.

Shared company, job, official-source, and sponsorship-evidence records are introduced in later
migrations. Candidate-specific scores, contacts, applications, and reports always retain a
candidate key; shared facts never imply shared private documents or workflow state.

