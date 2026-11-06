from pydantic import BaseModel, Field, validator
from typing import List, Optional, Any, Dict


class SummaryPayload(BaseModel):
    summary: str
    key_points: List[str] = []
    length_tokens: Optional[int] = None


class FlashcardPayload(BaseModel):
    front: str
    back: str
    tags: List[str] = []


class MCQOption(BaseModel):
    text: str
    is_correct: bool


class MCQPayload(BaseModel):
    stem: str
    options: List[MCQOption]
    correct_index: int
    explanation: str = ""
    distractor_rationale: str = ""

    @validator("options")
    def _four_options(cls, v):
        if len(v) != 4:
            raise ValueError("MCQ must have exactly 4 options")
        return v

    @validator("correct_index")
    def _valid_index(cls, v, values):
        if v < 0 or v > 3:
            raise ValueError("correct_index out of range")
        return v


class RubricItem(BaseModel):
    criterion: str
    points: int


class ShortAnswerPayload(BaseModel):
    question: str
    model_answer: str
    rubric: List[RubricItem] = []
    max_points: int = 1


class AnswerKeyPayload(BaseModel):
    item_id: int
    answer: str
    grading_notes: str = ""
    id: int
    title: str
    filename: Optional[str] = None
    doc_type: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: int
    title: str
    filename: Optional[str] = None
    doc_type: str
    status: str
    created_at: str

    class Config:
        from_attributes = True

class ChunkOut(BaseModel):
    id: int
    document_id: int
    order_index: int
    section: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    text: str
    token_count: int


class ContentItemOut(BaseModel):
    id: int
    document_id: int
    chunk_ids: List[int]
    item_type: str
    payload: Dict[str, Any]
    bloom_level: Optional[str] = None
    quality_score: Optional[float] = None
    status: str
    version: int
    created_by: str
    created_at: str


class GenerateRequest(BaseModel):
    document_id: int
    types: List[str] = ["summary"]
    items_per_chunk: int = 1
    bloom_distribution: Optional[Dict[str, float]] = None


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float
    message: Optional[str] = None
    result_ids: List[int] = []
