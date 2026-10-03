"""Email authentication delivery orchestration."""

from flask import current_app

from app.services.email_otp_service import (
    create_email_otp_challenge,
    invalidate_email_otp,
)
from app.services.email_sender import (
    EmailConfigurationError,
    EmailSenderError,
    send_auth_otp_email,
)


def request_email_auth_otp(
    email: str,
) -> dict:
    response, otp = (
        create_email_otp_challenge(
            email
        )
    )

    smtp_host = str(
        current_app.config.get(
            "SMTP_HOST",
            "",
        )
        or ""
    ).strip()

    # Local development may operate without SMTP
    # only when the dev OTP is explicitly exposed.
    if not smtp_host:
        if current_app.config.get(
            "EXPOSE_DEV_OTP",
            False,
        ):
            return response

        invalidate_email_otp(
            response["email"],
            clear_cooldown=True,
        )

        raise EmailConfigurationError(
            (
                "Email authentication "
                "delivery is not configured."
            )
        )

    try:
        send_auth_otp_email(
            recipient=response[
                "email"
            ],
            otp=otp,
            expires_in=response[
                "expires_in"
            ],
        )

    except EmailSenderError:
        # Never leave an undelivered OTP valid.
        invalidate_email_otp(
            response["email"],
            clear_cooldown=True,
        )

        raise

    return response
