from fastapi.testclient import TestClient


def test_health():
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_calibration_persists_config(aws):
    from app.main import app

    client = TestClient(app)
    payload = {
        "actuator_gain": 2.1,
        "stabilization_sensitivity": 0.6,
        "load_kg": 300,
        "label": "baseline attempt",
    }
    response = client.post("/calibrations", json=payload)
    assert response.status_code == 201
    assert "id" in response.json()


def test_trigger_run_starts_execution_and_returns_running(aws):
    from app.main import app

    client = TestClient(app)
    create_response = client.post(
        "/calibrations",
        json={"actuator_gain": 2.0, "stabilization_sensitivity": 0.5, "load_kg": 200},
    )
    calibration_id = create_response.json()["id"]

    run_response = client.post(
        f"/calibrations/{calibration_id}/run",
        json={
            "config": {
                "actuator_gain": 2.0,
                "stabilization_sensitivity": 0.5,
                "load_kg": 200,
            }
        },
    )
    assert run_response.status_code == 202
    body = run_response.json()
    assert body["status"] == "RUNNING"
    assert "run_id" in body


def test_get_run_returns_404_for_unknown_id(aws):
    from app.main import app

    client = TestClient(app)
    response = client.get("/runs/does-not-exist")
    assert response.status_code == 404


def test_get_run_returns_current_status(aws):
    from app.main import app

    client = TestClient(app)
    create_response = client.post(
        "/calibrations",
        json={"actuator_gain": 2.0, "stabilization_sensitivity": 0.5, "load_kg": 200},
    )
    calibration_id = create_response.json()["id"]
    run_response = client.post(
        f"/calibrations/{calibration_id}/run",
        json={
            "config": {
                "actuator_gain": 2.0,
                "stabilization_sensitivity": 0.5,
                "load_kg": 200,
            }
        },
    )
    run_id = run_response.json()["run_id"]

    get_response = client.get(f"/runs/{run_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "RUNNING"
