from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models import ContentItem, GenerationJob, Document

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/costs")
def costs(db: Session = Depends(get_db)):
    # item counts by type
    by_type = db.query(ContentItem.item_type, func.count(ContentItem.id)).group_by(ContentItem.item_type).all()
    # job token usage
    jobs = db.query(GenerationJob).all()
    total_tokens = sum(j.tokens_used or 0 for j in jobs)
    total_budget = sum(j.token_budget or 0 for j in jobs if j.token_budget)
    # documents
    doc_count = db.query(Document).count()
    return {
        "documents": doc_count,
        "items_by_type": {t: c for t, c in by_type},
        "jobs": len(jobs),
        "total_tokens_used_estimate": total_tokens,
        "total_token_budget": total_budget,
        "models": {
            "generation": __import__("app.config", fromlist=["LLM_MODEL"]).LLM_MODEL,
            "cheap": __import__("app.config", fromlist=["LLM_MODEL_CHEAP"]).LLM_MODEL_CHEAP,
        },
    }