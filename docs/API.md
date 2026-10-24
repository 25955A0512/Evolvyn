# API
FastAPI generates the exact schemas at `/docs` and `/openapi.json`. Business routes require `Authorization: Bearer <workspace token>`; health is public and reveals only database readiness.

| Method | Path | Purpose |
|---|---|---|
| GET, POST | /api/businesses | Saved business profiles and goals |
| GET | /api/health | Database readiness |
| GET, POST | /api/conversations | List/create conversations |
| GET | /api/conversations/{id} | History and file references |
| POST | /api/conversations/{id}/files | Multipart UTF-8 TXT/CSV |
| POST | /api/conversations/{id}/runs | Background analysis `{text, mode}`; mode is evidence or provider |
| GET | /api/conversations/{id}/retrieve | Ranked passages via `?q=` |
| POST | /api/conversations/{id}/analyze | Analyze `{text}` |
| POST | /api/conversations/{id}/research | Discover discussions `{query}` |
| GET | /api/executions/{id} | Execution and report |
| GET | /api/executions/{id}/live | Live SSE execution snapshots |
| POST | /api/executions/{id}/cancel | Cancel an eligible execution |
| GET | /api/executions/{id}/events | Stored events as finite SSE |
| POST | /api/executions/{id}/decision | `{approve, plan}` |
| GET | /api/artifacts/{id} | Approved internal brief |
| POST | /api/providers/test | Minimal provider connectivity probe |
| GET | /api/integrations | Configuration presence, not health |
| GET | /api/tools | Built-in capability metadata |

404 intentionally hides foreign and wrong-kind records. 409 rejects duplicate decisions. 413/415/422 cover upload/input limits. 502 reports external provider/source failures without response bodies or credential values.
