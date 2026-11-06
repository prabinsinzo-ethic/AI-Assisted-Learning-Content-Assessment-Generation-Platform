import os, sys, tempfile, pathlib
os.environ["MOCK_LLM"] = "true"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal

client = TestClient(app)


def test_health():
    assert client.get("/health").status_code == 200


def test_upload_and_generate_summary():
    content = b"Photosynthesis converts light to glucose."
    files = {"file": ("t.txt", content, "text/plain")}
    r = client.post("/documents", data={"title": "T"}, files=files)
    assert r.status_code == 200
    doc_id = r.json()["id"]
    r = client.post("/jobs/generate", json={"document_id": doc_id, "types": ["summary"], "items_per_chunk": 1})
    assert r.status_code == 200
    job = r.json()["job_id"]
    import time
    for _ in range(20):
        s = client.get(f"/jobs/{job}").json()
        if s["status"] in ("done", "failed"):
            break
        time.sleep(0.2)
    assert s["status"] == "done", s
    items = client.get(f"/items?document_id={doc_id}&item_type=summary").json()
    assert len(items) >= 1
    assert items[0]["item_type"] == "summary"
    assert "summary" in items[0]["payload"]
