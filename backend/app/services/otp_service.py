import hashlib
import hmac
import re
import secrets

from flask import current_app

from app.extensions import redis_store


class OtpError(Exception):
    """Base OTP service error."""


class InvalidPhoneNumber(OtpError):
    """Raised when a phone number is invalid."""


class OtpCooldownActive(OtpError):
    def __init__(self, retry_after: int):
        self.retry_after = max(
            int(retry_after),
            1,
        )

        super().__init__(
            "Please wait before requesting another OTP."
        )


class OtpRateLimited(OtpError):
    def __init__(self, retry_after: int):
        self.retry_after = max(
            int(retry_after),
            1,
        )

        super().__init__(
            "Too many OTP requests."
        )


class InvalidOtp(OtpError):
    """Raised when the supplied OTP is incorrect."""


class OtpExpired(OtpError):
    """Raised when the OTP no longer exists."""


class OtpAttemptsExceeded(OtpError):
    """Raised when too many incorrect OTPs were submitted."""


_REQUEST_GATE_SCRIPT = """
local cooldown_key = KEYS[1]
local rate_key = KEYS[2]

local cooldown_seconds = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])

if redis.call("EXISTS", cooldown_key) == 1 then
    local ttl = redis.call("TTL", cooldown_key)
    return {0, "cooldown", ttl}
end

local count = redis.call("INCR", rate_key)

if count == 1 then
    redis.call(
        "EXPIRE",
        rate_key,
        window_seconds
    )
end

if count > max_requests then
    local ttl = redis.call("TTL", rate_key)
    return {0, "rate_limited", ttl}
end

redis.call(
    "SET",
    cooldown_key,
    "1",
    "EX",
    cooldown_seconds
)

return {
    1,
    "allowed",
    cooldown_seconds
}
"""


_VERIFY_SCRIPT = """
local code_key = KEYS[1]
local attempts_key = KEYS[2]

local supplied_hash = ARGV[1]
local max_attempts = tonumber(ARGV[2])

local stored_hash = redis.call(
    "GET",
    code_key
)

if not stored_hash then
    return {0, "expired", 0}
end

local attempts = tonumber(
    redis.call(
        "GET",
        attempts_key
    ) or "0"
)

if attempts >= max_attempts then
    redis.call(
        "DEL",
        code_key,
        attempts_key
    )

    return {
        0,
        "attempts_exceeded",
        0
    }
end

if stored_hash == supplied_hash then
    redis.call(
        "DEL",
        code_key,
        attempts_key
    )

    return {
        1,
        "verified",
        0
    }
end

attempts = redis.call(
    "INCR",
    attempts_key
)

if attempts == 1 then
    local ttl = redis.call(
        "TTL",
        code_key
    )

    if ttl > 0 then
        redis.call(
            "EXPIRE",
            attempts_key,
            ttl
        )
    end
end

if attempts >= max_attempts then
    redis.call(
        "DEL",
        code_key,
        attempts_key
    )

    return {
        0,
        "attempts_exceeded",
        0
    }
end

return {
    0,
    "invalid",
    max_attempts - attempts
}
"""


def normalize_phone(
    phone: str,
) -> str:
    raw = str(
        phone or ""
    ).strip()

    cleaned = re.sub(
        r"[\s\-\(\)]",
        "",
        raw,
    )

    # Convenient Indian mobile-number input.
    if re.fullmatch(
        r"[6-9]\d{9}",
        cleaned,
    ):
        cleaned = "+91" + cleaned

    if not re.fullmatch(
        r"\+[1-9]\d{7,14}",
        cleaned,
    ):
        raise InvalidPhoneNumber(
            "Enter a valid mobile number."
        )

    return cleaned


def _identifier_digest(
    phone: str,
) -> str:
    return hashlib.sha256(
        phone.encode("utf-8")
    ).hexdigest()


def _redis_key(
    purpose: str,
    phone: str,
) -> str:
    prefix = current_app.config[
        "OTP_KEY_PREFIX"
    ]

    identifier = _identifier_digest(
        phone
    )

    return (
        f"{prefix}:{purpose}:{identifier}"
    )


