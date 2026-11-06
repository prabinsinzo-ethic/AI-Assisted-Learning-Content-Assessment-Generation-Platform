import time
import logging
from collections import defaultdict, deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .db import init_db
init_db()

from .logging_config import setup_logging, get_logger
from .config import RATE_LIMIT_PER_MIN, MAX_UPLOAD_MB, AUTH_REQUIRED
from .routers import documents, generation, items, auth, qc, export, studies, analysis, stats

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


_rate_buckets = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = _rate_buckets[ip]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_PER_MIN:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        bucket.append(now)
        return await call_next(request)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(documents.router)
app.include_router(generation.router)
app.include_router(items.router)
app.include_router(auth.router)
app.include_router(qc.router)
app.include_router(export.router)
app.include_router(studies.router)
app.include_router(analysis.router)
app.include_router(stats.router)


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
