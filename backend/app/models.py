import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from .db import Base
import hashlib
import os


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(64), nullable=False)
    role = Column(String(50), default="teacher")
    created_at = Column(DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.salt = os.urandom(16).hex()
        self.password_hash = hashlib.sha256((self.salt + password).encode()).hexdigest()

    def check_password(self, password: str) -> bool:
        return hashlib.sha256((self.salt + password).encode()).hexdigest() == self.password_hash


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    filename = Column(String(255))
    doc_type = Column(String(50), default="text")
    status = Column(String(50), default="uploaded")
    created_at = Column(DateTime, default=datetime.utcnow)
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    items = relationship("ContentItem", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    order_index = Column(Integer, default=0)
    section = Column(String(255))
    page_start = Column(Integer)
    page_end = Column(Integer)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    embedding = Column(Text)
    document = relationship("Document", back_populates="chunks")


class ContentItem(Base):
    __tablename__ = "content_items"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_ids = Column(Text)
    item_type = Column(String(50), nullable=False)
    payload = Column(Text, nullable=False)
    bloom_level = Column(String(50))
    quality_score = Column(Float)
    qc_details = Column(Text)
    embedding = Column(Text)
    status = Column(String(50), default="draft")
    version = Column(Integer, default=1)
    created_by = Column(String(50), default="ai")
    created_at = Column(DateTime, default=datetime.utcnow)
    model = Column(String(100))
    prompt_version = Column(String(50))
    temperature = Column(Float)
    parent_item_id = Column(Integer, ForeignKey("content_items.id"))
    document = relationship("Document", back_populates="items")

    def chunk_id_list(self):
        return json.loads(self.chunk_ids or "[]")

    def payload_obj(self):
        return json.loads(self.payload)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    id = Column(String(64), primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    requested_types = Column(Text, default="[]")
    params = Column(Text, default="{}")
    status = Column(String(50), default="queued")
    progress = Column(Float, default=0.0)
    message = Column(Text)
    result_ids = Column(Text, default="[]")
    cancel_requested = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    def types_list(self):
        return json.loads(self.requested_types or "[]")

    def result_list(self):
        return json.loads(self.result_ids or "[]")


class Study(Base):
    __tablename__ = "studies"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    design = Column(Text)
    status = Column(String(50), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)


class StudyPair(Base):
    __tablename__ = "study_pairs"
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    ai_item_id = Column(Integer, ForeignKey("content_items.id"), nullable=False)
    human_item_id = Column(Integer, ForeignKey("content_items.id"), nullable=False)


class StudyAssignment(Base):
    __tablename__ = "study_assignments"
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    pair_id = Column(Integer, ForeignKey("study_pairs.id"), nullable=False)
    rater_id = Column(Integer, nullable=False)
    blinded_label_ai = Column(String(10), nullable=False)


class Rating(Base):
    __tablename__ = "ratings"
    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    pair_id = Column(Integer, ForeignKey("study_pairs.id"), nullable=False)
    rater_id = Column(Integer, nullable=False)
    blinded_label = Column(String(10), nullable=False)
    item_id = Column(Integer, ForeignKey("content_items.id"), nullable=False)
    accuracy = Column(Integer)
    clarity = Column(Integer)
    difficulty = Column(Integer)
    distractor_quality = Column(Integer)
    bloom_alignment = Column(Integer)
    overall = Column(Integer)
    would_use = Column(Integer)
    comments = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)