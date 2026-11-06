from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from ..db import get_db
from ..models import ContentItem
from ..services.quality import verify_item_factual

router = APIRouter(prefix="/qc", tags=["qc"])


class VerifyRequest(BaseModel):
    document_id: int
    item_ids: Optional[List[int]] = None


@router.post("/verify")
def verify(req: VerifyRequest, db: Session = Depends(get_db)):
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