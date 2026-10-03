import pytest
import redis as redis_lib

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo


TEST_DATABASE = (
    "xuoroni_test_profile_api"
)

OTP_PREFIX = (
    "xuoroni:test:profile-api"
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
                "xuoroni-profile-api-test-"
                "secret-at-least-32-bytes"
            ),
            "OTP_HASH_SECRET": (
                "xuoroni-profile-api-otp-"
                "secret-at-least-32-bytes"
            ),
            "OTP_KEY_PREFIX": (
                OTP_PREFIX
            ),
            "EXPOSE_DEV_OTP": True,
            "DEV_OTP_CODE": "654321",
            "OTP_RESEND_COOLDOWN_SECONDS": 1,
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


def auth_headers(
    client,
):
    request_response = client.post(
        "/api/v1/auth/request-otp",
        json={
            "phone": "9876543210",
        },
    )

    assert (
        request_response.status_code
        == 200
    )

    verify_response = client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": "9876543210",
            "otp": "654321",
        },
    )

    assert (
        verify_response.status_code
        == 200
    )

    access_token = (
        verify_response.get_json()[
            "access_token"
        ]
    )

    return {
        "Authorization": (
            f"Bearer {access_token}"
        )
    }


def test_profile_requires_authentication(
    client,
):
    response = client.get(
        "/api/v1/profile/me"
    )

    assert (
        response.status_code
        == 401
    )


def test_get_my_profile_creates_default_profile(
    client,
):
    headers = auth_headers(
        client
    )

    response = client.get(
        "/api/v1/profile/me",
        headers=headers,
    )

    assert (
        response.status_code
        == 200
    )

    profile = response.get_json()[
        "profile"
    ]

    assert (
        profile[
            "onboarding_status"
        ]
        == "not_started"
    )

    assert (
        "surname_normalized"
        not in profile
    )

    assert (
        "location"
        not in profile
    )


def test_patch_my_profile(
    client,
):
    headers = auth_headers(
        client
    )

    response = client.patch(
        "/api/v1/profile/me",
        headers=headers,
        json={
            "display_name": "Xuoroni User",
            "birth_date": "2000-01-01",
            "gender_identity": "man",
            "current_city": {
                "city": "Guwahati",
                "state": "Assam",
            },
            "languages": [
                "Assamese",
                "English",
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    profile = response.get_json()[
        "profile"
    ]

    assert (
        profile["display_name"]
        == "Xuoroni User"
    )

    assert (
        profile[
            "current_city"
        ]["state"]
        == "Assam"
    )


def test_underage_profile_api_is_rejected(
    client,
):
    headers = auth_headers(
        client
    )

    response = client.patch(
        "/api/v1/profile/me",
        headers=headers,
        json={
            "birth_date": (
                "2015-01-01"
            )
        },
    )

    assert (
        response.status_code
        == 400
    )

    error = response.get_json()[
        "error"
    ]

    assert (
        error["field"]
        == "birth_date"
    )


def test_get_and_patch_discovery_preferences(
    client,
):
    headers = auth_headers(
        client
    )

    response = client.get(
        (
            "/api/v1/profile/me/"
            "discovery-preferences"
        ),
        headers=headers,
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.get_json()[
            "preferences"
        ]["age_min"]
        == 18
    )

    response = client.patch(
        (
            "/api/v1/profile/me/"
            "discovery-preferences"
        ),
        headers=headers,
        json={
            "interested_in": [
                "woman",
            ],
            "age_min": 21,
            "age_max": 35,
            "max_distance_km": 75,
        },
    )

    assert (
        response.status_code
        == 200
    )

    preferences = (
        response.get_json()[
            "preferences"
        ]
    )

    assert (
        preferences[
            "age_min"
        ]
        == 21
    )

    assert (
        preferences[
            "age_max"
        ]
        == 35
    )


def test_onboarding_state_api(
    client,
):
    headers = auth_headers(
        client
    )

    response = client.get(
        "/api/v1/onboarding/state",
        headers=headers,
    )

    assert (
        response.status_code
        == 200
    )

    state = response.get_json()[
        "onboarding"
    ]

    assert (
        state["status"]
        == "not_started"
    )

    assert (
        state["current_step"]
        == "basics"
    )


def test_onboarding_progress_api(
    client,
):
    headers = auth_headers(
        client
    )

    response = client.patch(
        "/api/v1/onboarding/state",
        headers=headers,
        json={
            "completed_step": "basics",
            "current_step": "identity",
        },
    )

    assert (
        response.status_code
        == 200
    )

    state = response.get_json()[
        "onboarding"
    ]

    assert (
        state["status"]
        == "in_progress"
    )

    assert (
        state["current_step"]
        == "identity"
    )

    assert (
        "basics"
        in state[
            "completed_steps"
        ]
    )

    assert (
        state["started_at"]
        is not None
    )


def test_invalid_onboarding_step_is_rejected(
    client,
):
    headers = auth_headers(
        client
    )

    response = client.patch(
        "/api/v1/onboarding/state",
        headers=headers,
        json={
            "current_step": (
                "not-a-real-step"
            )
        },
    )

    assert (
        response.status_code
        == 400
    )

