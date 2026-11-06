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
    role = Column(String(50), default="teacher")  # teacher, reviewer, admin
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
    embedding = Column(Text)  # JSON list
    document = relationship("Document", back_populates="chunks")


class ContentItem(Base):
    __tablename__ = "content_items"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_ids = Column(Text)  # JSON list
    item_type = Column(String(50), nullable=False)  # summary|flashcard|mcq|short_answer
    payload = Column(Text, nullable=False)  # JSON
    bloom_level = Column(String(50))
    quality_score = Column(Float)
    status = Column(String(50), default="draft")
    version = Column(Integer, default=1)
    created_by = Column(String(50), default="ai")
    created_at = Column(DateTime, default=datetime.utcnow)
    document = relationship("Document", back_populates="items")

    def chunk_id_list(self):
        return json.loads(self.chunk_ids or "[]")

    def payload_obj(self):
        return json.loads(self.payload)
