import json
import logging
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from ..models import ContentItem, Chunk
from ..services.llm import chat_json, embed, cosine as cos_sim
from ..logging_config import get_logger

logger = get_logger("app.quality")

GROUNDING_THRESHOLD = 0.8


def _extract_claims(text: str) -> List[str]:
    prompt = (
        "Extract the atomic factual claims from the following text. "
        "Return JSON: {\"claims\": [\"claim1\", ...]}. Only claims that assert facts.\n\n"
        f"Text:\n{text}"
    )
    try:
        data = chat_json(prompt, system="You extract atomic factual claims.")
        claims = data.get("claims", [])
        if not isinstance(claims, list):
            claims = []
        return [str(c) for c in claims]
    except Exception as e:
        logger.warning("Claim extraction failed: %s", e)
        return []


def _entailment_score(claim: str, source: str) -> float:
    prompt = (
        "Given a SOURCE and a CLAIM, output a JSON object with key 'score' (0.0 to 1.0) "
        "representing how well the source supports/entails the claim. "
        "1.0 = fully supported, 0.0 = contradicted or not in source.\n\n"
        f"SOURCE:\n{source}\n\nCLAIM:\n{claim}\n\nRespond JSON only."
    )
    try:
        data = chat_json(prompt, system="You are a strict fact-checker.")
        score = float(data.get("score", 0.0))
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.warning("Entailment scoring failed: %s", e)
        return 0.0


def verify_item_factual(item: ContentItem, db: Session) -> Dict[str, Any]:
    # gather source text
    chunks = [db.query(Chunk).get(cid) for cid in item.chunk_id_list()]
    chunks = [c for c in chunks if c]
    source_text = "\n\n".join(c.text for c in chunks)
    # build item text to check
    p = item.payload_obj()
    item_text = json.dumps(p)
    claims = _extract_claims(item_text)
    if not claims:
        claims = [item_text[:300]]
    details = []
    scores = []
    for claim in claims:
        # retrieve best chunk
        best = 0.0
        best_chunk = None
        for c in chunks:
            s = _entailment_score(claim, c.text)
            if s > best:
                best = s
                best_chunk = c.id
        # also check full source
        full_score = _entailment_score(claim, source_text)
        if full_score > best:
            best = full_score
            best_chunk = None
        scores.append(best)
        details.append({"claim": claim, "score": best, "support_chunk_id": best_chunk})
    grounding_score = (sum(scores) / len(scores)) if scores else 0.0
    passed = grounding_score >= GROUNDING_THRESHOLD and all(s >= GROUNDING_THRESHOLD for s in scores) if scores else False
    return {
        "grounding_score": grounding_score,
        "passed": bool(passed),
        "claims": details,
        "threshold": GROUNDING_THRESHOLD,
    }


def score_quality(item: ContentItem) -> Dict[str, Any]:
    p = item.payload_obj()
    prompt = (
        "Rate the quality of the following assessment item on a 1-5 scale. "
        "Provide scores for clarity, relevance, and difficulty appropriateness, plus an overall quality_score.\n\n"
        f"Item type: {item.item_type}\nItem: {json.dumps(p)}\n\n"
        "Return JSON: {\"quality_score\": 1-5, \"clarity\": 1-5, \"relevance\": 1-5, \"difficulty\": 1-5, \"passed\": true/false}."
    )
    try:
        data = chat_json(prompt, system="You are a strict assessment quality reviewer.")
        qs = int(data.get("quality_score", 3))
        qs = max(1, min(5, qs))
        clarity = int(data.get("clarity", qs))
        relevance = int(data.get("relevance", qs))
        difficulty = int(data.get("difficulty", qs))
        passed = bool(data.get("passed", qs >= 3))
    except Exception as e:
        logger.warning("Quality scoring failed: %s", e)
        qs = 3
        clarity = relevance = difficulty = 3
        passed = False
    return {
        "quality_score": qs,
        "clarity": clarity,
        "relevance": relevance,
        "difficulty": difficulty,
        "passed": passed,
    }


