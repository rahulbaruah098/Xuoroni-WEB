import pytest

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo
from app.repositories.session_repository import (
    get_session_by_id,
    get_session_by_refresh_hash,
)
from app.repositories.user_repository import create_user
from app.security.tokens import (
    decode_access_token,
    hash_refresh_token,
)
from app.services.auth_service import (
    InvalidRefreshToken,
    RefreshTokenReuseDetected,
    issue_session,
    logout_all_sessions,
    logout_refresh_token,
    rotate_refresh_token,
)


TEST_DATABASE = "xuoroni_test_auth_sessions"


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
                "xuoroni-test-auth-session-secret-at-least-32-bytes-long"
            ),
            "JWT_ISSUER": "xuoroni-test",
            "JWT_AUDIENCE": (
                "xuoroni-test-client"
            ),
            "JWT_ACCESS_TOKEN_MINUTES": 15,
            "JWT_REFRESH_TOKEN_DAYS": 30,
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


def test_issue_session_stores_only_refresh_hash(
    app,
):
    with app.app_context():
        user = create_user()

        tokens = issue_session(
            user["_id"]
        )

        stored = get_session_by_id(
            tokens["session_id"]
        )

        assert stored is not None

        assert (
            stored["refresh_token_hash"]
            == hash_refresh_token(
                tokens["refresh_token"]
            )
        )

        assert (
            tokens["refresh_token"]
            != stored["refresh_token_hash"]
        )

        payload = decode_access_token(
            tokens["access_token"]
        )

        assert (
            payload["sub"]
            == str(user["_id"])
        )

        assert (
            payload["sid"]
            == tokens["session_id"]
        )


def test_refresh_rotation_creates_new_session(
    app,
):
    with app.app_context():
        user = create_user()

        first = issue_session(
            user["_id"]
        )

        second = rotate_refresh_token(
            first["refresh_token"]
        )

        assert (
            first["refresh_token"]
            != second["refresh_token"]
        )

        assert (
            first["session_id"]
            != second["session_id"]
        )

        old_session = (
            get_session_by_refresh_hash(
                hash_refresh_token(
                    first["refresh_token"]
                )
            )
        )

        new_session = (
            get_session_by_refresh_hash(
                hash_refresh_token(
                    second["refresh_token"]
                )
            )
        )

        assert (
            old_session["revoke_reason"]
            == "rotated"
        )

        assert (
            old_session[
                "replaced_by_session_id"
            ]
            == second["session_id"]
        )

        assert (
            old_session["family_id"]
            == new_session["family_id"]
        )


def test_reusing_rotated_token_revokes_family(
    app,
):
    with app.app_context():
        user = create_user()

        first = issue_session(
            user["_id"]
        )

        second = rotate_refresh_token(
            first["refresh_token"]
        )

        with pytest.raises(
            RefreshTokenReuseDetected
        ):
            rotate_refresh_token(
                first["refresh_token"]
            )

        current = (
            get_session_by_refresh_hash(
                hash_refresh_token(
                    second["refresh_token"]
                )
            )
        )

        assert current["revoked_at"] is not None

        assert (
            current["revoke_reason"]
            == "refresh_token_reuse"
        )


def test_logout_revokes_refresh_token(
    app,
):
    with app.app_context():
        user = create_user()

        tokens = issue_session(
            user["_id"]
        )

        assert logout_refresh_token(
            tokens["refresh_token"]
        )

        with pytest.raises(
            InvalidRefreshToken
        ):
            rotate_refresh_token(
                tokens["refresh_token"]
            )


def test_logout_all_revokes_every_active_session(
    app,
):
    with app.app_context():
        user = create_user()

        first = issue_session(
            user["_id"]
        )

        second = issue_session(
            user["_id"]
        )

        revoked = logout_all_sessions(
            user["_id"]
        )

        assert revoked == 2

        for tokens in (
            first,
            second,
        ):
            stored = get_session_by_id(
                tokens["session_id"]
            )

            assert (
                stored["revoked_at"]
                is not None
            )

            assert (
                stored["revoke_reason"]
                == "logout_all"
            )


def test_unknown_refresh_token_is_rejected(
    app,
):
    with app.app_context():
        with pytest.raises(
            InvalidRefreshToken
        ):
            rotate_refresh_token(
                "not-a-real-refresh-token"
            )

