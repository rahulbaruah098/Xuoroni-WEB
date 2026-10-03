import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class BaseConfig:
    APP_NAME = "Xuoroni"

    API_VERSION = os.getenv(
        "API_VERSION",
        "v1",
    )

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-only-change-me",
    )

    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb://localhost:27017/xuoroni",
    )

    REDIS_URL = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0",
    )

    FRONTEND_ORIGIN = os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:5173",
    )

    SOCKETIO_MESSAGE_QUEUE = os.getenv(
        "SOCKETIO_MESSAGE_QUEUE",
        "",
    )

    CELERY_BROKER_URL = os.getenv(
        "CELERY_BROKER_URL",
        "redis://localhost:6379/1",
    )

    CELERY_RESULT_BACKEND = os.getenv(
        "CELERY_RESULT_BACKEND",
        "redis://localhost:6379/2",
    )

    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        "dev-only-jwt-secret-change-me",
    )

    JWT_ACCESS_TOKEN_MINUTES = int(
        os.getenv(
            "JWT_ACCESS_TOKEN_MINUTES",
            "15",
        )
    )

    JWT_REFRESH_TOKEN_DAYS = int(
        os.getenv(
            "JWT_REFRESH_TOKEN_DAYS",
            "30",
        )
    )

    GOOGLE_CLIENT_ID = os.getenv(
        "GOOGLE_CLIENT_ID",
        "",
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    JSON_SORT_KEYS = False

    MAX_CONTENT_LENGTH = int(
        os.getenv(
            "MAX_CONTENT_LENGTH",
            str(20 * 1024 * 1024),
        )
    )

    REQUEST_ID_HEADER = "X-Request-ID"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False

    SESSION_COOKIE_SECURE = False

    EXPOSE_DEV_OTP = _env_bool(
        "EXPOSE_DEV_OTP",
        True,
    )


class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True

    SESSION_COOKIE_SECURE = False

    EXPOSE_DEV_OTP = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False

    SESSION_COOKIE_SECURE = True

    EXPOSE_DEV_OTP = False


def get_config():
    environment = os.getenv(
        "APP_ENV",
        os.getenv(
            "FLASK_ENV",
            "development",
        ),
    ).strip().lower()

    if environment == "production":
        return ProductionConfig

    if environment == "testing":
        return TestingConfig

    return DevelopmentConfig
