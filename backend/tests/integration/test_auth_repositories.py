import pytest
from pymongo.errors import DuplicateKeyError

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo
from app.repositories.auth_repository import (
    create_identity,
    get_identities_for_user,
    get_identity,
    get_identity_by_email,
    get_identity_by_phone,
)
from app.repositories.user_repository import (
    create_user,
    get_user_by_id,
    set_account_status,
    update_last_login,
)


TEST_DATABASE = "xuoroni_test_auth_repository"


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


def test_create_and_get_user(app):
    with app.app_context():
        user = create_user()

        loaded = get_user_by_id(
            str(user["_id"])
        )

        assert loaded is not None
        assert loaded["_id"] == user["_id"]
        assert loaded["account_status"] == "active"
        assert (
            loaded["onboarding_status"]
            == "not_started"
        )


def test_update_user_state(app):
    with app.app_context():
        user = create_user()

        assert update_last_login(
            user["_id"]
        )

        assert set_account_status(
            user["_id"],
            "paused",
        )

        loaded = get_user_by_id(
            user["_id"]
        )

        assert (
            loaded["account_status"]
            == "paused"
        )


def test_create_phone_identity(app):
    with app.app_context():
        user = create_user()

        identity = create_identity(
            user_id=user["_id"],
            provider="phone",
            provider_subject="+919876543210",
            phone_normalized="+919876543210",
        )

        loaded = get_identity_by_phone(
            "+919876543210"
        )

        assert loaded is not None
        assert (
            loaded["_id"]
            == identity["_id"]
        )

        assert loaded["verified"] is True


def test_create_email_identity(app):
    with app.app_context():
        user = create_user()

        create_identity(
            user_id=user["_id"],
            provider="email",
            provider_subject="rahul@example.com",
            email_normalized="RAHUL@example.com",
        )

        loaded = get_identity_by_email(
            "rahul@example.com"
        )

        assert loaded is not None

        assert (
            loaded["email_normalized"]
            == "rahul@example.com"
        )


def test_provider_identity_lookup(app):
    with app.app_context():
        user = create_user()

        create_identity(
            user_id=user["_id"],
            provider="google",
            provider_subject="google-sub-123",
            email_normalized="user@example.com",
        )

        loaded = get_identity(
            provider="google",
            provider_subject="google-sub-123",
        )

        assert loaded is not None
        assert loaded["provider"] == "google"


def test_user_can_have_multiple_identities(app):
    with app.app_context():
        user = create_user()

        create_identity(
            user_id=user["_id"],
            provider="phone",
            provider_subject="+919876543210",
            phone_normalized="+919876543210",
        )

        create_identity(
            user_id=user["_id"],
            provider="email",
            provider_subject="user@example.com",
            email_normalized="user@example.com",
        )

        identities = get_identities_for_user(
            user["_id"]
        )

        assert len(identities) == 2


def test_duplicate_phone_identity_is_blocked(app):
    with app.app_context():
        first_user = create_user()
        second_user = create_user()

        create_identity(
            user_id=first_user["_id"],
            provider="phone",
            provider_subject="+919876543210",
            phone_normalized="+919876543210",
        )

        with pytest.raises(
            DuplicateKeyError
        ):
            create_identity(
                user_id=second_user["_id"],
                provider="phone",
                provider_subject="+919876543210",
                phone_normalized="+919876543210",
            )
