# app.py
# Unified Smart Agro App (Disease + Crop Recommendation + Indoor Plant + Chatbot)

import os
import json
import urllib.request
import numpy as np
import pandas as pd
import joblib
import datetime
import traceback
import csv
import io
from functools import wraps

from database import DBConnection, get_db_connection, init_db, is_integrity_error, is_mssql

from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    redirect,
    url_for,
    session,
    flash,
    Response,
    send_from_directory,
    has_request_context,
)
from urllib.parse import urlparse

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from PIL import Image

# TensorFlow, PyTorch, and OpenCV are imported lazily for faster Railway boot.

# Chatbot
from groq import Groq
import langdetect
from logging.handlers import RotatingFileHandler
import logging

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:
    Limiter = None
    get_remote_address = None

# =========================================================
# IMPORT GUIDES
# =========================================================
from guides.disease_guides import TREATMENT_GUIDE, DEFAULT_TREATMENT
from guides.crop_guides import CROP_GUIDE
from guides.feature_guides import FEATURE_GUIDES
from guides.indoor_plant_guides import INDOOR_PLANT_GUIDE
from guides.llm_guide_agent import (
    generate_crop_guide_llm,
    generate_indoor_plant_guide_llm,
    generate_treatment_llm,
)
from guides.groq_indoor_vision import predict_indoor_label_vision
from i18n import DEFAULT_LANG as I18N_DEFAULT_LANG, translate as i18n_translate

# =========================================================
# CONFIG
# =========================================================
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads/"
app.config["PROFILE_UPLOAD_FOLDER"] = "static/profile_uploads/"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")
IS_PRODUCTION = os.getenv("FLASK_ENV", "development").lower() == "production"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(hours=12)

if Limiter and get_remote_address:
    limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])
else:
    limiter = None

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["PROFILE_UPLOAD_FOLDER"], exist_ok=True)


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    file_handler = RotatingFileHandler("logs/app.log", maxBytes=1024 * 1024, backupCount=3)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    file_handler.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Application logging initialized.")


IOT_STALE_SECONDS = int(os.getenv("IOT_STALE_SECONDS", "300"))
IOT_API_KEY = os.getenv("IOT_API_KEY", "").strip()
# Crop model was trained on N~0-140, P~5-145, K~5-205, rainfall~20-300 mm, pH~3.5-9.9
IOT_NPK_SENSOR_MAX = float(os.getenv("IOT_NPK_SENSOR_MAX", "1999"))
IOT_NPK_SCALE = float(os.getenv("IOT_NPK_SCALE", "1"))  # set 0.1 if sensor reads 10x too high
IOT_ESP_IP = os.getenv("IOT_ESP_IP", "").strip()


def get_pc_lan_ip() -> str:
    """Local IPv4 used to reach the LAN (for UI hints)."""
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.2"


def is_likely_pc_ip(ip: str) -> bool:
    ip = (ip or "").strip().lower()
    if not ip or ip in ("127.0.0.1", "localhost", "0.0.0.0"):
        return True
    if ip == get_pc_lan_ip().lower():
        return True
    return False


