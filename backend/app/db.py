from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DB_URL

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    # lightweight migration for new columns
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "content_items" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("content_items")}
        alters = []
        if "model" not in cols:
            alters.append("ALTER TABLE content_items ADD COLUMN model VARCHAR(100)")
        if "prompt_version" not in cols:
            alters.append("ALTER TABLE content_items ADD COLUMN prompt_version VARCHAR(50)")
        if "temperature" not in cols:
            alters.append("ALTER TABLE content_items ADD COLUMN temperature FLOAT")
        if "parent_item_id" not in cols:
            alters.append("ALTER TABLE content_items ADD COLUMN parent_item_id INTEGER")
        if "qc_details" not in cols:
            alters.append("ALTER TABLE content_items ADD COLUMN qc_details TEXT")
        with engine.begin() as conn:
            for a in alters:
                conn.execute(text(a))
