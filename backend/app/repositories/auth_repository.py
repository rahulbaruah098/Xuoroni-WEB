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


def create_identity(
    *,
    user_id,
    provider: str,
    provider_subject: str,
    phone_normalized=None,
    email_normalized=None,
    verified: bool = True,
    metadata=None,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        raise ValueError(
            "Invalid user ID."
        )

    provider = str(
        provider
    ).strip().lower()

    provider_subject = str(
        provider_subject
    ).strip()

    if not provider:
        raise ValueError(
            "Authentication provider is required."
        )

    if not provider_subject:
        raise ValueError(
            "Provider subject is required."
        )

    now = utc_now()

    document = {
        "user_id": object_id,
        "provider": provider,
        "provider_subject": provider_subject,
        "verified": bool(
            verified
        ),
        "verified_at": (
            now
            if verified
            else None
        ),
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {},
    }

    if phone_normalized:
        document["phone_normalized"] = str(
            phone_normalized
        ).strip()

    if email_normalized:
        document["email_normalized"] = str(
            email_normalized
        ).strip().lower()

    result = mongo.db.auth_identities.insert_one(
        document
    )

    return mongo.db.auth_identities.find_one(
        {"_id": result.inserted_id}
    )


def get_identity(
    *,
    provider: str,
    provider_subject: str,
):
    return mongo.db.auth_identities.find_one(
        {
            "provider": str(
                provider
            ).strip().lower(),
            "provider_subject": str(
                provider_subject
            ).strip(),
        }
    )


def get_identity_by_phone(
    phone_normalized: str,
):
    if not phone_normalized:
        return None

    return mongo.db.auth_identities.find_one(
        {
            "phone_normalized": str(
                phone_normalized
            ).strip(),
        }
    )


def get_identity_by_email(
    email_normalized: str,
):
    if not email_normalized:
        return None

    return mongo.db.auth_identities.find_one(
        {
            "email_normalized": str(
                email_normalized
            ).strip().lower(),
        }
    )


def get_identities_for_user(
    user_id,
):
    object_id = _to_object_id(
        user_id
    )

    if object_id is None:
        return []

    return list(
        mongo.db.auth_identities.find(
            {
                "user_id": object_id,
            }
        ).sort(
            "created_at",
            1,
        )
    )
