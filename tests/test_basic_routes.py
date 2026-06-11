from app import app, init_db, save_iot_reading


def test_health_route():
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200


def test_public_professional_pages():
    client = app.test_client()
    for route in ["/privacy", "/terms", "/contact", "/robots.txt", "/sitemap.xml"]:
        response = client.get(route)
        assert response.status_code == 200


def test_iot_readings_api():
    init_db()
    client = app.test_client()

    payload = {
        "nitrogen": 0,
        "phosphorus": 0,
        "potassium": 0,
        "temperature": 0.0,
        "humidity": 0.0,
        "rainfall": 20.0,
        "ph": 6.92,
        "soilHumidity": 0,
        "user_id": 4,
    }

    post = client.post("/api/iot/upload", json=payload)
    assert post.status_code == 200
    assert post.get_json()["ok"] is True

    latest = client.get("/api/iot/latest")
    assert latest.status_code == 200
    data = latest.get_json()
    assert data["ok"] is True
    assert data["nitrogen"] == 0
    assert data["ph"] == 6.92
    assert data["rainfall"] == 20.0
    assert data["raw"]["temperature"] == 0.0

    cfg = client.get("/api/iot/config")
    assert cfg.status_code == 200
