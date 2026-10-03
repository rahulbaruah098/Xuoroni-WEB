from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ReturnDocument

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


def create_session(
    *,
    user_id,
    session_id: str,
    family_id: str,
    refresh_token_hash: str,
    expires_at,
    parent_session_id=None,
    metadata=None,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        raise ValueError(
            "Invalid user ID."
        )

    now = utc_now()

    document = {
        "user_id": object_id,
        "session_id": session_id,
        "family_id": family_id,
        "refresh_token_hash": refresh_token_hash,
        "parent_session_id": parent_session_id,
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_at,
        "revoked_at": None,
        "revoke_reason": None,
        "replaced_by_session_id": None,
        "metadata": metadata or {},
    }

    result = mongo.db.auth_sessions.insert_one(
        document
    )

    return mongo.db.auth_sessions.find_one(
        {
            "_id": result.inserted_id,
        }
    )


def get_session_by_id(
    session_id: str,
):
    return mongo.db.auth_sessions.find_one(
        {
            "session_id": session_id,
        }
    )


def get_session_by_refresh_hash(
    refresh_token_hash: str,
):
    return mongo.db.auth_sessions.find_one(
        {
            "refresh_token_hash": refresh_token_hash,
        }
    )


def claim_session_for_rotation(
    *,
    refresh_token_hash: str,
    replacement_session_id: str,
):
    now = utc_now()

    return mongo.db.auth_sessions.find_one_and_update(
        {
            "refresh_token_hash": refresh_token_hash,
            "revoked_at": None,
            "expires_at": {
                "$gt": now,
            },
        },
        {
            "$set": {
                "revoked_at": now,
                "revoke_reason": "rotated",
                "replaced_by_session_id": (
                    replacement_session_id
                ),
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.BEFORE,
    )


def revoke_session(
    session_id: str,
    *,
    reason: str = "revoked",
):
    now = utc_now()

    result = mongo.db.auth_sessions.update_one(
        {
            "session_id": session_id,
            "revoked_at": None,
        },
        {
            "$set": {
                "revoked_at": now,
                "revoke_reason": reason,
                "updated_at": now,
            }
        },
    )

    return result.modified_count == 1


def revoke_session_by_refresh_hash(
    refresh_token_hash: str,
    *,
    reason: str = "logout",
):
    now = utc_now()

    result = mongo.db.auth_sessions.update_one(
        {
            "refresh_token_hash": refresh_token_hash,
            "revoked_at": None,
        },
        {
            "$set": {
                "revoked_at": now,
                "revoke_reason": reason,
                "updated_at": now,
            }
        },
    )

    return result.modified_count == 1


def revoke_family(
    family_id: str,
    *,
    reason: str = "security_revoke",
):
    now = utc_now()

    result = mongo.db.auth_sessions.update_many(
        {
            "family_id": family_id,
            "revoked_at": None,
        },
        {
            "$set": {
                "revoked_at": now,
                "revoke_reason": reason,
                "updated_at": now,
            }
        },
    )

    return result.modified_count


def revoke_all_user_sessions(
    user_id,
    *,
    reason: str = "logout_all",
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return 0

    now = utc_now()

    result = mongo.db.auth_sessions.update_many(
        {
            "user_id": object_id,
            "revoked_at": None,
        },
        {
            "$set": {
                "revoked_at": now,
                "revoke_reason": reason,
                "updated_at": now,
            }
        },
    )

    return result.modified_count
