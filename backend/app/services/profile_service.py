"""Profile and onboarding business operations."""

from copy import deepcopy
from datetime import date, datetime, timezone

from bson import ObjectId

from app.repositories.profile_repository import (
    ensure_discovery_preferences,
    ensure_profile,
    update_discovery_preferences_fields,
    update_profile_fields,
)
from app.repositories.user_repository import (
    set_onboarding_status,
)
from app.schemas.profile import (
    ONBOARDING_STEPS,
)
from app.services.profile_validation import (
    calculate_profile_completion,
    validate_discovery_patch,
    validate_profile_patch,
)


OWNER_PROFILE_FIELDS = (
    "_id",
    "user_id",
    "profile_status",
    "visibility",
    "onboarding_status",
    "onboarding",
    "profile_completion_percent",
    "display_name",
    "first_name",
    "last_name",
    "surname_searchable",
    "birth_date",
    "gender_identity",
    "gender_custom_label",
    "pronouns",
    "current_city",
    "hometown",
    "culture",
    "languages",
    "bio",
    "interests",
    "prompts",
    "height_cm",
    "education",
    "work",
    "lifestyle",
    "relationship_intentions",
    "media",
    "primary_media_id",
    "privacy",
    "verification_summary",
    "last_active_at",
    "created_at",
    "updated_at",
)

OWNER_DISCOVERY_FIELDS = (
    "_id",
    "user_id",
    "interested_in",
    "age_min",
    "age_max",
    "distance_enabled",
    "max_distance_km",
    "relationship_intentions",
    "communities",
    "languages",
    "surname_filter",
    "created_at",
    "updated_at",
)


class ProfileLifecycleError(RuntimeError):
    def __init__(
        self,
        code,
        message,
    ):
        self.code = code
        self.message = message

        super().__init__(
            message
        )


def utc_now():
    return datetime.now(
        timezone.utc
    )


def _ensure_profile_editable(
    profile,
):
    if (
        profile.get(
            "profile_status"
        )
        == "disabled"
    ):
        raise ProfileLifecycleError(
            "PROFILE_DISABLED",
            (
                "This profile is currently "
                "disabled and cannot be edited."
            ),
        )


def _apply_dotted_updates(
    document,
    updates,
):
    document = deepcopy(
        document
    )

    for path, value in (
        updates.items()
    ):
        parts = path.split(
            "."
        )

        target = document

        for part in parts[:-1]:
            current = target.get(
                part
            )

            if not isinstance(
                current,
                dict,
            ):
                current = {}
                target[part] = current

            target = current

        target[
            parts[-1]
        ] = value

    return document


def _json_safe_value(
    value,
):
    if isinstance(
        value,
        ObjectId,
    ):
        return str(
            value
        )

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    if isinstance(
        value,
        date,
    ):
        return value.isoformat()

    if isinstance(
        value,
        dict,
    ):
        return {
            key: _json_safe_value(
                item
            )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        list,
    ):
        return [
            _json_safe_value(
                item
            )
            for item in value
        ]

    return value


def _allowlisted_document(
    document,
    allowed_fields,
):
    return {
        field: deepcopy(
            document[field]
        )
        for field in allowed_fields
        if field in document
    }


def serialize_profile_for_owner(
    profile,
):
    if profile is None:
        return None

    payload = _allowlisted_document(
        profile,
        OWNER_PROFILE_FIELDS,
    )

    return _json_safe_value(
        payload
    )


def serialize_discovery_preferences_for_owner(
    preferences,
):
    if preferences is None:
        return None

    payload = _allowlisted_document(
        preferences,
        OWNER_DISCOVERY_FIELDS,
    )

    return _json_safe_value(
        payload
    )


def get_my_profile(
    user_id,
):
    return ensure_profile(
        user_id
    )


def get_my_discovery_preferences(
    user_id,
):
    return ensure_discovery_preferences(
        user_id
    )


def update_my_profile(
    user_id,
    patch,
    *,
    today=None,
):
    profile = ensure_profile(
        user_id
    )

    _ensure_profile_editable(
        profile
    )

    updates = validate_profile_patch(
        patch,
        existing_profile=profile,
        today=today,
    )

    candidate = (
        _apply_dotted_updates(
            profile,
            updates,
        )
    )

    completion = (
        calculate_profile_completion(
            candidate
        )
    )

    updates[
        "profile_completion_percent"
    ] = completion

    current_status = profile.get(
        "onboarding_status",
        "not_started",
    )

    if (
        current_status
        == "not_started"
    ):
        current_status = (
            "in_progress"
        )

        onboarding = (
            profile.get(
                "onboarding"
            )
            or {}
        )

        if not onboarding.get(
            "started_at"
        ):
            updates[
                "onboarding.started_at"
            ] = utc_now()

    # Data completion alone must not complete
    # onboarding. The review step is explicit.
    if (
        current_status
        != "completed"
    ):
        current_status = (
            "in_progress"
        )

        updates[
            "profile_status"
        ] = "draft"

    updates[
        "onboarding_status"
    ] = current_status

    updated = update_profile_fields(
        user_id,
        updates,
    )

    if updated is None:
        raise RuntimeError(
            "Profile could not be updated."
        )

    set_onboarding_status(
        user_id,
        current_status,
    )

    return updated


