import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel

from ..db import get_db
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET = os.getenv("AUTH_SECRET", "dev-secret-change-me")
serializer = URLSafeTimedSerializer(SECRET, salt="auth")


class RegisterIn(BaseModel):
    username: str
    password: str
    role: str = "teacher"


class LoginIn(BaseModel):
    username: str
    password: str


def create_token(user: User) -> str:
    return serializer.dumps({"id": user.id, "username": user.username, "role": user.role})


def verify_token(token: str) -> dict:
    try:
        return serializer.loads(token, max_age=60 * 60 * 24 * 7)
    except SignatureExpired:
        raise HTTPException(401, "Token expired")
    except BadSignature:
        raise HTTPException(401, "Invalid token")


def get_current_user(token: str = None, db: Session = Depends(get_db)):
    if not token:
        return None
    data = verify_token(token)
    user = db.query(User).get(data["id"])
    if not user:
        raise HTTPException(401, "User not found")
    return user


@router.post("/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, "Username taken")
    if payload.role not in ("teacher", "reviewer", "admin"):
        raise HTTPException(400, "Invalid role")
    u = User(username=payload.username, role=payload.role)
    u.set_password(payload.password)
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "username": u.username, "role": u.role, "token": create_token(u)}


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == payload.username).first()
    if not u or not u.check_password(payload.password):
        raise HTTPException(401, "Invalid credentials")
    return {"id": u.id, "username": u.username, "role": u.role, "token": create_token(u)}


@router.get("/me")
def me(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token=token, db=db)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {"id": user.id, "username": user.username, "role": user.role}
