from datetime import date

import pytest

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo
from app.repositories.profile_repository import (
    ensure_profile,
)
from app.repositories.user_repository import (
    create_user,
    get_user_by_id,
)
from app.services.profile_service import (
    update_my_discovery_preferences,
    update_my_profile,
)
from app.services.profile_validation import (
    ProfileValidationError,
)


TEST_DATABASE = (
    "xuoroni_test_profile_updates"
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


def test_valid_profile_patch_starts_onboarding(
    app,
):
    with app.app_context():
        user = create_user()

        updated = update_my_profile(
            user["_id"],
            {
                "display_name": "Rahul",
                "birth_date": "2000-01-15",
                "gender_identity": "man",
                "current_city": {
                    "city": "Guwahati",
                    "state": "Assam",
                },
            },
            today=date(
                2026,
                10,
                3,
            ),
        )

        assert (
            updated[
                "onboarding_status"
            ]
            == "in_progress"
        )

        assert (
            updated[
                "onboarding"
            ]["started_at"]
            is not None
        )

        assert (
            updated[
                "birth_date"
            ]
            == "2000-01-15"
        )

        stored_user = (
            get_user_by_id(
                user["_id"]
            )
        )

        assert (
            stored_user[
                "onboarding_status"
            ]
            == "in_progress"
        )


def test_underage_profile_is_rejected(
    app,
):
    with app.app_context():
        user = create_user()

        with pytest.raises(
            ProfileValidationError
        ) as error:
            update_my_profile(
                user["_id"],
                {
                    "birth_date": (
                        "2010-01-01"
                    )
                },
                today=date(
                    2026,
                    10,
                    3,
                ),
            )

        assert (
            error.value.field
            == "birth_date"
        )


def test_surname_is_safely_normalized(
    app,
):
    with app.app_context():
        user = create_user()

        updated = update_my_profile(
            user["_id"],
            {
                "last_name": (
                    "  BaRuAh  "
                ),
                "surname_searchable": True,
            },
        )

        assert (
            updated[
                "last_name"
            ]
            == "BaRuAh"
        )

        assert (
            updated[
                "surname_normalized"
            ]
            == "baruah"
        )

        assert (
            updated[
                "surname_searchable"
            ]
            is True
        )


def test_partial_nested_update_preserves_profile_data(
    app,
):
    with app.app_context():
        user = create_user()

        ensure_profile(
            user["_id"]
        )

        update_my_profile(
            user["_id"],
            {
                "current_city": {
                    "city": "Guwahati",
                }
            },
        )

        updated = update_my_profile(
            user["_id"],
            {
                "current_city": {
                    "state": "Assam",
                }
            },
        )

        assert (
            updated[
                "current_city"
            ]["city"]
            == "Guwahati"
        )

        assert (
            updated[
                "current_city"
            ]["state"]
            == "Assam"
        )

        assert (
            updated[
                "current_city"
            ]["country"]
            == "India"
        )


def test_server_managed_profile_fields_are_rejected(
    app,
):
    with app.app_context():
        user = create_user()

        with pytest.raises(
            ProfileValidationError
        ):
            update_my_profile(
                user["_id"],
                {
                    "verification_summary": {
                        "identity_verified": True,
                    }
                },
            )


def test_discovery_preferences_update(
    app,
):
    with app.app_context():
        user = create_user()

        preferences = (
            update_my_discovery_preferences(
                user["_id"],
                {
                    "interested_in": [
                        "woman",
                    ],
                    "age_min": 21,
                    "age_max": 35,
                    "max_distance_km": 75,
                    "relationship_intentions": [
                        "long_term",
                    ],
                },
            )
        )

        assert (
            preferences[
                "interested_in"
            ]
            == ["woman"]
        )

        assert (
            preferences[
                "age_min"
            ]
            == 21
        )

        assert (
            preferences[
                "age_max"
            ]
            == 35
        )


def test_invalid_discovery_age_range_is_rejected(
    app,
):
    with app.app_context():
        user = create_user()

        with pytest.raises(
            ProfileValidationError
        ) as error:
            update_my_discovery_preferences(
                user["_id"],
                {
                    "age_min": 40,
                    "age_max": 30,
                },
            )

        assert (
            error.value.field
            == "age_range"
        )


def test_surname_filter_is_exact_normalized_and_deduplicated(
    app,
):
    with app.app_context():
        user = create_user()

        preferences = (
            update_my_discovery_preferences(
                user["_id"],
                {
                    "surname_filter": {
                        "mode": "exclude",
                        "values": [
                            " Baruah ",
                            "BARUAH",
                            "Gogoi",
                        ],
                    }
                },
            )
        )

        assert (
            preferences[
                "surname_filter"
            ]["mode"]
            == "exclude"
        )

        assert (
            preferences[
                "surname_filter"
            ]["values"]
            == [
                "baruah",
                "gogoi",
            ]
        )
