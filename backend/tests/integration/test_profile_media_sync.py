"""Integration tests for internal profile-media synchronization."""

from bson import ObjectId
import pytest

from app import create_app
from app.db.indexes import ensure_indexes
from app.extensions import mongo
from app.repositories.profile_repository import (
    create_profile,
    get_profile_by_user_id,
    sync_profile_media_fields,
)


TEST_DB = "xuoroni_test_profile_media_sync"


@pytest.fixture(scope="module")
def app():
    application = create_app(
        {
            "TESTING": True,
            "AUTO_ENSURE_INDEXES": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "MONGO_URI": (
                "mongodb://localhost:27017/"
                + TEST_DB
            ),
        }
    )

    with application.app_context():
        mongo.cx.drop_database(
            TEST_DB
        )

        ensure_indexes(
            mongo.db
        )

    yield application

    with application.app_context():
        mongo.cx.drop_database(
            TEST_DB
        )


@pytest.fixture(autouse=True)
def clean_profiles(app):
    with app.app_context():
        mongo.db.profiles.delete_many(
            {}
        )

    yield

    with app.app_context():
        mongo.db.profiles.delete_many(
            {}
        )


def media_reference(
    *,
    kind="profile_photo",
    position=0,
):
    return {
        "media_id": str(
            ObjectId()
        ),
        "kind": kind,
        "position": position,
    }


def test_sync_profile_media_fields(
    app,
):
    user_id = ObjectId()

    first = media_reference(
        position=0
    )

    second = media_reference(
        kind="profile_video",
        position=1,
    )

    with app.app_context():
        create_profile(
            user_id
        )

        updated = sync_profile_media_fields(
            user_id,
            media=[
                first,
                second,
            ],
            primary_media_id=first[
                "media_id"
            ],
            profile_completion_percent=75,
        )

    assert updated is not None

    assert updated["media"] == [
        first,
        second,
    ]

    assert (
        updated["primary_media_id"]
        == first["media_id"]
    )

    assert (
        updated[
            "profile_completion_percent"
        ]
        == 75
    )


def test_sync_can_clear_all_media(
    app,
):
    user_id = ObjectId()

    with app.app_context():
        create_profile(
            user_id
        )

        updated = sync_profile_media_fields(
            user_id,
            media=[],
            primary_media_id=None,
            profile_completion_percent=0,
        )

    assert updated["media"] == []

    assert (
        updated["primary_media_id"]
        is None
    )

    assert (
        updated[
            "profile_completion_percent"
        ]
        == 0
    )


def test_sync_preserves_unrelated_profile_fields(
    app,
):
    user_id = ObjectId()

    reference = media_reference()

    with app.app_context():
        create_profile(
            user_id
        )

        mongo.db.profiles.update_one(
            {
                "user_id": user_id,
            },
            {
                "$set": {
                    "display_name": "Media Sync Test",
                    "bio": (
                        "This value must remain untouched."
                    ),
                    "onboarding_status": "in_progress",
                    "onboarding.current_step": "media",
                }
            },
        )

        updated = sync_profile_media_fields(
            user_id,
            media=[
                reference
            ],
            primary_media_id=reference[
                "media_id"
            ],
            profile_completion_percent=60,
        )

    assert (
        updated["display_name"]
        == "Media Sync Test"
    )

    assert (
        updated["bio"]
        == "This value must remain untouched."
    )

    assert (
        updated["onboarding_status"]
        == "in_progress"
    )

    assert (
        updated["onboarding"][
            "current_step"
        ]
        == "media"
    )


def test_sync_does_not_change_onboarding_progress(
    app,
):
    user_id = ObjectId()

    reference = media_reference()

    with app.app_context():
        create_profile(
            user_id
        )

        before = get_profile_by_user_id(
            user_id
        )

        before_onboarding = dict(
            before.get(
                "onboarding"
            )
            or {}
        )

        before_status = before.get(
            "onboarding_status"
        )

        updated = sync_profile_media_fields(
            user_id,
            media=[
                reference
            ],
            primary_media_id=reference[
                "media_id"
            ],
            profile_completion_percent=50,
        )

    assert (
        updated.get(
            "onboarding_status"
        )
        == before_status
    )

    assert (
        updated.get(
            "onboarding"
        )
        == before_onboarding
    )


def test_completion_is_optional(
    app,
):
    user_id = ObjectId()

    reference = media_reference()

    with app.app_context():
        create_profile(
            user_id
        )

        mongo.db.profiles.update_one(
            {
                "user_id": user_id,
            },
            {
                "$set": {
                    "profile_completion_percent": 42,
                }
            },
        )

        updated = sync_profile_media_fields(
            user_id,
            media=[
                reference
            ],
            primary_media_id=reference[
                "media_id"
            ],
        )

    assert (
        updated[
            "profile_completion_percent"
        ]
        == 42
    )


@pytest.mark.parametrize(
    "completion",
    [
        -1,
        101,
        "not-an-integer",
    ],
)
def test_invalid_completion_is_rejected(
    app,
    completion,
):
    user_id = ObjectId()

    with app.app_context():
        create_profile(
            user_id
        )

        with pytest.raises(
            ValueError
        ):
            sync_profile_media_fields(
                user_id,
                media=[],
                primary_media_id=None,
                profile_completion_percent=(
                    completion
                ),
            )


def test_non_list_media_is_rejected(
    app,
):
    user_id = ObjectId()

    with app.app_context():
        create_profile(
            user_id
        )

        with pytest.raises(
            ValueError
        ):
            sync_profile_media_fields(
                user_id,
                media={
                    "media_id": str(
                        ObjectId()
                    )
                },
                primary_media_id=None,
            )


def test_invalid_user_id_returns_none(
    app,
):
    with app.app_context():
        result = sync_profile_media_fields(
            "invalid-object-id",
            media=[],
            primary_media_id=None,
        )

    assert result is None


def test_missing_profile_returns_none(
    app,
):
    user_id = ObjectId()

    with app.app_context():
        result = sync_profile_media_fields(
            user_id,
            media=[],
            primary_media_id=None,
        )

    assert result is None
