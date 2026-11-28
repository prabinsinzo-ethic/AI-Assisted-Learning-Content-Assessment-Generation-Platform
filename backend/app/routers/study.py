from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..db import get_db
from ..models import StudyProgress, ContentItem, User

router = APIRouter(prefix="/study", tags=["study"])


class ReviewIn(BaseModel):
    user_id: int
    item_id: int
    quality: int  # 0-5


@router.post("/review")
def review(payload: ReviewIn, db: Session = Depends(get_db)):
    if payload.quality < 0 or payload.quality > 5:
        raise HTTPException(400, "quality must be 0-5")
    user = db.query(User).get(payload.user_id)
    if not user:
        raise HTTPException(404, "User not found")
    item = db.query(ContentItem).get(payload.item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    prog = db.query(StudyProgress).filter(
        StudyProgress.user_id == payload.user_id,
        StudyProgress.item_id == payload.item_id,
    ).first()
    if not prog:
        prog = StudyProgress(user_id=payload.user_id, item_id=payload.item_id)
        db.add(prog)
    # ensure defaults
    prog.ease_factor = prog.ease_factor or 2.5
    prog.interval_days = prog.interval_days or 0
    prog.repetitions = prog.repetitions or 0
    # SM-2
    q = payload.quality
    if q < 3:
        prog.repetitions = 0
        prog.interval_days = 1
    else:
        prog.repetitions += 1
        if prog.repetitions == 1:
            prog.interval_days = 1
        elif prog.repetitions == 2:
            prog.interval_days = 6
        else:
            prog.interval_days = round(prog.interval_days * prog.ease_factor)
        prog.ease_factor = max(1.3, prog.ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    prog.next_review = datetime.utcnow() + timedelta(days=prog.interval_days)
    prog.last_reviewed = datetime.utcnow()
    db.commit()
    db.refresh(prog)
    return {"item_id": prog.item_id, "ease_factor": prog.ease_factor,
            "interval_days": prog.interval_days, "next_review": prog.next_review.isoformat()}


@router.get("/due")
def due(user_id: int, document_id: Optional[int] = None, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    q = db.query(StudyProgress).filter(StudyProgress.user_id == user_id, StudyProgress.next_review <= now)
    progs = q.all()
    item_ids = [p.item_id for p in progs]
    items = db.query(ContentItem).filter(ContentItem.id.in_(item_ids)) if item_ids else []
    if document_id:
        items = [i for i in items if i.document_id == document_id]
    return {"user_id": user_id, "due_count": len(items),
            "items": [{"id": i.id, "type": i.item_type, "payload": i.payload_obj()} for i in items]}