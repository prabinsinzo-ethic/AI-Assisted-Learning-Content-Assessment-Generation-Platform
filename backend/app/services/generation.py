import json
import logging
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from ..models import Document, Chunk, ContentItem
from ..services.llm import chat_json
from ..prompt_registry import load_template, render
from ..logging_config import get_logger

logger = get_logger("app.generation")


SUMMARY_SYSTEM = (
    "You are an expert educator. Generate a concise, accurate summary of the provided source text. "
    "Use ONLY information present in the source. Return JSON with keys: "
    "'summary' (string), 'key_points' (list of strings), 'length_tokens' (int)."
)


def _summary_prompt(chunk_text: str, section: str) -> str:
    return (
        f"Section: {section}\n\nSource text:\n\"\"\"{chunk_text}\"\"\"\n\n"
        "Produce a summary (3-5 sentences) and 3-5 key points. Respond with JSON only."
    )


FLASHCARD_SYSTEM = (
    "You are an expert educator. Generate a flashcard from the provided source text. "
    "Return JSON with keys: 'front' (question/term), 'back' (answer/definition), 'tags' (list of strings). "
    "Use ONLY information present in the source."
)


def _flashcard_prompt(chunk_text: str, section: str) -> str:
    return (
        f"Section: {section}\n\nSource text:\n\"\"\"{chunk_text}\"\"\"\n\n"
        "Produce one flashcard. Respond with JSON only."
    )


def generate_flashcards(db: Session, document_id: int, items_per_chunk: int = 1) -> List[int]:
    doc = db.query(Document).get(document_id)
    if not doc:
        logger.error("Document %s not found", document_id)
        raise ValueError("Document not found")
    logger.info("Generating flashcards for document %s (%d chunks)", document_id, len(doc.chunks))
    created_ids = []
    for chunk in sorted(doc.chunks, key=lambda c: c.order_index):
        for _ in range(items_per_chunk):
            tmpl = render(load_template("flashcard"), section=chunk.section or "", chunk_text=chunk.text)
            payload = chat_json(tmpl["user"], system=tmpl["system"])
            if "front" not in payload or "back" not in payload:
                payload = {"front": "Key concept", "back": chunk.text[:200], "tags": []}
            item = ContentItem(
                document_id=document_id,
                chunk_ids=json.dumps([chunk.id]),
                item_type="flashcard",
                payload=json.dumps(payload),
                bloom_level="Remember",
                quality_score=None,
                status="draft",
                created_by="ai",
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            created_ids.append(item.id)
            logger.debug("Created flashcard item %s for chunk %s", item.id, chunk.id)
    logger.info("Created %d flashcard items for document %s", len(created_ids), document_id)
    return created_ids


MCQ_SYSTEM = (
    "You are an expert educator. Generate one multiple-choice question from the source. "
    "Return JSON with keys: 'stem' (string), 'options' (list of 4 objects {text, is_correct}), "
    "'correct_index' (int 0-3), 'explanation' (string), 'distractor_rationale' (string). "
    "Exactly one option is correct. Use ONLY source information."
)


def _mcq_prompt(chunk_text: str, section: str) -> str:
    return (
        f"Section: {section}\n\nSource text:\n\"\"\"{chunk_text}\"\"\"\n\n"
        "Produce one MCQ with 4 options. Respond with JSON only."
    )


def generate_mcqs(db: Session, document_id: int, items_per_chunk: int = 1) -> List[int]:
    doc = db.query(Document).get(document_id)
    if not doc:
        logger.error("Document %s not found", document_id)
        raise ValueError("Document not found")
    logger.info("Generating MCQs for document %s (%d chunks)", document_id, len(doc.chunks))
    created_ids = []
    for chunk in sorted(doc.chunks, key=lambda c: c.order_index):
        for _ in range(items_per_chunk):
            tmpl = render(load_template("mcq"), section=chunk.section or "", chunk_text=chunk.text)
            payload = chat_json(tmpl["user"], system=tmpl["system"])
            if not _valid_mcq(payload):
                payload = {
                    "stem": "Which statement is correct?",
                    "options": [
                        {"text": chunk.text[:80], "is_correct": True},
                        {"text": "Distractor B", "is_correct": False},
                        {"text": "Distractor C", "is_correct": False},
                        {"text": "Distractor D", "is_correct": False},
                    ],
                    "correct_index": 0,
                    "explanation": "From source.",
                    "distractor_rationale": "Others unsupported.",
                }
            item = ContentItem(
                document_id=document_id,
                chunk_ids=json.dumps([chunk.id]),
                item_type="mcq",
                payload=json.dumps(payload),
                bloom_level="Understand",
                quality_score=None,
                status="draft",
                created_by="ai",
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            created_ids.append(item.id)
            logger.debug("Created MCQ item %s for chunk %s", item.id, chunk.id)
    logger.info("Created %d MCQ items for document %s", len(created_ids), document_id)
    return created_ids


def _valid_mcq(p: dict) -> bool:
    if not isinstance(p, dict):
        return False
    if "stem" not in p or "options" not in p:
        return False
    opts = p["options"]
    if not isinstance(opts, list) or len(opts) != 4:
        return False
    if not all(isinstance(o, dict) and "text" in o and "is_correct" in o for o in opts):
        return False
    ci = p.get("correct_index")
    if not isinstance(ci, int) or not (0 <= ci <= 3):
        return False
    if sum(1 for o in opts if o.get("is_correct")) != 1:
        return False
    return True

def generate_summaries(db: Session, document_id: int, items_per_chunk: int = 1) -> List[int]:
    doc = db.query(Document).get(document_id)
    if not doc:
        logger.error("Document %s not found", document_id)
        raise ValueError("Document not found")
    logger.info("Generating summaries for document %s (%d chunks)", document_id, len(doc.chunks))
    created_ids = []
    for chunk in sorted(doc.chunks, key=lambda c: c.order_index):
        for _ in range(items_per_chunk):
            tmpl = render(load_template("summary"), section=chunk.section or "", chunk_text=chunk.text)
            payload = chat_json(tmpl["user"], system=tmpl["system"])
            if "summary" not in payload:
                payload = {"summary": str(payload), "key_points": [], "length_tokens": len(chunk.text.split())}
            item = ContentItem(
                document_id=document_id,
                chunk_ids=json.dumps([chunk.id]),
                item_type="summary",
                payload=json.dumps(payload),
                bloom_level="Understand",
                quality_score=None,
                status="draft",
                created_by="ai",
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            created_ids.append(item.id)
            logger.debug("Created summary item %s for chunk %s", item.id, chunk.id)
    logger.info("Created %d summary items for document %s", len(created_ids), document_id)
    return created_ids
