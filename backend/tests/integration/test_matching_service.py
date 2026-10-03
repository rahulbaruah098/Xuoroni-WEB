"""Integration tests for Xuoroni matching business rules."""

import pytest
from bson import ObjectId

from app import create_app
from app.extensions import mongo
from app.repositories.match_repository import (
    create_match_if_absent,
    get_match_between,
    get_profile_action,
    upsert_profile_action,
)
from app.repositories.profile_repository import (
    create_profile,
)
from app.repositories.user_repository import (
    create_user,
)
from app.services.matching_service import (
    MatchingConflictError,
    MatchingLifecycleError,
    MatchingNotFoundError,
    MatchingValidationError,
    get_my_match,
    list_my_matches,
    submit_profile_action,
    unmatch_my_match,
)


@pytest.fixture(scope="module")
def app():
    application = create_app()

    with application.app_context():
        yield application


@pytest.fixture
def matching_users(app):
    created_user_ids = []

    def create_ready_user(
        *,
        account_status="active",
        profile_status="active",
        visibility="visible",
        onboarding_status="completed",
    ):
        user = create_user()

        user_id = user["_id"]

        created_user_ids.append(
            user_id
        )

        profile = create_profile(
            user_id
        )

        mongo.db.users.update_one(
            {
                "_id": user_id,
            },
            {
                "$set": {
                    "account_status": (
                        account_status
                    ),
                }
            },
        )

        mongo.db.profiles.update_one(
            {
                "_id": profile["_id"],
            },
            {
                "$set": {
                    "profile_status": (
                        profile_status
                    ),
                    "visibility": (
                        visibility
                    ),
                    "onboarding_status": (
                        onboarding_status
                    ),
                    "display_name": (
                        f"Matching Test {user_id}"
                    ),
                }
            },
        )

        return user_id

    yield create_ready_user

    if created_user_ids:
        mongo.db.profile_actions.delete_many(
            {
                "$or": [
                    {
                        "actor_id": {
                            "$in": created_user_ids,
                        }
                    },
                    {
                        "target_id": {
                            "$in": created_user_ids,
                        }
                    },
                ]
            }
        )

        mongo.db.matches.delete_many(
            {
                "user_ids": {
                    "$in": created_user_ids,
                }
            }
        )

        mongo.db.blocks.delete_many(
            {
                "$or": [
                    {
                        "blocker_id": {
                            "$in": created_user_ids,
                        }
                    },
                    {
                        "blocked_id": {
                            "$in": created_user_ids,
                        }
                    },
                ]
            }
        )

        mongo.db.discovery_preferences.delete_many(
            {
                "user_id": {
                    "$in": created_user_ids,
                }
            }
        )

        mongo.db.profiles.delete_many(
            {
                "user_id": {
                    "$in": created_user_ids,
                }
            }
        )

        mongo.db.users.delete_many(
            {
                "_id": {
                    "$in": created_user_ids,
                }
            }
        )


def test_like_without_reciprocal_does_not_match(
    app,
    matching_users,
):
    actor = matching_users()
    target = matching_users()

    with app.app_context():
        result = submit_profile_action(
            actor_id=actor,
            target_id=target,
            action="like",
        )

        assert result["action"] == "like"
        assert result["matched"] is False
        assert result["match"] is None

        stored = get_profile_action(
            actor,
            target,
        )

        assert stored is not None
        assert stored["action"] == "like"

        assert (
            get_match_between(
                actor,
                target,
            )
            is None
        )


def test_mutual_like_creates_match(
    app,
    matching_users,
):
    first = matching_users()
    second = matching_users()

    with app.app_context():
        first_result = submit_profile_action(
            actor_id=first,
            target_id=second,
            action="like",
        )

        assert (
            first_result["matched"]
            is False
        )

        second_result = submit_profile_action(
            actor_id=second,
            target_id=first,
            action="like",
        )

        assert (
            second_result["matched"]
            is True
        )

        assert (
            second_result["match"]
            is not None
        )

        assert (
            second_result[
                "match"
            ][
                "other_user_id"
            ]
            == str(first)
        )

        stored_match = get_match_between(
            first,
            second,
        )

        assert stored_match is not None
        assert (
            stored_match["status"]
            == "active"
        )


