import pytest

from app import create_app
from app.security.tokens import (
    InvalidAccessToken,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    generate_session_id,
    generate_token_family_id,
    hash_refresh_token,
)


@pytest.fixture()
def app():
    return create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "JWT_SECRET_KEY": (
                "test-secret-that-must-not-be-used-in-production"
            ),
            "JWT_ISSUER": "xuoroni-test",
            "JWT_AUDIENCE": "xuoroni-test-client",
            "JWT_ACCESS_TOKEN_MINUTES": 15,
        }
    )


def test_access_token_round_trip(app):
    with app.app_context():
        token = create_access_token(
            "user-123",
            session_id="session-456",
        )

        payload = decode_access_token(
            token
        )

        assert payload["sub"] == "user-123"
        assert payload["sid"] == "session-456"
        assert payload["type"] == "access"
        assert payload["iss"] == "xuoroni-test"
        assert payload["aud"] == "xuoroni-test-client"
        assert payload["jti"]


def test_access_token_rejects_tampering(app):
    with app.app_context():
        token = create_access_token(
            "user-123",
            session_id="session-456",
        )

        tampered = token + "x"

        with pytest.raises(
            InvalidAccessToken
        ):
            decode_access_token(
                tampered
            )


def test_refresh_tokens_are_random():
    first = generate_refresh_token()
    second = generate_refresh_token()

    assert first
    assert second
    assert first != second


def test_refresh_token_hash_is_deterministic():
    token = generate_refresh_token()

    first_hash = hash_refresh_token(
        token
    )

    second_hash = hash_refresh_token(
        token
    )

    assert first_hash == second_hash
    assert first_hash != token
    assert len(first_hash) == 64


def test_empty_refresh_token_is_rejected():
    with pytest.raises(
        ValueError
    ):
        hash_refresh_token("")


def test_session_ids_are_unique():
    assert (
        generate_session_id()
        != generate_session_id()
    )


def test_token_family_ids_are_unique():
    assert (
        generate_token_family_id()
        != generate_token_family_id()
    )
