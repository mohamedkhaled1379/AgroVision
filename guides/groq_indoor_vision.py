"""
Indoor plant label prediction from an image using Groq vision chat completions.
"""

from __future__ import annotations

import base64
import json
import os
import re
from difflib import get_close_matches
from typing import Any, Optional

GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "").strip()
_VISION_FALLBACKS = (
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.2-11b-vision-preview",
    "meta-llama/llama-3.2-11b-vision-preview",
)


def _image_data_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        raw = f.read()
    ext = (image_path.rsplit(".", 1)[-1] if "." in image_path else "").lower()
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _parse_json_loose(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return None
    m2 = re.search(r"\{[\s\S]*\}", text)
    if m2:
        try:
            return json.loads(m2.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _match_allowed(raw: str, allowed: list[str]) -> Optional[str]:
    s = (raw or "").strip()
    if not s:
        return None
    if s in allowed:
        return s
    low = {a.lower(): a for a in allowed}
    if s.lower() in low:
        return low[s.lower()]
    close = get_close_matches(s, allowed, n=1, cutoff=0.72)
    if close:
        return close[0]
    close2 = get_close_matches(s, list(low.keys()), n=1, cutoff=0.72)
    if close2:
        return low[close2[0]]
    return None


def predict_indoor_label_vision(
    image_path: str,
    client: Any,
    allowed_labels: list[str],
    model: Optional[str] = None,
) -> Optional[tuple[str, float]]:
    """
    Returns (label, confidence_0_1) with label exactly one of allowed_labels, or None on failure.
    Uses only a user message (no system role) for broader vision API compatibility.
    """
    if not allowed_labels or client is None:
        return None
    preferred = (model or GROQ_VISION_MODEL or "").strip()
    model_order = [preferred] if preferred else []
    for m in _VISION_FALLBACKS:
        if m not in model_order:
            model_order.append(m)
    labels_block = "\n".join(f"- {x}" for x in allowed_labels)
    prompt = (
        "You are a houseplant identification assistant. Look at the image and pick the SINGLE best matching "
        "plant name from the list below. The label string must match EXACTLY one line (character-for-character "
        "as given, including parentheses).\n\n"
        "Allowed labels:\n"
        f"{labels_block}\n\n"
        "Reply with JSON only, no markdown, in this shape:\n"
        '{"label":"<exact string from list>","confidence":0.85}\n'
        "confidence is your estimate from 0 to 1."
    )
    data_url = _image_data_url(image_path)
    completion = None
    for mdl in model_order:
        try:
            completion = client.chat.completions.create(
                model=mdl,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                temperature=0.2,
                max_tokens=256,
            )
            break
        except Exception:
            completion = None
            continue
    if completion is None:
        return None

    content = (completion.choices[0].message.content or "").strip()
    data = _parse_json_loose(content)
    if not isinstance(data, dict):
        return None
    raw_label = data.get("label") or data.get("plant") or data.get("name")
    if raw_label is None:
        return None
    label = _match_allowed(str(raw_label), allowed_labels)
    if not label:
        return None
    try:
        conf = float(data.get("confidence", 0.75))
    except (TypeError, ValueError):
        conf = 0.75
    conf = max(0.0, min(1.0, conf))
    return label, conf
