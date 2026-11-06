import json
import logging
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from ..models import Document, Chunk, ContentItem
from ..services.llm import chat_json, chat_json_with_retry
from ..schemas import SummaryPayload, FlashcardPayload, MCQPayload, ShortAnswerPayload, AnswerKeyPayload
from ..prompt_registry import load_template, render
from ..logging_config import get_logger
from ..config import LLM_MODEL

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
            try:
                payload = chat_json_with_retry(tmpl["user"], system=tmpl["system"], validate=lambda d: FlashcardPayload(**d))
            except ValueError:
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
            model=LLM_MODEL,
            prompt_version="1.0",
            temperature=0.7,
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
            try:
                payload = chat_json_with_retry(tmpl["user"], system=tmpl["system"], validate=lambda d: MCQPayload(**d))
            except ValueError:
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
            model=LLM_MODEL,
            prompt_version="1.0",
            temperature=0.7,
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

SHORT_ANSWER_SYSTEM = (
    "You are an expert educator. Generate one short-answer question from the source. "
    "Return JSON with keys: 'question' (string), 'model_answer' (string), "
    "'rubric' (list of {criterion, points}), 'max_points' (int). Use ONLY source information."
)


def _short_answer_prompt(chunk_text: str, section: str) -> str:
    return (
        f"Section: {section}\n\nSource text:\n\"\"\"{chunk_text}\"\"\"\n\n"
        "Produce one short-answer question with rubric. Respond with JSON only."
    )


