from flask import (
    Blueprint,
    g,
    jsonify,
    request,
)

from app.errors import error_response
from app.repositories.auth_repository import (
    get_identities_for_user,
)
from app.security.authentication import (
    auth_required,
)
from app.services.auth_service import (
    AccountUnavailable,
    AuthenticationError,
    GoogleAccountConflict,
    InvalidRefreshToken,
    RefreshTokenReuseDetected,
    authenticate_email_otp,
    authenticate_google_id_token,
    authenticate_phone_otp,
    logout_refresh_token,
    rotate_refresh_token,
)
from app.services.email_auth_service import (
    request_email_auth_otp,
)
from app.services.email_otp_service import (
    InvalidEmailAddress,
)
from app.services.email_sender import (
    EmailConfigurationError,
    EmailDeliveryError,
)
from app.services.google_token_service import (
    GoogleConfigurationError,
    GoogleEmailNotVerified,
    InvalidGoogleToken,
)
from app.services.otp_service import (
    InvalidOtp,
    InvalidPhoneNumber,
    OtpAttemptsExceeded,
    OtpCooldownActive,
    OtpExpired,
    OtpRateLimited,
    request_otp,
)


auth_bp = Blueprint(
    "auth_v1",
    __name__,
)


def _body():
    return (
        request.get_json(
            silent=True
        )
        or {}
    )


def _client_metadata(data):
    metadata = {}

    for key in (
        "device_id",
        "platform",
        "app_version",
        "device_name",
    ):
        value = data.get(
            key
        )

        if value is not None:
            metadata[key] = str(
                value
            )[:200]

    return metadata


def _serialize_user(
    user,
    *,
    phone=None,
    email=None,
):
    payload = {
        "id": str(
            user["_id"]
        ),
        "account_status": user.get(
            "account_status"
        ),
        "onboarding_status": user.get(
            "onboarding_status"
        ),
    }

    if phone:
        payload["phone"] = phone

    if email:
        payload["email"] = email

    return payload

@auth_bp.post("/request-otp")
def request_mobile_otp():
    data = _body()

    try:
        result = request_otp(
            data.get(
                "phone"
            )
        )

    except InvalidPhoneNumber as exc:
        return error_response(
            "INVALID_PHONE_NUMBER",
            str(exc),
            400,
        )

    except OtpCooldownActive as exc:
        response, status = (
            error_response(
                "OTP_COOLDOWN_ACTIVE",
                str(exc),
                429,
                details={
                    "retry_after": (
                        exc.retry_after
                    )
                },
            )
        )

        response.headers[
            "Retry-After"
        ] = str(
            exc.retry_after
        )

        return response, status

    except OtpRateLimited as exc:
        response, status = (
            error_response(
                "OTP_RATE_LIMITED",
                str(exc),
                429,
                details={
                    "retry_after": (
                        exc.retry_after
                    )
                },
            )
        )

        response.headers[
            "Retry-After"
        ] = str(
            exc.retry_after
        )

        return response, status

    return jsonify(
        result
    ), 200


@auth_bp.post("/verify-otp")
def verify_mobile_otp():
    data = _body()

    try:
        result = (
            authenticate_phone_otp(
                data.get(
                    "phone"
                ),
                data.get(
                    "otp"
                ),
                metadata=(
                    _client_metadata(
                        data
                    )
                ),
            )
        )

    except InvalidPhoneNumber as exc:
        return error_response(
            "INVALID_PHONE_NUMBER",
            str(exc),
            400,
        )

    except InvalidOtp as exc:
        details = None

        remaining = getattr(
            exc,
            "remaining_attempts",
            None,
        )

        if remaining is not None:
            details = {
                "remaining_attempts": (
                    remaining
                )
            }

        return error_response(
            "INVALID_OTP",
            str(exc),
            401,
            details=details,
        )

    except OtpExpired as exc:
        return error_response(
            "OTP_EXPIRED",
            str(exc),
            401,
        )

    except OtpAttemptsExceeded as exc:
        return error_response(
            "OTP_ATTEMPTS_EXCEEDED",
            str(exc),
            429,
        )

    except AccountUnavailable as exc:
        return error_response(
            "ACCOUNT_UNAVAILABLE",
            str(exc),
            403,
        )

    except AuthenticationError:
        return error_response(
            "AUTHENTICATION_FAILED",
            "Authentication could not be completed.",
            500,
        )

    tokens = result[
        "tokens"
    ]

    payload = {
        "user": _serialize_user(
            result["user"],
            phone=result[
                "phone"
            ],
        ),
        "is_new_user": result[
            "is_new_user"
        ],
        **tokens,
    }

    return jsonify(
        payload
    ), 200


@auth_bp.post("/request-email-otp")
def request_email_otp_route():
    data = _body()

    try:
        result = request_email_auth_otp(
            data.get(
                "email"
            )
        )

    except InvalidEmailAddress as exc:
        return error_response(
            "INVALID_EMAIL_ADDRESS",
            str(exc),
            400,
        )

    except OtpCooldownActive as exc:
        response, status = error_response(
            "OTP_COOLDOWN_ACTIVE",
            str(exc),
            429,
            details={
                "retry_after": (
                    exc.retry_after
                )
            },
        )

        response.headers[
            "Retry-After"
        ] = str(
            exc.retry_after
        )

        return response, status

    except OtpRateLimited as exc:
        response, status = error_response(
            "OTP_RATE_LIMITED",
            str(exc),
            429,
            details={
                "retry_after": (
                    exc.retry_after
                )
            },
        )

        response.headers[
            "Retry-After"
        ] = str(
            exc.retry_after
        )

        return response, status

    except EmailConfigurationError:
        return error_response(
            "EMAIL_DELIVERY_UNAVAILABLE",
            (
                "Email authentication "
                "is not configured."
            ),
            503,
        )

    except EmailDeliveryError:
        return error_response(
            "EMAIL_DELIVERY_FAILED",
            (
                "The verification email "
                "could not be delivered."
            ),
            503,
        )

    return jsonify(
        result
    ), 200


