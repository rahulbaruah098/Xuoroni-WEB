from flask import Blueprint

from app.api.v1.auth.routes import (
    auth_bp,
)


api_v1_bp = Blueprint(
    "api_v1",
    __name__,
    url_prefix="/api/v1",
)

api_v1_bp.register_blueprint(
    auth_bp,
    url_prefix="/auth",
)


__all__ = [
    "api_v1_bp",
]
