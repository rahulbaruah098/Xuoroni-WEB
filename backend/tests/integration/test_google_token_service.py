import pytest

from google.oauth2 import id_token as google_id_token

from app import create_app
from app.services.google_token_service import (
    GoogleConfigurationError,
    GoogleEmailNotVerified,
    InvalidGoogleToken,
    verify_google_id_token,
)


@pytest.fixture()
def app():
    return create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "GOOGLE_CLIENT_ID": (
                "xuoroni-test-client.apps."
                "googleusercontent.com"
            ),
        }
    )


def test_missing_google_token_is_rejected(
    app,
):
    with app.app_context():
        with pytest.raises(
            InvalidGoogleToken
        ):
            verify_google_id_token(
                ""
            )


def test_missing_google_client_id_is_rejected(
    app,
):
    with app.app_context():
        app.config[
            "GOOGLE_CLIENT_ID"
        ] = ""

        with pytest.raises(
            GoogleConfigurationError
        ):
            verify_google_id_token(
                "token"
            )


def test_google_verifier_uses_configured_audience(
    app,
    monkeypatch,
):
    captured = {}

    def fake_verify(
        token,
        request,
        audience,
    ):
        captured["token"] = token
        captured["audience"] = (
            audience
        )

        assert request is not None

        return {
            "sub": "google-user-123",
            "email": (
                "User@Example.COM"
            ),
            "email_verified": True,
        }

    monkeypatch.setattr(
        google_id_token,
        "verify_oauth2_token",
        fake_verify,
    )

    with app.app_context():
        result = (
            verify_google_id_token(
                "test-google-token"
            )
        )

    assert (
        captured["token"]
        == "test-google-token"
    )

    assert (
        captured["audience"]
        == (
            "xuoroni-test-client.apps."
            "googleusercontent.com"
        )
    )

    assert (
        result["sub"]
        == "google-user-123"
    )

    assert (
        result["email"]
        == "user@example.com"
    )


def test_invalid_google_token_is_wrapped(
    app,
    monkeypatch,
):
    def fake_verify(
        *args,
        **kwargs,
    ):
        raise ValueError(
            "Invalid token"
        )

    monkeypatch.setattr(
        google_id_token,
        "verify_oauth2_token",
        fake_verify,
    )

    with app.app_context():
        with pytest.raises(
            InvalidGoogleToken
        ):
            verify_google_id_token(
                "bad-token"
            )


def test_google_email_must_be_verified(
    app,
    monkeypatch,
):
    def fake_verify(
        *args,
        **kwargs,
    ):
        return {
            "sub": "google-user-123",
            "email": (
                "user@example.com"
            ),
            "email_verified": False,
        }

    monkeypatch.setattr(
        google_id_token,
        "verify_oauth2_token",
        fake_verify,
    )

    with app.app_context():
        with pytest.raises(
            GoogleEmailNotVerified
        ):
            verify_google_id_token(
                "token"
            )


def test_google_subject_is_required(
    app,
    monkeypatch,
):
    def fake_verify(
        *args,
        **kwargs,
    ):
        return {
            "email": (
                "user@example.com"
            ),
            "email_verified": True,
        }

    monkeypatch.setattr(
        google_id_token,
        "verify_oauth2_token",
        fake_verify,
    )

    with app.app_context():
        with pytest.raises(
            InvalidGoogleToken
        ):
            verify_google_id_token(
                "token"
            )


def test_optional_google_profile_claims_are_returned(
    app,
    monkeypatch,
):
    def fake_verify(
        *args,
        **kwargs,
    ):
        return {
            "sub": "google-user-456",
            "email": (
                "profile@example.com"
            ),
            "email_verified": True,
            "name": "Xuoroni User",
            "picture": (
                "https://example.com/"
                "avatar.jpg"
            ),
            "hd": "example.com",
        }

    monkeypatch.setattr(
        google_id_token,
        "verify_oauth2_token",
        fake_verify,
    )

    with app.app_context():
        result = (
            verify_google_id_token(
                "token"
            )
        )

    assert (
        result["name"]
        == "Xuoroni User"
    )

    assert (
        result["picture"]
        == (
            "https://example.com/"
            "avatar.jpg"
        )
    )

    assert (
        result["hosted_domain"]
        == "example.com"
    )
