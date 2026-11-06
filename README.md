# AI-Assisted Learning Content & Assessment Generation Platform

Phase 1.1 (Summary Generator) implemented.

## Run backend (manual)
```bash
cd backend
pip install -r requirements.txt
# edit .env (MOCK_LLM=true for no API key)
python -m uvicorn app.main:app --reload --port 8001
```

## Run / Stop (scripts)
```bash
# Windows
run.bat            # start
run.bat stop       # stop
run.bat restart    # restart
run.bat status     # status

# macOS / Linux
chmod +x run.sh
./run.sh           # start
./run.sh stop      # stop
./run.sh restart   # restart
./run.sh status    # status
```

## Test
```bash
cd backend
pytest -q
```

## Logging
Logs are written to console and `data/app.log` (rotating, 5MB x3). Set `LOG_LEVEL` in `.env` (default INFO).

## API
- POST /documents (multipart: title, file)
- GET /documents/{id}/chunks
- POST /jobs/generate {document_id, types, items_per_chunk}
- GET /jobs/{job_id}
- GET /items?document_id=&item_type=
- PATCH /items/{id}
```