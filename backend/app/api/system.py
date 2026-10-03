from flask import Blueprint, jsonify

from app.extensions import mongo, redis_store


system_bp = Blueprint(
    "system",
    __name__,
)


def _mongodb_ready() -> bool:
    try:
        mongo.cx.admin.command("ping")
        return True
    except Exception:
        return False


def _redis_ready() -> bool:
    return redis_store.ping()


@system_bp.get("/health")
def health():
    """
    Liveness endpoint.

    Confirms that the Flask process is alive.
    External dependencies are intentionally not checked here.
    """
    return jsonify(
        {
            "status": "ok",
            "service": "xuoroni-backend",
        }
    ), 200


@system_bp.get("/ready")
def ready():
    """
    Readiness endpoint.

    Confirms that critical dependencies required to serve
    application traffic are available.
    """
    dependencies = {
        "mongodb": _mongodb_ready(),
        "redis": _redis_ready(),
    }

    is_ready = all(
        dependencies.values()
    )

    return jsonify(
        {
            "status": (
                "ready"
                if is_ready
                else "not_ready"
            ),
            "dependencies": dependencies,
        }
    ), (
        200
        if is_ready
        else 503
    )
