import pytest
import redis as redis_lib

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import (
    mongo,
    redis_store,
)
from app.services.email_otp_service import (
    _redis_key,
    normalize_email,
)


TEST_DATABASE = (
    "xuoroni_test_email_auth_api"
)

OTP_PREFIX = (
    "xuoroni:test:email-auth-api"
)


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
                "xuoroni-email-auth-api-"
                "secret-at-least-32-bytes"
            ),
            "OTP_HASH_SECRET": (
                "xuoroni-email-auth-api-otp-"
                "secret-at-least-32-bytes"
            ),
            "EXPOSE_DEV_OTP": True,
            "DEV_EMAIL_OTP_CODE": "654321",
            "EMAIL_OTP_KEY_PREFIX": (
                OTP_PREFIX
            ),
            "OTP_RESEND_COOLDOWN_SECONDS": 1,
            "OTP_REQUEST_WINDOW_SECONDS": 60,
            "OTP_MAX_REQUESTS_PER_WINDOW": 5,
            "SMTP_HOST": "",
            "SMTP_FROM_EMAIL": "",
        }
    )

    redis_client = (
        redis_lib.Redis.from_url(
            application.config[
                "REDIS_URL"
            ],
            decode_responses=True,
        )
    )

    with application.app_context():
        mongo.cx.drop_database(
            TEST_DATABASE
        )

        ensure_indexes(
            mongo.db
        )

        keys = list(
            redis_client.scan_iter(
                f"{OTP_PREFIX}*"
            )
        )

        if keys:
            redis_client.delete(
                *keys
            )

        yield application

        mongo.cx.drop_database(
            TEST_DATABASE
        )

        keys = list(
            redis_client.scan_iter(
                f"{OTP_PREFIX}*"
            )
        )

        if keys:
            redis_client.delete(
                *keys
            )


@pytest.fixture()
def client(app):
    return app.test_client()


def _request_email_otp(
    client,
    email="user@example.com",
):
    response = client.post(
        "/api/v1/auth/request-email-otp",
        json={
            "email": email,
        },
    )

    assert (
        response.status_code
        == 200
    )

    return response


def _verify_email_otp(
    client,
    email="user@example.com",
):
    return client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": email,
            "otp": "654321",
            "device_id": "test-device",
            "platform": "pytest",
        },
    )


def test_request_email_otp_endpoint(
    client,
):
    response = _request_email_otp(
        client,
        "User@Example.com",
    )

    body = response.get_json()

    assert (
        body["email"]
        == "user@example.com"
    )

    assert (
        body["dev_otp"]
        == "654321"
    )


def test_invalid_email_is_rejected(
    client,
):
    response = client.post(
        "/api/v1/auth/request-email-otp",
        json={
            "email": "not-an-email",
        },
    )

    assert (
        response.status_code
        == 400
    )

    assert (
        response.get_json()[
            "code"
        ]
        == "INVALID_EMAIL_ADDRESS"
    )


def test_verify_email_creates_user_and_tokens(
    client,
):
    _request_email_otp(
        client
    )

    response = _verify_email_otp(
        client
    )

    assert (
        response.status_code
        == 200
    )

    body = response.get_json()

    assert (
        body["is_new_user"]
        is True
    )

    assert (
        body["user"]["email"]
        == "user@example.com"
    )

    assert (
        body["access_token"]
    )

    assert (
        body["refresh_token"]
    )

    assert (
        body["token_type"]
        == "Bearer"
    )


def test_second_email_login_reuses_user(
    client,
    app,
):
    _request_email_otp(
        client
    )

    first = _verify_email_otp(
        client
    ).get_json()

    # Preserve production cooldown behavior.
    # This test clears only the cooldown key so
    # it can exercise a second login immediately.
    with app.app_context():
        redis = (
            redis_store.get_client()
        )

        redis.delete(
            _redis_key(
                "cooldown",
                normalize_email(
                    "user@example.com"
                ),
            )
        )

    _request_email_otp(
        client
    )

    second = _verify_email_otp(
        client
    ).get_json()

    assert (
        second["is_new_user"]
        is False
    )

    assert (
        second["user"]["id"]
        == first["user"]["id"]
    )


def test_me_returns_email_identity(
    client,
):
    _request_email_otp(
        client
    )

    login = _verify_email_otp(
        client
    )

    token = login.get_json()[
        "access_token"
    ]

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert (
        response.status_code
        == 200
    )

    user = response.get_json()[
        "user"
    ]

    assert (
        user["email"]
        == "user@example.com"
    )


def test_email_access_token_works_with_profile_api(
    client,
):
    _request_email_otp(
        client
    )

    login = _verify_email_otp(
        client
    )

    token = login.get_json()[
        "access_token"
    ]

    response = client.get(
        "/api/v1/profile/me",
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert (
        response.status_code
        == 200
    )


def test_email_refresh_token_rotates(
    client,
):
    _request_email_otp(
        client
    )

    login = _verify_email_otp(
        client
    ).get_json()

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

    assert (
        response.status_code
        == 200
    )

    rotated = response.get_json()

    assert (
        rotated["access_token"]
    )

    assert (
        rotated["refresh_token"]
        != login["refresh_token"]
    )


def test_email_otp_is_single_use_at_api_level(
    client,
):
    _request_email_otp(
        client
    )

    first = _verify_email_otp(
        client
    )

    assert (
        first.status_code
        == 200
    )

    second = _verify_email_otp(
        client
    )

    assert (
        second.status_code
        == 401
    )

    assert (
        second.get_json()[
            "code"
        ]
        == "OTP_EXPIRED"
    )
