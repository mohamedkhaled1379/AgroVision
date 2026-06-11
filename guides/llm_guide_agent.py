"""
LLM-backed crop, disease treatment, and indoor plant care guides (Groq).
Output is normalized to match existing guide dict shapes used by templates.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

GROQ_GUIDE_MODEL = os.getenv("GROQ_GUIDE_MODEL", "llama-3.1-8b-instant").strip()


def _guide_temperature() -> float:
    try:
        return float(os.getenv("GROQ_GUIDE_TEMPERATURE", "0.2"))
    except ValueError:
        return 0.2

_CROP_FIELDS = (
    "season",
    "soil",
    "climate",
    "seed_rate",
    "spacing",
    "water_management",
    "fertilizer",
    "key_practices",
    "duration",
)

_TREATMENT_LIST_KEYS = (
    "symptoms",
    "immediate_actions",
    "organic_treatments",
    "chemical_treatments",
    "prevention",
)


def _parse_json_content(text: str) -> Optional[dict[str, Any]]:
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
    return None


def _as_str_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val.strip()] if val.strip() else []
    if isinstance(val, list):
        out: list[str] = []
        for x in val:
            s = str(x).strip()
            if s:
                out.append(s)
        return out
    return []


def normalize_crop_guide(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in _CROP_FIELDS:
        if k == "key_practices":
            kp = data.get("key_practices", data.get("keyPractices", []))
            out[k] = _as_str_list(kp)
            if not out[k]:
                out[k] = ["Follow local extension recommendations for this crop."]
        else:
            v = data.get(k)
            out[k] = str(v).strip() if v is not None else "—"
    return out


def normalize_treatment(data: dict[str, Any], default: dict[str, Any]) -> dict[str, Any]:
    out = dict(default)
    name = data.get("name")
    if name:
        out["name"] = str(name).strip()
    sev = data.get("severity")
    if sev:
        out["severity"] = str(sev).strip().lower()
    for k in _TREATMENT_LIST_KEYS:
        if k in data and data[k] is not None:
            lst = _as_str_list(data[k])
            if lst:
                out[k] = lst
    rt = data.get("recovery_time")
    if rt:
        out["recovery_time"] = str(rt).strip()
    sr = data.get("success_rate")
    if sr:
        out["success_rate"] = str(sr).strip()
    return out


def _groq_json_completion(client: Any, system: str, user: str) -> Optional[dict[str, Any]]:
    kwargs = {
        "model": GROQ_GUIDE_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": _guide_temperature(),
    }
    try:
        completion = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except Exception:
        completion = client.chat.completions.create(**kwargs)
    content = completion.choices[0].message.content
    return _parse_json_content(content or "")


def generate_crop_guide_llm(
    crop_display_name: str,
    client: Any,
    static_hint: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    hint = ""
    if static_hint:
        try:
            hint = "\nInternal reference draft for alignment—correct, supersede, and cite agronomic rationale in the JSON output:\n" + json.dumps(
                static_hint, ensure_ascii=False, indent=2
            )[:6000]
        except Exception:
            hint = ""

    system = (
        "You are a senior agronomist authoring a concise field production brief for extension agents and growers. "
        "Write in a formal, technical register: no colloquialisms, no emoji, no marketing language. "
        "Output must be a single JSON object (no markdown). Keys exactly: season, soil, climate, seed_rate, spacing, "
        "water_management, fertilizer, key_practices (array of strings), duration. "
        "Use integrated crop management framing: soil health, varietal adaptation, pest/disease risk reduction, and "
        "resource efficiency. Give quantitative guidance where appropriate (rates, spacing, temperature ranges, "
        "water depth or mm) and state assumptions if a region is unspecified. "
        "key_practices: 8–12 imperative, action-oriented items (each under ~140 characters), ordered roughly by season "
        "or crop stage. "
        "fertilizer: give typical N:P:K kg/ha or balanced guidance and explicitly recommend soil testing and label "
        "compliance for any agrochemicals. "
        "water_management: reference critical growth stages where water stress matters. "
        "If the reference material below conflicts with best practice, correct it in the JSON."
    )
    user = f'Crop: "{crop_display_name}".{hint}'
    raw = _groq_json_completion(client, system, user)
    if not raw or not isinstance(raw, dict):
        return None
    return normalize_crop_guide(raw)


def generate_treatment_llm(
    disease_key: str,
    client: Any,
    static_hint: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    from guides.disease_guides import DEFAULT_TREATMENT

    hint = ""
    if static_hint:
        try:
            hint = "\nInternal reference draft—validate against current IPM literature and correct in the JSON output:\n" + json.dumps(
                static_hint, ensure_ascii=False, indent=2
            )[:6000]
        except Exception:
            hint = ""

    system = (
        "You are a plant pathologist and IPM specialist preparing a technical advisory for commercial and serious "
        "hobby growers. Tone: clinical, precise, professional—no emoji, no casual phrasing. "
        "Output one JSON object only (no markdown). Keys: name (common disease name), severity (low|medium|high|unknown), "
        "symptoms, immediate_actions, organic_treatments, chemical_treatments, prevention, recovery_time, success_rate. "
        "symptoms: observable, diagnostically useful signs (morphology, distribution, timing). "
        "immediate_actions: prioritize scouting, sanitation, isolation, environmental correction, then intervention. "
        "organic_treatments and chemical_treatments: list evidence-aligned options; prefer generic modes of action or "
        "active-ingredient classes where appropriate; every chemical-related line must remind the reader to follow "
        "registered product labels, pre-harvest intervals, and local regulations. "
        "prevention: cultural, resistant varieties, rotation, monitoring. "
        "recovery_time and success_rate: give realistic ranges qualified by severity and timeliness of intervention. "
        "Each list value is an array of concise, imperative strings. "
        "If the disease id is ambiguous, infer the most likely crop disease and state implicit assumptions briefly in one list item."
    )
    user = f'Disease / class id: "{disease_key}".{hint}'
    raw = _groq_json_completion(client, system, user)
    if not raw or not isinstance(raw, dict):
        return None
    return normalize_treatment(raw, DEFAULT_TREATMENT)


def _pick_str(d: Any, key: str) -> str:
    if not isinstance(d, dict):
        return ""
    v = d.get(key)
    if v is None:
        return ""
    s = str(v).strip()
    return s


def _label_pretty(key: str) -> str:
    """Turn snake_case or kebab-combined keys into short title fragments."""
    chunks: list[str] = []
    for segment in str(key).strip().split("_"):
        if not segment:
            continue
        sub = "-".join(s.capitalize() for s in segment.split("-") if s)
        if sub:
            chunks.append(sub)
    return " ".join(chunks)


def _dict_to_prose(d: dict[str, Any]) -> str:
    """Turn a shallow or nested mapping into one professional sentence-style line."""
    if not d:
        return ""
    parts: list[str] = []
    for k, vv in d.items():
        label = _label_pretty(str(k))
        if isinstance(vv, dict):
            inner = _dict_to_prose(vv)
            if inner:
                parts.append(f"{label}: {inner}")
        elif isinstance(vv, list):
            bits = []
            for x in vv:
                if isinstance(x, dict):
                    bits.append(_indoor_scalar_prose(x))
                else:
                    sx = str(x).strip()
                    if sx:
                        bits.append(sx)
            if bits:
                parts.append(f"{label}: {', '.join(bits)}")
        else:
            s = str(vv).strip() if vv is not None else ""
            if s:
                parts.append(f"{label}: {s}")
    return "; ".join(parts)


def _indoor_scalar_prose(val: Any) -> str:
    """Coerce model output (string, dict, list) to a single display string."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, dict):
        keys_lower = {str(k).lower() for k in val}

        def _get_ci(*names: str) -> str:
            for n in names:
                for kk in val:
                    if str(kk).lower() == n.lower():
                        out = val[kk]
                        return str(out).strip() if out is not None else ""
            return ""

        if "etiology" in keys_lower or "symptom" in keys_lower:
            e = _get_ci("etiology")
            s = _get_ci("symptom")
            if e and s:
                return f"{e} — {s}"
            return e or s or _dict_to_prose(val)
        if "tip" in keys_lower or "action" in keys_lower:
            t = _get_ci("tip")
            a = _get_ci("action")
            if t and a:
                return f"{t} — {a}"
            return t or a or _dict_to_prose(val)
        return _dict_to_prose(val)
    if isinstance(val, list):
        bits = [_indoor_scalar_prose(x) for x in val]
        bits = [b for b in bits if b]
        return "; ".join(bits)
    return str(val).strip()


