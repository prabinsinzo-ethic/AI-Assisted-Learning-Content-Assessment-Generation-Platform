from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from ..db import get_db
from ..models import ContentItem
from ..services.quality import verify_item_factual, detect_duplicates

router = APIRouter(prefix="/qc", tags=["qc"])


class VerifyRequest(BaseModel):
    document_id: int
    item_ids: Optional[List[int]] = None


class DedupRequest(BaseModel):
    document_id: int
    threshold: float = 0.85


@router.post("/dedup")
def dedup(req: DedupRequest, db: Session = Depends(get_db)):
    dups = detect_duplicates(db, req.document_id, req.threshold)
    return {"duplicates_found": len(dups), "duplicates": dups}
    q = db.query(ContentItem).filter(ContentItem.document_id == req.document_id)
    if req.item_ids:
        q = q.filter(ContentItem.id.in_(req.item_ids))
    items = q.all()
    results = []
    for it in items:
        res = verify_item_factual(it, db)
        it.quality_score = res["grounding_score"]
        it.qc_details = __import__("json").dumps(res)
        db.commit()
        results.append({"item_id": it.id, "item_type": it.item_type, **res})
    return {"verified": len(results), "results": results}