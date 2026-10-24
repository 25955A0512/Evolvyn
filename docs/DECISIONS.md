# Decisions
- FastAPI and React/TypeScript support a small Python analytical core and a conversational interface without premature microservices.
- PostgreSQL JSONB makes persistence explicit with little initial infrastructure. Relational migrations and stronger entities are needed before broadening scope.
- Structured numerical questions use CSV calculations. TXT uses bounded BM25-style passage retrieval with character offsets; embeddings and semantic RAG are not claimed.
- A finite background workflow with bounded context, live output and cancellation provides approval enforcement without claiming a full graph harness. No framework is needed to prove this first slice; durable graph orchestration should follow demonstrated requirements.
- A real internal database brief is the initial safe action. External campaign or production execution needs separate adapters and authorization.
- Missing credentials and blocked research access must remain visible, with deterministic mode clearly labeled.
