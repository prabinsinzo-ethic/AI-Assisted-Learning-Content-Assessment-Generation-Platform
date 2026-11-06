import json
import logging
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from ..models import ContentItem, Chunk
from ..services.llm import chat_json
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