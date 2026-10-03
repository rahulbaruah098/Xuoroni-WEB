import pytest
from werkzeug.security import (
    generate_password_hash,
)

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo


TEST_DATABASE = "xuoroni_test_legacy_api"


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "MONGO_URI": (
                "mongodb://localhost:27017/"
                + TEST_DATABASE
            ),
            "SECRET_KEY": (
                "xuoroni-legacy-api-test-secret"
            ),
        }
    )

    with application.app_context():
        mongo.cx.drop_database(
            TEST_DATABASE
        )

        ensure_indexes(
            mongo.db
        )

        mongo.db.admins.insert_one(
            {
                "email": "admin@test.local",
                "password_hash": (
                    generate_password_hash(
                        "TestPassword123!"
                    )
                ),
            }
        )

        yield application

        mongo.cx.drop_database(
            TEST_DATABASE
        )


@pytest.fixture()
def client(app):
    return app.test_client()


def _login_admin(client):
    response = client.post(
        "/api/admin/login",
        json={
            "email": "admin@test.local",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200


def test_legacy_health(client):
    response = client.get(
        "/api/health"
    )

    assert response.status_code == 200

    assert response.get_json() == {
        "status": "ok",
        "database": "connected",
    }


def test_public_settings(client):
    response = client.get(
        "/api/public/settings"
    )

    assert response.status_code == 200

    assert response.get_json() == {
        "launch_at": None,
    }


def test_create_tester(client):
    response = client.post(
        "/api/testers",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "city": "Guwahati",
        },
    )

    assert response.status_code == 201


def test_duplicate_tester_is_rejected(
    client,
):
    payload = {
        "name": "Test User",
        "email": "duplicate@example.com",
        "city": "Guwahati",
    }

    assert (
        client.post(
            "/api/testers",
            json=payload,
        ).status_code
        == 201
    )

    assert (
        client.post(
            "/api/testers",
            json=payload,
        ).status_code
        == 409
    )


def test_admin_login_and_testers(
    client,
):
    _login_admin(
        client
    )

    response = client.get(
        "/api/admin/testers"
    )

    assert response.status_code == 200


def test_admin_routes_require_login(
    client,
):
    response = client.get(
        "/api/admin/testers"
    )

    assert response.status_code == 401


def test_countdown_update(
    client,
):
    _login_admin(
        client
    )

    response = client.put(
        "/api/admin/settings/countdown",
        json={
            "launch_at": (
                "2026-12-01T10:00:00+05:30"
            )
        },
    )

    assert response.status_code == 200

    assert response.get_json()[
        "launch_at"
    ].endswith(
        "+00:00"
    )


def test_csv_export(
    client,
):
    _login_admin(
        client
    )

    client.post(
        "/api/testers",
        json={
            "name": "CSV User",
            "email": "csv@example.com",
            "city": "Shillong",
        },
    )

    response = client.get(
        "/api/admin/testers.csv"
    )

    assert response.status_code == 200

    assert (
        "CSV User"
        in response.get_data(
            as_text=True
        )
    )
