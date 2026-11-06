from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ContentItem
from ..schemas import ContentItemOut

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ContentItemOut])
def list_items(document_id: int = None, item_type: str = None, db: Session = Depends(get_db)):
    q = db.query(ContentItem)
    if document_id is not None:
        q = q.filter(ContentItem.document_id == document_id)
    if item_type is not None:
        q = q.filter(ContentItem.item_type == item_type)
    items = q.order_by(ContentItem.id.desc()).all()
    out = []
    for it in items:
        import json
        out.append(ContentItemOut(
            id=it.id, document_id=it.document_id, chunk_ids=it.chunk_id_list(),
            item_type=it.item_type, payload=it.payload_obj(), bloom_level=it.bloom_level,
            quality_score=it.quality_score, status=it.status, version=it.version,
            created_by=it.created_by, created_at=it.created_at.isoformat()))
    return out


@router.patch("/{item_id}")
def update_item(item_id: int, payload: dict, db: Session = Depends(get_db)):
    it = db.query(ContentItem).get(item_id)
    if not it:
        raise HTTPException(404, "Not found")
    if "status" in payload:
        it.status = payload["status"]
    if "payload" in payload:
        it.payload = __import__("json").dumps(payload["payload"])
    db.commit()
    return {"ok": True}
