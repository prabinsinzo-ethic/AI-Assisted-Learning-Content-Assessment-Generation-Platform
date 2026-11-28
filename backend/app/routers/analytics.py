from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ..db import get_db
from ..models import User, StudyProgress, QuizAttempt, ContentItem, Document

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    # streak: consecutive days with review
    progress = db.query(StudyProgress).filter(StudyProgress.user_id == user_id).all()
    review_dates = sorted({p.last_reviewed.date() for p in progress if p.last_reviewed})
    streak = 0
    today = datetime.utcnow().date()
    d = today
    while d in review_dates:
        streak += 1
        d = d - timedelta(days=1)
    # mastery: % of due items with interval >= 21 days
    total = len(progress)
    mastered = sum(1 for p in progress if (p.interval_days or 0) >= 21)
    mastery_pct = (mastered / total * 100) if total else 0.0
    # weak areas: items with ease_factor < 2.0
    weak = [p.item_id for p in progress if (p.ease_factor or 2.5) < 2.0]
    # quiz accuracy
    attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id).all()
    quiz_acc = None
    if attempts:
        scores = [a.score for a in attempts if a.score is not None]
        maxs = [1 for _ in scores]  # placeholder
        quiz_acc = (sum(scores) / len(scores)) if scores else None
    return {
        "user_id": user_id,
        "streak_days": streak,
        "total_reviewed": total,
        "mastered": mastered,
        "mastery_percent": round(mastery_pct, 1),
        "weak_item_ids": weak,
        "quiz_attempts": len(attempts),
        "quiz_avg_score": quiz_acc,
    }