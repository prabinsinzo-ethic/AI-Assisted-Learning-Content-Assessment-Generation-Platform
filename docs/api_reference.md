# API Reference

Interactive docs: http://127.0.0.1:8001/docs (Swagger) and /redoc.

## Documents
- POST /documents (multipart title, file)
- GET /documents
- GET /documents/{id}
- GET /documents/{id}/chunks

## Jobs
- POST /jobs/generate {document_id, types, items_per_chunk, token_budget}
- GET /jobs/{job_id}
- POST /jobs/{job_id}/cancel

## Items
- GET /items?document_id=&item_type=&status=
- PATCH /items/{id} {status, payload, bloom_level}
- GET /items/{id}/versions

## Quality Control
- POST /qc/verify {document_id, item_ids}
- POST /qc/dedup {document_id, threshold}
- POST /qc/ambiguity {document_id, item_ids}
- POST /qc/bloom {document_id, item_ids}
- POST /qc/heuristics {document_id, item_ids}
- POST /qc/quality-score {document_id, item_ids}
- POST /qc/consistency {document_id, item_ids}
- POST /qc/run {document_id, max_retries}

## Export
- GET /export/{document_id}?format=json|csv|anki|qti

## Auth
- POST /auth/register {username, password, role}
- POST /auth/login {username, password}
- GET /auth/me?token=

## Studies
- POST /studies {name, design, pairs}
- GET /studies
- GET /studies/{id}
- GET /studies/{id}/pairs?rater_id=
- POST /studies/{id}/ratings {...}
- GET /studies/{id}/results
- GET /studies/{id}/analysis
- GET /studies/{id}/report
- GET /studies/{id}/progress
- GET /studies/{id}/monitoring
- POST/GET/DELETE /studies/{id}/raters

## Stats
- GET /stats/costs