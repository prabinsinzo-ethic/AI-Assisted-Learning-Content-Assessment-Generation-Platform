from pydantic import BaseModel
from typing import List, Optional, Any, Dict


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
