import pytest

from app import create_app
from app.extensions import (
    redis_store,
)
from app.services.email_otp_service import (
    InvalidEmailAddress,
    normalize_email,
    request_email_otp,
    verify_email_otp,
)
from app.services.otp_service import (
    InvalidOtp,
    OtpAttemptsExceeded,
    OtpCooldownActive,
    OtpExpired,
    OtpRateLimited,
)


TEST_PREFIX = (
    "xuoroni:test:email-otp"
)


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "EXPOSE_DEV_OTP": True,
            "DEV_EMAIL_OTP_CODE": (
                "654321"
            ),
            "EMAIL_OTP_KEY_PREFIX": (
                TEST_PREFIX
            ),
            "OTP_RESEND_COOLDOWN_SECONDS": 1,
            "OTP_REQUEST_WINDOW_SECONDS": 60,
            "OTP_MAX_REQUESTS_PER_WINDOW": 3,
            "OTP_MAX_ATTEMPTS": 3,
            "OTP_TTL_SECONDS": 30,
        }
    )

    with application.app_context():
        redis = (
            redis_store.get_client()
        )

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


def test_normalizes_email_address(
    app,
):
    with app.app_context():
        assert (
            normalize_email(
                "  Test.User@Example.COM  "
            )
            == "test.user@example.com"
        )


def test_invalid_email_is_rejected(
    app,
):
    with app.app_context():
        with pytest.raises(
            InvalidEmailAddress
        ):
            normalize_email(
                "not-an-email"
            )


def test_request_email_otp_returns_dev_code(
    app,
):
    with app.app_context():
        result = (
            request_email_otp(
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

        assert (
            result["expires_in"]
            == 30
        )


def test_email_resend_cooldown_is_enforced(
    app,
):
    with app.app_context():
        request_email_otp(
            "cooldown@example.com"
        )

        with pytest.raises(
            OtpCooldownActive
        ):
            request_email_otp(
                "cooldown@example.com"
            )


def test_correct_email_otp_is_single_use(
    app,
):
    with app.app_context():
        request_email_otp(
            "single@example.com"
        )

        result = verify_email_otp(
            "SINGLE@example.com",
            "654321",
        )

        assert (
            result["verified"]
            is True
        )

        assert (
            result["email"]
            == "single@example.com"
        )

        with pytest.raises(
            OtpExpired
        ):
            verify_email_otp(
                "single@example.com",
                "654321",
            )


def test_wrong_email_otp_tracks_attempts(
    app,
):
    with app.app_context():
        request_email_otp(
            "wrong@example.com"
        )

        with pytest.raises(
            InvalidOtp
        ) as error:
            verify_email_otp(
                "wrong@example.com",
                "111111",
            )

        assert (
            error.value.remaining_attempts
            == 2
        )


def test_email_attempt_limit_is_enforced(
    app,
):
    with app.app_context():
        request_email_otp(
            "attempts@example.com"
        )

        with pytest.raises(
            InvalidOtp
        ):
            verify_email_otp(
                "attempts@example.com",
                "111111",
            )

        with pytest.raises(
            InvalidOtp
        ):
            verify_email_otp(
                "attempts@example.com",
                "222222",
            )

        with pytest.raises(
            OtpAttemptsExceeded
        ):
            verify_email_otp(
                "attempts@example.com",
                "333333",
            )


def test_email_request_rate_limit_is_enforced(
    app,
):
    with app.app_context():
        redis = (
            redis_store.get_client()
        )

        email = (
            "rate@example.com"
        )

        # Remove only the cooldown between
        # requests while preserving the
        # rolling request counter.
        for _ in range(3):
            request_email_otp(
                email
            )

            normalized = (
                normalize_email(
                    email
                )
            )

            from app.services.email_otp_service import (
                _redis_key,
            )

            redis.delete(
                _redis_key(
                    "cooldown",
                    normalized,
                )
            )

        with pytest.raises(
            OtpRateLimited
        ):
            request_email_otp(
                email
            )
