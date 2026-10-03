import app.api.system as system_module

from app import create_app


def create_test_client():
    app = create_app(
        {
            "TESTING": True,
            "SOCKETIO_MESSAGE_QUEUE": "",
        }
    )

    return app.test_client()


def test_health_returns_200():
    client = create_test_client()

    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload == {
        "service": "xuoroni-backend",
        "status": "ok",
    }

    assert response.headers.get(
        "X-Request-ID"
    )


def test_ready_when_dependencies_are_available(
    monkeypatch,
):
    monkeypatch.setattr(
        system_module,
        "_mongodb_ready",
        lambda: True,
    )

    monkeypatch.setattr(
        system_module,
        "_redis_ready",
        lambda: True,
    )

    client = create_test_client()

    response = client.get(
        "/ready"
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["status"] == "ready"

    assert payload["dependencies"] == {
        "mongodb": True,
        "redis": True,
    }


def test_ready_fails_when_mongodb_is_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        system_module,
        "_mongodb_ready",
        lambda: False,
    )

    monkeypatch.setattr(
        system_module,
        "_redis_ready",
        lambda: True,
    )

    client = create_test_client()

    response = client.get(
        "/ready"
    )

    assert response.status_code == 503

    payload = response.get_json()

    assert payload["status"] == "not_ready"

    assert payload["dependencies"] == {
        "mongodb": False,
        "redis": True,
    }


def test_ready_fails_when_redis_is_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        system_module,
        "_mongodb_ready",
        lambda: True,
    )

    monkeypatch.setattr(
        system_module,
        "_redis_ready",
        lambda: False,
    )

    client = create_test_client()

    response = client.get(
        "/ready"
    )

    assert response.status_code == 503

    payload = response.get_json()

    assert payload["status"] == "not_ready"

    assert payload["dependencies"] == {
        "mongodb": True,
        "redis": False,
    }
