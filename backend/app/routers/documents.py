import shutil
import json
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Document, Chunk
from ..schemas import DocumentOut, ChunkOut
from ..services.ingestion import parse_document, make_chunks_from_blocks
from ..config import UPLOAD_DIR

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut)
async def upload_document(title: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    from ..config import MAX_UPLOAD_MB
    if file.size and file.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, "File too large")
    allowed = {".pdf", ".docx", ".txt", ".md"}
    if Path(file.filename).suffix.lower() not in allowed:
        raise HTTPException(400, "Unsupported file type")
    dest = UPLOAD_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    doc = Document(title=title, filename=file.filename, doc_type="text", status="uploaded")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    blocks = parse_document(dest)
    chunk_dicts = make_chunks_from_blocks(blocks)
    chunks = []
    for cd in chunk_dicts:
        ch = Chunk(
            document_id=doc.id,
            order_index=cd["order_index"],
            section=cd["section"],
            page_start=cd["page_start"],
            page_end=cd["page_end"],
            text=cd["text"],
            token_count=len(cd["text"].split()),
        )
        db.add(ch)
        chunks.append(ch)
    db.commit()
    # compute embeddings
    try:
        from ..services.llm import embed
        vecs = embed([c.text for c in chunks])
        for c, v in zip(chunks, vecs):
            c.embedding = json.dumps(v)
        db.commit()
    except Exception as e:
        import logging
        logging.getLogger("app.documents").warning("Embedding failed: %s", e)
    doc.status = "chunked"
    db.commit()
    db.refresh(doc)
    return _doc_out(doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.id.desc()).all()
    return [_doc_out(d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).get(doc_id)
    if not doc:
        raise HTTPException(404, "Not found")
    return _doc_out(doc)


@router.get("/{doc_id}/chunks", response_model=list[ChunkOut])
def get_chunks(doc_id: int, db: Session = Depends(get_db)):
    chunks = db.query(Chunk).filter(Chunk.document_id == doc_id).order_by(Chunk.order_index).all()
    return [ChunkOut(id=c.id, document_id=c.document_id, order_index=c.order_index, section=c.section,
                    page_start=c.page_start, page_end=c.page_end, text=c.text, token_count=c.token_count) for c in chunks]


def _doc_out(doc):
    return DocumentOut(id=doc.id, title=doc.title, filename=doc.filename, doc_type=doc.doc_type,
                      status=doc.status, created_at=doc.created_at.isoformat())
