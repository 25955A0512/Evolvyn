# Governance
Read operations require the workspace bearer token. Analysis is read-only except for persisted history. Public research is a user-triggered external read. The only supported approved action is creation of an internal experiment brief; no campaigns, deployments or third-party modifications are supported.

Approval accepts an edited plan and Boolean decision. Only WAITING_FOR_APPROVAL executions are eligible. A PostgreSQL row lock prevents duplicate execution. Rejection records CANCELLED. Approval records COMPLETED and creates a retrievable artifact. Evidence content and provider output cannot set authorization flags. New tool execution paths must use backend permission checks before becoming available.
