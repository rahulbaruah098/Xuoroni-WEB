from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.extensions import mongo
from app.schemas.profile import (
    build_discovery_preferences_document,
    build_profile_document,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_object_id(value):
    if isinstance(value, ObjectId):
        return value

    try:
        return ObjectId(
            str(value)
        )
    except Exception:
        return None


def create_profile(
    user_id,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        raise ValueError(
            "Invalid user ID."
        )

    document = build_profile_document(
        user_id=object_id
    )

    result = mongo.db.profiles.insert_one(
        document
    )

    return mongo.db.profiles.find_one(
        {
            "_id": result.inserted_id,
        }
    )


def get_profile_by_user_id(
    user_id,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return None

    return mongo.db.profiles.find_one(
        {
            "user_id": object_id,
        }
    )


def ensure_profile(
    user_id,
):
    existing = get_profile_by_user_id(
        user_id
    )

    if existing is not None:
        return existing

    try:
        return create_profile(
            user_id
        )

    except DuplicateKeyError:
        # Handles a concurrent first-login/onboarding request.
        return get_profile_by_user_id(
            user_id
        )


def create_discovery_preferences(
    user_id,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        raise ValueError(
            "Invalid user ID."
        )

    document = (
        build_discovery_preferences_document(
            user_id=object_id
        )
    )

    result = (
        mongo.db.discovery_preferences.insert_one(
            document
        )
    )

    return (
        mongo.db.discovery_preferences.find_one(
            {
                "_id": result.inserted_id,
            }
        )
    )


def get_discovery_preferences(
    user_id,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return None

    return (
        mongo.db.discovery_preferences.find_one(
            {
                "user_id": object_id,
            }
        )
    )


def ensure_discovery_preferences(
    user_id,
):
    existing = get_discovery_preferences(
        user_id
    )

    if existing is not None:
        return existing

    try:
        return create_discovery_preferences(
            user_id
        )

    except DuplicateKeyError:
        return get_discovery_preferences(
            user_id
        )


def touch_profile_activity(
    user_id,
    *,
    at=None,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return False

    timestamp = at or utc_now()

    result = mongo.db.profiles.update_one(
        {
            "user_id": object_id,
        },
        {
            "$set": {
                "last_active_at": timestamp,
                "updated_at": timestamp,
            }
        },
    )

    return result.matched_count == 1


def _validate_update_paths(
    updates,
):
    protected = {
        "_id",
        "user_id",
        "created_at",
    }

    for path in updates:
        root = path.split(
            ".",
            1,
        )[0]

        if (
            root in protected
            or path.startswith(
                "$"
            )
            or ".$" in path
        ):
            raise ValueError(
                "Protected profile field update."
            )


def update_profile_fields(
    user_id,
    updates,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return None

    if not updates:
        return get_profile_by_user_id(
            object_id
        )

    _validate_update_paths(
        updates
    )

    fields = dict(
        updates
    )

    fields[
        "updated_at"
    ] = utc_now()

    result = mongo.db.profiles.update_one(
        {
            "user_id": object_id,
        },
        {
            "$set": fields,
        },
    )

    if result.matched_count != 1:
        return None

    return get_profile_by_user_id(
        object_id
    )


def update_discovery_preferences_fields(
    user_id,
    updates,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return None

    if not updates:
        return get_discovery_preferences(
            object_id
        )

    _validate_update_paths(
        updates
    )

    fields = dict(
        updates
    )

    fields[
        "updated_at"
    ] = utc_now()

    result = (
        mongo.db.discovery_preferences.update_one(
            {
                "user_id": object_id,
            },
            {
                "$set": fields,
            },
        )
    )

    if result.matched_count != 1:
        return None

    return get_discovery_preferences(
        object_id
    )
