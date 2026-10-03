import csv
import io
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint,
    Response,
    jsonify,
    request,
    session,
)
from werkzeug.security import check_password_hash

from app.extensions import mongo


legacy_api_bp = Blueprint(
    "legacy_api",
    __name__,
)


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get(
            "admin_id"
        ):
            return jsonify(
                {
                    "error": (
                        "Please sign in to continue."
                    )
                }
            ), 401

        return fn(
            *args,
            **kwargs,
        )

    return wrapped


def serialize(doc):
    return {
        "id": str(
            doc.get("_id")
        ),
        **{
            key: value
            for key, value
            in doc.items()
            if key != "_id"
        },
    }


@legacy_api_bp.get("/api/health")
def legacy_health():
    try:
        mongo.cx.admin.command(
            "ping"
        )

        return jsonify(
            {
                "status": "ok",
                "database": "connected",
            }
        )

    except Exception:
        return jsonify(
            {
                "status": "degraded",
                "database": "unavailable",
            }
        ), 503


@legacy_api_bp.get(
    "/api/public/settings"
)
def public_settings():
    settings = (
        mongo.db.settings.find_one(
            {
                "key": "launch",
            }
        )
        or {}
    )

    return jsonify(
        {
            "launch_at": settings.get(
                "launch_at"
            )
        }
    )


@legacy_api_bp.post("/api/testers")
def create_tester():
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    name = str(
        data.get(
            "name",
            "",
        )
    ).strip()

    email = str(
        data.get(
            "email",
            "",
        )
    ).strip().lower()

    city = str(
        data.get(
            "city",
            "",
        )
    ).strip()

    if not all(
        (
            name,
            email,
            city,
        )
    ):
        return jsonify(
            {
                "error": (
                    "Please enter your name, "
                    "email, and city."
                )
            }
        ), 400

    if (
        len(name) > 100
        or len(email) > 254
        or len(city) > 100
        or "@" not in email
    ):
        return jsonify(
            {
                "error": (
                    "Please check the details "
                    "and try again."
                )
            }
        ), 400

    now = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    try:
        mongo.db.testers.insert_one(
            {
                "name": name,
                "email": email,
                "city": city,
                "created_at": now,
            }
        )

    except Exception as exc:
        if getattr(
            exc,
            "code",
            None,
        ) == 11000:
            return jsonify(
                {
                    "error": (
                        "That email is already registered."
                    )
                }
            ), 409

        raise

    return jsonify(
        {
            "message": (
                "You're on the list. "
                "We'll be in touch."
            )
        }
    ), 201


@legacy_api_bp.post(
    "/api/admin/login"
)
def admin_login():
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    email = str(
        data.get(
            "email",
            "",
        )
    ).strip().lower()

    admin = (
        mongo.db.admins.find_one(
            {
                "email": email,
            }
        )
    )

    if (
        not admin
        or not check_password_hash(
            admin[
                "password_hash"
            ],
            str(
                data.get(
                    "password",
                    "",
                )
            ),
        )
    ):
        return jsonify(
            {
                "error": (
                    "Email or password is incorrect."
                )
            }
        ), 401

    session.clear()

    session["admin_id"] = str(
        admin["_id"]
    )

    session["admin_email"] = (
        admin["email"]
    )

    return jsonify(
        {
            "email": admin["email"],
        }
    )


@legacy_api_bp.post(
    "/api/admin/logout"
)
@admin_required
def admin_logout():
    session.clear()

    return jsonify(
        {
            "message": "Signed out.",
        }
    )


@legacy_api_bp.get(
    "/api/admin/testers"
)
@admin_required
def list_testers():
    docs = (
        mongo.db.testers.find()
        .sort(
            "created_at",
            -1,
        )
    )

    return jsonify(
        [
            serialize(doc)
            for doc in docs
        ]
    )


@legacy_api_bp.get(
    "/api/admin/testers.csv"
)
@admin_required
def export_testers():
    output = io.StringIO()

    writer = csv.writer(
        output
    )

    writer.writerow(
        [
            "Name",
            "Email",
            "City",
            "Registered at",
        ]
    )

    for doc in (
        mongo.db.testers.find()
        .sort(
            "created_at",
            -1,
        )
    ):
        writer.writerow(
            [
                doc.get(
                    "name",
                    "",
                ),
                doc.get(
                    "email",
                    "",
                ),
                doc.get(
                    "city",
                    "",
                ),
                doc.get(
                    "created_at",
                    "",
                ),
            ]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; "
                "filename=xuoroni-testers.csv"
            )
        },
    )


@legacy_api_bp.put(
    "/api/admin/settings/countdown"
)
@admin_required
def update_countdown():
    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    launch_at = data.get(
        "launch_at"
    )

    if launch_at:
        try:
            parsed = (
                datetime.fromisoformat(
                    launch_at.replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

            if parsed.tzinfo is None:
                return jsonify(
                    {
                        "error": (
                            "Choose a date and time "
                            "with a timezone."
                        )
                    }
                ), 400

            launch_at = (
                parsed.astimezone(
                    timezone.utc
                ).isoformat()
            )

        except (
            ValueError,
            AttributeError,
        ):
            return jsonify(
                {
                    "error": (
                        "Enter a valid launch "
                        "date and time."
                    )
                }
            ), 400

    mongo.db.settings.update_one(
        {
            "key": "launch",
        },
        {
            "$set": {
                "launch_at": launch_at,
                "updated_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }
        },
        upsert=True,
    )

    return jsonify(
        {
            "launch_at": launch_at,
        }
    )