def get_iot_esp_ip() -> str:
    conn = get_db_connection()
    row = conn.execute("SELECT iot_esp_ip FROM site_settings WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return ""
    return (row["iot_esp_ip"] or "").strip()


def save_iot_esp_ip(ip: str) -> None:
    ip = (ip or "").strip()
    if not ip or ip in ("127.0.0.1", "::1"):
        return
    conn = get_db_connection()
    conn.execute(
        "UPDATE site_settings SET iot_esp_ip = ?, updated_at = ? WHERE id = 1",
        (ip, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def pull_live_from_esp(esp_ip: str) -> dict:
    host = esp_ip.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
    url = f"http://{host}/sensors"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ESP /sensors must return a JSON object")
    return data


def sync_iot_from_esp(esp_ip: str | None = None) -> tuple[dict | None, str | None]:
    esp_ip = (esp_ip or IOT_ESP_IP or get_iot_esp_ip()).strip()
    if not esp_ip:
        return None, (
            "ESP32 IP not set. Enter the number from Serial Monitor (e.g. 192.168.1.45) "
            "in the box above and click Save IP."
        )
    if is_likely_pc_ip(esp_ip):
        pc = get_pc_lan_ip()
        return None, (
            f"{esp_ip} is your PC, not the ESP32. Open Arduino Serial Monitor and copy "
            f"the line 'ESP32 IP: ...' — it will be different from {pc}."
        )
    try:
        payload = pull_live_from_esp(esp_ip)
        result = _iot_ingest_payload(payload, device_ip=esp_ip)
        return result, None
    except Exception as exc:
        return None, f"Cannot reach ESP32 at {esp_ip}: {exc}"


def _npk_for_crop_model(value: float | None, dataset_max: float) -> float | None:
    if value is None:
        return None
    if value < 0:
        return None
    scaled = value * IOT_NPK_SCALE
    if scaled <= dataset_max:
        return round(scaled, 1)
    if scaled <= IOT_NPK_SENSOR_MAX:
        return round(scaled * dataset_max / IOT_NPK_SENSOR_MAX, 1)
    return round(min(scaled / 10.0, dataset_max), 1)


def normalize_iot_for_crop_model(reading: dict) -> tuple[dict, list[str]]:
    """Map raw sensor units to the scale expected by crop_recommender_xgb.pkl."""
    warnings: list[str] = []

    def warn(msg: str):
        if msg not in warnings:
            warnings.append(msg)

    n_raw = reading.get("nitrogen")
    p_raw = reading.get("phosphorus")
    k_raw = reading.get("potassium")
    temp = reading.get("temperature")
    hum = reading.get("humidity")
    rain = reading.get("rainfall")
    ph = reading.get("ph")

    if n_raw is not None and n_raw < 0:
        warn("Nitrogen sensor read failed — check RS485/NPK wiring")
    if p_raw is not None and p_raw < 0:
        warn("Phosphorus sensor read failed")
    if k_raw is not None and k_raw < 0:
        warn("Potassium sensor read failed")

    nitrogen = _npk_for_crop_model(n_raw if n_raw is not None and n_raw >= 0 else None, 140)
    phosphorus = _npk_for_crop_model(p_raw if p_raw is not None and p_raw >= 0 else None, 145)
    potassium = _npk_for_crop_model(k_raw if k_raw is not None and k_raw >= 0 else None, 205)

    if nitrogen is None or phosphorus is None or potassium is None:
        warn("NPK values missing or invalid — crop suggestion may be wrong")

    if temp is not None and temp <= 0:
        warn("Temperature is 0 — check DHT22 wiring on GPIO 5")
    if hum is not None and hum <= 0:
        warn("Humidity is 0 — check DHT22 on GPIO 5")
    if n_raw == 0 and p_raw == 0 and k_raw == 0:
        warn("NPK is 0-0-0 — check RS485 wiring and NPK sensor power")

    if ph is not None:
        if ph < 3.5 or ph > 9.9:
            warn("pH out of range — calibrate neutralVoltage/slope in iot.ino")
            ph = round(max(3.5, min(9.9, ph)), 2)
    else:
        warn("pH missing")

    if rain is not None:
        rain = round(max(20.0, min(300.0, float(rain))), 1)
    else:
        warn("Rainfall missing")

    crop = {
        "nitrogen": nitrogen,
        "phosphorus": phosphorus,
        "potassium": potassium,
        "temperature": round(float(temp), 1) if temp is not None else None,
        "humidity": round(float(hum), 1) if hum is not None else None,
        "rainfall": rain,
        "ph": ph,
    }
    return crop, warnings


def iot_reading_row_to_raw(row) -> dict:
    return {
        "nitrogen": row["nitrogen"],
        "phosphorus": row["phosphorus"],
        "potassium": row["potassium"],
        "temperature": row["temperature"],
        "humidity": row["humidity"],
        "rainfall": row["rainfall"],
        "ph": row["ph"],
        "soil_moisture": row["soil_moisture"],
    }


def _iot_api_authorized() -> bool:
    if not IOT_API_KEY:
        return True
    provided = (
        request.headers.get("X-IoT-Key")
        or request.args.get("key")
        or (request.get_json(silent=True) or {}).get("api_key")
        or ""
    )
    return str(provided).strip() == IOT_API_KEY


def _parse_iot_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")

    def pick(*keys, default=None, allow_negative=False):
        for key in keys:
            if key in payload and payload[key] is not None and str(payload[key]).strip() != "":
                value = float(payload[key])
                if value < 0 and not allow_negative:
                    continue
                return value
        if default is not None:
            return float(default)
        raise KeyError(keys[0])

    soil = payload.get("soil_moisture", payload.get("soilHumidity", payload.get("soil_humidity")))
    soil_val = None if soil is None or str(soil).strip() == "" else float(soil)

    user_id = None
    raw_user = payload.get("user_id")
    if raw_user is not None and str(raw_user).strip() not in ("", "0"):
        user_id = int(raw_user)

    return {
        "user_id": user_id,
        "nitrogen": pick("nitrogen", allow_negative=True),
        "phosphorus": pick("phosphorus", allow_negative=True),
        "potassium": pick("potassium", allow_negative=True),
        "temperature": pick("temperature", "temp"),
        "humidity": pick("humidity", "hum"),
        "rainfall": pick("rainfall", "rain"),
        "ph": pick("ph", "pH"),
        "soil_moisture": soil_val,
    }


def save_iot_reading(reading: dict) -> int:
    conn = get_db_connection()
    cur = conn.execute(
        """
        INSERT INTO iot_readings (
            user_id, nitrogen, phosphorus, potassium, temperature, humidity,
            rainfall, ph, soil_moisture, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            reading.get("user_id"),
            reading["nitrogen"],
            reading["phosphorus"],
            reading["potassium"],
            reading["temperature"],
            reading["humidity"],
            reading["rainfall"],
            reading["ph"],
            reading.get("soil_moisture"),
            datetime.datetime.now().isoformat(),
        ),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_latest_iot_reading(user_id: int | None = None):
    """Latest reading for user_id if any; otherwise latest from any device (ESP32 uploads)."""
    conn = get_db_connection()
    row = None
    if user_id:
        row = conn.execute(
            """
            SELECT id, user_id, nitrogen, phosphorus, potassium, temperature, humidity,
                   rainfall, ph, soil_moisture, created_at
            FROM iot_readings
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        row = conn.execute(
            """
            SELECT id, user_id, nitrogen, phosphorus, potassium, temperature, humidity,
                   rainfall, ph, soil_moisture, created_at
            FROM iot_readings
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    conn.close()
    return row


def _iot_ingest_payload(payload: dict, device_ip: str | None = None):
    reading = _parse_iot_payload(payload)
    row_id = save_iot_reading(reading)
    if device_ip:
        save_iot_esp_ip(device_ip)
    return {
        "ok": True,
        "id": row_id,
        "read_at": datetime.datetime.now().isoformat(),
    }


def iot_row_to_json(row, stale_seconds: int = IOT_STALE_SECONDS):
    if not row:
        return {"ok": False, "available": False, "message": "No sensor data yet"}

    created = datetime.datetime.fromisoformat(row["created_at"])
    age = (datetime.datetime.now() - created).total_seconds()
    stale = age > stale_seconds

    raw = iot_reading_row_to_raw(row)
    _, warnings = normalize_iot_for_crop_model(raw)

    return {
        "ok": True,
        "available": True,
        "stale": stale,
        "fresh": not stale,
        "age_seconds": round(age, 1),
        "read_at": row["created_at"],
        "raw": raw,
        "warnings": warnings,
        # Form fields = exact values from ESP32 (same as Serial Monitor)
        "nitrogen": raw["nitrogen"],
        "phosphorus": raw["phosphorus"],
        "potassium": raw["potassium"],
        "temperature": raw["temperature"],
        "humidity": raw["humidity"],
        "rainfall": raw["rainfall"],
        "ph": raw["ph"],
        "soil_moisture": raw["soil_moisture"],
        "soilHumidity": raw["soil_moisture"],
        "user_id": row["user_id"] if "user_id" in row.keys() else None,
    }


IOT_WINDOW_HOURS = {"1h": 1, "24h": 24, "7d": 168, "14d": 336, "30d": 720}
ALLOWED_ANALYSIS_DURATIONS = (7, 14, 30)


def save_analysis_booking(user_id: int, start_date: str, duration_days: int) -> dict:
    start = datetime.date.fromisoformat(start_date)
    end = start + datetime.timedelta(days=duration_days)
    now = datetime.datetime.now().isoformat()
    conn = get_db_connection()
    cur = conn.execute(
        """
        INSERT INTO analysis_bookings (user_id, start_date, end_date, duration_days, status, created_at)
        VALUES (?, ?, ?, ?, 'scheduled', ?)
        """,
        (user_id, start.isoformat(), end.isoformat(), duration_days, now),
    )
    booking_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": booking_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "duration_days": duration_days,
        "status": "scheduled",
        "created_at": now,
    }


def get_user_analysis_bookings(user_id: int, limit: int = 20):
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, start_date, end_date, duration_days, status, created_at
        FROM analysis_bookings
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


def _cancel_booking_record(booking_id: int, user_id: int, *, as_admin: bool = False) -> tuple[bool, str]:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT id, user_id, status, start_date, end_date FROM analysis_bookings WHERE id = ?",
        (booking_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False, "Booking not found."
    if row["user_id"] != user_id and not as_admin:
        conn.close()
        return False, "You can only cancel your own booking."
    if row["status"] != "scheduled":
        conn.close()
        return False, "This booking cannot be cancelled."
    conn.execute(
        "UPDATE analysis_bookings SET status = 'cancelled' WHERE id = ?",
        (booking_id,),
    )
    conn.commit()
    conn.close()
    return True, f"{row['start_date']} → {row['end_date']}"


def get_all_analysis_bookings(status_filter: str = "", limit: int = 100):
    conn = get_db_connection()
    query = """
        SELECT b.id, b.user_id, u.username, b.start_date, b.end_date, b.duration_days,
               b.status, b.confirmed_at, b.started_at, b.created_at,
               w.username AS confirmed_by_name
        FROM analysis_bookings b
        JOIN users u ON b.user_id = u.id
        LEFT JOIN users w ON b.confirmed_by = w.id
        WHERE 1=1
    """
    params: list = []
    if status_filter in ("scheduled", "confirmed", "in_progress", "cancelled"):
        query += " AND b.status = ?"
        params.append(status_filter)
    query += " ORDER BY b.id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def duration_to_window_key(duration_days: int) -> str:
    return {7: "7d", 14: "14d", 30: "30d"}.get(duration_days, "7d")


def get_booking_by_id(booking_id: int):
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT b.id, b.user_id, u.username AS username, b.start_date, b.end_date,
               b.duration_days, b.status, b.confirmed_by, b.confirmed_at, b.started_at,
               b.created_at, w.username AS confirmed_by_name
        FROM analysis_bookings b
        JOIN users u ON b.user_id = u.id
        LEFT JOIN users w ON b.confirmed_by = w.id
        WHERE b.id = ?
        """,
        (booking_id,),
    ).fetchone()
    conn.close()
    return row


def get_worker_my_bookings(worker_id: int, limit: int = 50):
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT b.id, b.user_id, u.username, b.start_date, b.end_date, b.duration_days,
               b.status, b.confirmed_at, b.started_at, b.created_at,
               w.username AS confirmed_by_name
        FROM analysis_bookings b
        JOIN users u ON b.user_id = u.id
        LEFT JOIN users w ON b.confirmed_by = w.id
        WHERE b.confirmed_by = ? AND b.status IN ('confirmed', 'in_progress')
        ORDER BY b.id DESC
        LIMIT ?
        """,
        (worker_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_active_worker_booking():
    booking_id = session.get("active_booking_id")
    if not booking_id:
        return None
    row = get_booking_by_id(booking_id)
    if not row or row["status"] not in ("confirmed", "in_progress"):
        session.pop("active_booking_id", None)
        return None
    if is_worker() and row["confirmed_by"] != session.get("user_id"):
        session.pop("active_booking_id", None)
        return None
    return row


def _start_booking_analysis(booking_id: int, worker_id: int) -> tuple[bool, str]:
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT id, status, start_date, end_date, confirmed_by
        FROM analysis_bookings WHERE id = ?
        """,
        (booking_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False, "Booking not found."
    now = datetime.datetime.now().isoformat()
    if row["status"] == "scheduled":
        conn.execute(
            """
            UPDATE analysis_bookings
            SET status = 'in_progress', confirmed_by = ?, confirmed_at = ?, started_at = ?
            WHERE id = ?
            """,
            (worker_id, now, now, booking_id),
        )
    elif row["status"] == "in_progress":
        if row["confirmed_by"] != worker_id:
            conn.close()
            return False, "This booking is assigned to another worker."
    elif row["status"] == "confirmed":
        if row["confirmed_by"] not in (None, worker_id):
            conn.close()
            return False, "This booking is assigned to another worker."
        conn.execute(
            """
            UPDATE analysis_bookings
            SET status = 'in_progress', confirmed_by = ?, started_at = COALESCE(started_at, ?)
            WHERE id = ?
            """,
            (worker_id, now, booking_id),
        )
    else:
        conn.close()
        return False, "This booking cannot be started."
    conn.commit()
    conn.close()
    return True, f"{row['start_date']} → {row['end_date']}"


def get_iot_readings_history(hours: float = 24, limit: int = 300):
    since = (datetime.datetime.now() - datetime.timedelta(hours=hours)).isoformat()
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT nitrogen, phosphorus, potassium, temperature, humidity,
               rainfall, ph, soil_moisture, created_at
        FROM iot_readings
        WHERE created_at >= ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (since, limit),
    ).fetchall()
    conn.close()
    return rows


def average_iot_rows(rows) -> dict | None:
    if not rows:
        return None
    keys = ("nitrogen", "phosphorus", "potassium", "temperature", "humidity", "rainfall", "ph", "soil_moisture")
    out = {}
    for key in keys:
        vals = [float(r[key]) for r in rows if r[key] is not None]
        out[key] = round(sum(vals) / len(vals), 2) if vals else None
    return out


def build_crop_feature_frame(raw_form: dict) -> tuple[pd.DataFrame, list[str]]:
    crop_vals, warnings = normalize_iot_for_crop_model(raw_form)
    use = {}
    for key, model_key in [
        ("nitrogen", "N"),
        ("phosphorus", "P"),
        ("potassium", "K"),
        ("temperature", "temperature"),
        ("humidity", "humidity"),
        ("ph", "ph"),
        ("rainfall", "rainfall"),
    ]:
        use[model_key] = crop_vals.get(key) if crop_vals.get(key) is not None else raw_form[key]
    return pd.DataFrame([use]), warnings


def predict_crop_with_confidence(raw_form: dict) -> dict:
    crop_model, scaler, label_encoder = _ensure_crop_models()
    features, warnings = build_crop_feature_frame(raw_form)
    scaled = scaler.transform(features)
    encoded = int(crop_model.predict(scaled)[0])
    try:
        crop = label_encoder.inverse_transform([encoded])[0]
    except Exception:
        crop = str(encoded)

    confidence = 100.0
    alternatives = []
    if hasattr(crop_model, "predict_proba"):
        proba = crop_model.predict_proba(scaled)[0]
        order = np.argsort(proba)[::-1]
        confidence = round(float(proba[order[0]]) * 100, 1)
        for idx in order[1:3]:
            try:
                alt_name = label_encoder.inverse_transform([int(idx)])[0]
            except Exception:
                alt_name = str(idx)
            alternatives.append({
                "crop": alt_name,
                "confidence": round(float(proba[idx]) * 100, 1),
            })

    return {
        "crop": crop,
        "confidence": confidence,
        "alternatives": alternatives,
        "warnings": warnings,
    }


def iot_payload_from_raw(raw: dict) -> dict:
    return {
        "nitrogen": raw.get("nitrogen"),
        "phosphorus": raw.get("phosphorus"),
        "potassium": raw.get("potassium"),
        "temperature": raw.get("temperature"),
        "humidity": raw.get("humidity"),
        "rainfall": raw.get("rainfall"),
        "soilHumidity": raw.get("soil_moisture"),
        "ph": raw.get("ph"),
    }


def build_iot_dashboard_payload(window_key: str = "24h", sync_esp: bool = False, esp_ip: str = "") -> dict:
    hours = IOT_WINDOW_HOURS.get(window_key, 24)
    sync_error = None
    if sync_esp and (esp_ip or IOT_ESP_IP or get_iot_esp_ip()):
        _, sync_error = sync_iot_from_esp(esp_ip=esp_ip or None)

    row = get_latest_iot_reading()
    if not row:
        return {
            "ok": False,
            "message": "No sensor data yet. Run run_agro.ps1 and start the serial bridge or ESP32 upload.",
            "sync_error": sync_error,
        }

    latest = iot_row_to_json(row)
    raw = latest.get("raw") or iot_reading_row_to_raw(row)
    prediction = predict_crop_with_confidence(raw)
    history_rows = get_iot_readings_history(hours=hours)
    history = []
    for r in history_rows:
        ts = r["created_at"]
        try:
            label = datetime.datetime.fromisoformat(ts).strftime("%I:%M %p")
        except Exception:
            label = ts
        history.append({
            "label": label,
            "created_at": ts,
            "temperature": r["temperature"],
            "humidity": r["humidity"],
            "rainfall": r["rainfall"],
            "soil_moisture": r["soil_moisture"],
            "ph": r["ph"],
        })

    read_dt = datetime.datetime.fromisoformat(row["created_at"])
    return {
        "ok": True,
        "pipeline_connected": latest.get("fresh", False),
        "esp32_online": latest.get("fresh", False),
        "stale": latest.get("stale", True),
        "read_at": row["created_at"],
        "last_ping_display": read_dt.strftime("%I:%M %p"),
        "last_ping_utc": read_dt.strftime("%Y-%m-%d %H:%M UTC"),
        "sensors": {
            "nitrogen": raw.get("nitrogen"),
            "phosphorus": raw.get("phosphorus"),
            "potassium": raw.get("potassium"),
            "temperature": raw.get("temperature"),
            "humidity": raw.get("humidity"),
            "rainfall": raw.get("rainfall"),
            "soil_moisture": raw.get("soil_moisture"),
            "ph": raw.get("ph"),
        },
        "payload": iot_payload_from_raw(raw),
        "prediction": {
            "crop": prediction["crop"],
            "confidence": prediction["confidence"],
            "alternatives": prediction["alternatives"],
            "source": "Automated (IoT / anonymous)",
            "predicted_at": read_dt.strftime("%Y-%m-%d %H:%M UTC"),
            "warnings": prediction["warnings"],
        },
        "history": history,
        "window": window_key,
        "sync_error": sync_error,
        "esp_ip": esp_ip or get_iot_esp_ip() or IOT_ESP_IP,
        "warnings": latest.get("warnings") or [],
    }


def add_history(user_id: int, action: str, details: str = "", image_file: str = ""):
    if not user_id:
        return
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO history (user_id, action, details, image_file, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, action, details, image_file, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_site_settings():
    conn = get_db_connection()
    row = conn.execute(
        "SELECT instagram_url, whatsapp_phone, disease_info, indoor_info FROM site_settings WHERE id = 1"
    ).fetchone()
    conn.close()
    if not row:
        return {"instagram_url": "", "whatsapp_phone": "", "disease_info": "", "indoor_info": ""}
    return {
        "instagram_url": (row["instagram_url"] or "").strip(),
        "whatsapp_phone": (row["whatsapp_phone"] or "").strip(),
        "disease_info": (row["disease_info"] or "").strip(),
        "indoor_info": (row["indoor_info"] or "").strip(),
    }


def sorted_friend_pair(user_a: int, user_b: int):
    return (user_a, user_b) if user_a < user_b else (user_b, user_a)


def are_friends(conn: DBConnection, user_a: int, user_b: int) -> bool:
    u1, u2 = sorted_friend_pair(user_a, user_b)
    row = conn.execute(
        "SELECT id FROM friendships WHERE user1_id = ? AND user2_id = ?",
        (u1, u2)
    ).fetchone()
    return row is not None


VALID_ROLES = frozenset({"admin", "user", "worker"})

WORKER_ALLOWED_ENDPOINTS = frozenset({
    "worker_dashboard",
    "crop_predict",
    "crop_guide",
    "logout",
    "change_password",
    "set_language",
    "login",
    "static",
    "iot_config",
    "iot_load_for_crop",
    "iot_readings_latest",
    "iot_sync_from_device",
    "iot_dashboard_api",
    "iot_analyze_predict",
    "analysis_booking_page",
    "cancel_analysis_booking",
    "worker_bookings_page",
    "start_worker_booking",
    "end_worker_booking",
})


def current_role() -> str:
    return session.get("role") or ""


def can_use_iot() -> bool:
    return current_role() in ("admin", "worker")


def is_worker() -> bool:
    return current_role() == "worker"


def is_admin() -> bool:
    return current_role() == "admin"


def iot_access_denied_response():
    return jsonify({"ok": False, "error": "IoT access is restricted to admin and worker accounts."}), 403


def login_required(role=None, roles=None):
    allowed = set()
    if role:
        allowed.add(role)
    if roles:
        allowed.update(roles)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if allowed and session.get("role") not in allowed:
                return render_template("error.html", error="Access denied"), 403
            return func(*args, **kwargs)
        return wrapper
    return decorator


def is_strong_password(password: str) -> bool:
    if len(password) < 8:
        return False
    has_upper = any(ch.isupper() for ch in password)
    has_lower = any(ch.islower() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    return has_upper and has_lower and has_digit


def is_valid_phone(phone: str) -> bool:
    cleaned = "".join(ch for ch in phone if ch.isdigit())
    return 7 <= len(cleaned) <= 15



@app.before_request
def ensure_session_language():
    session.setdefault("lang", I18N_DEFAULT_LANG)
    if session.get("lang") not in ("en", "ar"):
        session["lang"] = I18N_DEFAULT_LANG


@app.before_request
def enforce_https_in_production():
    if IS_PRODUCTION and request.headers.get("X-Forwarded-Proto", "http") != "https":
        return redirect(request.url.replace("http://", "https://", 1), code=301)


@app.before_request
def enforce_worker_access():
    if not is_worker():
        return None
    endpoint = request.endpoint or ""
    if endpoint in WORKER_ALLOWED_ENDPOINTS:
        return None
    if endpoint.startswith("static") or request.path.startswith("/static/"):
        return None
    if request.path.startswith("/api/iot/") and can_use_iot():
        return None
    return redirect(url_for("worker_bookings_page"))


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'"

    return response


@app.context_processor
def inject_footer_settings():
    lang = session.get("lang", I18N_DEFAULT_LANG)
    if lang not in ("en", "ar"):
        lang = I18N_DEFAULT_LANG

    def t(key, default=None):
        return i18n_translate(lang, key, default)

    return {
        "footer_settings": get_site_settings(),
        "current_lang": lang,
        "is_rtl": lang == "ar",
        "t": t,
        "is_admin": is_admin(),
        "is_worker": is_worker(),
        "can_use_iot": can_use_iot(),
    }


@app.route("/set-language/<lang_code>", methods=["GET"])
def set_language(lang_code):
    code = (lang_code or "").strip().lower()[:2]
    if code not in ("en", "ar"):
        code = I18N_DEFAULT_LANG
    session["lang"] = code
    nxt = (request.args.get("next") or "").strip()
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    ref = request.referrer or ""
    try:
        p = urlparse(ref)
        host = request.host.split(":")[0]
        if p.netloc and host and (p.netloc == request.host or p.netloc.split(":")[0] == host):
            path = p.path or "/"
            if p.query:
                path += "?" + p.query
            if path.startswith("/") and not path.startswith("//"):
                return redirect(path)
    except Exception:
        pass
    return redirect(url_for("home"))

# =========================================================
# GROQ CHATBOT CLIENT
# =========================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
# Optional: use a separate key only for AI crop/treatment guides (chatbot still uses GROQ_API_KEY).
GROQ_GUIDE_API_KEY = os.getenv("GROQ_GUIDE_API_KEY", "").strip()
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
guide_client = Groq(api_key=GROQ_GUIDE_API_KEY) if GROQ_GUIDE_API_KEY else client

# =========================================================
# MODELS
# =========================================================
disease_model = None
indoor_model = None
indoor_device = None
crop_model = None
scaler = None
label_encoder = None
_torch_transform = None

# =========================================================
# DISEASE CLASS NAMES
# =========================================================
CLASS_NAMES = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust", "Apple___healthy",
    "Blueberry___healthy", "Cherry_(including_sour)___Powdery_mildew", "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot_Gray_leaf_spot", "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight", "Corn_(maize)___healthy", "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)", "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)", "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)", "Peach___Bacterial_spot", "Peach___healthy",
    "Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy", "Potato___Early_blight",
    "Potato___Late_blight", "Potato___healthy", "Raspberry___healthy", "Soybean___healthy",
    "Squash___Powdery_mildew", "Strawberry___Leaf_scorch", "Strawberry___healthy",
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight", "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot", "Tomato___Spider_mites_Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus", "Tomato___healthy"
]

# =========================================================
# INDOOR PLANT LABELS
# =========================================================
INDOOR_LABELS = {
    "0": "African Violet (Saintpaulia ionantha)",
    "1": "Aloe Vera",
    "2": "Anthurium (Anthurium andraeanum)",
    "3": "Areca Palm (Dypsis lutescens)",
    "4": "Asparagus Fern (Asparagus setaceus)",
    "5": "Begonia (Begonia spp.)",
    "6": "Bird of Paradise (Strelitzia reginae)",
    "7": "Birds Nest Fern (Asplenium nidus)",
    "8": "Boston Fern (Nephrolepis exaltata)",
    "9": "Calathea",
    "10": "Cast Iron Plant (Aspidistra elatior)",
    "11": "Chinese Money Plant (Pilea peperomioides)",
    "12": "Chinese evergreen (Aglaonema)",
    "13": "Christmas Cactus (Schlumbergera bridgesii)",
    "14": "Chrysanthemum",
    "15": "Ctenanthe",
    "16": "Daffodils (Narcissus spp.)",
    "17": "Dracaena",
    "18": "Dumb Cane (Dieffenbachia spp.)",
    "19": "Elephant Ear (Alocasia spp.)",
    "20": "English Ivy (Hedera helix)",
    "21": "Hyacinth (Hyacinthus orientalis)",
    "22": "Iron Cross begonia (Begonia masoniana)",
    "23": "Jade plant (Crassula ovata)",
    "24": "Kalanchoe",
    "25": "Lilium (Hemerocallis)",
    "26": "Lily of the valley (Convallaria majalis)",
    "27": "Money Tree (Pachira aquatica)",
    "28": "Monstera Deliciosa (Monstera deliciosa)",
    "29": "Orchid",
    "30": "Parlor Palm (Chamaedorea elegans)",
    "31": "Peace lily",
    "32": "Poinsettia (Euphorbia pulcherrima)",
    "33": "Polka Dot Plant (Hypoestes phyllostachya)",
    "34": "Ponytail Palm (Beaucarnea recurvata)",
    "35": "Pothos (Ivy arum)",
    "36": "Prayer Plant (Maranta leuconeura)",
    "37": "Rattlesnake Plant (Calathea lancifolia)",
    "38": "Rubber Plant (Ficus elastica)",
    "39": "Sago Palm (Cycas revoluta)",
    "40": "Schefflera",
    "41": "Snake plant (Sanseviera)",
    "42": "Tradescantia",
    "43": "Tulip",
    "44": "Venus Flytrap",
    "45": "Yucca",
    "46": "ZZ Plant (Zamioculcas zamiifolia)"
}

INDOOR_CLASS_LABELS = list(INDOOR_LABELS.values())

# =========================================================
# LOAD MODELS
# =========================================================
def _get_indoor_device():
    global indoor_device
    if indoor_device is None:
        import torch
        indoor_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return indoor_device


def _get_torch_transform():
    global _torch_transform
    if _torch_transform is None:
        import torchvision.transforms as transforms
        _torch_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])
    return _torch_transform


def _ensure_crop_models():
    global crop_model, scaler, label_encoder
    if crop_model is None:
        crop_model = joblib.load("crop_recommender_xgb.pkl")
        scaler = joblib.load("scaler.pkl")
        label_encoder = joblib.load("label_encoder.pkl")
    return crop_model, scaler, label_encoder


def warm_up_models() -> None:
    """Load ML models once per gunicorn worker."""
    if os.getenv("DISABLE_CROP_MODEL", "").lower() not in ("1", "true", "yes"):
        _ensure_crop_models()
        app.logger.info("Crop recommendation model loaded.")
    if os.getenv("DISABLE_DISEASE_MODEL", "").lower() not in ("1", "true", "yes"):
        load_disease_model()
    if os.getenv("DISABLE_INDOOR_MODEL", "").lower() not in ("1", "true", "yes"):
        load_indoor_model()


def load_disease_model() -> bool:
    global disease_model
    try:
        from tensorflow.keras.models import load_model as keras_load_model
        model_path = "my_keras_model.h5"
        if not os.path.exists(model_path):
            app.logger.warning("Disease model not found: %s", os.path.abspath(model_path))
            return False
        disease_model = keras_load_model(model_path)
        app.logger.info("Disease model loaded.")
        return True
    except Exception as e:
        app.logger.error("Disease model load error: %s", e)
        app.logger.error(traceback.format_exc())
        return False


def build_indoor_model(num_classes: int = 47):
    import torch.nn as nn
    from torchvision import models
    model = models.efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    return model


def load_indoor_model() -> bool:
    global indoor_model
    try:
        import torch
        candidate_paths = [
            os.getenv("INDOOR_MODEL_PATH", "").strip(),
            os.path.join(os.getcwd(), "plant_model.pth"),
        ]
        model_path = next((p for p in candidate_paths if p and os.path.exists(p)), None)
        app.logger.info("Indoor model candidates: %s", [p for p in candidate_paths if p])

        if not model_path:
            app.logger.warning("Indoor plant model NOT FOUND.")
            indoor_model = None
            return False

        device = _get_indoor_device()
        state = torch.load(model_path, map_location=device)
        model = build_indoor_model(num_classes=47)
        model.load_state_dict(state)
        model.to(device).eval()

        indoor_model = model
        app.logger.info("Indoor plant model loaded from: %s", model_path)
        return True

    except Exception as e:
        app.logger.error("Indoor plant model load error: %s", e)
        app.logger.error(traceback.format_exc())
        indoor_model = None
        return False

# =========================================================
# HELPERS
# =========================================================
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def preprocess_keras_image(image_path: str, size=(224, 224)) -> np.ndarray:
    import cv2
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Could not read image file")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, size)
    image = image.astype("float32") / 255.0
    image = np.expand_dims(image, axis=0)
    return image


def get_float_form_value(field_name: str, default: float = 0.0) -> float:
    value = request.form.get(field_name, "")
    if value is None:
        return default

    value = str(value).strip()
    if value == "":
        return default

    return float(value)


# =========================================================
# DISEASE PREDICTION
# =========================================================
def predict_disease(image_path: str):
    try:
        if disease_model is None:
            return None, "Disease model not loaded"

        x = preprocess_keras_image(image_path, (224, 224))
        preds = disease_model.predict(x, verbose=0)[0]

        idx = int(np.argmax(preds))
        confidence = float(preds[idx])
        predicted_class = CLASS_NAMES[idx]

        treatment_info = TREATMENT_GUIDE.get(predicted_class, DEFAULT_TREATMENT)

        top_3_idx = np.argsort(preds)[-3:][::-1]
        top_3 = [
            {
                "disease": CLASS_NAMES[i],
                "confidence": float(preds[i]),
                "treatment_url": f"/treatment/{CLASS_NAMES[i].replace('___', '_')}"
            }
            for i in top_3_idx
        ]

        result = {
            "predicted_disease": predicted_class,
            "common_name": treatment_info.get("name", predicted_class),
            "confidence": confidence,
            "severity": treatment_info.get("severity", "unknown"),
            "treatment_guide": treatment_info,
            "treatment_url": f"/treatment/{predicted_class.replace('___', '_')}",
            "top_predictions": top_3
        }
        return result, None

    except Exception as e:
        return None, str(e)

# =========================================================
# INDOOR PLANT PREDICTION
# =========================================================
def _use_groq_indoor_vision_first() -> bool:
    """Try Groq vision first unless USE_GROQ_INDOOR_PREDICTION=0 or ?groq=model."""
    if has_request_context():
        q = (request.args.get("groq") or "").strip().lower()
        if q in ("0", "false", "no", "model", "pytorch", "local"):
            return False
        if q in ("1", "true", "yes", "groq"):
            return True
    v = os.getenv("USE_GROQ_INDOOR_PREDICTION", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _predict_indoor_plant_pytorch(image_path: str):
    try:
        import torch
        if indoor_model is None:
            return None, "Indoor plant model not loaded"

        device = _get_indoor_device()
        img = Image.open(image_path).convert("RGB")
        x = _get_torch_transform()(img).unsqueeze(0).to(device)

        with torch.no_grad():
            outputs = indoor_model(x)
            probs = torch.softmax(outputs, dim=1)[0]
            idx = int(torch.argmax(probs).item())
            confidence = float(probs[idx].item())

        label = INDOOR_LABELS.get(str(idx))
        if label is None:
            return None, f"Predicted index {idx} not in INDOOR_LABELS. Output size={len(probs)}"

        return {"predicted_plant": label, "confidence": confidence}, None

    except Exception as e:
        return None, str(e)


def predict_indoor_plant(image_path: str):
    """
    Prefer Groq vision (same API key family as guide_client) when enabled and a client exists;
    falls back to the local PyTorch classifier.
    """
    if guide_client and _use_groq_indoor_vision_first():
        try:
            out = predict_indoor_label_vision(image_path, guide_client, INDOOR_CLASS_LABELS)
            if out:
                label, conf = out
                return {
                    "predicted_plant": label,
                    "confidence": conf,
                    "guide": INDOOR_PLANT_GUIDE.get(label),
                    "predict_source": "groq",
                }, None
        except Exception:
            app.logger.warning("Groq indoor vision failed: %s", traceback.format_exc())

    result, error = _predict_indoor_plant_pytorch(image_path)
    if error:
        return None, error
    result["guide"] = INDOOR_PLANT_GUIDE.get(result["predicted_plant"])
    result["predict_source"] = "model"
    return result, None

# =========================================================
# ROUTES
# =========================================================
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if is_worker():
        return redirect(url_for("worker_bookings_page"))
    return render_template("index.html")


@app.route("/worker")
@login_required(roles={"admin", "worker"})
def worker_dashboard():
    active_booking = None
    default_window = "7d"
    lang = session.get("lang", I18N_DEFAULT_LANG)

    if is_worker():
        active_booking = get_active_worker_booking()
        if not active_booking:
            flash(i18n_translate(lang, "worker_select_job_first"))
            return redirect(url_for("worker_bookings_page"))
        default_window = duration_to_window_key(active_booking["duration_days"])
    elif session.get("active_booking_id"):
        active_booking = get_active_worker_booking()
        if active_booking:
            default_window = duration_to_window_key(active_booking["duration_days"])

    return render_template(
        "worker_dashboard.html",
        pc_ip=get_pc_lan_ip(),
        active_booking=active_booking,
        default_window=default_window,
    )


@app.route("/worker/bookings")
@login_required(roles={"admin", "worker"})
def worker_bookings_page():
    lang = session.get("lang", I18N_DEFAULT_LANG)
    status_filter = (request.args.get("status") or "").strip().lower()
    if status_filter not in ("", "scheduled", "confirmed", "in_progress", "cancelled"):
        status_filter = ""

    available_bookings = get_all_analysis_bookings(status_filter="scheduled")
    my_bookings = get_worker_my_bookings(session["user_id"]) if not is_admin() else []
    pending_count = len(available_bookings)
    active_booking_id = session.get("active_booking_id")

    bookings = []
    if is_admin():
        bookings = get_all_analysis_bookings(status_filter=status_filter)

    return render_template(
        "worker_bookings.html",
        available_bookings=available_bookings,
        my_bookings=my_bookings,
        bookings=bookings,
        status_filter=status_filter,
        pending_count=pending_count,
        active_booking_id=active_booking_id,
        is_admin_view=is_admin(),
    )


@app.route("/worker/bookings/start/<int:booking_id>", methods=["POST"])
@login_required(roles={"admin", "worker"})
def start_worker_booking(booking_id: int):
    ok, detail = _start_booking_analysis(booking_id, session["user_id"])
    lang = session.get("lang", I18N_DEFAULT_LANG)
    if ok:
        session["active_booking_id"] = booking_id
        add_history(session["user_id"], "analysis_booking_start", f"Started analysis: {detail}")
        flash(i18n_translate(lang, "worker_booking_started_ok"))
        return redirect(url_for("worker_dashboard"))
    flash(detail)
    return redirect(url_for("worker_bookings_page"))


@app.route("/worker/bookings/end", methods=["POST"])
@login_required(roles={"admin", "worker"})
def end_worker_booking():
    session.pop("active_booking_id", None)
    lang = session.get("lang", I18N_DEFAULT_LANG)
    flash(i18n_translate(lang, "worker_booking_ended_ok"))
    return redirect(url_for("worker_bookings_page"))


@app.route("/analysis-booking", methods=["GET", "POST"])
@login_required()
def analysis_booking_page():
    if request.method == "POST":
        start_date = (request.form.get("start_date") or "").strip()
        duration_days = request.form.get("duration_days", type=int)

        if not start_date:
            flash("Please choose a start date.")
            return redirect(url_for("analysis_booking_page"))
        if duration_days not in ALLOWED_ANALYSIS_DURATIONS:
            flash("Please choose 7, 14, or 30 days.")
            return redirect(url_for("analysis_booking_page"))

        try:
            start = datetime.date.fromisoformat(start_date)
        except ValueError:
            flash("Invalid start date.")
            return redirect(url_for("analysis_booking_page"))

        if start < datetime.date.today():
            flash("Start date cannot be in the past.")
            return redirect(url_for("analysis_booking_page"))

        booking = save_analysis_booking(session["user_id"], start.isoformat(), duration_days)
        add_history(
            session["user_id"],
            "analysis_booking",
            f"Booked {duration_days}-day analysis from {booking['start_date']} to {booking['end_date']}",
        )
        flash("Analysis booking confirmed.")
        return render_template(
            "analysis_booking.html",
            bookings=get_user_analysis_bookings(session["user_id"]),
            durations=ALLOWED_ANALYSIS_DURATIONS,
            booking=booking,
            success=True,
        )

    return render_template(
        "analysis_booking.html",
        bookings=get_user_analysis_bookings(session["user_id"]),
        durations=ALLOWED_ANALYSIS_DURATIONS,
        booking=None,
        success=False,
    )


@app.route("/analysis-booking/cancel/<int:booking_id>", methods=["POST"])
@login_required()
def cancel_analysis_booking(booking_id: int):
    ok, detail = _cancel_booking_record(
        booking_id,
        session["user_id"],
        as_admin=is_admin(),
    )
    lang = session.get("lang", I18N_DEFAULT_LANG)
    if ok:
        add_history(session["user_id"], "analysis_booking_cancel", f"Cancelled booking: {detail}")
        flash(i18n_translate(lang, "booking_cancelled_ok"))
    else:
        flash(detail)
    return redirect(url_for("analysis_booking_page"))


@app.route("/guides/<slug>")
def feature_guide(slug):
    if "user_id" not in session:
        return redirect(url_for("login"))
    if slug not in FEATURE_GUIDES:
        return render_template("error.html", error="Page not found"), 404
    if is_worker() and slug not in ("crop", "iot"):
        return redirect(url_for("worker_bookings_page"))
    meta = FEATURE_GUIDES[slug]
    cta_url = url_for(meta["endpoint"])
    if slug == "iot":
        cta_url = url_for("analysis_booking_page")
    elif meta.get("anchor"):
        cta_url = f"{cta_url}#{meta['anchor']}"
    elif is_worker() and slug == "crop":
        cta_url = url_for("worker_bookings_page")
    return render_template("feature_guide.html", slug=slug, meta=meta, cta_url=cta_url)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not username or not phone or not password or not confirm_password:
        flash("Username, phone number, password, and confirm password are required.")
        return render_template("register.html")
    if not is_valid_phone(phone):
        flash("Please enter a valid phone number.")
        return render_template("register.html")
    if password != confirm_password:
        flash("Password and confirm password do not match.")
        return render_template("register.html")
    if not is_strong_password(password):
        flash("Password must be at least 8 chars and include uppercase, lowercase, and a number.")
        return render_template("register.html")

    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM users WHERE username = ? OR phone = ?", (username, phone)).fetchone()
    if existing:
        conn.close()
        flash("Username or phone number already exists. Choose another one.")
        return render_template("register.html")

    conn.execute(
        "INSERT INTO users (username, phone, password_hash, role, created_at) VALUES (?, ?, ?, 'user', ?)",
        (username, phone, generate_password_hash(password), datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    flash("Registration successful. You can login now.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute") if limiter else (lambda f: f)
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        add_history(user["id"], "login", "User logged in")

        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        if user["role"] == "worker":
            return redirect(url_for("worker_bookings_page"))
        return redirect(url_for("home"))

    flash("Invalid username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if session.get("user_id"):
        add_history(session["user_id"], "logout", "User logged out")
    session.clear()
    return redirect(url_for("home"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required()
def change_password():
    if request.method == "GET":
        return render_template("change_password.html")

    current_password = request.form.get("current_password", "").strip()
    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not current_password or not new_password or not confirm_password:
        flash("All password fields are required.")
        return render_template("change_password.html")

    if new_password != confirm_password:
        flash("New password and confirm password do not match.")
        return render_template("change_password.html")
    if not is_strong_password(new_password):
        flash("New password must be at least 8 chars and include uppercase, lowercase, and a number.")
        return render_template("change_password.html")

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if not user or not check_password_hash(user["password_hash"], current_password):
        conn.close()
        flash("Current password is incorrect.")
        return render_template("change_password.html")

    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), session["user_id"])
    )
    conn.commit()
    conn.close()
    add_history(session["user_id"], "change_password", "User changed account password")
    flash("Password changed successfully.")
    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "worker":
        return redirect(url_for("worker_bookings_page"))
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required(role="admin")
def user_dashboard():
    return redirect(url_for("admin_dashboard"))


@app.route("/user/history")
@login_required()
def user_history_page():
    allowed_actions = ("crop_recommendation", "indoor_plant_detection", "disease_detection")
    action_filter = request.args.get("action", "").strip()
    date_filter = request.args.get("date", "").strip()
    query = """
        SELECT action, details, created_at
        FROM history
        WHERE user_id = ?
          AND action IN (?, ?, ?)
    """
    params = [session["user_id"]]
    params.extend(list(allowed_actions))

    if action_filter:
        if action_filter not in allowed_actions:
            action_filter = ""
        else:
            query += " AND action = ?"
            params.append(action_filter)
    if date_filter:
        query += " AND substr(created_at, 1, 10) = ?"
        params.append(date_filter)

    query += " ORDER BY id DESC LIMIT 200"
    conn = get_db_connection()
    user_history = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("user_dashboard.html", history=user_history, action_filter=action_filter, date_filter=date_filter)


@app.route("/history/export")
@login_required()
def export_user_history():
    allowed_actions = ("crop_recommendation", "indoor_plant_detection", "disease_detection")
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT action, details, created_at
        FROM history
        WHERE user_id = ?
          AND action IN (?, ?, ?)
        ORDER BY id DESC
        """,
        (session["user_id"], allowed_actions[0], allowed_actions[1], allowed_actions[2])
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["action", "details", "created_at"])
    for row in rows:
        writer.writerow([row["action"], row["details"], row["created_at"]])

    filename = f"user_history_{session['username']}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    action_filter = request.args.get("action", "").strip()
    username_filter = request.args.get("username", "").strip()
    date_filter = request.args.get("date", "").strip()

    conn = get_db_connection()
    users = conn.execute(
        "SELECT id, username, role, created_at, profile_image FROM users ORDER BY id DESC"
    ).fetchall()

    history_query = """
        SELECT h.action, h.details, h.image_file, h.created_at, u.username, u.profile_image
        FROM history h
        JOIN users u ON h.user_id = u.id
        WHERE 1=1
    """
    params = []
    if action_filter:
        history_query += " AND h.action = ?"
        params.append(action_filter)
    if username_filter:
        history_query += " AND u.username LIKE ?"
        params.append(f"%{username_filter}%")
    if date_filter:
        history_query += " AND substr(h.created_at, 1, 10) = ?"
        params.append(date_filter)
    history_query += " ORDER BY h.id DESC LIMIT 300"

    recent_history = conn.execute(history_query, params).fetchall()
    site_settings = conn.execute(
        "SELECT instagram_url, whatsapp_phone, disease_info, indoor_info, updated_at FROM site_settings WHERE id = 1"
    ).fetchone()
    conn.close()
    return render_template(
        "admin_dashboard.html",
        users=users,
        history=recent_history,
        action_filter=action_filter,
        username_filter=username_filter,
        date_filter=date_filter,
        site_settings=site_settings
    )


@app.route("/admin/site-settings", methods=["POST"])
@login_required(role="admin")
def update_site_settings():
    instagram_url = request.form.get("instagram_url", "").strip()
    whatsapp_phone = request.form.get("whatsapp_phone", "").strip()
    disease_info = request.form.get("disease_info", "").strip()
    indoor_info = request.form.get("indoor_info", "").strip()

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE site_settings
        SET instagram_url = ?, whatsapp_phone = ?, disease_info = ?, indoor_info = ?, updated_at = ?
        WHERE id = 1
        """,
        (instagram_url, whatsapp_phone, disease_info, indoor_info, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    add_history(session["user_id"], "update_site_settings", "Updated site footer and module info settings")
    flash("Site settings updated successfully.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/history/export")
@login_required(role="admin")
def export_admin_history():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT u.username, h.action, h.details, h.image_file, h.created_at
        FROM history h
        JOIN users u ON h.user_id = u.id
        ORDER BY h.id DESC
        """
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["username", "action", "details", "created_at"])
    for row in rows:
        writer.writerow([row["username"], row["action"], row["details"], row["created_at"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=all_users_history.csv"}
    )


@app.route("/admin/export-images/<string:action_name>")
@login_required(role="admin")
def export_action_images_csv(action_name: str):
    allowed = {"indoor_plant_detection", "disease_detection"}
    if action_name not in allowed:
        return render_template("error.html", error="Invalid export type"), 400

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT u.username, h.action, h.details, h.image_file, h.created_at
        FROM history h
        JOIN users u ON h.user_id = u.id
        WHERE h.action = ? AND h.image_file IS NOT NULL AND TRIM(h.image_file) != ''
        ORDER BY h.id DESC
        """,
        (action_name,)
    ).fetchall()
    conn.close()

    base_url = request.host_url.rstrip("/")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["username", "action", "details", "image_file", "image_url", "created_at"])
    for row in rows:
        image_url = f"{base_url}/static/uploads/{row['image_file']}"
        writer.writerow([row["username"], row["action"], row["details"], row["image_file"], image_url, row["created_at"]])

    filename = f"{action_name}_images.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
@login_required(role="admin")
def admin_delete_user(user_id: int):
    conn = get_db_connection()
    target = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        flash("User not found.")
        return redirect(url_for("admin_dashboard"))

    if target["id"] == session["user_id"]:
        conn.close()
        flash("You cannot delete your own account.")
        return redirect(url_for("admin_dashboard"))

    if target["role"] == "admin":
        admin_count = conn.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'").fetchone()["total"]
        if admin_count <= 1:
            conn.close()
            flash("Cannot delete the last admin account.")
            return redirect(url_for("admin_dashboard"))

    conn.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    add_history(session["user_id"], "admin_delete_user", f"Deleted user: {target['username']}")
    flash(f"User '{target['username']}' deleted.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/reset-password/<int:user_id>", methods=["POST"])
@login_required(role="admin")
def admin_reset_password(user_id: int):
    new_password = request.form.get("new_password", "").strip()
    if not new_password:
        flash("New password is required for reset.")
        return redirect(url_for("admin_dashboard"))
    if not is_strong_password(new_password):
        flash("Password must be strong: 8+ chars, uppercase, lowercase, number.")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    target = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        flash("User not found.")
        return redirect(url_for("admin_dashboard"))

    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user_id)
    )
    conn.commit()
    conn.close()
    add_history(session["user_id"], "admin_reset_password", f"Reset password for user: {target['username']}")
    flash(f"Password reset for '{target['username']}'.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/create-user", methods=["POST"])
@login_required(role="admin")
def admin_create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "user").strip().lower()

    if not username or not password:
        flash("Username and password are required.")
        return redirect(url_for("admin_dashboard"))
    if role not in VALID_ROLES:
        flash("Invalid role selected.")
        return redirect(url_for("admin_dashboard"))
    if not is_strong_password(password):
        flash("Password must be strong: 8+ chars, uppercase, lowercase, number.")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        flash(f"Username '{username}' already exists.")
        return redirect(url_for("admin_dashboard"))

    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, generate_password_hash(password), role, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    add_history(session["user_id"], "admin_create_user", f"Created {role} account: {username}")
    flash(f"User '{username}' created as {role}.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/set-role/<int:user_id>", methods=["POST"])
@login_required(role="admin")
def admin_set_role(user_id: int):
    role = request.form.get("role", "").strip().lower()
    if role not in VALID_ROLES:
        flash("Invalid role selected.")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    target = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        flash("User not found.")
        return redirect(url_for("admin_dashboard"))

    if target["role"] == "admin" and role != "admin":
        admin_count = conn.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'").fetchone()["total"]
        if admin_count <= 1:
            conn.close()
            flash("Cannot change role of the last admin account.")
            return redirect(url_for("admin_dashboard"))

    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()
    add_history(session["user_id"], "admin_set_role", f"Set role {role} for user: {target['username']}")
    flash(f"Role for '{target['username']}' updated to {role}.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/download-image/<path:filename>")
@login_required(role="admin")
def admin_download_image(filename: str):
    uploads_dir = os.path.join(app.root_path, app.config["UPLOAD_FOLDER"])
    safe_name = os.path.basename(filename)
    return send_from_directory(uploads_dir, safe_name, as_attachment=True)


@app.route("/admin/download-profile-image/<path:filename>")
@login_required(role="admin")
def admin_download_profile_image(filename: str):
    profile_dir = os.path.join(app.root_path, app.config["PROFILE_UPLOAD_FOLDER"])
    safe_name = os.path.basename(filename)
    return send_from_directory(profile_dir, safe_name, as_attachment=True)


@app.route("/communications")
@login_required()
def communications_page():
    conn = get_db_connection()
    current_user_profile = conn.execute(
        "SELECT profile_image FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    posts = conn.execute(
        """
        SELECT p.id, p.user_id, p.content, p.image_file, p.created_at, u.username, u.profile_image
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.id DESC
        LIMIT 100
        """
    ).fetchall()

    friends = conn.execute(
        """
        SELECT u.id, u.username
        FROM friendships f
        JOIN users u
          ON u.id = CASE
            WHEN f.user1_id = ? THEN f.user2_id
            ELSE f.user1_id
          END
        WHERE f.user1_id = ? OR f.user2_id = ?
        ORDER BY u.username
        """,
        (session["user_id"], session["user_id"], session["user_id"])
    ).fetchall()

    incoming_friend_requests = conn.execute(
        """
        SELECT fr.id, fr.sender_id, fr.created_at, u.username AS sender_name
        FROM friend_requests fr
        JOIN users u ON fr.sender_id = u.id
        WHERE fr.receiver_id = ? AND fr.status = 'pending'
        ORDER BY fr.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    outgoing_friend_requests = conn.execute(
        """
        SELECT fr.id, fr.receiver_id, fr.created_at, u.username AS receiver_name
        FROM friend_requests fr
        JOIN users u ON fr.receiver_id = u.id
        WHERE fr.sender_id = ? AND fr.status = 'pending'
        ORDER BY fr.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    discover_users = conn.execute(
        """
        SELECT id, username
        FROM users
        WHERE id != ?
          AND id NOT IN (
              SELECT CASE
                  WHEN f.user1_id = ? THEN f.user2_id
                  ELSE f.user1_id
              END
              FROM friendships f
              WHERE f.user1_id = ? OR f.user2_id = ?
          )
          AND id NOT IN (
              SELECT receiver_id
              FROM friend_requests
              WHERE sender_id = ? AND status = 'pending'
          )
          AND id NOT IN (
              SELECT sender_id
              FROM friend_requests
              WHERE receiver_id = ? AND status = 'pending'
          )
        ORDER BY username
        LIMIT 200
        """,
        (
            session["user_id"],
            session["user_id"],
            session["user_id"],
            session["user_id"],
            session["user_id"],
            session["user_id"],
        )
    ).fetchall()

    post_ids = [p["id"] for p in posts]
    likes_by_post = {}
    reaction_counts_by_post = {}
    user_reaction_by_post = {}
    replies_by_post = {}

    if post_ids:
        placeholders = ",".join(["?"] * len(post_ids))
        reaction_rows = conn.execute(
            f"""
            SELECT post_id, reaction_type, COUNT(*) AS total
            FROM post_reactions
            WHERE post_id IN ({placeholders})
            GROUP BY post_id, reaction_type
            """,
            post_ids
        ).fetchall()
        for row in reaction_rows:
            reaction_counts_by_post.setdefault(row["post_id"], {})[row["reaction_type"]] = row["total"]

        user_reaction_rows = conn.execute(
            f"SELECT post_id, reaction_type FROM post_reactions WHERE user_id = ? AND post_id IN ({placeholders})",
            [session["user_id"], *post_ids]
        ).fetchall()
        user_reaction_by_post = {row["post_id"]: row["reaction_type"] for row in user_reaction_rows}

        reply_rows = conn.execute(
            f"""
            SELECT r.id, r.post_id, r.user_id, r.content, r.created_at, u.username, u.profile_image
            FROM post_replies r
            JOIN users u ON r.user_id = u.id
            WHERE r.post_id IN ({placeholders})
            ORDER BY r.id ASC
            """,
            post_ids
        ).fetchall()
        for row in reply_rows:
            replies_by_post.setdefault(row["post_id"], []).append(row)

    conn.close()

    return render_template(
        "communications.html",
        posts=posts,
        current_user_profile=current_user_profile["profile_image"] if current_user_profile else "",
        likes_by_post=likes_by_post,
        reaction_counts_by_post=reaction_counts_by_post,
        user_reaction_by_post=user_reaction_by_post,
        replies_by_post=replies_by_post,
    )


@app.route("/direct-messages")
@login_required()
def direct_messages_page():
    search = request.args.get("search", "").strip()
    selected_friend_id_raw = request.args.get("friend_id", "").strip()
    conn = get_db_connection()

    friends = conn.execute(
        """
        SELECT u.id, u.username, u.profile_image
        FROM friendships f
        JOIN users u
          ON u.id = CASE
            WHEN f.user1_id = ? THEN f.user2_id
            ELSE f.user1_id
          END
        WHERE f.user1_id = ? OR f.user2_id = ?
        ORDER BY u.username
        """,
        (session["user_id"], session["user_id"], session["user_id"])
    ).fetchall()

    incoming_friend_requests = conn.execute(
        """
        SELECT fr.id, fr.sender_id, fr.created_at, u.username AS sender_name, u.profile_image AS sender_profile_image
        FROM friend_requests fr
        JOIN users u ON fr.sender_id = u.id
        WHERE fr.receiver_id = ? AND fr.status = 'pending'
        ORDER BY fr.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    outgoing_friend_requests = conn.execute(
        """
        SELECT fr.id, fr.receiver_id, fr.created_at, u.username AS receiver_name, u.profile_image AS receiver_profile_image
        FROM friend_requests fr
        JOIN users u ON fr.receiver_id = u.id
        WHERE fr.sender_id = ? AND fr.status = 'pending'
        ORDER BY fr.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    discover_users_query = """
        SELECT id, username, profile_image
        FROM users
        WHERE id != ?
          AND id NOT IN (
              SELECT CASE
                  WHEN f.user1_id = ? THEN f.user2_id
                  ELSE f.user1_id
              END
              FROM friendships f
              WHERE f.user1_id = ? OR f.user2_id = ?
          )
          AND id NOT IN (
              SELECT receiver_id
              FROM friend_requests
              WHERE sender_id = ? AND status = 'pending'
          )
          AND id NOT IN (
              SELECT sender_id
              FROM friend_requests
              WHERE receiver_id = ? AND status = 'pending'
          )
    """
    params = [
        session["user_id"],
        session["user_id"],
        session["user_id"],
        session["user_id"],
        session["user_id"],
        session["user_id"],
    ]
    if search:
        discover_users_query += " AND username LIKE ?"
        params.append(f"%{search}%")
    discover_users_query += " ORDER BY username LIMIT 200"
    discover_users = conn.execute(discover_users_query, params).fetchall()

    friends_map = {row["id"]: row for row in friends}
    selected_friend_id = None
    selected_friend = None
    conversation = []
    if selected_friend_id_raw.isdigit():
        candidate_id = int(selected_friend_id_raw)
        if candidate_id in friends_map:
            selected_friend_id = candidate_id
            selected_friend = friends_map[candidate_id]
            conversation = conn.execute(
                """
                SELECT m.id, m.sender_id, m.receiver_id, m.content, m.created_at, m.deleted_for_all
                FROM messages m
                WHERE (
                    m.sender_id = ? AND m.receiver_id = ? AND COALESCE(m.deleted_for_sender, 0) = 0
                ) OR (
                    m.sender_id = ? AND m.receiver_id = ? AND COALESCE(m.deleted_for_receiver, 0) = 0
                )
                ORDER BY m.id ASC
                LIMIT 500
                """,
                (session["user_id"], selected_friend_id, selected_friend_id, session["user_id"])
            ).fetchall()
    conn.close()

    return render_template(
        "direct_messages.html",
        friends=friends,
        incoming_friend_requests=incoming_friend_requests,
        outgoing_friend_requests=outgoing_friend_requests,
        discover_users=discover_users,
        selected_friend_id=selected_friend_id,
        selected_friend=selected_friend,
        conversation=conversation,
        search=search,
    )


@app.route("/communications/post", methods=["POST"])
@login_required()
def create_post():
    content = request.form.get("content", "").strip()
    image_file = request.files.get("image")

    if not content and (not image_file or image_file.filename == ""):
        flash("Post must include text or an image.")
        return redirect(url_for("communications_page"))
    if len(content) > 1000:
        flash("Post is too long. Max 1000 characters.")
        return redirect(url_for("communications_page"))

    saved_image_name = ""
    if image_file and image_file.filename:
        if not allowed_file(image_file.filename):
            flash("Invalid image file type. Allowed: png, jpg, jpeg, gif.")
            return redirect(url_for("communications_page"))
        saved_image_name = secure_filename(image_file.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_image_name)
        image_file.save(image_path)

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO posts (user_id, content, image_file, created_at) VALUES (?, ?, ?, ?)",
        (session["user_id"], content, saved_image_name, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    add_history(session["user_id"], "create_post", "Created a community post")
    return redirect(url_for("communications_page"))


@app.route("/communications/post/edit/<int:post_id>", methods=["POST"])
@login_required()
def edit_post(post_id: int):
    content = request.form.get("content", "").strip()
    if not content:
        flash("Post content cannot be empty.")
        return redirect(url_for("communications_page"))

    conn = get_db_connection()
    post = conn.execute("SELECT id, user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        flash("Post not found.")
        return redirect(url_for("communications_page"))
    if post["user_id"] != session["user_id"]:
        conn.close()
        flash("You can edit only your own post.")
        return redirect(url_for("communications_page"))

    conn.execute("UPDATE posts SET content = ? WHERE id = ?", (content, post_id))
    conn.commit()
    conn.close()
    return redirect(url_for("communications_page"))


@app.route("/communications/post/delete/<int:post_id>", methods=["POST"])
@login_required()
def delete_post(post_id: int):
    conn = get_db_connection()
    post = conn.execute("SELECT id, user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        flash("Post not found.")
        return redirect(url_for("communications_page"))
    if post["user_id"] != session["user_id"] and session.get("role") != "admin":
        conn.close()
        flash("You can delete only your own post (or admin can delete any post).")
        return redirect(url_for("communications_page"))

    conn.execute("DELETE FROM post_replies WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM post_likes WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM post_reactions WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("communications_page"))


@app.route("/communications/post/react/<int:post_id>", methods=["POST"])
@login_required()
def react_post(post_id: int):
    reaction_type = request.form.get("reaction_type", "").strip().lower()
    allowed_reactions = {"like", "haha", "angry", "wow"}
    if reaction_type not in allowed_reactions:
        flash("Invalid reaction.")
        return redirect(url_for("communications_page"))

    conn = get_db_connection()
    post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        flash("Post not found.")
        return redirect(url_for("communications_page"))

    existing = conn.execute(
        "SELECT id, reaction_type FROM post_reactions WHERE post_id = ? AND user_id = ?",
        (post_id, session["user_id"])
    ).fetchone()
    if existing and existing["reaction_type"] == reaction_type:
        conn.execute(
            "DELETE FROM post_reactions WHERE post_id = ? AND user_id = ?",
            (post_id, session["user_id"])
        )
    elif existing:
        conn.execute(
            "UPDATE post_reactions SET reaction_type = ?, created_at = ? WHERE id = ?",
            (reaction_type, datetime.datetime.now().isoformat(), existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO post_reactions (post_id, user_id, reaction_type, created_at) VALUES (?, ?, ?, ?)",
            (post_id, session["user_id"], reaction_type, datetime.datetime.now().isoformat())
        )
    conn.commit()
    conn.close()
    return redirect(url_for("communications_page"))


@app.route("/communications/post/reply/<int:post_id>", methods=["POST"])
@login_required()
def reply_post(post_id: int):
    content = request.form.get("content", "").strip()
    if not content:
        flash("Reply cannot be empty.")
        return redirect(url_for("communications_page"))
    if len(content) > 500:
        flash("Reply is too long. Max 500 characters.")
        return redirect(url_for("communications_page"))

    conn = get_db_connection()
    post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        flash("Post not found.")
        return redirect(url_for("communications_page"))

    conn.execute(
        "INSERT INTO post_replies (post_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
        (post_id, session["user_id"], content, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return redirect(url_for("communications_page"))


@app.route("/communications/comment/delete/<int:comment_id>", methods=["POST"])
@login_required()
def delete_comment(comment_id: int):
    conn = get_db_connection()
    comment = conn.execute(
        "SELECT id, user_id FROM post_replies WHERE id = ?",
        (comment_id,)
    ).fetchone()
    if not comment:
        conn.close()
        flash("Comment not found.")
        return redirect(url_for("communications_page"))

    if comment["user_id"] != session["user_id"] and session.get("role") != "admin":
        conn.close()
        flash("You can delete only your own comment (or admin can delete any comment).")
        return redirect(url_for("communications_page"))

    conn.execute("DELETE FROM post_replies WHERE id = ?", (comment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("communications_page"))


@app.route("/communications/message", methods=["POST"])
@login_required()
def send_message():
    receiver_id = request.form.get("receiver_id", "").strip()
    content = request.form.get("content", "").strip()

    if not receiver_id or not receiver_id.isdigit():
        flash("Please choose a valid user.")
        return redirect(url_for("direct_messages_page"))
    if not content:
        flash("Message content cannot be empty.")
        return redirect(url_for("direct_messages_page", friend_id=receiver_id))
    if len(content) > 1000:
        flash("Message is too long. Max 1000 characters.")
        return redirect(url_for("direct_messages_page", friend_id=receiver_id))

    receiver_id_int = int(receiver_id)
    if receiver_id_int == session["user_id"]:
        flash("You cannot send a message to yourself.")
        return redirect(url_for("direct_messages_page"))

    conn = get_db_connection()
    target = conn.execute("SELECT id FROM users WHERE id = ?", (receiver_id_int,)).fetchone()
    if not target:
        conn.close()
        flash("Selected user does not exist.")
        return redirect(url_for("direct_messages_page"))
    if not are_friends(conn, session["user_id"], receiver_id_int):
        conn.close()
        flash("You can send direct messages only to friends.")
        return redirect(url_for("direct_messages_page", friend_id=receiver_id_int))

    conn.execute(
        "INSERT INTO messages (sender_id, receiver_id, content, created_at) VALUES (?, ?, ?, ?)",
        (session["user_id"], receiver_id_int, content, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    add_history(session["user_id"], "send_message", f"Sent message to user_id={receiver_id_int}")
    return redirect(url_for("direct_messages_page", friend_id=receiver_id_int))


@app.route("/api/messages/send", methods=["POST"])
@login_required()
def api_send_message():
    receiver_id = request.form.get("receiver_id", "").strip()
    content = request.form.get("content", "").strip()

    if not receiver_id or not receiver_id.isdigit():
        return jsonify({"ok": False, "error": "Please choose a valid user."}), 400
    if not content:
        return jsonify({"ok": False, "error": "Message content cannot be empty."}), 400
    if len(content) > 1000:
        return jsonify({"ok": False, "error": "Message is too long. Max 1000 characters."}), 400

    receiver_id_int = int(receiver_id)
    if receiver_id_int == session["user_id"]:
        return jsonify({"ok": False, "error": "You cannot send a message to yourself."}), 400

    conn = get_db_connection()
    target = conn.execute("SELECT id FROM users WHERE id = ?", (receiver_id_int,)).fetchone()
    if not target:
        conn.close()
        return jsonify({"ok": False, "error": "Selected user does not exist."}), 404
    if not are_friends(conn, session["user_id"], receiver_id_int):
        conn.close()
        return jsonify({"ok": False, "error": "You can send direct messages only to friends."}), 403

    created_at = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT INTO messages (sender_id, receiver_id, content, created_at) VALUES (?, ?, ?, ?)",
        (session["user_id"], receiver_id_int, content, created_at)
    )
    message_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    conn.close()
    add_history(session["user_id"], "send_message", f"Sent message to user_id={receiver_id_int}")
    return jsonify({"ok": True, "message_id": message_id, "content": content, "created_at": created_at})


@app.route("/communications/friend-request", methods=["POST"])
@login_required()
def send_friend_request():
    receiver_id = request.form.get("receiver_id", "").strip()
    if not receiver_id or not receiver_id.isdigit():
        flash("Please choose a valid user.")
        return redirect(url_for("direct_messages_page"))

    receiver_id_int = int(receiver_id)
    if receiver_id_int == session["user_id"]:
        flash("You cannot send a friend request to yourself.")
        return redirect(url_for("direct_messages_page"))

    conn = get_db_connection()
    target = conn.execute("SELECT id, username FROM users WHERE id = ?", (receiver_id_int,)).fetchone()
    if not target:
        conn.close()
        flash("Selected user does not exist.")
        return redirect(url_for("direct_messages_page"))

    if are_friends(conn, session["user_id"], receiver_id_int):
        conn.close()
        flash("You are already friends.")
        return redirect(url_for("direct_messages_page"))

    reverse_pending = conn.execute(
        """
        SELECT id FROM friend_requests
        WHERE sender_id = ? AND receiver_id = ? AND status = 'pending'
        """,
        (receiver_id_int, session["user_id"])
    ).fetchone()
    if reverse_pending:
        conn.close()
        flash("This user already sent you a request. Accept it from incoming requests.")
        return redirect(url_for("direct_messages_page"))

    existing = conn.execute(
        """
        SELECT id, status FROM friend_requests
        WHERE sender_id = ? AND receiver_id = ?
        """,
        (session["user_id"], receiver_id_int)
    ).fetchone()
    now = datetime.datetime.now().isoformat()
    if existing:
        if existing["status"] == "pending":
            conn.close()
            flash("Friend request already pending.")
            return redirect(url_for("direct_messages_page"))
        conn.execute(
            "UPDATE friend_requests SET status = 'pending', updated_at = ? WHERE id = ?",
            (now, existing["id"])
        )
    else:
        conn.execute(
            """
            INSERT INTO friend_requests (sender_id, receiver_id, status, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (session["user_id"], receiver_id_int, now, now)
        )
    conn.commit()
    conn.close()
    flash(f"Friend request sent to {target['username']}.")
    return redirect(url_for("direct_messages_page"))


@app.route("/communications/friend-request/<int:request_id>/accept", methods=["POST"])
@login_required()
def accept_friend_request(request_id: int):
    conn = get_db_connection()
    req = conn.execute(
        """
        SELECT id, sender_id, receiver_id, status
        FROM friend_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()
    if not req:
        conn.close()
        flash("Friend request not found.")
        return redirect(url_for("direct_messages_page"))
    if req["receiver_id"] != session["user_id"]:
        conn.close()
        flash("You can accept only requests sent to you.")
        return redirect(url_for("direct_messages_page"))
    if req["status"] != "pending":
        conn.close()
        flash("This friend request is no longer pending.")
        return redirect(url_for("direct_messages_page"))

    u1, u2 = sorted_friend_pair(req["sender_id"], req["receiver_id"])
    conn.execute(
        """
        INSERT OR IGNORE INTO friendships (user1_id, user2_id, created_at)
        VALUES (?, ?, ?)
        """,
        (u1, u2, datetime.datetime.now().isoformat())
    )
    conn.execute(
        "UPDATE friend_requests SET status = 'accepted', updated_at = ? WHERE id = ?",
        (datetime.datetime.now().isoformat(), request_id)
    )
    conn.commit()
    conn.close()
    flash("Friend request accepted.")
    return redirect(url_for("direct_messages_page"))


@app.route("/communications/friend-request/<int:request_id>/reject", methods=["POST"])
@login_required()
def reject_friend_request(request_id: int):
    conn = get_db_connection()
    req = conn.execute(
        "SELECT id, receiver_id, status FROM friend_requests WHERE id = ?",
        (request_id,)
    ).fetchone()
    if not req:
        conn.close()
        flash("Friend request not found.")
        return redirect(url_for("direct_messages_page"))
    if req["receiver_id"] != session["user_id"]:
        conn.close()
        flash("You can reject only requests sent to you.")
        return redirect(url_for("direct_messages_page"))
    if req["status"] != "pending":
        conn.close()
        flash("This friend request is no longer pending.")
        return redirect(url_for("direct_messages_page"))

    conn.execute(
        "UPDATE friend_requests SET status = 'rejected', updated_at = ? WHERE id = ?",
        (datetime.datetime.now().isoformat(), request_id)
    )
    conn.commit()
    conn.close()
    flash("Friend request rejected.")
    return redirect(url_for("direct_messages_page"))


@app.route("/communications/message/edit/<int:message_id>", methods=["POST"])
@login_required()
def edit_message(message_id: int):
    content = request.form.get("content", "").strip()
    if not content:
        flash("Message cannot be empty.")
        return redirect(url_for("direct_messages_page"))

    conn = get_db_connection()
    msg = conn.execute("SELECT id, sender_id FROM messages WHERE id = ?", (message_id,)).fetchone()
    if not msg:
        conn.close()
        flash("Message not found.")
        return redirect(url_for("direct_messages_page"))
    if msg["sender_id"] != session["user_id"]:
        conn.close()
        flash("You can edit only your own sent messages.")
        return redirect(url_for("direct_messages_page"))

    conn.execute("UPDATE messages SET content = ? WHERE id = ?", (content, message_id))
    conn.commit()
    conn.close()
    return redirect(url_for("direct_messages_page"))


@app.route("/communications/message/delete/<int:message_id>", methods=["POST"])
@login_required()
def delete_message(message_id: int):
    mode = request.form.get("mode", "me").strip().lower()
    if mode not in {"me", "everyone"}:
        mode = "me"

    conn = get_db_connection()
    msg = conn.execute(
        "SELECT id, sender_id, receiver_id, deleted_for_all FROM messages WHERE id = ?",
        (message_id,)
    ).fetchone()
    if not msg:
        conn.close()
        flash("Message not found.")
        return redirect(url_for("direct_messages_page"))
    if msg["sender_id"] != session["user_id"] and msg["receiver_id"] != session["user_id"]:
        conn.close()
        flash("You can delete only your related messages.")
        return redirect(url_for("direct_messages_page"))

    if mode == "everyone":
        if msg["sender_id"] != session["user_id"]:
            conn.close()
            flash("Only sender can delete for everyone.")
            return redirect(url_for("direct_messages_page"))
        conn.execute(
            "UPDATE messages SET deleted_for_all = 1, deleted_at = ? WHERE id = ?",
            (datetime.datetime.now().isoformat(), message_id)
        )
    else:
        if msg["sender_id"] == session["user_id"]:
            conn.execute("UPDATE messages SET deleted_for_sender = 1 WHERE id = ?", (message_id,))
        else:
            conn.execute("UPDATE messages SET deleted_for_receiver = 1 WHERE id = ?", (message_id,))

    conn.commit()
    conn.close()
    other_id = msg["receiver_id"] if msg["sender_id"] == session["user_id"] else msg["sender_id"]
    return redirect(url_for("direct_messages_page", friend_id=other_id))


@app.route("/api/messages/delete", methods=["POST"])
@login_required()
def api_delete_message():
    message_id_raw = request.form.get("message_id", "").strip()
    mode = request.form.get("mode", "me").strip().lower()
    if mode not in {"me", "everyone"}:
        mode = "me"
    if not message_id_raw.isdigit():
        return jsonify({"ok": False, "error": "Invalid message id."}), 400
    message_id = int(message_id_raw)

    conn = get_db_connection()
    msg = conn.execute(
        "SELECT id, sender_id, receiver_id, deleted_for_all FROM messages WHERE id = ?",
        (message_id,)
    ).fetchone()
    if not msg:
        conn.close()
        return jsonify({"ok": False, "error": "Message not found."}), 404
    if msg["sender_id"] != session["user_id"] and msg["receiver_id"] != session["user_id"]:
        conn.close()
        return jsonify({"ok": False, "error": "Not allowed."}), 403

    if mode == "everyone":
        if msg["sender_id"] != session["user_id"]:
            conn.close()
            return jsonify({"ok": False, "error": "Only sender can delete for everyone."}), 403
        conn.execute(
            "UPDATE messages SET deleted_for_all = 1, deleted_at = ? WHERE id = ?",
            (datetime.datetime.now().isoformat(), message_id)
        )
    else:
        if msg["sender_id"] == session["user_id"]:
            conn.execute("UPDATE messages SET deleted_for_sender = 1 WHERE id = ?", (message_id,))
        else:
            conn.execute("UPDATE messages SET deleted_for_receiver = 1 WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "mode": mode, "message_id": message_id})


@app.route("/menu")
def menu_page():
    return render_template("menu.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required()
def profile_page():
    conn = get_db_connection()
    current_user = conn.execute(
        "SELECT id, username, phone, profile_image, role FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    if not current_user:
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    if request.method == "GET":
        conn.close()
        return render_template("profile.html", profile=current_user)

    new_username = request.form.get("username", "").strip()
    new_phone = request.form.get("phone", "").strip()
    image_file = request.files.get("profile_image")

    if not new_username:
        conn.close()
        flash("Username is required.")
        return render_template("profile.html", profile=current_user)

    if new_phone and not is_valid_phone(new_phone):
        conn.close()
        flash("Please enter a valid phone number.")
        return render_template("profile.html", profile=current_user)

    duplicate = conn.execute(
        """
        SELECT id FROM users
        WHERE id != ?
          AND (username = ? OR (? != '' AND phone = ?))
        LIMIT 1
        """,
        (session["user_id"], new_username, new_phone, new_phone)
    ).fetchone()
    if duplicate:
        conn.close()
        flash("Username or phone already exists.")
        return render_template("profile.html", profile=current_user)

    profile_image_name = current_user["profile_image"]
    if image_file and image_file.filename:
        if not allowed_file(image_file.filename):
            conn.close()
            flash("Invalid image type. Use png/jpg/jpeg/gif.")
            return render_template("profile.html", profile=current_user)
        safe_name = secure_filename(image_file.filename)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        profile_image_name = f"{session['user_id']}_{timestamp}_{safe_name}"
        save_path = os.path.join(app.config["PROFILE_UPLOAD_FOLDER"], profile_image_name)
        image_file.save(save_path)

    conn.execute(
        "UPDATE users SET username = ?, phone = ?, profile_image = ? WHERE id = ?",
        (new_username, new_phone, profile_image_name, session["user_id"])
    )
    conn.commit()
    updated_user = conn.execute(
        "SELECT id, username, phone, profile_image, role FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()

    session["username"] = updated_user["username"]
    add_history(session["user_id"], "update_profile", "Updated profile information")
    flash("Profile updated successfully.")
    return render_template("profile.html", profile=updated_user)


@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")


@app.route("/indoor-plant")
def indoor_plant_alias():
    return redirect(url_for("indoor_plant_detection"))


@app.route("/indoor-plant-detection", methods=["GET", "POST"])
def indoor_plant_detection():
    if request.method == "GET":
        return render_template("indoor-plant-detection.html")

    try:
        if "file" not in request.files:
            return render_template("indoor-plant-detection.html", error="No file uploaded")

        file = request.files["file"]
        if file.filename == "":
            return render_template("indoor-plant-detection.html", error="No file selected")
        if not allowed_file(file.filename):
            return render_template("indoor-plant-detection.html", error="Invalid file type")

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        result, error = predict_indoor_plant(filepath)
        if error:
            return render_template("indoor-plant-detection.html", error=error)
        if session.get("user_id"):
            add_history(
                session["user_id"],
                "indoor_plant_detection",
                f"Predicted: {result['predicted_plant']}",
                image_file=filename,
            )

        plant_label = result["predicted_plant"]
        guide, guide_source = _resolve_indoor_plant_guide(plant_label)
        return render_template(
            "indoor_plant_result.html",
            image_file=filename,
            predicted_plant=plant_label,
            confidence=f"{result['confidence']*100:.2f}%",
            guide=guide,
            guide_source=guide_source,
            ai_guides_available=guide_client is not None,
            care_only=False,
            predict_source=result.get("predict_source", "model"),
        )

    except Exception as e:
        return render_template("indoor-plant-detection.html", error=str(e))


@app.route("/indoor-plants")
def indoor_plants_page():
    return render_template("indoor_plants.html", plants=INDOOR_PLANT_GUIDE)


@app.route("/indoor-plants/<path:plant_name>")
def indoor_plant_detail(plant_name):
    return redirect(url_for("indoor_plant_care", plant=plant_name))


@app.route("/api/iot/upload", methods=["POST"])
@app.route("/api/iot/readings", methods=["POST"])
def iot_readings_ingest():
    if not _iot_api_authorized():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"ok": False, "error": "Expected JSON body"}), 400

    try:
        device_ip = (request.remote_addr or "").split("%")[0]
        result = _iot_ingest_payload(payload, device_ip=device_ip)
        app.logger.info("IoT upload from %s saved id=%s", device_ip, result.get("id"))
        return jsonify(result), 200
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/iot/config", methods=["GET", "POST"])
def iot_config():
    """GET: current ESP IP. POST JSON {\"esp_ip\":\"192.168.1.45\"} to save."""
    if not can_use_iot():
        return iot_access_denied_response()
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        esp_ip = (payload.get("esp_ip") or request.form.get("esp_ip") or "").strip()
        if not esp_ip:
            return jsonify({"ok": False, "error": "esp_ip required"}), 400
        if is_likely_pc_ip(esp_ip):
            pc = get_pc_lan_ip()
            return jsonify({
                "ok": False,
                "error": f"{esp_ip} is your PC address. ESP32 has a different IP — read Serial Monitor.",
                "pc_ip": pc,
            }), 400
        save_iot_esp_ip(esp_ip)
        return jsonify({"ok": True, "esp_ip": esp_ip, "pc_ip": get_pc_lan_ip()})

    esp_ip = IOT_ESP_IP or get_iot_esp_ip()
    pc_ip = get_pc_lan_ip()
    if esp_ip and is_likely_pc_ip(esp_ip):
        esp_ip = ""
    host = f"http://{pc_ip}:5000"
    sensors_url = f"http://{esp_ip}/sensors" if esp_ip else ""
    return jsonify({
        "ok": True,
        "esp_ip": esp_ip,
        "pc_ip": pc_ip,
        "sensors_url": sensors_url,
        "upload_url": f"{host}/api/iot/upload",
        "website_url": host,
    })


@app.route("/api/iot/sync", methods=["POST", "GET"])
def iot_sync_from_device():
    if not can_use_iot():
        return iot_access_denied_response()
    esp_ip = (request.args.get("esp_ip") or "").strip()
    result, err = sync_iot_from_esp(esp_ip=esp_ip or None)
    if err:
        return jsonify({"ok": False, "error": err, "esp_ip": esp_ip or get_iot_esp_ip()}), 502
    row = get_latest_iot_reading()
    resp = iot_row_to_json(row)
    resp["source"] = "esp_live"
    resp["sync"] = result
    return jsonify(resp)


@app.route("/api/iot/load", methods=["GET", "POST"])
def iot_load_for_crop():
    """Pull live from ESP32 /sensors, save, return values for the crop form."""
    if not can_use_iot():
        return iot_access_denied_response()
    esp_ip = (request.args.get("esp_ip") or (request.get_json(silent=True) or {}).get("esp_ip") or "").strip()
    sync_error = None
    source = "database"

    if esp_ip or IOT_ESP_IP or get_iot_esp_ip():
        _, sync_error = sync_iot_from_esp(esp_ip=esp_ip or None)
        source = "esp_live" if not sync_error else "database"
    else:
        sync_error = "Enter ESP32 IP from Serial Monitor, click Save IP, then Load."

    row = get_latest_iot_reading()
    if not row:
        return jsonify({
            "ok": False,
            "message": "No sensor data yet. Run run_agro.ps1, upload iot.ino, check Serial for HTTP 200.",
            "sync_error": sync_error,
        }), 404

    resp = iot_row_to_json(row)
    resp["source"] = source
    resp["esp_ip"] = esp_ip or get_iot_esp_ip() or IOT_ESP_IP
    if sync_error:
        resp["sync_error"] = sync_error
        resp["warnings"] = list(resp.get("warnings") or []) + [sync_error]
    # Always 200 when we have data so the browser can fill the form even if ESP pull failed
    return jsonify(resp), 200


@app.route("/api/iot/latest", methods=["GET"])
def iot_readings_latest():
    if not can_use_iot():
        return iot_access_denied_response()
    row = get_latest_iot_reading(user_id=request.args.get("user_id", type=int))
    resp = iot_row_to_json(row)
    if resp.get("ok"):
        resp["source"] = "database"
        resp["esp_ip"] = IOT_ESP_IP or get_iot_esp_ip()
    return jsonify(resp)


@app.route("/api/iot/dashboard", methods=["GET"])
def iot_dashboard_api():
    if not can_use_iot():
        return iot_access_denied_response()
    window = (request.args.get("window") or "24h").strip().lower()
    sync = request.args.get("sync", "").strip().lower() in ("1", "true", "yes")
    esp_ip = (request.args.get("esp_ip") or "").strip()
    payload = build_iot_dashboard_payload(window_key=window, sync_esp=sync, esp_ip=esp_ip)
    status = 200 if payload.get("ok") else 404
    return jsonify(payload), status


@app.route("/api/iot/analyze", methods=["POST"])
def iot_analyze_predict():
    if not can_use_iot():
        return iot_access_denied_response()
    body = request.get_json(silent=True) or {}
    window = (body.get("window") or request.args.get("window") or "7d").strip().lower()
    hours = IOT_WINDOW_HOURS.get(window, 168)
    rows = get_iot_readings_history(hours=hours)
    if not rows:
        return jsonify({"ok": False, "error": "No historical IoT data for the selected window."}), 404

    averaged = average_iot_rows(rows)
    if not averaged:
        return jsonify({"ok": False, "error": "Could not aggregate sensor readings."}), 400

    prediction = predict_crop_with_confidence(averaged)
    if session.get("user_id"):
        add_history(
            session["user_id"],
            "crop_recommendation",
            f"IoT window {window}: {prediction['crop']} ({prediction['confidence']}%)",
        )

    return jsonify({
        "ok": True,
        "window": window,
        "samples": len(rows),
        "averaged_inputs": iot_payload_from_raw(averaged),
        "prediction": {
            "crop": prediction["crop"],
            "confidence": prediction["confidence"],
            "alternatives": prediction["alternatives"],
            "source": f"Historical average ({window})",
            "predicted_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            "warnings": prediction["warnings"],
        },
    })


@app.route("/crop-recommendation")
def crop_recommend_page():
    if is_worker():
        return redirect(url_for("worker_bookings_page"))
    return render_template("crop-recommendation.html", pc_ip=get_pc_lan_ip(), can_use_iot=can_use_iot())


@app.route("/crop-predict", methods=["POST"])
def crop_predict():
    try:
        crop_model, scaler, label_encoder = _ensure_crop_models()
        print("DEBUG request.form:", request.form)

        raw_form = {
            "nitrogen": get_float_form_value("nitrogen"),
            "phosphorus": get_float_form_value("phosphorus"),
            "potassium": get_float_form_value("potassium"),
            "temperature": get_float_form_value("temperature"),
            "humidity": get_float_form_value("humidity"),
            "ph": get_float_form_value("ph"),
            "rainfall": get_float_form_value("rainfall"),
        }
        crop_vals, _ = normalize_iot_for_crop_model(raw_form)
        use = {}
        for key, model_key in [
            ("nitrogen", "N"),
            ("phosphorus", "P"),
            ("potassium", "K"),
            ("temperature", "temperature"),
            ("humidity", "humidity"),
            ("ph", "ph"),
            ("rainfall", "rainfall"),
        ]:
            use[model_key] = crop_vals.get(key) if crop_vals.get(key) is not None else raw_form[key]

        features = pd.DataFrame([use])

        print("DEBUG features:")
        print(features)

        scaled_features = scaler.transform(features)
        prediction_encoded = crop_model.predict(scaled_features)[0]

        try:
            prediction = label_encoder.inverse_transform([prediction_encoded])[0]
        except Exception:
            prediction = str(prediction_encoded)
        if session.get("user_id"):
            add_history(session["user_id"], "crop_recommendation", f"Recommended crop: {prediction}")

        return redirect(url_for("crop_guide", crop_name=prediction))

    except Exception as e:
        print("CROP PREDICT ERROR:", str(e))
        print(traceback.format_exc())
        return render_template("crop-recommendation.html", error=str(e), pc_ip=get_pc_lan_ip(), can_use_iot=can_use_iot())


def _use_ai_guides() -> bool:
    """USE_AI_GUIDES=1 enables Groq-generated crop/treatment guides. ?ai=1 forces on; ?ai=0 forces static."""
    q = (request.args.get("ai") or "").strip().lower()
    if q in ("0", "false", "no", "static"):
        return False
    if q in ("1", "true", "yes", "llm"):
        return True
    v = os.getenv("USE_AI_GUIDES", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _resolve_indoor_plant_guide(plant_label: str):
    """Static guide from DB, optionally replaced or filled by Groq (see USE_AI_GUIDES / ?ai=)."""
    static_guide = INDOOR_PLANT_GUIDE.get(plant_label)
    guide = static_guide
    guide_source = "static"
    if guide_client and (_use_ai_guides() or not static_guide):
        try:
            ai_g = generate_indoor_plant_guide_llm(plant_label, guide_client, static_hint=static_guide)
            if ai_g:
                return ai_g, "ai"
        except Exception:
            app.logger.warning("AI indoor plant guide failed: %s", traceback.format_exc())
    return guide, guide_source


@app.route("/indoor-plant-care", methods=["GET"])
def indoor_plant_care():
    plant = (request.args.get("plant") or "").strip()
    if not plant:
        flash("Missing plant name for care guide.")
        return redirect(url_for("indoor_plant_detection"))
    guide, guide_source = _resolve_indoor_plant_guide(plant)
    if not guide:
        return render_template(
            "error.html",
            error=f"No care guide available for «{plant}». Add a Groq guide key or use a supported plant name.",
        )
    safe_image = ""
    img = (request.args.get("image") or "").strip()
    if img:
        bn = os.path.basename(img)
        pth = os.path.join(app.root_path, app.config["UPLOAD_FOLDER"], bn)
        if os.path.isfile(pth):
            safe_image = bn
    return render_template(
        "indoor_plant_result.html",
        image_file=safe_image,
        predicted_plant=plant,
        confidence="—",
        guide=guide,
        guide_source=guide_source,
        ai_guides_available=guide_client is not None,
        care_only=True,
        predict_source="care_link",
    )


@app.route("/guide/<crop_name>")
def crop_guide(crop_name):
    normalized = (crop_name or "").strip()

    # Support inputs coming from disease predictions such as:
    # "Tomato___Late_blight" -> "tomato"
    base_name = normalized.split("___")[0].strip()
    base_name = base_name.replace("_", " ").replace("-", " ").strip().lower()

    alias_map = {
        "grape": "grapes",
        "orange": "orange",
        "apple": "apple",
        "corn (maize)": "maize",
        "corn maize": "maize",
        "maize": "maize",
        "potato": "potato",
        "tomato": "tomato",
        "pepper bell": "pepper",
        "pepper, bell": "pepper",
        "cherry (including sour)": "chickpea",
        "strawberry": "watermelon",
        "blueberry": "mango",
        "raspberry": "mango",
        "soybean": "mungbean",
        "squash": "watermelon",
        "peach": "mango",
    }

    candidates = [
        normalized,
        normalized.lower(),
        base_name,
        alias_map.get(base_name, ""),
    ]

    guide = None
    final_crop_name = normalized
    for name in candidates:
        if not name:
            continue
        guide = CROP_GUIDE.get(name)
        if guide:
            final_crop_name = name
            break

    # Crop recommendation and normal links use the static CROP_GUIDE only (original behavior).
    # Optional Groq plan: open the same URL with ?ai=1 (does not use USE_AI_GUIDES—treatment/indoor still do).
    guide_source = "static"
    want_ai_crop = (request.args.get("ai") or "").strip().lower() in ("1", "true", "yes", "llm")
    if guide_client and want_ai_crop:
        try:
            hint = guide if guide else None
            display = (final_crop_name or normalized or crop_name).replace("_", " ").title()
            ai_guide = generate_crop_guide_llm(display, guide_client, static_hint=hint)
            if ai_guide:
                guide = ai_guide
                final_crop_name = final_crop_name or normalized or crop_name
                guide_source = "ai"
        except Exception:
            app.logger.warning("AI crop guide failed: %s", traceback.format_exc())
        if not guide:
            return render_template(
                "error.html",
                error=f"No guide found for: {crop_name}. Please open Crop Recommendation and try there."
            )
    elif not guide:
        return render_template(
            "error.html",
            error=f"No guide found for: {crop_name}. Please open Crop Recommendation and try there."
        )

    # Optional photo only when ?image= is present (e.g. disease flow). Crop recommendation has no image—do not use session.
    crop_image = ""
    image_candidate = (request.args.get("image") or "").strip()
    if image_candidate:
        safe_image = os.path.basename(image_candidate)
        image_path = os.path.join(app.root_path, app.config["UPLOAD_FOLDER"], safe_image)
        if os.path.isfile(image_path):
            crop_image = safe_image

    guide_image_url = ""
    if crop_image:
        guide_image_url = url_for("static", filename=f"uploads/{crop_image}")

    return render_template(
        "guide.html",
        crop_name=final_crop_name,
        guide=guide,
        guide_image_url=guide_image_url,
        guide_source=guide_source,
        ai_guides_available=guide_client is not None,
    )


@app.route("/disease-detection", methods=["GET", "POST"])
def disease_detection():
    if request.method == "GET":
        return render_template("disease-detection.html")

    try:
        if "file" not in request.files:
            return render_template("disease-detection.html", error="No file uploaded")

        file = request.files["file"]
        if file.filename == "":
            return render_template("disease-detection.html", error="No file selected")
        if not allowed_file(file.filename):
            return render_template("disease-detection.html", error="Invalid file type")

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        result, error = predict_disease(filepath)
        if error:
            return render_template("disease-detection.html", error=error)
        session["last_uploaded_image"] = filename
        if session.get("user_id"):
            add_history(
                session["user_id"],
                "disease_detection",
                f"Predicted disease: {result['predicted_disease']}",
                image_file=filename,
            )

        input_data = {
            "Image File": filename,
            "Predicted Disease": result["predicted_disease"],
            "Common Name": result["common_name"],
            "Confidence": f"{result['confidence']*100:.2f}%"
        }

        return render_template(
            "result.html",
            crop=result["predicted_disease"],
            input_data=input_data,
            image_file=filename,
        )

    except Exception as e:
        return render_template("disease-detection.html", error=str(e))


@app.route("/treatment/<disease_name>")
def treatment_guide(disease_name):
    formatted_name = disease_name.replace("_", "___").replace("-", "___")
    treatment = TREATMENT_GUIDE.get(formatted_name, DEFAULT_TREATMENT)
    guide_source = "static"
    if guide_client and _use_ai_guides():
        try:
            ai_t = generate_treatment_llm(formatted_name, guide_client, static_hint=treatment)
            if ai_t:
                treatment = ai_t
                guide_source = "ai"
        except Exception:
            app.logger.warning("AI treatment guide failed: %s", traceback.format_exc())
    return render_template(
        "treatment_guide.html",
        disease_name=formatted_name,
        treatment=treatment,
        current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        guide_source=guide_source,
        ai_guides_available=guide_client is not None,
    )


@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per minute") if limiter else (lambda f: f)
def api_chat():
    data = request.get_json(force=True)
    user_msg = data.get("message", "")

    if client is None:
        return jsonify({"reply": "Chatbot is not configured. Please set GROQ_API_KEY in environment variables."})

    def detect_language(text: str) -> str:
        try:
            return langdetect.detect(text)
        except Exception:
            return "en"

    user_lang = detect_language(user_msg)

    if user_lang == "ar":
        system_prompt = (
            "أنت مساعد ذكاء اصطناعي متخصص فقط في الزراعة. "
            "إذا سأل المستخدم عن أي شيء غير زراعي، أجب: "
            "'أنا متخصص فقط في المواضيع الزراعية.'"
        )
    else:
        system_prompt = (
            "You are an AI assistant specialized ONLY in agriculture. "
            "If the user asks anything unrelated to agriculture, respond: "
            "'I am specialized only in agricultural topics.'"
        )

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
    )
    reply = completion.choices[0].message.content
    if session.get("user_id"):
        add_history(session["user_id"], "chatbot", f"Asked: {user_msg[:100]}")
    return jsonify({"reply": reply})


# =========================================================
# MOBILE API (JSON for Flutter app)
# =========================================================
@app.route("/api/mobile/login", methods=["POST"])
@limiter.limit("10 per minute") if limiter else (lambda f: f)
def mobile_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"}), 400

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"ok": False, "error": "Invalid username or password"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    add_history(user["id"], "login", "Mobile login")
    return jsonify({
        "ok": True,
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
    })


@app.route("/api/mobile/register", methods=["POST"])
def mobile_register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()
    confirm_password = (data.get("confirm_password") or password).strip()

    if not username or not phone or not password:
        return jsonify({"ok": False, "error": "Username, phone, and password required"}), 400
    if not is_valid_phone(phone):
        return jsonify({"ok": False, "error": "Invalid phone number"}), 400
    if password != confirm_password:
        return jsonify({"ok": False, "error": "Passwords do not match"}), 400
    if not is_strong_password(password):
        return jsonify({
            "ok": False,
            "error": "Password must be 8+ chars with upper, lower, and a number",
        }), 400

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ? OR phone = ?", (username, phone)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"ok": False, "error": "Username or phone already exists"}), 409

    conn.execute(
        "INSERT INTO users (username, phone, password_hash, role, created_at) VALUES (?, ?, ?, 'user', ?)",
        (username, phone, generate_password_hash(password), datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "Registration successful. Please log in."})


def _mobile_save_upload(file) -> tuple[str | None, str | None]:
    if not file or file.filename == "":
        return None, "No file selected"
    if not allowed_file(file.filename):
        return None, "Invalid file type"
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    return filepath, filename


@app.route("/api/mobile/disease", methods=["POST"])
def mobile_disease_detect():
    try:
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "No file uploaded"}), 400
        filepath, filename = _mobile_save_upload(request.files["file"])
        if not filepath:
            return jsonify({"ok": False, "error": filename or "Upload failed"}), 400

        result, error = predict_disease(filepath)
        if error:
            return jsonify({"ok": False, "error": error}), 500
        if session.get("user_id"):
            add_history(
                session["user_id"],
                "disease_detection",
                f"Predicted: {result['predicted_disease']}",
                image_file=filename,
            )
        return jsonify({"ok": True, "image_file": filename, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mobile/indoor", methods=["POST"])
def mobile_indoor_detect():
    try:
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "No file uploaded"}), 400
        filepath, filename = _mobile_save_upload(request.files["file"])
        if not filepath:
            return jsonify({"ok": False, "error": filename or "Upload failed"}), 400

        result, error = predict_indoor_plant(filepath)
        if error:
            return jsonify({"ok": False, "error": error}), 500

        plant_label = result["predicted_plant"]
        guide, guide_source = _resolve_indoor_plant_guide(plant_label)
        if session.get("user_id"):
            add_history(
                session["user_id"],
                "indoor_plant_detection",
                f"Predicted: {plant_label}",
                image_file=filename,
            )
        return jsonify({
            "ok": True,
            "image_file": filename,
            "predicted_plant": plant_label,
            "confidence": result["confidence"],
            "predict_source": result.get("predict_source", "model"),
            "guide": guide,
            "guide_source": guide_source,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mobile/crop-predict", methods=["POST"])
def mobile_crop_predict():
    try:
        crop_model, scaler, label_encoder = _ensure_crop_models()
        data = request.get_json(silent=True) or {}
        raw_form = {
            "nitrogen": float(data.get("nitrogen", 0)),
            "phosphorus": float(data.get("phosphorus", 0)),
            "potassium": float(data.get("potassium", 0)),
            "temperature": float(data.get("temperature", 0)),
            "humidity": float(data.get("humidity", 0)),
            "ph": float(data.get("ph", 0)),
            "rainfall": float(data.get("rainfall", 0)),
        }
        crop_vals, warnings = normalize_iot_for_crop_model(raw_form)
        use = {}
        for key, model_key in [
            ("nitrogen", "N"),
            ("phosphorus", "P"),
            ("potassium", "K"),
            ("temperature", "temperature"),
            ("humidity", "humidity"),
            ("ph", "ph"),
            ("rainfall", "rainfall"),
        ]:
            use[model_key] = crop_vals.get(key) if crop_vals.get(key) is not None else raw_form[key]

        features = pd.DataFrame([use])
        scaled_features = scaler.transform(features)
        prediction_encoded = crop_model.predict(scaled_features)[0]
        try:
            prediction = label_encoder.inverse_transform([prediction_encoded])[0]
        except Exception:
            prediction = str(prediction_encoded)

        guide = CROP_GUIDE.get(prediction)
        guide_source = "static"
        if guide_client and _use_ai_guides():
            try:
                ai_g = generate_crop_guide_llm(prediction, guide_client, static_hint=guide)
                if ai_g:
                    guide = ai_g
                    guide_source = "ai"
            except Exception:
                pass

        if session.get("user_id"):
            add_history(session["user_id"], "crop_recommendation", f"Recommended: {prediction}")

        return jsonify({
            "ok": True,
            "crop": prediction,
            "warnings": warnings,
            "guide": guide,
            "guide_source": guide_source,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mobile/indoor-plants", methods=["GET"])
def mobile_indoor_plants_list():
    plants = []
    for name, guide in INDOOR_PLANT_GUIDE.items():
        short = name.split("(")[0].strip()
        plants.append({
            "name": name,
            "short_name": short,
            "category": guide.get("category", "Indoor"),
            "difficulty": guide.get("difficulty", ""),
        })
    return jsonify({"ok": True, "plants": plants})


@app.route("/health/live")
def health_live():
    return jsonify({"status": "ok"}), 200


@app.route("/health")
def health_check():
    row = None
    try:
        row = get_latest_iot_reading()
    except Exception:
        pass
    return jsonify({
        "status": "ok",
        "disease_model_loaded": disease_model is not None,
        "indoor_model_loaded": indoor_model is not None,
        "crop_model_loaded": crop_model is not None,
        "device": str(indoor_device) if indoor_device is not None else "cpu",
        "iot_esp_ip": IOT_ESP_IP or get_iot_esp_ip(),
        "iot_has_reading": row is not None,
        "iot_last_read_at": row["created_at"] if row else None,
        "timestamp": datetime.datetime.now().isoformat(),
    })


@app.route("/privacy")
def privacy_page():
    return render_template("privacy.html")


@app.route("/terms")
def terms_page():
    return render_template("terms.html")


@app.route("/contact")
def contact_page():
    return render_template("contact.html")


@app.route("/robots.txt")
def robots_txt():
    content = "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    pages = ["/", "/login", "/register", "/privacy", "/terms", "/contact"]
    xml_items = "".join([f"<url><loc>{request.host_url.rstrip('/')}{p}</loc></url>" for p in pages])
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xml_items}</urlset>'
    return Response(xml, mimetype="application/xml")


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", error="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("error.html", error="Internal server error"), 500

# Ensure tables (including iot_readings) exist for flask run / gunicorn / wsgi.
try:
    init_db()
except Exception:
    pass

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    print("Starting Unified Smart Agro App...")
    print("Current directory:", os.getcwd())
    init_db()
    setup_logging()
    warm_up_models()
    print(f"Database backend: {'Microsoft SQL Server' if is_mssql() else 'SQLite'}")
    print("App ready: http://localhost:5000")
    app.run(debug=not IS_PRODUCTION, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))