def _hash_otp(
    phone: str,
    otp: str,
) -> str:
    secret = current_app.config[
        "OTP_HASH_SECRET"
    ]

    message = (
        f"{phone}:{otp}"
    ).encode("utf-8")

    return hmac.new(
        str(secret).encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _generate_otp() -> str:
    configured_code = str(
        current_app.config.get(
            "DEV_OTP_CODE",
            "",
        )
    ).strip()

    if (
        current_app.config.get(
            "EXPOSE_DEV_OTP",
            False,
        )
        and configured_code
    ):
        return configured_code

    length = int(
        current_app.config[
            "OTP_LENGTH"
        ]
    )

    if length < 4 or length > 8:
        raise RuntimeError(
            "OTP_LENGTH must be between 4 and 8."
        )

    upper_bound = 10 ** length

    return str(
        secrets.randbelow(
            upper_bound
        )
    ).zfill(
        length
    )


def request_otp(
    phone: str,
) -> dict:
    normalized_phone = normalize_phone(
        phone
    )

    redis = redis_store.get_client()

    cooldown_key = _redis_key(
        "cooldown",
        normalized_phone,
    )

    rate_key = _redis_key(
        "requests",
        normalized_phone,
    )

    result = redis.eval(
        _REQUEST_GATE_SCRIPT,
        2,
        cooldown_key,
        rate_key,
        int(
            current_app.config[
                "OTP_RESEND_COOLDOWN_SECONDS"
            ]
        ),
        int(
            current_app.config[
                "OTP_REQUEST_WINDOW_SECONDS"
            ]
        ),
        int(
            current_app.config[
                "OTP_MAX_REQUESTS_PER_WINDOW"
            ]
        ),
    )

    allowed = int(
        result[0]
    )

    status = str(
        result[1]
    )

    retry_after = int(
        result[2]
    )

    if not allowed:
        if status == "cooldown":
            raise OtpCooldownActive(
                retry_after
            )

        if status == "rate_limited":
            raise OtpRateLimited(
                retry_after
            )

        raise OtpError(
            "OTP request could not be processed."
        )

    otp = _generate_otp()

    code_key = _redis_key(
        "code",
        normalized_phone,
    )

    attempts_key = _redis_key(
        "attempts",
        normalized_phone,
    )

    redis.delete(
        attempts_key
    )

    redis.set(
        code_key,
        _hash_otp(
            normalized_phone,
            otp,
        ),
        ex=int(
            current_app.config[
                "OTP_TTL_SECONDS"
            ]
        ),
    )

    response = {
        "phone": normalized_phone,
        "expires_in": int(
            current_app.config[
                "OTP_TTL_SECONDS"
            ]
        ),
        "resend_after": int(
            current_app.config[
                "OTP_RESEND_COOLDOWN_SECONDS"
            ]
        ),
    }

    if current_app.config.get(
        "EXPOSE_DEV_OTP",
        False,
    ):
        response["dev_otp"] = otp

    return response


def verify_otp(
    phone: str,
    otp: str,
) -> dict:
    normalized_phone = normalize_phone(
        phone
    )

    supplied_otp = str(
        otp or ""
    ).strip()

    if not supplied_otp.isdigit():
        raise InvalidOtp(
            "OTP is invalid."
        )

    redis = redis_store.get_client()

    code_key = _redis_key(
        "code",
        normalized_phone,
    )

    attempts_key = _redis_key(
        "attempts",
        normalized_phone,
    )

    result = redis.eval(
        _VERIFY_SCRIPT,
        2,
        code_key,
        attempts_key,
        _hash_otp(
            normalized_phone,
            supplied_otp,
        ),
        int(
            current_app.config[
                "OTP_MAX_ATTEMPTS"
            ]
        ),
    )

    verified = int(
        result[0]
    )

    status = str(
        result[1]
    )

    remaining_attempts = int(
        result[2]
    )

    if verified:
        return {
            "verified": True,
            "phone": normalized_phone,
        }

    if status == "expired":
        raise OtpExpired(
            "OTP has expired or was already used."
        )

    if status == "attempts_exceeded":
        raise OtpAttemptsExceeded(
            "Too many incorrect OTP attempts."
        )

    if status == "invalid":
        error = InvalidOtp(
            "OTP is incorrect."
        )

        error.remaining_attempts = (
            remaining_attempts
        )

        raise error

    raise OtpError(
        "OTP verification could not be processed."
    )

