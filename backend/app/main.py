import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .db import init_db
init_db()

from .logging_config import setup_logging, get_logger
from .routers import documents, generation, items, auth

setup_logging()
logger = get_logger("app.main")

app = FastAPI(title="AI Learning Content Platform", version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
            raise
        duration = (time.time() - start) * 1000
        logger.info("%s %s -> %d (%.1f ms)", request.method, request.url.path, response.status_code, duration)
        return response


app.add_middleware(RequestLoggingMiddleware)

app.include_router(documents.router)
app.include_router(generation.router)
app.include_router(items.router)
app.include_router(auth.router)


@app.on_event("startup")
def startup():
    init_db()
    logger.info("Application startup complete; database initialized.")


@app.get("/")
def root():
    return {"name": "AI Learning Content Platform", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok"}
