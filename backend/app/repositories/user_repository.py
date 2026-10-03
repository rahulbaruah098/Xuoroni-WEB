from datetime import datetime, timezone

from bson import ObjectId

from app.extensions import mongo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_object_id(value):
    if isinstance(value, ObjectId):
        return value

    try:
        return ObjectId(str(value))
    except Exception:
        return None


def create_user(
    *,
    account_status: str = "active",
    onboarding_status: str = "not_started",
):
    now = utc_now()

    document = {
        "account_status": account_status,
        "onboarding_status": onboarding_status,
        "created_at": now,
        "updated_at": now,
        "last_login_at": now,
    }

    result = mongo.db.users.insert_one(
        document
    )

    return mongo.db.users.find_one(
        {"_id": result.inserted_id}
    )


def get_user_by_id(user_id):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return None

    return mongo.db.users.find_one(
        {"_id": object_id}
    )


def update_last_login(
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

    result = mongo.db.users.update_one(
        {
            "_id": object_id,
        },
        {
            "$set": {
                "last_login_at": timestamp,
                "updated_at": timestamp,
            }
        },
    )

    return result.matched_count == 1


def set_account_status(
    user_id,
    status: str,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return False

    result = mongo.db.users.update_one(
        {
            "_id": object_id,
        },
        {
            "$set": {
                "account_status": status,
                "updated_at": utc_now(),
            }
        },
    )

    return result.matched_count == 1


def delete_user(user_id):
    """
    Internal rollback helper.

    Used only when user creation succeeds but identity
    creation loses a uniqueness race.
    """
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return False

    result = mongo.db.users.delete_one(
        {
            "_id": object_id,
        }
    )

    return result.deleted_count == 1


def set_onboarding_status(
    user_id,
    status: str,
):
    allowed = {
        "not_started",
        "in_progress",
        "completed",
    }

    if status not in allowed:
        raise ValueError(
            "Invalid onboarding status."
        )

    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return False

    result = mongo.db.users.update_one(
        {
            "_id": object_id,
        },
        {
            "$set": {
                "onboarding_status": status,
                "updated_at": utc_now(),
            }
        },
    )

    return result.matched_count == 1
