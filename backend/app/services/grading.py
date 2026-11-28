import json
from typing import List, Dict, Any
from ..services.llm import chat_json
from ..logging_config import get_logger

logger = get_logger("app.grading")


def grade_short_answer(question: str, model_answer: str, rubric: List[dict], student_answer: str, max_points: int) -> Dict[str, Any]:
    prompt = (
        "Grade the student's answer using the rubric and model answer. "
        "Return JSON: {\"score\": int, \"max_points\": int, \"feedback\": \"...\", \"matched_criteria\": [\"...\"]}.\n\n"
        f"QUESTION: {question}\n"
        f"MODEL ANSWER: {model_answer}\n"
        f"RUBRIC: {json.dumps(rubric)}\n"
        f"MAX POINTS: {max_points}\n"
        f"STUDENT ANSWER: {student_answer}\n"
    )
    try:
        data = chat_json(prompt, system="You are a strict but fair grader.")
        score = int(data.get("score", 0))
        score = max(0, min(max_points, score))
        return {
            "score": score,
            "max_points": max_points,
            "feedback": data.get("feedback", ""),
            "matched_criteria": data.get("matched_criteria", []),
        }
    except Exception as e:
        logger.warning("Grading failed: %s", e)
        return {"score": 0, "max_points": max_points, "feedback": "Grading failed.", "matched_criteria": []}