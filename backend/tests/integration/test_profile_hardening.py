import pytest

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo
from app.repositories.profile_repository import (
    ensure_profile,
    update_profile_fields,
)
from app.repositories.user_repository import (
    create_user,
    get_user_by_id,
)
from app.schemas.profile import (
    ONBOARDING_STEPS,
)
from app.services.profile_service import (
    ProfileLifecycleError,
    serialize_profile_for_owner,
    update_my_discovery_preferences,
    update_my_profile,
    update_onboarding_progress,
)


TEST_DATABASE = (
    "xuoroni_test_profile_hardening"
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


def _make_complete_profile(
    user_id,
):
    ensure_profile(
        user_id
    )

    update_profile_fields(
        user_id,
        {
            "media": [
                {
                    "media_id": "photo-1",
                }
            ]
        },
    )

    return update_my_profile(
        user_id,
        {
            "display_name": "Xuoroni User",
            "birth_date": "2000-01-01",
            "gender_identity": "man",
            "current_city": {
                "city": "Guwahati",
                "state": "Assam",
            },
            "languages": [
                "Assamese",
                "English",
            ],
            "bio": (
                "Culture, coffee and good "
                "conversations."
            ),
            "interests": [
                "Travel",
                "Music",
                "Food",
            ],
            "relationship_intentions": [
                "long_term",
            ],
            "prompts": [
                {
                    "prompt_id": (
                        "perfect_weekend"
                    ),
                    "answer": (
                        "A quiet road trip."
                    ),
                }
            ],
        },
    )


def test_owner_serializer_uses_allowlist(
    app,
):
    with app.app_context():
        user = create_user()

        profile = ensure_profile(
            user["_id"]
        )

        profile[
            "surname_normalized"
        ] = "internal-value"

        profile[
            "location"
        ] = {
            "type": "Point",
            "coordinates": [
                91.7,
                26.1,
            ],
        }

        profile[
            "future_internal_secret"
        ] = "must-not-leak"

        payload = (
            serialize_profile_for_owner(
                profile
            )
        )

        assert (
            "surname_normalized"
            not in payload
        )

        assert (
            "location"
            not in payload
        )

        assert (
            "future_internal_secret"
            not in payload
        )


def test_full_profile_does_not_auto_complete_onboarding(
    app,
):
    with app.app_context():
        user = create_user()

        profile = (
            _make_complete_profile(
                user["_id"]
            )
        )

        assert (
            profile[
                "profile_completion_percent"
            ]
            == 100
        )

        assert (
            profile[
                "onboarding_status"
            ]
            == "in_progress"
        )

        assert (
            profile[
                "profile_status"
            ]
            == "draft"
        )


def test_cannot_skip_onboarding_steps(
    app,
):
    with app.app_context():
        user = create_user()

        ensure_profile(
            user["_id"]
        )

        with pytest.raises(
            ValueError
        ):
            update_onboarding_progress(
                user["_id"],
                current_step="culture",
            )


def test_review_requires_complete_profile(
    app,
):
    with app.app_context():
        user = create_user()

        ensure_profile(
            user["_id"]
        )

        for index, step in enumerate(
            ONBOARDING_STEPS[:-1]
        ):
            next_step = (
                ONBOARDING_STEPS[
                    index + 1
                ]
            )

            update_onboarding_progress(
                user["_id"],
                completed_step=step,
                current_step=next_step,
            )

        with pytest.raises(
            ValueError
        ):
            update_onboarding_progress(
                user["_id"],
                completed_step="review",
            )


def test_complete_review_activates_profile_and_user(
    app,
):
    with app.app_context():
        user = create_user()

        profile = (
            _make_complete_profile(
                user["_id"]
            )
        )

        assert (
            profile[
                "profile_completion_percent"
            ]
            == 100
        )

        for index, step in enumerate(
            ONBOARDING_STEPS
        ):
            next_step = (
                ONBOARDING_STEPS[
                    index + 1
                ]
                if index + 1
                < len(
                    ONBOARDING_STEPS
                )
                else None
            )

            state = (
                update_onboarding_progress(
                    user["_id"],
                    completed_step=step,
                    current_step=next_step,
                )
            )

        assert (
            state["status"]
            == "completed"
        )

        stored_profile = (
            mongo.db.profiles.find_one(
                {
                    "user_id": user["_id"],
                }
            )
        )

        assert (
            stored_profile[
                "profile_status"
            ]
            == "active"
        )

        assert (
            stored_profile[
                "onboarding"
            ]["completed_at"]
            is not None
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
            == "completed"
        )


def test_disabled_profile_blocks_profile_edits(
    app,
):
    with app.app_context():
        user = create_user()

        ensure_profile(
            user["_id"]
        )

        update_profile_fields(
            user["_id"],
            {
                "profile_status": (
                    "disabled"
                )
            },
        )

        with pytest.raises(
            ProfileLifecycleError
        ):
            update_my_profile(
                user["_id"],
                {
                    "display_name": (
                        "Blocked"
                    )
                },
            )


def test_disabled_profile_blocks_discovery_updates(
    app,
):
    with app.app_context():
        user = create_user()

        ensure_profile(
            user["_id"]
        )

        update_profile_fields(
            user["_id"],
            {
                "profile_status": (
                    "disabled"
                )
            },
        )

        with pytest.raises(
            ProfileLifecycleError
        ):
            update_my_discovery_preferences(
                user["_id"],
                {
                    "age_min": 25,
                },
            )


def test_disabled_profile_blocks_onboarding_updates(
    app,
):
    with app.app_context():
        user = create_user()

        ensure_profile(
            user["_id"]
        )

        update_profile_fields(
            user["_id"],
            {
                "profile_status": (
                    "disabled"
                )
            },
        )

        with pytest.raises(
            ProfileLifecycleError
        ):
            update_onboarding_progress(
                user["_id"],
                current_step="basics",
            )
