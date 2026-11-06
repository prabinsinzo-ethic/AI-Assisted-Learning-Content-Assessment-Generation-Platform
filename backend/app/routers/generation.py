from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import GenerateRequest, JobStatus
from ..services.generation import generate_summaries, generate_flashcards, generate_mcqs

router = APIRouter(prefix="/jobs", tags=["jobs"])

# in-memory job store
_JOBS = {}


@router.post("/generate", response_model=JobStatus)
def trigger_generate(req: GenerateRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    import uuid
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {"status": "queued", "progress": 0.0, "result_ids": []}

    def run():
        try:
            _JOBS[job_id]["status"] = "running"
            if "summary" in req.types:
                ids = generate_summaries(db, req.document_id, req.items_per_chunk)
                _JOBS[job_id]["result_ids"].extend(ids)
            if "flashcard" in req.types:
                ids = generate_flashcards(db, req.document_id, req.items_per_chunk)
                _JOBS[job_id]["result_ids"].extend(ids)
            if "mcq" in req.types:
                ids = generate_mcqs(db, req.document_id, req.items_per_chunk)
                _JOBS[job_id]["result_ids"].extend(ids)
            _JOBS[job_id]["progress"] = 1.0
            _JOBS[job_id]["status"] = "done"
        except Exception as e:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["message"] = str(e)

    bg.add_task(run)
    return JobStatus(job_id=job_id, status="queued", progress=0.0)


@router.get("/{job_id}", response_model=JobStatus)
def get_job(job_id: str):
    j = _JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return JobStatus(job_id=job_id, status=j["status"], progress=j["progress"],
                     message=j.get("message"), result_ids=j.get("result_ids", []))
