import random
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from ..db import get_db
from ..models import Study, StudyPair, StudyAssignment, Rating, ContentItem

router = APIRouter(prefix="/studies", tags=["studies"])


class PairIn(BaseModel):
    ai_item_id: int
    human_item_id: int


class StudyIn(BaseModel):
    name: str
    design: Optional[str] = None
    pairs: List[PairIn]


class RatingIn(BaseModel):
    rater_id: int
    pair_id: int
    blinded_label: str  # 'A' or 'B'
    item_id: int
    accuracy: Optional[int] = None
    clarity: Optional[int] = None
    difficulty: Optional[int] = None
    distractor_quality: Optional[int] = None
    bloom_alignment: Optional[int] = None
    overall: Optional[int] = None
    would_use: Optional[int] = None
    comments: Optional[str] = None


@router.post("")
def create_study(payload: StudyIn, db: Session = Depends(get_db)):
    study = Study(name=payload.name, design=payload.design, status="active")
    db.add(study)
    db.commit()
    db.refresh(study)
    for p in payload.pairs:
        sp = StudyPair(study_id=study.id, ai_item_id=p.ai_item_id, human_item_id=p.human_item_id)
        db.add(sp)
    db.commit()
    return {"id": study.id, "name": study.name, "pairs": len(payload.pairs)}


@router.get("/{study_id}")
def get_study(study_id: int, db: Session = Depends(get_db)):
    st = db.query(Study).get(study_id)
    if not st:
        raise HTTPException(404, "Study not found")
    pairs = db.query(StudyPair).filter(StudyPair.study_id == study_id).all()
    return {"id": st.id, "name": st.name, "design": st.design, "status": st.status,
            "pairs": [{"id": p.id, "ai_item_id": p.ai_item_id, "human_item_id": p.human_item_id} for p in pairs]}


@router.get("/{study_id}/pairs")
def get_pairs(study_id: int, rater_id: int = Query(...), db: Session = Depends(get_db)):
    st = db.query(Study).get(study_id)
    if not st:
        raise HTTPException(404, "Study not found")
    pairs = db.query(StudyPair).filter(StudyPair.study_id == study_id).all()
    out = []
    for p in pairs:
        # get or create assignment for this rater
        assign = db.query(StudyAssignment).filter(
            StudyAssignment.study_id == study_id,
            StudyAssignment.pair_id == p.id,
            StudyAssignment.rater_id == rater_id,
        ).first()
        if not assign:
            label_ai = random.choice(["A", "B"])
            assign = StudyAssignment(study_id=study_id, pair_id=p.id, rater_id=rater_id, blinded_label_ai=label_ai)
            db.add(assign)
            db.commit()
            db.refresh(assign)
        label_ai = assign.blinded_label_ai
        label_human = "B" if label_ai == "A" else "A"
        # item for A and B
        item_a = p.ai_item_id if label_ai == "A" else p.human_item_id
        item_b = p.human_item_id if label_ai == "A" else p.ai_item_id
        out.append({
            "pair_id": p.id,
            "A": {"item_id": item_a, "payload": db.query(ContentItem).get(item_a).payload_obj()},
            "B": {"item_id": item_b, "payload": db.query(ContentItem).get(item_b).payload_obj()},
        })
    return {"rater_id": rater_id, "pairs": out}


@router.post("/{study_id}/ratings")
def submit_rating(study_id: int, payload: RatingIn, db: Session = Depends(get_db)):
    st = db.query(Study).get(study_id)
    if not st:
        raise HTTPException(404, "Study not found")
    pair = db.query(StudyPair).get(payload.pair_id)
    if not pair or pair.study_id != study_id:
        raise HTTPException(404, "Pair not found")
    # determine which original item (ai/human) corresponds to blinded label
    assign = db.query(StudyAssignment).filter(
        StudyAssignment.study_id == study_id,
        StudyAssignment.pair_id == pair.id,
        StudyAssignment.rater_id == payload.rater_id,
    ).first()
    if not assign:
        raise HTTPException(400, "No assignment for rater")
    rating = Rating(
        study_id=study_id,
        pair_id=pair.id,
        rater_id=payload.rater_id,
        blinded_label=payload.blinded_label,
        item_id=payload.item_id,
        accuracy=payload.accuracy,
        clarity=payload.clarity,
        difficulty=payload.difficulty,
        distractor_quality=payload.distractor_quality,
        bloom_alignment=payload.bloom_alignment,
        overall=payload.overall,
        would_use=payload.would_use,
        comments=payload.comments,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return {"id": rating.id, "ok": True}


@router.get("/{study_id}/results")
def results(study_id: int, db: Session = Depends(get_db)):
    st = db.query(Study).get(study_id)
    if not st:
        raise HTTPException(404, "Study not found")
    pairs = db.query(StudyPair).filter(StudyPair.study_id == study_id).all()
    out_pairs = []
    for p in pairs:
        assign_rows = db.query(StudyAssignment).filter(StudyAssignment.pair_id == p.id).all()
        # map blinded label -> original group (ai/human) using first assignment? Need unblind per rater; aggregate by group.
        ratings = db.query(Rating).filter(Rating.pair_id == p.id).all()
        # group ratings by whether item is ai or human
        ai_scores = []
        human_scores = []
        for r in ratings:
            if r.item_id == p.ai_item_id:
                ai_scores.append(r)
            elif r.item_id == p.human_item_id:
                human_scores.append(r)
        def agg(rs):
            if not rs:
                return None
            def mean(attr):
                vals = [getattr(x, attr) for x in rs if getattr(x, attr) is not None]
                return (sum(vals) / len(vals)) if vals else None
            return {
                "n": len(rs),
                "accuracy": mean("accuracy"),
                "clarity": mean("clarity"),
                "difficulty": mean("difficulty"),
                "distractor_quality": mean("distractor_quality"),
                "bloom_alignment": mean("bloom_alignment"),
                "overall": mean("overall"),
                "would_use": mean("would_use"),
            }
        out_pairs.append({
            "pair_id": p.id,
            "ai": agg(ai_scores),
            "human": agg(human_scores),
        })
    return {"study_id": study_id, "pairs": out_pairs}