def test_super_like_and_like_create_match(
    app,
    matching_users,
):
    first = matching_users()
    second = matching_users()

    with app.app_context():
        first_result = submit_profile_action(
            actor_id=first,
            target_id=second,
            action="super_like",
        )

        assert (
            first_result["matched"]
            is False
        )

        second_result = submit_profile_action(
            actor_id=second,
            target_id=first,
            action="like",
        )

        assert (
            second_result["matched"]
            is True
        )

        assert (
            get_match_between(
                first,
                second,
            )
            is not None
        )


def test_pass_never_creates_match(
    app,
    matching_users,
):
    actor = matching_users()
    target = matching_users()

    with app.app_context():
        result = submit_profile_action(
            actor_id=actor,
            target_id=target,
            action="pass",
        )

        assert result == {
            "action": "pass",
            "matched": False,
            "match": None,
        }

        assert (
            get_match_between(
                actor,
                target,
            )
            is None
        )


@pytest.mark.parametrize(
    "reverse_block",
    [
        False,
        True,
    ],
)
def test_blocked_pair_cannot_interact(
    app,
    matching_users,
    reverse_block,
):
    actor = matching_users()
    target = matching_users()

    blocker = (
        target
        if reverse_block
        else actor
    )

    blocked = (
        actor
        if reverse_block
        else target
    )

    with app.app_context():
        mongo.db.blocks.insert_one(
            {
                "blocker_id": blocker,
                "blocked_id": blocked,
            }
        )

        with pytest.raises(
            MatchingConflictError
        ) as exc_info:
            submit_profile_action(
                actor_id=actor,
                target_id=target,
                action="like",
            )

        assert (
            exc_info.value.code
            == "PAIR_BLOCKED"
        )


def test_self_action_is_rejected(
    app,
    matching_users,
):
    user_id = matching_users()

    with app.app_context():
        with pytest.raises(
            MatchingValidationError
        ) as exc_info:
            submit_profile_action(
                actor_id=user_id,
                target_id=user_id,
                action="like",
            )

        assert (
            exc_info.value.code
            == "SELF_ACTION_NOT_ALLOWED"
        )


def test_inactive_target_account_is_rejected(
    app,
    matching_users,
):
    actor = matching_users()

    target = matching_users(
        account_status="disabled"
    )

    with app.app_context():
        with pytest.raises(
            MatchingLifecycleError
        ) as exc_info:
            submit_profile_action(
                actor_id=actor,
                target_id=target,
                action="like",
            )

        assert (
            exc_info.value.code
            == "USER_ACCOUNT_INACTIVE"
        )


def test_hidden_target_profile_is_rejected(
    app,
    matching_users,
):
    actor = matching_users()

    target = matching_users(
        visibility="hidden"
    )

    with app.app_context():
        with pytest.raises(
            MatchingLifecycleError
        ) as exc_info:
            submit_profile_action(
                actor_id=actor,
                target_id=target,
                action="like",
            )

        assert (
            exc_info.value.code
            == "PROFILE_NOT_VISIBLE"
        )


def test_incomplete_profile_is_rejected(
    app,
    matching_users,
):
    actor = matching_users()

    target = matching_users(
        onboarding_status="in_progress"
    )

    with app.app_context():
        with pytest.raises(
            MatchingLifecycleError
        ) as exc_info:
            submit_profile_action(
                actor_id=actor,
                target_id=target,
                action="like",
            )

        assert (
            exc_info.value.code
            == "ONBOARDING_INCOMPLETE"
        )


def test_active_match_rejects_pass(
    app,
    matching_users,
):
    first = matching_users()
    second = matching_users()

    with app.app_context():
        create_match_if_absent(
            first_user_id=first,
            second_user_id=second,
            matched_by=first,
        )

        with pytest.raises(
            MatchingConflictError
        ) as exc_info:
            submit_profile_action(
                actor_id=first,
                target_id=second,
                action="pass",
            )

        assert (
            exc_info.value.code
            == "MATCH_ALREADY_ACTIVE"
        )


