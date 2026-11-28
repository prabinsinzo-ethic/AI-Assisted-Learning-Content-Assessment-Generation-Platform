from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..db import get_db
from ..models import Folder, Deck, User

router = APIRouter(prefix="/folders", tags=["folders"])


class FolderIn(BaseModel):
    user_id: int
    name: str
    parent_id: Optional[int] = None


class DeckIn(BaseModel):
    user_id: int
    name: str
    folder_id: Optional[int] = None
    document_id: Optional[int] = None


@router.post("")
def create_folder(payload: FolderIn, db: Session = Depends(get_db)):
    if not db.query(User).get(payload.user_id):
        raise HTTPException(404, "User not found")
    f = Folder(user_id=payload.user_id, name=payload.name, parent_id=payload.parent_id)
    db.add(f)
    db.commit()
    db.refresh(f)
    return {"id": f.id, "name": f.name}


@router.get("")
def list_folders(user_id: int, db: Session = Depends(get_db)):
    folders = db.query(Folder).filter(Folder.user_id == user_id).all()
    return [{"id": f.id, "name": f.name, "parent_id": f.parent_id} for f in folders]


@router.post("/decks")
def create_deck(payload: DeckIn, db: Session = Depends(get_db)):
    if not db.query(User).get(payload.user_id):
        raise HTTPException(404, "User not found")
    d = Deck(folder_id=payload.folder_id, document_id=payload.document_id, name=payload.name)
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"id": d.id, "name": d.name}


@router.get("/decks")
def list_decks(user_id: int, db: Session = Depends(get_db)):
    folders = db.query(Folder).filter(Folder.user_id == user_id).all()
    fids = [f.id for f in folders]
    decks = db.query(Deck).filter(Deck.folder_id.in_(fids) if fids else False).all() if fids else []
    # also decks without folder? include all decks linked to user's documents
    return [{"id": d.id, "name": d.name, "folder_id": d.folder_id, "document_id": d.document_id} for d in decks]