def update_my_discovery_preferences(
    user_id,
    patch,
):
    profile = ensure_profile(
        user_id
    )

    _ensure_profile_editable(
        profile
    )

    preferences = (
        ensure_discovery_preferences(
            user_id
        )
    )

    updates = (
        validate_discovery_patch(
            patch,
            existing_preferences=(
                preferences
            ),
        )
    )

    updated = (
        update_discovery_preferences_fields(
            user_id,
            updates,
        )
    )

    if updated is None:
        raise RuntimeError(
            (
                "Discovery preferences "
                "could not be updated."
            )
        )

    return updated


def _ordered_completed_steps(
    values,
):
    completed = set(
        values
        or []
    )

    return [
        step
        for step in ONBOARDING_STEPS
        if step in completed
    ]


def _next_incomplete_step(
    completed_steps,
):
    completed = set(
        completed_steps
    )

    for step in ONBOARDING_STEPS:
        if step not in completed:
            return step

    return None


def get_onboarding_state(
    user_id,
):
    profile = ensure_profile(
        user_id
    )

    onboarding = (
        profile.get(
            "onboarding"
        )
        or {}
    )

    completed_steps = (
        _ordered_completed_steps(
            onboarding.get(
                "completed_steps",
                [],
            )
        )
    )

    return _json_safe_value(
        {
            "status": profile.get(
                "onboarding_status",
                "not_started",
            ),
            "current_step": (
                onboarding.get(
                    "current_step"
                )
                or _next_incomplete_step(
                    completed_steps
                )
                or ONBOARDING_STEPS[-1]
            ),
            "completed_steps": (
                completed_steps
            ),
            "started_at": onboarding.get(
                "started_at"
            ),
            "completed_at": onboarding.get(
                "completed_at"
            ),
            "profile_completion_percent": (
                profile.get(
                    "profile_completion_percent",
                    0,
                )
            ),
            "steps": list(
                ONBOARDING_STEPS
            ),
        }
    )


def update_onboarding_progress(
    user_id,
    *,
    current_step=None,
    completed_step=None,
):
    profile = ensure_profile(
        user_id
    )

    _ensure_profile_editable(
        profile
    )

    onboarding = (
        profile.get(
            "onboarding"
        )
        or {}
    )

    if (
        current_step is not None
        and current_step
        not in ONBOARDING_STEPS
    ):
        raise ValueError(
            "Invalid onboarding step."
        )

    if (
        completed_step is not None
        and completed_step
        not in ONBOARDING_STEPS
    ):
        raise ValueError(
            (
                "Invalid completed "
                "onboarding step."
            )
        )

    completed_steps = (
        _ordered_completed_steps(
            onboarding.get(
                "completed_steps",
                [],
            )
        )
    )

    existing_step = (
        onboarding.get(
            "current_step"
        )
        or _next_incomplete_step(
            completed_steps
        )
        or ONBOARDING_STEPS[-1]
    )

    if (
        completed_step is not None
        and completed_step
        not in completed_steps
    ):
        if (
            completed_step
            != existing_step
        ):
            raise ValueError(
                (
                    "Onboarding steps must "
                    "be completed in order."
                )
            )

        if (
            completed_step
            == "review"
            and profile.get(
                "profile_completion_percent",
                0,
            )
            < 100
        ):
            raise ValueError(
                (
                    "Complete the required "
                    "profile information "
                    "before finishing review."
                )
            )

        completed_steps.append(
            completed_step
        )

        completed_steps = (
            _ordered_completed_steps(
                completed_steps
            )
        )

    next_step = (
        _next_incomplete_step(
            completed_steps
        )
    )

    if current_step is not None:
        if (
            current_step
            not in completed_steps
            and current_step
            != next_step
        ):
            raise ValueError(
                (
                    "Cannot skip unfinished "
                    "onboarding steps."
                )
            )

        selected_step = (
            current_step
        )

    else:
        selected_step = (
            next_step
            or ONBOARDING_STEPS[-1]
        )

    all_steps_complete = (
        len(
            completed_steps
        )
        == len(
            ONBOARDING_STEPS
        )
    )

    completion_percent = (
        profile.get(
            "profile_completion_percent",
            0,
        )
    )

    fully_complete = (
        all_steps_complete
        and completion_percent == 100
    )

    updates = {
        "onboarding.current_step": (
            selected_step
        ),
        "onboarding.completed_steps": (
            completed_steps
        ),
    }

    started_at = onboarding.get(
        "started_at"
    )

    if not started_at:
        updates[
            "onboarding.started_at"
        ] = utc_now()

    if fully_complete:
        new_status = "completed"

        updates[
            "onboarding.completed_at"
        ] = (
            onboarding.get(
                "completed_at"
            )
            or utc_now()
        )

        updates[
            "profile_status"
        ] = "active"

    else:
        new_status = "in_progress"

        updates[
            "profile_status"
        ] = "draft"

    updates[
        "onboarding_status"
    ] = new_status

    updated = update_profile_fields(
        user_id,
        updates,
    )

    if updated is None:
        raise RuntimeError(
            (
                "Onboarding progress "
                "could not be updated."
            )
        )

    set_onboarding_status(
        user_id,
        new_status,
    )

    return get_onboarding_state(
        user_id
    )
