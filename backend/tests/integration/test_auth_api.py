import pytest

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import (
    mongo,
    redis_store,
)


TEST_DATABASE = "xuoroni_test_auth_api"
TEST_PREFIX = "xuoroni:test:auth-api"


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
            "JWT_SECRET_KEY": (
                "xuoroni-auth-api-test-secret-at-least-32-bytes"
            ),
            "JWT_ISSUER": "xuoroni-test",
            "JWT_AUDIENCE": "xuoroni-test-client",
            "JWT_ACCESS_TOKEN_MINUTES": 15,
            "JWT_REFRESH_TOKEN_DAYS": 30,
            "EXPOSE_DEV_OTP": True,
            "DEV_OTP_CODE": "654321",
            "OTP_TTL_SECONDS": 60,
            "OTP_RESEND_COOLDOWN_SECONDS": 1,
            "OTP_MAX_ATTEMPTS": 3,
            "OTP_REQUEST_WINDOW_SECONDS": 60,
            "OTP_MAX_REQUESTS_PER_WINDOW": 5,
            "OTP_KEY_PREFIX": TEST_PREFIX,
            "OTP_HASH_SECRET": (
                "xuoroni-auth-api-otp-secret-at-least-32-bytes"
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

        redis = (
            redis_store.get_client()
        )

        keys = list(
            redis.scan_iter(
                f"{TEST_PREFIX}:*"
            )
        )

        if keys:
            redis.delete(
                *keys
            )

        yield application

        mongo.cx.drop_database(
            TEST_DATABASE
        )

        keys = list(
            redis.scan_iter(
                f"{TEST_PREFIX}:*"
            )
        )

        if keys:
            redis.delete(
                *keys
            )


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client):
    response = client.post(
        "/api/v1/auth/request-otp",
        json={
            "phone": "9876543290",
        },
    )

    assert response.status_code == 200
    assert (
        response.get_json()[
            "dev_otp"
        ]
        == "654321"
    )

    response = client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": "9876543290",
            "otp": "654321",
            "device_id": "test-device",
            "platform": "android",
        },
    )

    assert response.status_code == 200

    return response.get_json()


def test_request_otp_endpoint(
    client,
):
    response = client.post(
        "/api/v1/auth/request-otp",
        json={
            "phone": "9876543291",
        },
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert (
        payload["phone"]
        == "+919876543291"
    )

    assert (
        payload["dev_otp"]
        == "654321"
    )


def test_verify_otp_creates_user_and_tokens(
    client,
):
    payload = _login(
        client
    )

    assert (
        payload["is_new_user"]
        is True
    )

    assert payload[
        "access_token"
    ]

    assert payload[
        "refresh_token"
    ]

    assert payload[
        "session_id"
    ]

    assert (
        payload["user"]["phone"]
        == "+919876543290"
    )


def test_me_requires_access_token(
    client,
):
    response = client.get(
        "/api/v1/auth/me"
    )

    assert response.status_code == 401

    assert (
        response.get_json()[
            "code"
        ]
        == "AUTHENTICATION_REQUIRED"
    )


def test_me_returns_authenticated_user(
    client,
):
    login = _login(
        client
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                "Bearer "
                + login[
                    "access_token"
                ]
            )
        },
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert (
        payload["user"]["id"]
        == login["user"]["id"]
    )


def test_refresh_rotates_tokens(
    client,
):
    login = _login(
        client
    )

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": (
                login[
                    "refresh_token"
                ]
            )
        },
    )

    assert response.status_code == 200

    refreshed = (
        response.get_json()
    )

    assert (
        refreshed[
            "refresh_token"
        ]
        != login[
            "refresh_token"
        ]
    )

    assert (
        refreshed[
            "session_id"
        ]
        != login[
            "session_id"
        ]
    )


def test_logout_invalidates_session(
    client,
):
    login = _login(
        client
    )

    response = client.post(
        "/api/v1/auth/logout",
        json={
            "refresh_token": (
                login[
                    "refresh_token"
                ]
            )
        },
    )

    assert response.status_code == 200

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                "Bearer "
                + login[
                    "access_token"
                ]
            )
        },
    )

    assert response.status_code == 401

    assert (
        response.get_json()[
            "code"
        ]
        == "INVALID_ACCESS_TOKEN"
    )
