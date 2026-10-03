from flask import Blueprint

from app.api.v1.auth.routes import (
    auth_bp,
)
from app.api.v1.onboarding.routes import (
    onboarding_bp,
)
from app.api.v1.profiles.routes import (
    profiles_bp,
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

api_v1_bp.register_blueprint(
    profiles_bp
)

api_v1_bp.register_blueprint(
    onboarding_bp
)


__all__ = [
    "api_v1_bp",
]
