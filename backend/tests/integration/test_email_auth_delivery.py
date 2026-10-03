import pytest

from app import create_app
from app.extensions import redis_store
from app.services.email_auth_service import (
    request_email_auth_otp,
)
from app.services.email_otp_service import (
    verify_email_otp,
)
from app.services.email_sender import (
    EmailConfigurationError,
    EmailDeliveryError,
)
from app.services.otp_service import (
    OtpExpired,
)


TEST_PREFIX = (
    "xuoroni:test:email-auth-delivery"
)


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "EXPOSE_DEV_OTP": True,
            "DEV_EMAIL_OTP_CODE": "654321",
            "EMAIL_OTP_KEY_PREFIX": (
                TEST_PREFIX
            ),
            "OTP_RESEND_COOLDOWN_SECONDS": 1,
            "OTP_REQUEST_WINDOW_SECONDS": 60,
            "OTP_MAX_REQUESTS_PER_WINDOW": 5,
            "OTP_MAX_ATTEMPTS": 3,
            "OTP_TTL_SECONDS": 30,
            "SMTP_HOST": "",
            "SMTP_FROM_EMAIL": "",
        }
    )

    with application.app_context():
        redis = redis_store.get_client()

        keys = list(
            redis.scan_iter(
                f"{TEST_PREFIX}*"
            )
        )

        if keys:
            redis.delete(
                *keys
            )

        yield application

        keys = list(
            redis.scan_iter(
                f"{TEST_PREFIX}*"
            )
        )

        if keys:
            redis.delete(
                *keys
            )


def test_dev_mode_can_issue_without_smtp(
    app,
):
    with app.app_context():
        result = (
            request_email_auth_otp(
                "User@Example.com"
            )
        )

        assert (
            result["email"]
            == "user@example.com"
        )

        assert (
            result["dev_otp"]
            == "654321"
        )

        verification = (
            verify_email_otp(
                "user@example.com",
                "654321",
            )
        )

        assert (
            verification["verified"]
            is True
        )


def test_smtp_delivery_receives_real_otp(
    app,
    monkeypatch,
):
    captured = {}

    def fake_send(
        *,
        recipient,
        otp,
        expires_in,
    ):
        captured["recipient"] = (
            recipient
        )
        captured["otp"] = otp
        captured["expires_in"] = (
            expires_in
        )

        return True

    monkeypatch.setattr(
        (
            "app.services.email_auth_service."
            "send_auth_otp_email"
        ),
        fake_send,
    )

    with app.app_context():
        app.config[
            "SMTP_HOST"
        ] = "smtp.example.com"

        result = (
            request_email_auth_otp(
                "SMTP@Example.com"
            )
        )

        assert (
            captured["recipient"]
            == "smtp@example.com"
        )

        assert (
            captured["otp"]
            == "654321"
        )

        assert (
            captured["expires_in"]
            == 30
        )

        assert (
            result["email"]
            == "smtp@example.com"
        )


def test_delivery_failure_invalidates_otp(
    app,
    monkeypatch,
):
    def broken_send(
        **kwargs,
    ):
        raise EmailDeliveryError(
            "Delivery failed."
        )

    monkeypatch.setattr(
        (
            "app.services.email_auth_service."
            "send_auth_otp_email"
        ),
        broken_send,
    )

    with app.app_context():
        app.config[
            "SMTP_HOST"
        ] = "smtp.example.com"

        with pytest.raises(
            EmailDeliveryError
        ):
            request_email_auth_otp(
                "failure@example.com"
            )

        with pytest.raises(
            OtpExpired
        ):
            verify_email_otp(
                "failure@example.com",
                "654321",
            )


def test_production_requires_email_delivery(
    app,
):
    with app.app_context():
        app.config[
            "EXPOSE_DEV_OTP"
        ] = False

        app.config[
            "SMTP_HOST"
        ] = ""

        with pytest.raises(
            EmailConfigurationError
        ):
            request_email_auth_otp(
                "production@example.com"
            )

        with pytest.raises(
            OtpExpired
        ):
            verify_email_otp(
                "production@example.com",
                "654321",
            )
