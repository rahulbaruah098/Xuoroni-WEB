from functools import wraps

from flask import g, request

from app.errors import error_response
from app.repositories.session_repository import (
    get_session_by_id,
)
from app.repositories.user_repository import (
    get_user_by_id,
)
from app.security.tokens import (
    InvalidAccessToken,
    decode_access_token,
)


def _extract_bearer_token():
    header = str(
        request.headers.get(
            "Authorization",
            "",
        )
    ).strip()

    parts = header.split()

    if (
        len(parts) != 2
        or parts[0].lower()
        != "bearer"
    ):
        return None

    return parts[1]


def authenticate_access_token(
    token: str,
):
    payload = decode_access_token(
        token
    )

    session = get_session_by_id(
        payload["sid"]
    )

    if session is None:
        raise InvalidAccessToken(
            "Authentication session does not exist."
        )

    if session.get(
        "revoked_at"
    ) is not None:
        raise InvalidAccessToken(
            "Authentication session has been revoked."
        )

    if (
        str(
            session.get(
                "user_id"
            )
        )
        != payload["sub"]
    ):
        raise InvalidAccessToken(
            "Authentication session is invalid."
        )

    user = get_user_by_id(
        payload["sub"]
    )

    if user is None:
        raise InvalidAccessToken(
            "User account does not exist."
        )

    if user.get(
        "account_status"
    ) in {
        "suspended",
        "banned",
        "deleted",
    }:
        raise InvalidAccessToken(
            "User account is unavailable."
        )

    return {
        "payload": payload,
        "session": session,
        "user": user,
    }


def auth_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        token = _extract_bearer_token()

        if not token:
            return error_response(
                "AUTHENTICATION_REQUIRED",
                "A valid access token is required.",
                401,
            )

        try:
            authentication = (
                authenticate_access_token(
                    token
                )
            )

        except InvalidAccessToken:
            return error_response(
                "INVALID_ACCESS_TOKEN",
                "The access token is invalid or expired.",
                401,
            )

        g.current_user = (
            authentication["user"]
        )

        g.auth_session = (
            authentication["session"]
        )

        g.access_token_payload = (
            authentication["payload"]
        )

        return fn(
            *args,
            **kwargs,
        )

    return wrapped