def _indoor_coalesce_scalar(ai_val: Any, fb_val: Any) -> str:
    for cand in (ai_val, fb_val):
        if cand is None or cand == "" or cand == {}:
            continue
        text = _indoor_scalar_prose(cand)
        if text:
            return text
    return "—"


def _indoor_coalesce_list(ai_val: Any, fb_val: Any) -> list[str]:
    src = ai_val
    if src in (None, "", []):
        src = fb_val
    if src in (None, "", []):
        return []
    if not isinstance(src, list):
        src = [src]
    out: list[str] = []
    for item in src:
        line = _indoor_scalar_prose(item)
        if line:
            out.append(line)
    return out


def normalize_indoor_plant_guide(
    data: dict[str, Any],
    static_fallback: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Shape matches `guides/indoor_plant_guides.py` entries (strings + watering dict + string lists)."""
    fb = static_fallback or {}
    w_ai = data.get("watering")
    if isinstance(w_ai, str):
        w_ai = {"frequency": w_ai, "method": "", "notes": ""}
    if not isinstance(w_ai, dict):
        w_ai = {}
    w_fb = fb.get("watering") if isinstance(fb.get("watering"), dict) else {}

    def w_coerce(key: str) -> str:
        v_ai = w_ai.get(key) if isinstance(w_ai, dict) else None
        v_fb = w_fb.get(key) if isinstance(w_fb, dict) else None
        return _indoor_coalesce_scalar(v_ai, v_fb)

    probs = _indoor_coalesce_list(data.get("common_problems"), fb.get("common_problems"))
    pests = _indoor_coalesce_list(data.get("pests"), fb.get("pests"))
    tips = _indoor_coalesce_list(data.get("care_tips"), fb.get("care_tips"))

    out: dict[str, Any] = {
        "category": _indoor_coalesce_scalar(data.get("category"), fb.get("category")),
        "difficulty": _indoor_coalesce_scalar(data.get("difficulty"), fb.get("difficulty")),
        "light": _indoor_coalesce_scalar(data.get("light"), fb.get("light")),
        "temperature": _indoor_coalesce_scalar(data.get("temperature"), fb.get("temperature")),
        "humidity": _indoor_coalesce_scalar(data.get("humidity"), fb.get("humidity")),
        "soil": _indoor_coalesce_scalar(data.get("soil"), fb.get("soil")),
        "fertilizer": _indoor_coalesce_scalar(data.get("fertilizer"), fb.get("fertilizer")),
        "pet_safety": _indoor_coalesce_scalar(data.get("pet_safety"), fb.get("pet_safety")),
        "watering": {
            "frequency": w_coerce("frequency"),
            "method": w_coerce("method"),
            "notes": w_coerce("notes"),
        },
        "common_problems": probs or ["—"],
        "pests": pests or ["—"],
        "care_tips": tips or ["—"],
    }
    return out


def generate_indoor_plant_guide_llm(
    plant_label: str,
    client: Any,
    static_hint: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    hint = ""
    if static_hint:
        try:
            hint = "\nInternal reference draft for alignment—correct, supersede, and cite horticultural rationale in the JSON output:\n" + json.dumps(
                static_hint, ensure_ascii=False, indent=2
            )[:6000]
        except Exception:
            hint = ""

    system = (
        "You are a professional horticulturist writing an interior-plant maintenance specification for facilities "
        "managers and advanced home growers. Tone: technical, neutral, and precise—no emoji, no sales language. "
        "Output one JSON object only (no markdown). "
        "STRICT FLAT SCHEMA (required for downstream rendering): "
        "category, difficulty (Easy|Medium|Hard), light, temperature, humidity, soil, fertilizer, and pet_safety "
        "(Safe|Toxic|Unknown) must each be a single plain string (never a nested object or array). "
        "Encode all structured detail inside those strings using clear prose and semicolons, e.g. light might read "
        "'Bright indirect; 6–8 h photoperiod; south- or west-facing within 1 m of glazing'. "
        "watering must be an object with exactly three STRING values: frequency, method, notes (no sub-objects). "
        "common_problems, pests, and care_tips must be arrays of strings only—each item one complete sentence; "
        "do not use {etiology:...} objects; instead write e.g. 'Insufficient light — shortened bloom life indoors'. "
        "Substrate (soil field): one string naming components, drainage, and aeration. "
        "Fertilizer: one string naming product class, timing, and rate guidance. "
        "pet_safety: be conservative; use Unknown when uncertain."
    )
    user = f'Indoor plant label: "{plant_label}".{hint}'
    raw = _groq_json_completion(client, system, user)
    if not raw or not isinstance(raw, dict):
        return None
    return normalize_indoor_plant_guide(raw, static_fallback=static_hint)
