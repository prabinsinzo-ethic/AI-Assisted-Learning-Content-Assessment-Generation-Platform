from fastapi import APIRouter, Depends, HTTPException
import json
from sqlalchemy.orm import Session
from ..db import get_db
from ..schemas import GenerateFlashcardsRequest, GenerateQuestionsRequest, GenerateSummaryRequest, GradeRequest, ChatRequest
from ..services.generation import generate_flashcard_models, generate_question_models, generate_summary_model
from ..services.grading import grade_short_answer
from ..services.rag import answer_question
from ..models import Flashcard, Question, Summary

router = APIRouter(prefix="/study-suite", tags=["study-suite"])


@router.post("/flashcards")
def gen_flashcards(req: GenerateFlashcardsRequest, db: Session = Depends(get_db)):
    try:
        ids = generate_flashcard_models(db, req.document_id, req.count)
    except ValueError as e:
        raise HTTPException(404, str(e))
    cards = db.query(Flashcard).filter(Flashcard.id.in_(ids)).all()
    return {"ids": ids, "flashcards": [{"id": c.id, "front": c.front, "back": c.back, "tags": c.tags} for c in cards]}


@router.post("/mcqs")
def gen_mcqs(req: GenerateQuestionsRequest, db: Session = Depends(get_db)):
    req.qtype = "mcq"
    try:
        ids = generate_question_models(db, req.document_id, "mcq", req.count)
    except ValueError as e:
        raise HTTPException(404, str(e))
    qs = db.query(Question).filter(Question.id.in_(ids)).all()
    return {"ids": ids, "questions": [{"id": q.id, "stem": q.stem, "options": json.loads(q.options) if q.options else [],
                                       "correct_index": q.correct_index, "explanation": q.explanation} for q in qs]}


@router.post("/short-answers")
def gen_short_answers(req: GenerateQuestionsRequest, db: Session = Depends(get_db)):
    try:
        ids = generate_question_models(db, req.document_id, "short_answer", req.count)
    except ValueError as e:
        raise HTTPException(404, str(e))
    qs = db.query(Question).filter(Question.id.in_(ids)).all()
    return {"ids": ids, "questions": [{"id": q.id, "question": q.stem, "model_answer": q.model_answer,
                                       "rubric": json.loads(q.rubric) if q.rubric else [], "max_points": q.max_points} for q in qs]}


@router.post("/summary")
def gen_summary(req: GenerateSummaryRequest, db: Session = Depends(get_db)):
    try:
        sid = generate_summary_model(db, req.document_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    s = db.query(Summary).get(sid)
    return {"id": s.id, "summary": s.summary, "key_points": s.key_points,
            "glossary": s.glossary, "concept_hierarchy": s.concept_hierarchy}


@router.post("/grade")
def grade(req: GradeRequest, db: Session = Depends(get_db)):
    result = grade_short_answer(req.question, req.model_answer, req.rubric, req.student_answer, req.max_points)
    return result


@router.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    result = answer_question(db, req.document_id, req.message, req.history)
    return result