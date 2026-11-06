from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ContentItem
from ..schemas import ContentItemOut

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ContentItemOut])
def list_items(document_id: int = None, item_type: str = None, status: str = None, db: Session = Depends(get_db)):
    q = db.query(ContentItem)
    if document_id is not None:
        q = q.filter(ContentItem.document_id == document_id)
    if item_type is not None:
        q = q.filter(ContentItem.item_type == item_type)
    if status is not None:
        q = q.filter(ContentItem.status == status)
    items = q.order_by(ContentItem.id.desc()).all()
    out = []
    for it in items:
        import json
        out.append(ContentItemOut(
            id=it.id, document_id=it.document_id, chunk_ids=it.chunk_id_list(),
            item_type=it.item_type, payload=it.payload_obj(), bloom_level=it.bloom_level,
            quality_score=it.quality_score, status=it.status, version=it.version,
            created_by=it.created_by, created_at=it.created_at.isoformat(),
            model=it.model, prompt_version=it.prompt_version, temperature=it.temperature,
            parent_item_id=it.parent_item_id))
    return out


@router.patch("/{item_id}")
def update_item(item_id: int, payload: dict, db: Session = Depends(get_db)):
    it = db.query(ContentItem).get(item_id)
    if not it:
        raise HTTPException(404, "Not found")
    # If payload content changes, create a new version (lineage)
    if "payload" in payload:
        new_item = ContentItem(
            document_id=it.document_id,
            chunk_ids=it.chunk_ids,
            item_type=it.item_type,
            payload=__import__("json").dumps(payload["payload"]),
            bloom_level=payload.get("bloom_level", it.bloom_level),
            quality_score=it.quality_score,
            status=payload.get("status", it.status),
            version=it.version + 1,
            created_by="human",
            model=it.model,
            prompt_version=it.prompt_version,
            temperature=it.temperature,
            parent_item_id=it.id,
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return {"id": new_item.id, "version": new_item.version, "parent_item_id": it.id}
    # status-only update
    if "status" in payload:
        it.status = payload["status"]
    if "bloom_level" in payload:
        it.bloom_level = payload["bloom_level"]
    db.commit()
    return {"id": it.id, "version": it.version}
