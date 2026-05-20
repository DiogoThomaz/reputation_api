from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


DEFAULT_OLLAMA_MODEL = "qwen2.5:3b-instruct"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"


def extract_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def response_content(response: Any) -> str:
    content = getattr(response, "content", None)
    if content is not None:
        return str(content)

    message = getattr(response, "message", None)
    if message is not None:
        message_content = getattr(message, "content", None)
        if message_content is not None:
            return str(message_content)

    return str(response or "")


def to_snake_case(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text
