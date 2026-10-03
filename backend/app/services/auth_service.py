from datetime import datetime, timedelta, timezone

from flask import current_app
from pymongo.errors import DuplicateKeyError

from app.repositories.auth_repository import (
    create_identity,
    get_identity_by_phone,
)
from app.repositories.session_repository import (
    claim_session_for_rotation,
    create_session,
    get_session_by_refresh_hash,
    revoke_all_user_sessions,
    revoke_family,
    revoke_session_by_refresh_hash,
)
from app.repositories.user_repository import (
    create_user,
    delete_user,
    get_user_by_id,
    update_last_login,
)
from app.security.tokens import (
    create_access_token,
    generate_refresh_token,
    generate_session_id,
    generate_token_family_id,
    hash_refresh_token,
)
from app.services.otp_service import verify_otp


class AuthenticationError(Exception):
    """Base authentication service error."""


class InvalidRefreshToken(AuthenticationError):
    """Raised when a refresh token cannot be used."""


class RefreshTokenReuseDetected(AuthenticationError):
    """Raised when a rotated refresh token is reused."""


class AccountUnavailable(AuthenticationError):
    """Raised when an account cannot authenticate."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _refresh_expiry() -> datetime:
    return utc_now() + timedelta(
        days=current_app.config[
            "JWT_REFRESH_TOKEN_DAYS"
        ]
    )


def _build_token_response(
    *,
    user_id,
    session_id,
    refresh_token,
):
    access_token = create_access_token(
        str(user_id),
        session_id=session_id,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": (
            current_app.config[
                "JWT_ACCESS_TOKEN_MINUTES"
            ]
            * 60
        ),
        "session_id": session_id,
    }


def issue_session(
    user_id,
    *,
    metadata=None,
):
    session_id = generate_session_id()
    family_id = generate_token_family_id()

    refresh_token = generate_refresh_token()

    create_session(
        user_id=user_id,
        session_id=session_id,
        family_id=family_id,
        refresh_token_hash=hash_refresh_token(
            refresh_token
        ),
        expires_at=_refresh_expiry(),
        metadata=metadata,
    )

    return _build_token_response(
        user_id=user_id,
        session_id=session_id,
        refresh_token=refresh_token,
    )


def rotate_refresh_token(
    refresh_token: str,
    *,
    metadata=None,
):
    if not refresh_token:
        raise InvalidRefreshToken(
            "Refresh token is required."
        )

    token_hash = hash_refresh_token(
        refresh_token
    )

    existing = get_session_by_refresh_hash(
        token_hash
    )

    if existing is None:
        raise InvalidRefreshToken(
            "Refresh token is invalid."
        )

    if existing.get(
        "revoked_at"
    ) is not None:
        if (
            existing.get(
                "revoke_reason"
            )
            == "rotated"
            or existing.get(
                "replaced_by_session_id"
            )
        ):
            revoke_family(
                existing["family_id"],
                reason="refresh_token_reuse",
            )

            raise RefreshTokenReuseDetected(
                "Refresh token reuse detected."
            )

        raise InvalidRefreshToken(
            "Refresh token has been revoked."
        )

    new_session_id = generate_session_id()

    previous_session = (
        claim_session_for_rotation(
            refresh_token_hash=token_hash,
            replacement_session_id=(
                new_session_id
            ),
        )
    )

    if previous_session is None:
        latest = get_session_by_refresh_hash(
            token_hash
        )

        if latest and (
            latest.get(
                "revoke_reason"
            )
            == "rotated"
            or latest.get(
                "replaced_by_session_id"
            )
        ):
            revoke_family(
                latest["family_id"],
                reason="refresh_token_reuse",
            )

            raise RefreshTokenReuseDetected(
                "Refresh token reuse detected."
            )

        raise InvalidRefreshToken(
            "Refresh token is expired or unavailable."
        )

    new_refresh_token = (
        generate_refresh_token()
    )

    create_session(
        user_id=previous_session[
            "user_id"
        ],
        session_id=new_session_id,
        family_id=previous_session[
            "family_id"
        ],
        refresh_token_hash=(
            hash_refresh_token(
                new_refresh_token
            )
        ),
        expires_at=_refresh_expiry(),
        parent_session_id=(
            previous_session[
                "session_id"
            ]
        ),
        metadata=metadata,
    )

    return _build_token_response(
        user_id=previous_session[
            "user_id"
        ],
        session_id=new_session_id,
        refresh_token=new_refresh_token,
    )


def logout_refresh_token(
    refresh_token: str,
):
    if not refresh_token:
        return False

    return revoke_session_by_refresh_hash(
        hash_refresh_token(
            refresh_token
        ),
        reason="logout",
    )


def logout_all_sessions(
    user_id,
):
    return revoke_all_user_sessions(
        user_id,
        reason="logout_all",
    )


def authenticate_phone_otp(
    phone: str,
    otp: str,
    *,
    metadata=None,
):
    verification = verify_otp(
        phone,
        otp,
    )

    normalized_phone = verification[
        "phone"
    ]

    identity = get_identity_by_phone(
        normalized_phone
    )

    is_new_user = False

    if identity is not None:
        user = get_user_by_id(
            identity["user_id"]
        )

    else:
        user = create_user()

        try:
            identity = create_identity(
                user_id=user["_id"],
                provider="phone",
                provider_subject=(
                    normalized_phone
                ),
                phone_normalized=(
                    normalized_phone
                ),
                verified=True,
            )

            is_new_user = True

        except DuplicateKeyError:
            # Another request created the identity first.
            # Roll back the unused user and load the winner.
            delete_user(
                user["_id"]
            )

            identity = get_identity_by_phone(
                normalized_phone
            )

            if identity is None:
                raise AuthenticationError(
                    "Authentication identity could not be created."
                )

            user = get_user_by_id(
                identity["user_id"]
            )

    if user is None:
        raise AuthenticationError(
            "Authentication account is unavailable."
        )

    account_status = user.get(
        "account_status",
        "active",
    )

    if account_status in {
        "suspended",
        "banned",
        "deleted",
    }:
        raise AccountUnavailable(
            "This account is unavailable."
        )

    update_last_login(
        user["_id"]
    )

    tokens = issue_session(
        user["_id"],
        metadata=metadata,
    )

    return {
        "user": user,
        "phone": normalized_phone,
        "is_new_user": is_new_user,
        "tokens": tokens,
    }
