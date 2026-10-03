import time

import pytest

from app import create_app
from app.extensions import redis_store
from app.services.otp_service import (
    InvalidOtp,
    InvalidPhoneNumber,
    OtpAttemptsExceeded,
    OtpCooldownActive,
    OtpExpired,
    OtpRateLimited,
    normalize_phone,
    request_otp,
    verify_otp,
)


TEST_PREFIX = "xuoroni:test:otp"


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "EXPOSE_DEV_OTP": True,
            "DEV_OTP_CODE": "654321",
            "OTP_TTL_SECONDS": 60,
            "OTP_RESEND_COOLDOWN_SECONDS": 1,
            "OTP_MAX_ATTEMPTS": 3,
            "OTP_REQUEST_WINDOW_SECONDS": 60,
            "OTP_MAX_REQUESTS_PER_WINDOW": 2,
            "OTP_KEY_PREFIX": TEST_PREFIX,
            "OTP_HASH_SECRET": (
                "xuoroni-test-otp-secret-at-least-32-bytes"
            ),
        }
    )

    with application.app_context():
        redis = redis_store.get_client()

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

        keys = list(
            redis.scan_iter(
                f"{TEST_PREFIX}:*"
            )
        )

        if keys:
            redis.delete(
                *keys
            )


def test_normalizes_indian_mobile_number(
    app,
):
    with app.app_context():
        assert (
            normalize_phone(
                "9876543210"
            )
            == "+919876543210"
        )

        assert (
            normalize_phone(
                "+91 98765 43210"
            )
            == "+919876543210"
        )


def test_invalid_phone_is_rejected(
    app,
):
    with app.app_context():
        with pytest.raises(
            InvalidPhoneNumber
        ):
            normalize_phone(
                "12345"
            )


def test_request_otp_returns_dev_code(
    app,
):
    with app.app_context():
        response = request_otp(
            "9876543210"
        )

        assert (
            response["phone"]
            == "+919876543210"
        )

        assert (
            response["dev_otp"]
            == "654321"
        )

        assert (
            response["expires_in"]
            == 60
        )


def test_resend_cooldown_is_enforced(
    app,
):
    with app.app_context():
        request_otp(
            "9876543211"
        )

        with pytest.raises(
            OtpCooldownActive
        ):
            request_otp(
                "9876543211"
            )


def test_correct_otp_is_single_use(
    app,
):
    with app.app_context():
        request_otp(
            "9876543212"
        )

        result = verify_otp(
            "9876543212",
            "654321",
        )

        assert (
            result["verified"]
            is True
        )

        with pytest.raises(
            OtpExpired
        ):
            verify_otp(
                "9876543212",
                "654321",
            )


def test_wrong_otp_tracks_attempts(
    app,
):
    with app.app_context():
        request_otp(
            "9876543213"
        )

        with pytest.raises(
            InvalidOtp
        ) as error:
            verify_otp(
                "9876543213",
                "111111",
            )

        assert (
            error.value.remaining_attempts
            == 2
        )

        result = verify_otp(
            "9876543213",
            "654321",
        )

        assert (
            result["verified"]
            is True
        )


def test_too_many_wrong_attempts_blocks_otp(
    app,
):
    with app.app_context():
        request_otp(
            "9876543214"
        )

        with pytest.raises(
            InvalidOtp
        ):
            verify_otp(
                "9876543214",
                "111111",
            )

        with pytest.raises(
            InvalidOtp
        ):
            verify_otp(
                "9876543214",
                "222222",
            )

        with pytest.raises(
            OtpAttemptsExceeded
        ):
            verify_otp(
                "9876543214",
                "333333",
            )

        with pytest.raises(
            OtpExpired
        ):
            verify_otp(
                "9876543214",
                "654321",
            )


def test_request_rate_limit_is_enforced(
    app,
):
    with app.app_context():
        request_otp(
            "9876543215"
        )

        time.sleep(
            1.1
        )

        request_otp(
            "9876543215"
        )

        time.sleep(
            1.1
        )

        with pytest.raises(
            OtpRateLimited
        ):
            request_otp(
                "9876543215"
            )
