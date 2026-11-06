import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from ..db import get_db
from ..models import ContentItem
from ..services.quality import verify_item_factual, detect_duplicates, detect_ambiguity, classify_item_bloom, heuristic_filter, score_quality

router = APIRouter(prefix="/qc", tags=["qc"])


class VerifyRequest(BaseModel):
    document_id: int
    item_ids: Optional[List[int]] = None


class DedupRequest(BaseModel):
    document_id: int
    threshold: float = 0.85


class AmbiguityRequest(BaseModel):
    document_id: int
    item_ids: Optional[List[int]] = None


class BloomRequest(BaseModel):
    document_id: int
    item_ids: Optional[List[int]] = None


class HeuristicRequest(BaseModel):
    document_id: int
    item_ids: Optional[List[int]] = None


class QualityRequest(BaseModel):
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
        it.qc_details = json.dumps(res)
        db.commit()
        results.append({"item_id": it.id, "item_type": it.item_type, **res})
    return {"verified": len(results), "results": results}


@router.post("/dedup")
def dedup(req: DedupRequest, db: Session = Depends(get_db)):
    dups = detect_duplicates(db, req.document_id, req.threshold)
    return {"duplicates_found": len(dups), "duplicates": dups}


@router.post("/ambiguity")
def ambiguity(req: AmbiguityRequest, db: Session = Depends(get_db)):
    q = db.query(ContentItem).filter(ContentItem.document_id == req.document_id)
    if req.item_ids:
        q = q.filter(ContentItem.id.in_(req.item_ids))
    items = q.all()
    results = []
    for it in items:
        res = detect_ambiguity(it)
        details = json.loads(it.qc_details or "{}")
        details["ambiguity"] = res
        it.qc_details = json.dumps(details)
        db.commit()
        results.append({"item_id": it.id, "item_type": it.item_type, **res})
    return {"checked": len(results), "results": results}


@router.post("/bloom")
def bloom(req: BloomRequest, db: Session = Depends(get_db)):
    q = db.query(ContentItem).filter(ContentItem.document_id == req.document_id)
    if req.item_ids:
        q = q.filter(ContentItem.id.in_(req.item_ids))
    items = q.all()
    results = []
    for it in items:
        res = classify_item_bloom(it)
        details = json.loads(it.qc_details or "{}")
        details["bloom"] = res
        it.qc_details = json.dumps(details)
        db.commit()
        results.append({"item_id": it.id, "item_type": it.item_type, **res})
    return {"classified": len(results), "results": results}


@router.post("/heuristics")
def heuristics(req: HeuristicRequest, db: Session = Depends(get_db)):
    q = db.query(ContentItem).filter(ContentItem.document_id == req.document_id)
    if req.item_ids:
        q = q.filter(ContentItem.id.in_(req.item_ids))
    items = q.all()
    results = []
    for it in items:
        res = heuristic_filter(it)
        details = json.loads(it.qc_details or "{}")
        details["heuristics"] = res
        it.qc_details = json.dumps(details)
        db.commit()
        results.append({"item_id": it.id, "item_type": it.item_type, **res})
    return {"checked": len(results), "results": results}


@router.post("/quality-score")
def quality_score(req: QualityRequest, db: Session = Depends(get_db)):
    q = db.query(ContentItem).filter(ContentItem.document_id == req.document_id)
    if req.item_ids:
        q = q.filter(ContentItem.id.in_(req.item_ids))
    items = q.all()
    results = []
    for it in items:
        res = score_quality(it)
        details = json.loads(it.qc_details or "{}")
        details["llm_quality"] = res
        it.qc_details = json.dumps(details)
        db.commit()
        results.append({"item_id": it.id, "item_type": it.item_type, **res})
    return {"scored": len(results), "results": results}