def generate_short_answers(db: Session, document_id: int, items_per_chunk: int = 1) -> List[int]:
    doc = db.query(Document).get(document_id)
    if not doc:
        logger.error("Document %s not found", document_id)
        raise ValueError("Document not found")
    logger.info("Generating short-answer questions for document %s (%d chunks)", document_id, len(doc.chunks))
    created_ids = []
    for chunk in sorted(doc.chunks, key=lambda c: c.order_index):
        for _ in range(items_per_chunk):
            tmpl = render(load_template("short_answer"), section=chunk.section or "", chunk_text=chunk.text)
            try:
                payload = chat_json_with_retry(tmpl["user"], system=tmpl["system"], validate=lambda d: ShortAnswerPayload(**d))
            except ValueError:
                payload = {
                    "question": "Explain the main concept described.",
                    "model_answer": chunk.text[:200],
                    "rubric": [{"criterion": "mentions key concept", "points": 1}],
                    "max_points": 2,
                }
            item = ContentItem(
                document_id=document_id,
                chunk_ids=json.dumps([chunk.id]),
                item_type="short_answer",
                payload=json.dumps(payload),
                bloom_level="Apply",
                quality_score=None,
                status="draft",
                created_by="ai",
            model=LLM_MODEL,
            prompt_version="1.0",
            temperature=0.7,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            created_ids.append(item.id)
            logger.debug("Created short-answer item %s for chunk %s", item.id, chunk.id)
    logger.info("Created %d short-answer items for document %s", len(created_ids), document_id)
    return created_ids


def _valid_short_answer(p: dict) -> bool:
    if not isinstance(p, dict):
        return False
    if not all(k in p for k in ("question", "model_answer", "rubric", "max_points")):
        return False
    if not isinstance(p["rubric"], list):
        return False
    if not isinstance(p["max_points"], int):
        return False
    return True

ANSWER_KEY_SYSTEM = (
    "You are an expert educator. Given an assessment item and its source, produce an answer key. "
    "Return JSON with keys: 'answer' (string), 'grading_notes' (string)."
)


def generate_answer_keys(db: Session, document_id: int) -> List[int]:
    doc = db.query(Document).get(document_id)
    if not doc:
        logger.error("Document %s not found", document_id)
        raise ValueError("Document not found")
    items = db.query(ContentItem).filter(ContentItem.document_id == document_id).all()
    logger.info("Generating answer keys for document %s (%d items)", document_id, len(items))
    created_ids = []
    for it in items:
        if it.item_type == "answer_key":
            continue
        # gather source text
        chunk_ids = it.chunk_id_list()
        chunk = db.query(Chunk).get(chunk_ids[0]) if chunk_ids else None
        source = chunk.text if chunk else ""
        tmpl = render(load_template("answer_key"), item_type=it.item_type, payload=it.payload, chunk_text=source)
        try:
            payload_llm = chat_json_with_retry(tmpl["user"], system=tmpl["system"], validate=lambda d: AnswerKeyPayload(item_id=it.id, **d))
        except ValueError:
            payload_llm = {}
        answer = payload_llm.get("answer")
        grading_notes = payload_llm.get("grading_notes", "")
        if not answer:
            # fallback derive
            p = it.payload_obj()
            if it.item_type == "mcq":
                opts = p.get("options", [])
                correct = [o["text"] for o in opts if o.get("is_correct")]
                answer = correct[0] if correct else ""
                grading_notes = p.get("explanation", "")
            elif it.item_type == "short_answer":
                answer = p.get("model_answer", "")
                grading_notes = "Award points per rubric."
            elif it.item_type == "flashcard":
                answer = p.get("back", "")
                grading_notes = ""
            elif it.item_type == "summary":
                answer = p.get("summary", "")
                grading_notes = "; ".join(p.get("key_points", []))
            else:
                answer = str(p)
        ak_payload = {
            "item_id": it.id,
            "answer": answer,
            "grading_notes": grading_notes,
        }
        item = ContentItem(
            document_id=document_id,
            chunk_ids=json.dumps(chunk_ids),
            item_type="answer_key",
            payload=json.dumps(ak_payload),
            bloom_level=it.bloom_level,
            quality_score=None,
            status="draft",
            created_by="ai",
            model=LLM_MODEL,
            prompt_version="1.0",
            temperature=0.7,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        created_ids.append(item.id)
        logger.debug("Created answer key %s for item %s", item.id, it.id)
    logger.info("Created %d answer key items for document %s", len(created_ids), document_id)
    return created_ids


VALIDATORS = {
    "summary": lambda d: SummaryPayload(**d),
    "flashcard": lambda d: FlashcardPayload(**d),
    "mcq": lambda d: MCQPayload(**d),
    "short_answer": lambda d: ShortAnswerPayload(**d),
}


def regenerate_item(db: Session, item: ContentItem) -> ContentItem:
    if item.item_type == "answer_key":
        return item
    chunk_ids = item.chunk_id_list()
    chunk = db.query(Chunk).get(chunk_ids[0]) if chunk_ids else None
    section = chunk.section if chunk else ""
    text = chunk.text if chunk else ""
    tmpl = render(load_template(item.item_type), section=section or "", chunk_text=text)
    validate = VALIDATORS.get(item.item_type)
    payload = chat_json_with_retry(tmpl["user"], system=tmpl["system"], validate=validate)
    item.payload = json.dumps(payload)
    item.version = (item.version or 1) + 1
    item.created_by = "ai"
    item.model = LLM_MODEL
    item.prompt_version = "1.0"
    item.temperature = 0.7
    item.status = "draft"
    db.commit()
    db.refresh(item)
    logger.info("Regenerated item %s (v%s)", item.id, item.version)
    return item


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
            try:
                payload = chat_json_with_retry(tmpl["user"], system=tmpl["system"], validate=lambda d: SummaryPayload(**d))
            except ValueError:
                payload = {"summary": str(chunk.text)[:200], "key_points": [], "length_tokens": len(chunk.text.split())}
            item = ContentItem(
                document_id=document_id,
                chunk_ids=json.dumps([chunk.id]),
                item_type="summary",
                payload=json.dumps(payload),
                bloom_level="Understand",
                quality_score=None,
                status="draft",
                created_by="ai",
            model=LLM_MODEL,
            prompt_version="1.0",
            temperature=0.7,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            created_ids.append(item.id)
            logger.debug("Created summary item %s for chunk %s", item.id, chunk.id)
    logger.info("Created %d summary items for document %s", len(created_ids), document_id)
    return created_ids