def test_positive_action_on_existing_match_is_idempotent(
    app,
    matching_users,
):
    first = matching_users()
    second = matching_users()

    with app.app_context():
        created = create_match_if_absent(
            first_user_id=first,
            second_user_id=second,
            matched_by=second,
        )

        result = submit_profile_action(
            actor_id=first,
            target_id=second,
            action="super_like",
        )

        assert result["matched"] is True

        assert (
            result["match"]["id"]
            == str(
                created["match"]["_id"]
            )
        )

        count = mongo.db.matches.count_documents(
            {
                "user_ids": first,
            }
        )

        assert count == 1


def test_list_get_and_unmatch_flow(
    app,
    matching_users,
):
    first = matching_users()
    second = matching_users()

    with app.app_context():
        created = create_match_if_absent(
            first_user_id=first,
            second_user_id=second,
            matched_by=second,
        )

        match_id = (
            created["match"]["_id"]
        )

        listing = list_my_matches(
            first,
            status="active",
            limit=20,
        )

        assert listing["returned"] == 1

        assert (
            listing[
                "matches"
            ][0][
                "id"
            ]
            == str(match_id)
        )

        single = get_my_match(
            user_id=first,
            match_id=match_id,
        )

        assert (
            single["other_user_id"]
            == str(second)
        )

        unmatched = unmatch_my_match(
            user_id=first,
            match_id=match_id,
        )

        assert (
            unmatched["status"]
            == "unmatched"
        )

        active_listing = (
            list_my_matches(
                first,
                status="active",
            )
        )

        assert (
            active_listing["returned"]
            == 0
        )

        old_listing = list_my_matches(
            first,
            status="unmatched",
        )

        assert (
            old_listing["returned"]
            == 1
        )


def test_non_member_cannot_get_match(
    app,
    matching_users,
):
    first = matching_users()
    second = matching_users()
    outsider = matching_users()

    with app.app_context():
        created = create_match_if_absent(
            first_user_id=first,
            second_user_id=second,
            matched_by=first,
        )

        with pytest.raises(
            MatchingNotFoundError
        ) as exc_info:
            get_my_match(
                user_id=outsider,
                match_id=(
                    created[
                        "match"
                    ][
                        "_id"
                    ]
                ),
            )

        assert (
            exc_info.value.code
            == "MATCH_NOT_FOUND"
        )


@pytest.mark.parametrize(
    "status",
    [
        "",
        "pending",
        "deleted",
        None,
    ],
)
def test_invalid_match_status_is_rejected(
    app,
    matching_users,
    status,
):
    user_id = matching_users()

    with app.app_context():
        with pytest.raises(
            MatchingValidationError
        ) as exc_info:
            list_my_matches(
                user_id,
                status=status,
            )

        assert (
            exc_info.value.code
            == "INVALID_MATCH_STATUS"
        )


@pytest.mark.parametrize(
    "limit",
    [
        0,
        101,
        "abc",
    ],
)
def test_invalid_match_limit_is_rejected(
    app,
    matching_users,
    limit,
):
    user_id = matching_users()

    with app.app_context():
        with pytest.raises(
            MatchingValidationError
        ) as exc_info:
            list_my_matches(
                user_id,
                limit=limit,
            )

        assert (
            exc_info.value.code
            == "INVALID_LIMIT"
        )


def test_invalid_profile_action_is_rejected(
    app,
    matching_users,
):
    actor = matching_users()
    target = matching_users()

    with app.app_context():
        with pytest.raises(
            MatchingValidationError
        ) as exc_info:
            submit_profile_action(
                actor_id=actor,
                target_id=target,
                action="block",
            )

        assert (
            exc_info.value.code
            == "INVALID_PROFILE_ACTION"
        )


def test_missing_target_user_is_rejected(
    app,
    matching_users,
):
    actor = matching_users()
    missing = ObjectId()

    with app.app_context():
        with pytest.raises(
            MatchingNotFoundError
        ) as exc_info:
            submit_profile_action(
                actor_id=actor,
                target_id=missing,
                action="like",
            )

        assert (
            exc_info.value.code
            == "USER_NOT_FOUND"
        )
