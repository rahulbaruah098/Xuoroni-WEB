import pytest

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo
from app.repositories.auth_repository import (
    create_identity,
    get_identity,
)
from app.repositories.user_repository import (
    create_user,
)


TEST_DATABASE = (
    "xuoroni_test_google_auth_api"
)


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "MONGO_URI": (
                "mongodb://localhost:27017/"
                + TEST_DATABASE
            ),
            "JWT_SECRET_KEY": (
                "xuoroni-google-auth-api-"
                "secret-at-least-32-bytes"
            ),
            "GOOGLE_CLIENT_ID": (
                "xuoroni-test-client.apps."
                "googleusercontent.com"
            ),
        }
    )

    with application.app_context():
        mongo.cx.drop_database(
            TEST_DATABASE
        )

        ensure_indexes(
            mongo.db
        )

        yield application

        mongo.cx.drop_database(
            TEST_DATABASE
        )


@pytest.fixture()
def client(app):
    return app.test_client()


def _claims(
    *,
    sub="google-user-123",
    email="google@example.com",
):
    return {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": "Google User",
        "picture": (
            "https://example.com/avatar.jpg"
        ),
    }


def _mock_google(
    monkeypatch,
    claims,
):
    monkeypatch.setattr(
        (
            "app.services.auth_service."
            "verify_google_id_token"
        ),
        lambda token: claims,
    )


def _google_login(
    client,
    *,
    token="google-token",
):
    return client.post(
        "/api/v1/auth/google",
        json={
            "id_token": token,
            "device_id": "google-test-device",
            "platform": "pytest",
        },
    )


def test_google_login_creates_user_and_tokens(
    client,
    monkeypatch,
):
    _mock_google(
        monkeypatch,
        _claims(),
    )

    response = _google_login(
        client
    )

    assert (
        response.status_code
        == 200
    )

    body = response.get_json()

    assert (
        body["is_new_user"]
        is True
    )

    assert (
        body["linked_existing_account"]
        is False
    )

    assert (
        body["user"]["email"]
        == "google@example.com"
    )

    assert body["access_token"]
    assert body["refresh_token"]


def test_second_google_login_reuses_user(
    client,
    monkeypatch,
):
    _mock_google(
        monkeypatch,
        _claims(),
    )

    first = _google_login(
        client
    ).get_json()

    second = _google_login(
        client
    ).get_json()

    assert (
        second["is_new_user"]
        is False
    )

    assert (
        second["user"]["id"]
        == first["user"]["id"]
    )


def test_google_links_existing_email_account(
    app,
    client,
    monkeypatch,
):
    with app.app_context():
        existing_user = (
            create_user()
        )

        create_identity(
            user_id=existing_user[
                "_id"
            ],
            provider="email",
            provider_subject=(
                "linked@example.com"
            ),
            email_normalized=(
                "linked@example.com"
            ),
            verified=True,
        )

        existing_id = str(
            existing_user["_id"]
        )

    _mock_google(
        monkeypatch,
        _claims(
            sub="google-linked-user",
            email="linked@example.com",
        ),
    )

    response = _google_login(
        client
    )

    assert (
        response.status_code
        == 200
    )

    body = response.get_json()

    assert (
        body["user"]["id"]
        == existing_id
    )

    assert (
        body["is_new_user"]
        is False
    )

    assert (
        body["linked_existing_account"]
        is True
    )

    with app.app_context():
        google_identity = (
            get_identity(
                provider="google",
                provider_subject=(
                    "google-linked-user"
                ),
            )
        )

        assert (
            str(
                google_identity[
                    "user_id"
                ]
            )
            == existing_id
        )


def test_google_identity_conflict_is_rejected(
    app,
    client,
    monkeypatch,
):
    with app.app_context():
        google_user = create_user()
        email_user = create_user()

        create_identity(
            user_id=google_user[
                "_id"
            ],
            provider="google",
            provider_subject=(
                "google-conflict"
            ),
            verified=True,
        )

        create_identity(
            user_id=email_user[
                "_id"
            ],
            provider="email",
            provider_subject=(
                "conflict@example.com"
            ),
            email_normalized=(
                "conflict@example.com"
            ),
            verified=True,
        )

    _mock_google(
        monkeypatch,
        _claims(
            sub="google-conflict",
            email=(
                "conflict@example.com"
            ),
        ),
    )

    response = _google_login(
        client
    )

    assert (
        response.status_code
        == 409
    )

    assert (
        response.get_json()[
            "code"
        ]
        == "GOOGLE_ACCOUNT_CONFLICT"
    )


def test_invalid_google_token_is_rejected(
    client,
    monkeypatch,
):
    from app.services.google_token_service import (
        InvalidGoogleToken,
    )

    def fail(_token):
        raise InvalidGoogleToken(
            "Invalid Google token."
        )

    monkeypatch.setattr(
        (
            "app.services.auth_service."
            "verify_google_id_token"
        ),
        fail,
    )

    response = _google_login(
        client
    )

    assert (
        response.status_code
        == 401
    )

    assert (
        response.get_json()[
            "code"
        ]
        == "INVALID_GOOGLE_TOKEN"
    )


def test_unverified_google_email_is_rejected(
    client,
    monkeypatch,
):
    from app.services.google_token_service import (
        GoogleEmailNotVerified,
    )

    def fail(_token):
        raise GoogleEmailNotVerified(
            "Google email is not verified."
        )

    monkeypatch.setattr(
        (
            "app.services.auth_service."
            "verify_google_id_token"
        ),
        fail,
    )

    response = _google_login(
        client
    )

    assert (
        response.status_code
        == 401
    )

    assert (
        response.get_json()[
            "code"
        ]
        == "GOOGLE_EMAIL_NOT_VERIFIED"
    )


def test_google_me_returns_verified_email(
    client,
    monkeypatch,
):
    _mock_google(
        monkeypatch,
        _claims(),
    )

    login = _google_login(
        client
    ).get_json()

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                "Bearer "
                + login[
                    "access_token"
                ]
            )
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.get_json()[
            "user"
        ]["email"]
        == "google@example.com"
    )


def test_google_refresh_token_rotates(
    client,
    monkeypatch,
):
    _mock_google(
        monkeypatch,
        _claims(),
    )

    login = _google_login(
        client
    ).get_json()

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": (
                login[
                    "refresh_token"
                ]
            )
        },
    )

    assert (
        response.status_code
        == 200
    )

    rotated = response.get_json()

    assert rotated[
        "access_token"
    ]

    assert (
        rotated[
            "refresh_token"
        ]
        != login[
            "refresh_token"
        ]
    )


def test_google_credential_alias_is_supported(
    client,
    monkeypatch,
):
    _mock_google(
        monkeypatch,
        _claims(
            sub="credential-user",
            email=(
                "credential@example.com"
            ),
        ),
    )

    response = client.post(
        "/api/v1/auth/google",
        json={
            "credential": (
                "google-credential"
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )
