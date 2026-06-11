#!/usr/bin/env python3
"""
Read ESP32 Serial Monitor lines and POST to Flask.
Use when WiFi upload fails but USB serial works.

  python iot/serial_bridge.py COM3
  python iot/serial_bridge.py COM3 --server http://192.168.1.2:5000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

ESP_IP_RE = re.compile(r"ESP32 IP:\s*((?:\d{1,3}\.){3}\d{1,3})", re.IGNORECASE)

LINE_RE = re.compile(
    r"Temp:\s*([\d.]+)C\s*\|\s*Hum:\s*([\d.]+)%.*"
    r"Soil Humidity:\s*(\d+)%.*"
    r"Rain:\s*([\d.]+)\s*mm.*"
    r"pH:\s*([\d.]+).*"
    r"NPK:\s*(-?\d+)-(-?\d+)-(-?\d+)",
    re.DOTALL | re.IGNORECASE,
)


def post_reading(server: str, payload: dict) -> None:
    url = server.rstrip("/") + "/api/iot/upload"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(resp.status, resp.read().decode())


def save_esp_ip(server: str, esp_ip: str) -> None:
    url = server.rstrip("/") + "/api/iot/config"
    data = json.dumps({"esp_ip": esp_ip}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode()
        print(f"ESP32 IP auto-saved: {esp_ip} -> {resp.status}")
        if body:
            print(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="Serial port, e.g. COM3")
    parser.add_argument("--server", default="http://127.0.0.1:5000")
    parser.add_argument("--user-id", type=int, default=4)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--save-esp-ip",
        action="store_true",
        help="Auto-detect 'ESP32 IP: ...' lines and save to website config",
    )
    args = parser.parse_args()

    try:
        import serial
    except ImportError:
        print("Install pyserial: pip install pyserial", file=sys.stderr)
        return 1

    buf = ""
    last_saved_ip = None
    ser = serial.Serial(args.port, args.baud, timeout=1)
    print(f"Listening on {args.port}, posting to {args.server}")

    while True:
        chunk = ser.read(512).decode("utf-8", errors="ignore")
        if not chunk:
            continue

        if args.save_esp_ip:
            for ip in ESP_IP_RE.findall(chunk):
                if ip != last_saved_ip:
                    try:
                        save_esp_ip(args.server, ip)
                        last_saved_ip = ip
                    except Exception as exc:
                        print("ESP IP save failed:", exc)

        buf += chunk
        while "====" in buf:
            block, buf = buf.split("====", 1)
            m = LINE_RE.search(block)
            if not m:
                continue
            payload = {
                "user_id": args.user_id,
                "temperature": float(m.group(1)),
                "humidity": float(m.group(2)),
                "soilHumidity": int(m.group(3)),
                "rainfall": float(m.group(4)),
                "ph": float(m.group(5)),
                "nitrogen": int(m.group(6)),
                "phosphorus": int(m.group(7)),
                "potassium": int(m.group(8)),
            }
            try:
                post_reading(args.server, payload)
            except Exception as exc:
                print("POST failed:", exc)


if __name__ == "__main__":
    raise SystemExit(main())