@auth_bp.post("/verify-email-otp")
def verify_email_otp_route():
    data = _body()

    try:
        result = authenticate_email_otp(
            data.get(
                "email"
            ),
            data.get(
                "otp"
            ),
            metadata=(
                _client_metadata(
                    data
                )
            ),
        )

    except InvalidEmailAddress as exc:
        return error_response(
            "INVALID_EMAIL_ADDRESS",
            str(exc),
            400,
        )

    except InvalidOtp as exc:
        details = None

        remaining = getattr(
            exc,
            "remaining_attempts",
            None,
        )

        if remaining is not None:
            details = {
                "remaining_attempts": (
                    remaining
                )
            }

        return error_response(
            "INVALID_OTP",
            str(exc),
            401,
            details=details,
        )

    except OtpExpired as exc:
        return error_response(
            "OTP_EXPIRED",
            str(exc),
            401,
        )

    except OtpAttemptsExceeded as exc:
        return error_response(
            "OTP_ATTEMPTS_EXCEEDED",
            str(exc),
            429,
        )

    except AccountUnavailable as exc:
        return error_response(
            "ACCOUNT_UNAVAILABLE",
            str(exc),
            403,
        )

    except AuthenticationError:
        return error_response(
            "AUTHENTICATION_FAILED",
            (
                "Authentication could "
                "not be completed."
            ),
            500,
        )

    tokens = result[
        "tokens"
    ]

    payload = {
        "user": _serialize_user(
            result["user"],
            email=result[
                "email"
            ],
        ),
        "is_new_user": result[
            "is_new_user"
        ],
        **tokens,
    }

    return jsonify(
        payload
    ), 200


@auth_bp.post("/google")
def google_login():
    data = _body()

    token = (
        data.get(
            "id_token"
        )
        or data.get(
            "credential"
        )
    )

    try:
        result = (
            authenticate_google_id_token(
                token,
                metadata=(
                    _client_metadata(
                        data
                    )
                ),
            )
        )

    except GoogleConfigurationError:
        return error_response(
            "GOOGLE_AUTH_UNAVAILABLE",
            (
                "Google authentication "
                "is not configured."
            ),
            503,
        )

    except InvalidGoogleToken as exc:
        return error_response(
            "INVALID_GOOGLE_TOKEN",
            str(exc),
            401,
        )

    except GoogleEmailNotVerified as exc:
        return error_response(
            "GOOGLE_EMAIL_NOT_VERIFIED",
            str(exc),
            401,
        )

    except GoogleAccountConflict as exc:
        return error_response(
            "GOOGLE_ACCOUNT_CONFLICT",
            str(exc),
            409,
        )

    except AccountUnavailable as exc:
        return error_response(
            "ACCOUNT_UNAVAILABLE",
            str(exc),
            403,
        )

    except AuthenticationError:
        return error_response(
            "AUTHENTICATION_FAILED",
            (
                "Google authentication "
                "could not be completed."
            ),
            500,
        )

    tokens = result[
        "tokens"
    ]

    payload = {
        "user": _serialize_user(
            result["user"],
            email=result[
                "email"
            ],
        ),
        "is_new_user": result[
            "is_new_user"
        ],
        "linked_existing_account": (
            result[
                "linked_existing_account"
            ]
        ),
        **tokens,
    }

    return jsonify(
        payload
    ), 200


@auth_bp.post("/refresh")
def refresh_access_token():
    data = _body()

    try:
        tokens = (
            rotate_refresh_token(
                data.get(
                    "refresh_token"
                ),
                metadata=(
                    _client_metadata(
                        data
                    )
                ),
            )
        )

    except RefreshTokenReuseDetected:
        return error_response(
            "REFRESH_TOKEN_REUSE",
            "The session is no longer valid.",
            401,
        )

    except InvalidRefreshToken:
        return error_response(
            "INVALID_REFRESH_TOKEN",
            "The refresh token is invalid or expired.",
            401,
        )

    return jsonify(
        tokens
    ), 200


@auth_bp.post("/logout")
def logout():
    data = _body()

    refresh_token = data.get(
        "refresh_token"
    )

    if refresh_token:
        logout_refresh_token(
            refresh_token
        )

    # Logout is intentionally idempotent.
    return jsonify(
        {
            "message": "Signed out.",
        }
    ), 200


@auth_bp.get("/me")
@auth_required
def me():
    user = g.current_user

    identities = (
        get_identities_for_user(
            user["_id"]
        )
    )

    phone = None
    email = None

    for identity in identities:
        provider = identity.get(
            "provider"
        )

        if (
            provider == "phone"
            and phone is None
        ):
            phone = identity.get(
                "phone_normalized"
            )

        if (
            email is None
            and identity.get(
                "verified"
            )
            and identity.get(
                "email_normalized"
            )
        ):
            email = identity.get(
                "email_normalized"
            )

    return jsonify(
        {
            "user": _serialize_user(
                user,
                phone=phone,
                email=email,
            )
        }
    ), 200
