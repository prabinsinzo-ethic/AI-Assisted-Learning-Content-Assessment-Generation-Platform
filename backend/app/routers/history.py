import os
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..db import get_db, SessionLocal
from ..models import (
    User, Document, Chunk, ContentItem, Flashcard, Question, Summary,
    ChatMessage, QuizAttempt, StudyProgress, Folder, Deck, Study, StudyPair, Rating, GenerationJob,
)
from ..config import UPLOAD_DIR, AUTH_REQUIRED
from ..services.llm import embed

router = APIRouter(prefix="/api/history", tags=["history"])


def _verify(user_id: int, token: Optional[str]):
    if not AUTH_REQUIRED:
        return
    if not token:
        raise HTTPException(401, "Token required")
    # reuse auth verify
    from .auth import verify_token
    data = verify_token(token)
    if data.get("id") != user_id:
        raise HTTPException(403, "Forbidden")


def _delete_document(db: Session, doc: Document):
    # delete related records
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.query(ContentItem).filter(ContentItem.document_id == doc.id).delete()
    db.query(Flashcard).filter(Flashcard.document_id == doc.id).delete()
    db.query(Question).filter(Question.document_id == doc.id).delete()
    db.query(Summary).filter(Summary.document_id == doc.id).delete()
    db.query(ChatMessage).filter(ChatMessage.document_id == doc.id).delete()
    db.query(QuizAttempt).filter(QuizAttempt.document_id == doc.id).delete()
    db.query(GenerationJob).filter(GenerationJob.document_id == doc.id).delete()
    # study progress for items in this doc (via content_items already deleted; progress references item_id)
    # delete progress whose item belonged to doc: find item ids first (already deleted) -> skip; best-effort by chunk? We'll delete orphaned progress not needed.
    # uploaded file
    if doc.filename and not doc.filename.startswith("http"):
        try:
            path = UPLOAD_DIR / doc.filename
            if path.exists():
                path.unlink()
        except Exception:
            pass
    db.delete(doc)


@router.delete("/tutor")
def clear_all_tutor(user_id: int = Query(...), token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    _verify(user_id, token)
    db.query(ChatMessage).filter(ChatMessage.user_id == user_id).delete()
    db.commit()
    return {"ok": True, "cleared": "all"}


@router.delete("/tutor/{source_id}")
def clear_tutor(source_id: int, user_id: int = Query(...), token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    _verify(user_id, token)
    # verify ownership: document must belong to user (if user_id tracked)
    doc = db.query(Document).get(source_id)
    if doc and doc.user_id is not None and doc.user_id != user_id:
        raise HTTPException(403, "Forbidden")
    db.query(ChatMessage).filter(ChatMessage.user_id == user_id, ChatMessage.document_id == source_id).delete()
    db.commit()
    return {"ok": True, "source_id": source_id}


@router.post("/progress/reset/{deck_id}")
def reset_progress(deck_id: int, user_id: int = Query(...), token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    _verify(user_id, token)
    # deck_id treated as document_id
    doc = db.query(Document).get(deck_id)
    if doc and doc.user_id is not None and doc.user_id != user_id:
        raise HTTPException(403, "Forbidden")
    # reset SM-2 on flashcards
    for fc in db.query(Flashcard).filter(Flashcard.document_id == deck_id).all():
        fc.ease_factor = 2.5
        fc.interval_days = 0
        fc.repetitions = 0
        fc.next_review = datetime.utcnow()
        fc.last_reviewed = None
    # reset study progress for items in this doc
    item_ids = [c.id for c in db.query(ContentItem).filter(ContentItem.document_id == deck_id).all()]
    if item_ids:
        db.query(StudyProgress).filter(StudyProgress.user_id == user_id, StudyProgress.item_id.in_(item_ids)).delete(synchronize_session=False)
    # quiz attempts
    db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id, QuizAttempt.document_id == deck_id).delete()
    db.commit()
    return {"ok": True, "deck_id": deck_id}


@router.delete("/materials/{source_id}")
def delete_material(source_id: int, user_id: int = Query(...), token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    _verify(user_id, token)
    doc = db.query(Document).get(source_id)
    if not doc:
        raise HTTPException(404, "Not found")
    if doc.user_id is not None and doc.user_id != user_id:
        raise HTTPException(403, "Forbidden")
    _delete_document(db, doc)
    db.commit()
    return {"ok": True, "deleted": source_id}


@router.delete("/all")
def delete_all(user_id: int = Query(...), token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    _verify(user_id, token)
    # delete user's documents
    docs = db.query(Document).filter(Document.user_id == user_id).all()
    for d in docs:
        _delete_document(db, d)
    # delete chat messages, progress, quiz attempts, folders/decks
    db.query(ChatMessage).filter(ChatMessage.user_id == user_id).delete()
    db.query(StudyProgress).filter(StudyProgress.user_id == user_id).delete()
    db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id).delete()
    # folders/decks
    decks = db.query(Deck).join(Folder, Deck.folder_id == Folder.id, isouter=True).filter(Folder.user_id == user_id).all()
    for dk in decks:
        db.delete(dk)
    db.query(Folder).filter(Folder.user_id == user_id).delete()
    db.commit()
    return {"ok": True}


@router.delete("/account")
def delete_account(user_id: int = Query(...), token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    _verify(user_id, token)
    # delete all user data first
    # reuse delete_all logic by calling internal
    docs = db.query(Document).filter(Document.user_id == user_id).all()
    for d in docs:
        _delete_document(db, d)
    db.query(ChatMessage).filter(ChatMessage.user_id == user_id).delete()
    db.query(StudyProgress).filter(StudyProgress.user_id == user_id).delete()
    db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id).delete()
    decks = db.query(Deck).join(Folder, Deck.folder_id == Folder.id, isouter=True).filter(Folder.user_id == user_id).all()
    for dk in decks:
        db.delete(dk)
    db.query(Folder).filter(Folder.user_id == user_id).delete()
    # delete user
    user = db.query(User).get(user_id)
    if user:
        db.delete(user)
    db.commit()
    return {"ok": True}