# Admin Runbook

## Environment
- Copy `backend/.env.example` (or edit `backend/.env`).
- Key variables: `MOCK_LLM`, `OPENAI_API_KEY`, `LLM_MODEL`, `LLM_MODEL_CHEAP`, `DATABASE_URL`, `DATA_DIR`, `AUTH_REQUIRED`, `MAX_UPLOAD_MB`, `RATE_LIMIT_PER_MIN`, `LOG_LEVEL`.

## Running
- Backend: `run.bat` / `./run.sh` (port 8001).
- Dashboard: `run.bat dashboard` / `./run.sh dashboard` (port 8501).
- Stop: `run.bat stop` / `./run.sh stop`.

## Database
- SQLite by default at `data/app.db`. Migrations are automatic on startup (`init_db`).
- Back up `data/` regularly.

## Logs
- Console + `data/app.log` (rotating 5MB x3). Set `LOG_LEVEL`.

## Auth
- Register users via `/auth/register` with roles teacher/reviewer/admin.
- Set `AUTH_REQUIRED=true` to enforce authentication.

## Deployment
- Docker: `docker-compose up --build`.
- See `docker-compose.yml` and `backend/Dockerfile`.

## Monitoring
- Health: `/health`. Stats: `/stats/costs`. Study monitoring: `/studies/{id}/monitoring`.