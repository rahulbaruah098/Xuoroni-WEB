import pytest
from pymongo.errors import DuplicateKeyError

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo
from app.repositories.profile_repository import (
    create_discovery_preferences,
    create_profile,
    ensure_discovery_preferences,
    ensure_profile,
    get_discovery_preferences,
    get_profile_by_user_id,
    touch_profile_activity,
)
from app.repositories.user_repository import (
    create_user,
)


TEST_DATABASE = "xuoroni_test_profiles"


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


def test_create_default_profile(
    app,
):
    with app.app_context():
        user = create_user()

        profile = create_profile(
            user["_id"]
        )

        assert (
            profile["user_id"]
            == user["_id"]
        )

        assert (
            profile["profile_status"]
            == "draft"
        )

        assert (
            profile["visibility"]
            == "hidden"
        )

        assert (
            profile["onboarding_status"]
            == "not_started"
        )

        assert (
            profile[
                "profile_completion_percent"
            ]
            == 0
        )


def test_profile_contains_culture_privacy_and_media(
    app,
):
    with app.app_context():
        user = create_user()

        profile = create_profile(
            user["_id"]
        )

        assert (
            profile["culture"][
                "communities"
            ]
            == []
        )

        assert (
            profile["culture"][
                "tribes"
            ]
            == []
        )

        assert (
            profile["media"]
            == []
        )

        assert (
            profile["privacy"][
                "show_surname"
            ]
            is False
        )

        assert (
            "location"
            not in profile
        )


def test_only_one_profile_per_user(
    app,
):
    with app.app_context():
        user = create_user()

        create_profile(
            user["_id"]
        )

        with pytest.raises(
            DuplicateKeyError
        ):
            create_profile(
                user["_id"]
            )


def test_ensure_profile_is_idempotent(
    app,
):
    with app.app_context():
        user = create_user()

        first = ensure_profile(
            user["_id"]
        )

        second = ensure_profile(
            user["_id"]
        )

        assert (
            first["_id"]
            == second["_id"]
        )


def test_default_discovery_preferences(
    app,
):
    with app.app_context():
        user = create_user()

        preferences = (
            create_discovery_preferences(
                user["_id"]
            )
        )

        assert (
            preferences["age_min"]
            == 18
        )

        assert (
            preferences["age_max"]
            == 99
        )

        assert (
            preferences[
                "surname_filter"
            ]["mode"]
            == "none"
        )

        assert (
            preferences[
                "surname_filter"
            ]["values"]
            == []
        )

        loaded = (
            get_discovery_preferences(
                user["_id"]
            )
        )

        assert (
            loaded["_id"]
            == preferences["_id"]
        )


def test_profile_and_preferences_helpers(
    app,
):
    with app.app_context():
        user = create_user()

        profile = ensure_profile(
            user["_id"]
        )

        preferences = (
            ensure_discovery_preferences(
                user["_id"]
            )
        )

        assert (
            get_profile_by_user_id(
                user["_id"]
            )["_id"]
            == profile["_id"]
        )

        assert (
            preferences["user_id"]
            == user["_id"]
        )

        assert touch_profile_activity(
            user["_id"]
        ) is True
