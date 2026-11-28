import os, sys, pathlib, time
os.environ["MOCK_LLM"] = "true"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _doc():
    r = client.post("/documents", data={"title": "T"}, files={"file": ("t.txt", b"Photosynthesis uses light.", "text/plain")})
    assert r.status_code == 200
    return r.json()["id"]


def test_flashcards():
    did = _doc()
    r = client.post("/study-suite/flashcards", json={"document_id": did, "count": 2})
    assert r.status_code == 200
    assert len(r.json()["flashcards"]) == 2
    assert "front" in r.json()["flashcards"][0]


def test_mcqs():
    did = _doc()
    r = client.post("/study-suite/mcqs", json={"document_id": did, "count": 2})
    assert r.status_code == 200
    q = r.json()["questions"][0]
    assert len(q["options"]) == 4
    assert "correct_index" in q


def test_short_answers():
    did = _doc()
    r = client.post("/study-suite/short-answers", json={"document_id": did, "count": 1})
    assert r.status_code == 200
    q = r.json()["questions"][0]
    assert "question" in q and "model_answer" in q


def test_summary():
    did = _doc()
    r = client.post("/study-suite/summary", json={"document_id": did})
    assert r.status_code == 200
    assert "summary" in r.json()
    assert "glossary" in r.json()


def test_grade():
    r = client.post("/study-suite/grade", json={
        "question": "What is X?", "model_answer": "X is Y",
        "rubric": [{"criterion": "mentions X", "points": 1}],
        "max_points": 2, "student_answer": "X is Y",
    })
    assert r.status_code == 200
    assert "score" in r.json()


def test_chat():
    did = _doc()
    r = client.post("/study-suite/chat", json={"document_id": did, "message": "What is this?"})
    assert r.status_code == 200
    assert "answer" in r.json()