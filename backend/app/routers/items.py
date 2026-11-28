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
        from ..models import Document, Chunk
        doc = db.query(Document).get(it.document_id)
        chunks = [db.query(Chunk).get(cid) for cid in it.chunk_id_list()]
        chunks = [c for c in chunks if c]
        section = chunks[0].section if chunks else None
        pages = None
        if chunks:
            ps = min((c.page_start for c in chunks if c.page_start is not None), default=None)
            pe = max((c.page_end for c in chunks if c.page_end is not None), default=None)
            if ps is not None and pe is not None:
                pages = f"{ps}-{pe}" if ps != pe else str(ps)
            elif ps is not None:
                pages = str(ps)
        out.append(ContentItemOut(
            id=it.id, document_id=it.document_id, chunk_ids=it.chunk_id_list(),
            item_type=it.item_type, payload=it.payload_obj(), bloom_level=it.bloom_level,
            quality_score=it.quality_score, status=it.status, version=it.version,
            created_by=it.created_by, created_at=it.created_at.isoformat(),
            model=it.model, prompt_version=it.prompt_version, temperature=it.temperature,
            parent_item_id=it.parent_item_id,
            source_document=doc.title if doc else None,
            source_section=section,
            source_pages=pages))
    return out


@router.post("/bulk-approve")
def bulk_approve(payload: dict, db: Session = Depends(get_db)):
    doc_id = payload.get("document_id")
    min_q = payload.get("min_quality", 0.8)
    q = db.query(ContentItem).filter(ContentItem.document_id == doc_id, ContentItem.status == "draft")
    items = q.all()
    approved = 0
    for it in items:
        if (it.quality_score or 0) >= min_q:
            it.status = "approved"
            approved += 1
    db.commit()
    return {"approved": approved}


@router.get("/{item_id}/versions")
def item_versions(item_id: int, db: Session = Depends(get_db)):
    # collect lineage
    versions = []
    cur = db.query(ContentItem).get(item_id)
    if not cur:
        raise HTTPException(404, "Not found")
    # walk up parents
    chain = [cur]
    parent_id = cur.parent_item_id
    while parent_id:
        p = db.query(ContentItem).get(parent_id)
        if not p:
            break
        chain.insert(0, p)
        parent_id = p.parent_item_id
    # walk down children
    def children_of(iid):
        return db.query(ContentItem).filter(ContentItem.parent_item_id == iid).all()
    # BFS
    stack = [cur.id]
    seen = {cur.id}
    while stack:
        cid = stack.pop()
        for ch in children_of(cid):
            if ch.id not in seen:
                seen.add(ch.id)
                chain.append(ch)
                stack.append(ch.id)
    # dedup by id preserving order
    uniq = []
    seen_ids = set()
    for c in chain:
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            uniq.append(c)
    out = []
    for it in uniq:
        out.append(ContentItemOut(
            id=it.id, document_id=it.document_id, chunk_ids=it.chunk_id_list(),
            item_type=it.item_type, payload=it.payload_obj(), bloom_level=it.bloom_level,
            quality_score=it.quality_score, status=it.status, version=it.version,
            created_by=it.created_by, created_at=it.created_at.isoformat(),
            model=it.model, prompt_version=it.prompt_version, temperature=it.temperature,
            parent_item_id=it.parent_item_id))
    return out

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
