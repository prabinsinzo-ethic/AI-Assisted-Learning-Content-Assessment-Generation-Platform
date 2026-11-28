import json
import math
from typing import List, Tuple
from sqlalchemy.orm import Session

from ..models import Document, Chunk
from ..services.llm import chat, embed, cosine
from ..logging_config import get_logger

logger = get_logger("app.rag")


def retrieve_chunks(db: Session, document_id: int, query: str, k: int = 5) -> List[Chunk]:
    chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
    if not chunks:
        return []
    qvec = embed([query])[0]
    scored = []
    for c in chunks:
        try:
            cvec = json.loads(c.embedding) if c.embedding else None
        except Exception:
            cvec = None
        if cvec:
            sim = cosine(qvec, cvec)
        else:
            # keyword fallback
            qwords = set(query.lower().split())
            cwords = set(c.text.lower().split())
            sim = len(qwords & cwords) / max(len(qwords), 1)
        scored.append((sim, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]


def answer_question(db: Session, document_id: int, question: str, history: List[dict] = None) -> dict:
    chunks = retrieve_chunks(db, document_id, question, k=5)
    context = "\n\n".join(f"[Chunk {c.id}] {c.text}" for c in chunks)
    history = history or []
    hist_text = "\n".join(f"{h.get('role','user')}: {h.get('content','')}" for h in history[-6:])
    prompt = (
        "You are a tutor. Answer the student's question using ONLY the provided source context. "
        "If the answer is not in the context, say you don't know. Cite chunk IDs.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"HISTORY:\n{hist_text}\n\n"
        f"QUESTION: {question}\n\n"
        "Return JSON: {\"answer\": \"...\", \"sources\": [chunk_ids]}."
    )
    try:
        from ..services.llm import chat_json
        data = chat_json(prompt, system="You are a strict, source-grounded tutor.", model=None)
        return {"answer": data.get("answer", ""), "sources": data.get("sources", [c.id for c in chunks])}
    except Exception as e:
        logger.warning("Chat failed: %s", e)
        return {"answer": "I could not generate an answer.", "sources": []}