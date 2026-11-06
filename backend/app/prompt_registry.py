import os
from pathlib import Path
from typing import Dict

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _parse_template(text: str) -> Dict[str, str]:
    if "---USER---" in text:
        system_part, user_part = text.split("---USER---", 1)
    else:
        system_part, user_part = "", text
    system = system_part.replace("SYSTEM:", "", 1).strip() if "SYSTEM:" in system_part else system_part.strip()
    return {"system": system, "user": user_part.strip()}


def load_template(name: str) -> Dict[str, str]:
    """Load a versioned prompt template by base name (e.g. 'summary')."""
    # allow version suffix: summary_v1
    for candidate in (name, name + "_v1"):
        path = PROMPT_DIR / f"{candidate}.txt"
        if path.exists():
            return _parse_template(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Prompt template not found: {name}")


def render(template: Dict[str, str], **kwargs) -> Dict[str, str]:
    out = {}
    for key in ("system", "user"):
        text = template[key]
        for k, v in kwargs.items():
            text = text.replace("{" + k + "}", str(v))
        out[key] = text
    return out
