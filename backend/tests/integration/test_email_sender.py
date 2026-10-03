import smtplib

import pytest

from app import create_app
from app.services.email_sender import (
    EmailConfigurationError,
    EmailDeliveryError,
    send_auth_otp_email,
    send_email,
)


class FakeSmtp:
    instances = []

    def __init__(
        self,
        host,
        port,
        timeout=None,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout

        self.ehlo_calls = 0
        self.starttls_calls = 0
        self.login_calls = []
        self.messages = []

        type(self).instances.append(
            self
        )

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def ehlo(
        self,
    ):
        self.ehlo_calls += 1

    def starttls(
        self,
        *,
        context,
    ):
        assert context is not None

        self.starttls_calls += 1

    def login(
        self,
        username,
        password,
    ):
        self.login_calls.append(
            (
                username,
                password,
            )
        )

    def send_message(
        self,
        message,
    ):
        self.messages.append(
            message
        )


@pytest.fixture()
def app():
    return create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "SMTP_HOST": (
                "smtp.example.com"
            ),
            "SMTP_PORT": 587,
            "SMTP_USERNAME": (
                "xuoroni@example.com"
            ),
            "SMTP_PASSWORD": (
                "test-password"
            ),
            "SMTP_FROM_EMAIL": (
                "no-reply@xuoroni.example"
            ),
            "SMTP_FROM_NAME": "Xuoroni",
            "SMTP_USE_TLS": True,
            "SMTP_TIMEOUT_SECONDS": 10,
        }
    )


@pytest.fixture(autouse=True)
def reset_fake_smtp():
    FakeSmtp.instances = []


def test_missing_smtp_host_is_rejected(
    app,
):
    with app.app_context():
        app.config[
            "SMTP_HOST"
        ] = ""

        with pytest.raises(
            EmailConfigurationError
        ):
            send_email(
                recipient=(
                    "user@example.com"
                ),
                subject="Test",
                text_body="Hello",
            )


def test_missing_sender_is_rejected(
    app,
):
    with app.app_context():
        app.config[
            "SMTP_FROM_EMAIL"
        ] = ""

        with pytest.raises(
            EmailConfigurationError
        ):
            send_email(
                recipient=(
                    "user@example.com"
                ),
                subject="Test",
                text_body="Hello",
            )


def test_sends_tls_authenticated_email(
    app,
    monkeypatch,
):
    monkeypatch.setattr(
        smtplib,
        "SMTP",
        FakeSmtp,
    )

    with app.app_context():
        result = send_email(
            recipient=(
                "user@example.com"
            ),
            subject=(
                "Xuoroni Test"
            ),
            text_body=(
                "Plain body"
            ),
            html_body=(
                "<p>HTML body</p>"
            ),
        )

    assert result is True

    smtp = (
        FakeSmtp.instances[0]
    )

    assert (
        smtp.host
        == "smtp.example.com"
    )

    assert smtp.port == 587
    assert smtp.timeout == 10

    assert (
        smtp.starttls_calls
        == 1
    )

    assert (
        smtp.ehlo_calls
        == 2
    )

    assert (
        smtp.login_calls
        == [
            (
                "xuoroni@example.com",
                "test-password",
            )
        ]
    )

    assert len(
        smtp.messages
    ) == 1

    message = (
        smtp.messages[0]
    )

    assert (
        message["To"]
        == "user@example.com"
    )

    assert (
        message["Subject"]
        == "Xuoroni Test"
    )


def test_tls_can_be_disabled(
    app,
    monkeypatch,
):
    monkeypatch.setattr(
        smtplib,
        "SMTP",
        FakeSmtp,
    )

    with app.app_context():
        app.config[
            "SMTP_USE_TLS"
        ] = False

        send_email(
            recipient=(
                "user@example.com"
            ),
            subject="Test",
            text_body="Hello",
        )

    smtp = (
        FakeSmtp.instances[0]
    )

    assert (
        smtp.starttls_calls
        == 0
    )

    assert (
        smtp.ehlo_calls
        == 1
    )


def test_smtp_login_is_optional(
    app,
    monkeypatch,
):
    monkeypatch.setattr(
        smtplib,
        "SMTP",
        FakeSmtp,
    )

    with app.app_context():
        app.config[
            "SMTP_USERNAME"
        ] = ""

        app.config[
            "SMTP_PASSWORD"
        ] = ""

        send_email(
            recipient=(
                "user@example.com"
            ),
            subject="Test",
            text_body="Hello",
        )

    smtp = (
        FakeSmtp.instances[0]
    )

    assert (
        smtp.login_calls
        == []
    )


def test_delivery_failure_is_wrapped(
    app,
    monkeypatch,
):
    class BrokenSmtp:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            raise OSError(
                "Connection failed"
            )

    monkeypatch.setattr(
        smtplib,
        "SMTP",
        BrokenSmtp,
    )

    with app.app_context():
        with pytest.raises(
            EmailDeliveryError
        ):
            send_email(
                recipient=(
                    "user@example.com"
                ),
                subject="Test",
                text_body="Hello",
            )


def test_auth_otp_email_contains_code(
    app,
    monkeypatch,
):
    monkeypatch.setattr(
        smtplib,
        "SMTP",
        FakeSmtp,
    )

    with app.app_context():
        send_auth_otp_email(
            recipient=(
                "user@example.com"
            ),
            otp="654321",
            expires_in=300,
        )

    smtp = (
        FakeSmtp.instances[0]
    )

    message = (
        smtp.messages[0]
    )

    assert (
        "654321"
        in message.as_string()
    )

    assert (
        "5 minutes"
        in message.as_string()
    )

    assert (
        "verification code"
        in message[
            "Subject"
        ].lower()
    )
