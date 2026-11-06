import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ..db import get_db, SessionLocal
from ..models import GenerationJob, ContentItem
from ..schemas import GenerateRequest, JobStatus
from ..services.generation import (
    generate_summaries, generate_flashcards, generate_mcqs,
    generate_short_answers, generate_answer_keys,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

GENERATORS = {
    "summary": (generate_summaries, True),
    "flashcard": (generate_flashcards, True),
    "mcq": (generate_mcqs, True),
    "short_answer": (generate_short_answers, True),
    "answer_key": (generate_answer_keys, False),
}


def _run_job(job_id: str, db_factory):
    db = db_factory()
    try:
        job = db.query(GenerationJob).get(job_id)
        if not job:
            return
        types = job.types_list()
        items_per_chunk = (job.params and __import__("json").loads(job.params).get("items_per_chunk", 1)) or 1
        job.status = "running"
        db.commit()
        total = len(types) or 1
        results = []
        from ..models import Chunk
        for idx, t in enumerate(types):
            db.refresh(job)
            if job.cancel_requested:
                job.status = "cancelled"
                db.commit()
                return
            # token budget check
            if job.token_budget:
                doc_chunks = db.query(Chunk).filter(Chunk.document_id == job.document_id).all()
                est = sum(c.token_count for c in doc_chunks) * items_per_chunk
                if (job.tokens_used or 0) + est > job.token_budget:
                    job.status = "failed"
                    job.message = "Token budget exceeded"
                    db.commit()
                    return
            gen, needs_items = GENERATORS.get(t, (None, False))
            if gen is None:
                continue
            if needs_items:
                ids = gen(db, job.document_id, items_per_chunk)
            else:
                ids = gen(db, job.document_id)
            results.extend(ids)
            job.result_ids = __import__("json").dumps(results)
            job.progress = (idx + 1) / total
            # update tokens used estimate
            if job.token_budget:
                doc_chunks = db.query(Chunk).filter(Chunk.document_id == job.document_id).all()
                job.tokens_used = (job.tokens_used or 0) + sum(c.token_count for c in doc_chunks) * items_per_chunk
            db.commit()
        job.progress = 1.0
        job.status = "done"
        db.commit()
    except Exception as e:
        job = db.query(GenerationJob).get(job_id)
        if job:
            job.status = "failed"
            job.message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/generate", response_model=JobStatus)
def trigger_generate(req: GenerateRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    import json
    job = GenerationJob(
        id=job_id,
        document_id=req.document_id,
        requested_types=json.dumps(req.types),
        params=json.dumps({"items_per_chunk": req.items_per_chunk, "bloom_distribution": req.bloom_distribution}),
        token_budget=req.token_budget,
        status="queued",
        progress=0.0,
    )
    db.add(job)
    db.commit()
    bg.add_task(_run_job, job_id, SessionLocal)
    return JobStatus(job_id=job_id, status="queued", progress=0.0)


@router.get("/{job_id}", response_model=JobStatus)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatus(job_id=job.id, status=job.status, progress=job.progress,
                     message=job.message, result_ids=job.result_list())


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.cancel_requested = 1
    db.commit()
    return {"ok": True, "status": job.status}