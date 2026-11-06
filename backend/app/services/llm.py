import json
import logging
import os
import struct
import hashlib
import math
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ..config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, EMBED_MODEL, MOCK_LLM
from ..logging_config import get_logger

logger = get_logger("app.llm")

_client = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY or "sk-mock", base_url=OPENAI_BASE_URL)
    return _client


def chat(prompt: str, system: str = "", json_mode: bool = False, temperature: float = 0.7) -> str:
    if MOCK_LLM or not OPENAI_API_KEY:
        logger.debug("Using mock LLM response")
        return _mock_chat(prompt, json_mode)
    kwargs = {"model": LLM_MODEL, "messages": [], "temperature": temperature}
    if system:
        kwargs["messages"].append({"role": "system", "content": system})
    kwargs["messages"].append({"role": "user", "content": prompt})
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    logger.debug("LLM call model=%s json_mode=%s", LLM_MODEL, json_mode)
    resp = client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def chat_json(prompt: str, system: str = "", temperature: float = 0.7) -> Dict[str, Any]:
    raw = chat(prompt, system=system, json_mode=True, temperature=temperature)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])
        raise


def chat_json_with_retry(prompt: str, system: str = "", validate=None, max_retries: int = 3, temperature: float = 0.7) -> Dict[str, Any]:
    last_err = None
    cur_prompt = prompt
    for attempt in range(max_retries):
        raw = chat(cur_prompt, system=system, json_mode=True, temperature=temperature)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1:
                try:
                    data = json.loads(raw[start:end + 1])
                except json.JSONDecodeError as e:
                    last_err = e
                    cur_prompt = prompt + f"\n\nPrevious output was invalid JSON: {e}. Return valid JSON only."
                    continue
            else:
                last_err = ValueError("No JSON found")
                cur_prompt = prompt + "\n\nPrevious output was invalid JSON. Return valid JSON only."
                continue
        if validate is not None:
            try:
                validate(data)
            except Exception as e:
                last_err = e
                cur_prompt = prompt + f"\n\nPrevious output failed validation: {e}. Fix and return valid JSON only."
                continue
        return data
    raise ValueError(f"Failed to generate valid JSON after {max_retries} attempts: {last_err}")


def embed(texts: List[str]) -> List[List[float]]:
    if MOCK_LLM or not OPENAI_API_KEY:
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            vec = [struct.unpack("f", h[i:i + 4])[0] if i + 4 <= len(h) else 0.0 for i in range(0, 32, 4)]
            while len(vec) < 8:
                vec.append(0.0)
            out.append(vec)
        return out
    resp = client().embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _mock_chat(prompt: str, json_mode: bool) -> str:
    low = prompt.lower()
    if "atomic factual claims" in low:
        return json.dumps({"claims": ["The source states the main concept."]})
    if "supports/entails" in low or "fact-checker" in low:
        return json.dumps({"score": 0.9})
    if "ambiguity" in low or "ambiguity_score" in low:
        return json.dumps({"ambiguity_score": 1, "issues": []})
    if "summary" in low:
        return json.dumps({"summary": "This is a mock summary of the provided content.", "key_points": ["Point A", "Point B"]})
    if "flashcard" in low:
        return json.dumps({"front": "What is X?", "back": "X is Y."})
    if "mcq" in low or "multiple choice" in low:
        return json.dumps({
            "stem": "Which of the following is correct?",
            "options": [{"text": "Option A", "is_correct": True}, {"text": "Option B", "is_correct": False},
                        {"text": "Option C", "is_correct": False}, {"text": "Option D", "is_correct": False}],
            "correct_index": 0,
            "explanation": "Because A.",
            "distractor_rationale": "B,C,D are wrong."
        })
    if "short" in low and "answer" in low:
        return json.dumps({"question": "Explain X.", "model_answer": "X is ...", "rubric": [{"criterion": "mentions X", "points": 1}], "max_points": 2})
    if "answer key" in low or "answer_key" in low:
        return json.dumps({"answer": "mock answer", "grading_notes": "mock grading notes"})
    return json.dumps({"result": "mock"})