def heuristic_filter(item: ContentItem) -> Dict[str, Any]:
    p = item.payload_obj()
    reasons = []
    t = item.item_type
    if t == "summary":
        s = p.get("summary", "")
        if len(s) < 20:
            reasons.append("summary too short")
        if len(s) > 5000:
            reasons.append("summary too long")
        if not p.get("key_points"):
            reasons.append("missing key_points")
    elif t == "flashcard":
        if not p.get("front") or not p.get("back"):
            reasons.append("missing front/back")
        if len(p.get("front", "")) > 500 or len(p.get("back", "")) > 2000:
            reasons.append("flashcard too long")
    elif t == "mcq":
        stem = p.get("stem", "")
        opts = p.get("options", [])
        if not stem:
            reasons.append("missing stem")
        if len(opts) != 4:
            reasons.append("mcq must have 4 options")
        texts = [str(o.get("text", "")).strip().lower() for o in opts]
        if len(set(texts)) != len(texts):
            reasons.append("duplicate options")
        if sum(1 for o in opts if o.get("is_correct")) != 1:
            reasons.append("mcq must have exactly one correct option")
        if p.get("correct_index") is not None and not (0 <= int(p["correct_index"]) <= 3):
            reasons.append("invalid correct_index")
        low_stem = stem.lower()
        for ot in texts:
            if ot and ot in low_stem:
                reasons.append("answer leakage in stem")
                break
        for ot in texts:
            if "all of the above" in ot or "none of the above" in ot:
                reasons.append("avoid all/none of the above")
                break
        if stem.lower().startswith("which") and len(stem) < 10:
            reasons.append("trivial stem")
    elif t == "short_answer":
        if not p.get("question"):
            reasons.append("missing question")
        if not p.get("model_answer"):
            reasons.append("missing model_answer")
        if not p.get("rubric"):
            reasons.append("missing rubric")
        if not isinstance(p.get("max_points"), int) or p.get("max_points", 0) < 1:
            reasons.append("invalid max_points")
    elif t == "answer_key":
        if not p.get("answer"):
            reasons.append("missing answer")
    else:
        reasons.append("unknown item type")
    # generic emptiness
    if not p:
        reasons.append("empty payload")
    return {"passed": len(reasons) == 0, "reasons": reasons}


BLOOM_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]


def classify_bloom(text: str) -> Dict[str, Any]:
    prompt = (
        "Classify the following assessment item into one Bloom's Taxonomy level: "
        "Remember, Understand, Apply, Analyze, Evaluate, or Create.\n\n"
        f"Item:\n{text}\n\n"
        "Return JSON: {\"bloom_level\": \"...\", \"confidence\": 0.0-1.0}."
    )
    try:
        data = chat_json(prompt, system="You are an expert in Bloom's Taxonomy.")
        level = data.get("bloom_level", "Understand")
        if level not in BLOOM_LEVELS:
            level = "Understand"
        conf = float(data.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
    except Exception as e:
        logger.warning("Bloom classification failed: %s", e)
        level = "Understand"
        conf = 0.0
    return {"bloom_level": level, "confidence": conf}


def classify_item_bloom(item: ContentItem) -> Dict[str, Any]:
    res = classify_bloom(json.dumps(item.payload_obj()))
    item.bloom_level = res["bloom_level"]
    return res


def detect_ambiguity(item: ContentItem) -> Dict[str, Any]:
    p = item.payload_obj()
    prompt = (
        "Evaluate the following assessment item for ambiguity. Consider: "
        "Is the question stem clear and unambiguous? Is there exactly one correct answer? "
        "Are options mutually exclusive and exhaustive (for MCQ)? Is the rubric observable and non-overlapping (for short answer)?\n\n"
        f"Item type: {item.item_type}\nItem: {json.dumps(p)}\n\n"
        "Return JSON: {\"ambiguity_score\": 1-5 (1=clear, 5=very ambiguous), \"issues\": [\"...\"]}."
    )
    try:
        data = chat_json(prompt, system="You are a strict assessment reviewer.")
        score = int(data.get("ambiguity_score", 3))
        score = max(1, min(5, score))
        issues = data.get("issues", [])
        if not isinstance(issues, list):
            issues = []
    except Exception as e:
        logger.warning("Ambiguity detection failed: %s", e)
        score = 3
        issues = [str(e)]
    passed = score <= 2
    return {"ambiguity_score": score, "passed": passed, "issues": issues}


def item_text(item: ContentItem) -> str:
    p = item.payload_obj()
    t = item.item_type
    if t == "summary":
        return p.get("summary", "") + " " + " ".join(p.get("key_points", []))
    if t == "flashcard":
        return p.get("front", "") + " " + p.get("back", "")
    if t == "mcq":
        opts = " ".join(o.get("text", "") for o in p.get("options", []))
        return p.get("stem", "") + " " + opts
    if t == "short_answer":
        return p.get("question", "") + " " + p.get("model_answer", "")
    if t == "answer_key":
        return p.get("answer", "") + " " + p.get("grading_notes", "")
    return str(p)


def detect_duplicates(db: Session, document_id: int, threshold: float = 0.85) -> List[Dict[str, Any]]:
    items = db.query(ContentItem).filter(ContentItem.document_id == document_id).all()
    texts = [item_text(it) for it in items]
    vecs = [json.loads(it.embedding) if it.embedding else None for it in items]
    for i, v in enumerate(vecs):
        if v is None:
            ev = embed([texts[i]])[0]
            items[i].embedding = json.dumps(ev)
            vecs[i] = ev
    db.commit()
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            sim = cos_sim(vecs[i], vecs[j])
            if sim >= threshold:
                if items[j].status != "rejected":
                    items[j].status = "rejected"
                details = json.loads(items[j].qc_details or "{}")
                details["duplicate_of"] = items[i].id
                details["similarity"] = sim
                items[j].qc_details = json.dumps(details)
                duplicates.append({"item_id": items[j].id, "duplicate_of": items[i].id, "similarity": sim})
    db.commit()
    logger.info("Found %d duplicates in document %s", len(duplicates), document_id)
    return duplicates