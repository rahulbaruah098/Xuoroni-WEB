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

    JWT_ALGORITHM = "HS256"

    JWT_ISSUER = os.getenv(
        "JWT_ISSUER",
        "xuoroni-backend",
    )

    JWT_AUDIENCE = os.getenv(
        "JWT_AUDIENCE",
        "xuoroni-mobile",
    )

    GOOGLE_CLIENT_ID = os.getenv(
        "GOOGLE_CLIENT_ID",
        "",
    )

    # SMTP / Email Authentication
    SMTP_HOST = os.getenv(
        "SMTP_HOST",
        "",
    )

    SMTP_PORT = int(
        os.getenv(
            "SMTP_PORT",
            "587",
        )
    )

    SMTP_USERNAME = os.getenv(
        "SMTP_USERNAME",
        "",
    )

    SMTP_PASSWORD = os.getenv(
        "SMTP_PASSWORD",
        "",
    )

    SMTP_FROM_EMAIL = os.getenv(
        "SMTP_FROM_EMAIL",
        "",
    )

    SMTP_FROM_NAME = os.getenv(
        "SMTP_FROM_NAME",
        "Xuoroni",
    )

    SMTP_USE_TLS = (
        os.getenv(
            "SMTP_USE_TLS",
            "true",
        ).strip().lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )

    SMTP_TIMEOUT_SECONDS = int(
        os.getenv(
            "SMTP_TIMEOUT_SECONDS",
            "15",
        )
    )

    # Email OTP uses its own Redis namespace so it
    # can never collide with mobile OTP records.
    EMAIL_OTP_KEY_PREFIX = os.getenv(
        "EMAIL_OTP_KEY_PREFIX",
        "xuoroni:email-otp",
    )

    # Development only. Never expose this in production.
    DEV_EMAIL_OTP_CODE = os.getenv(
        "DEV_EMAIL_OTP_CODE",
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

    OTP_LENGTH = int(
        os.getenv(
            "OTP_LENGTH",
            "6",
        )
    )

    OTP_TTL_SECONDS = int(
        os.getenv(
            "OTP_TTL_SECONDS",
            "300",
        )
    )

    OTP_RESEND_COOLDOWN_SECONDS = int(
        os.getenv(
            "OTP_RESEND_COOLDOWN_SECONDS",
            "60",
        )
    )

    OTP_MAX_ATTEMPTS = int(
        os.getenv(
            "OTP_MAX_ATTEMPTS",
            "5",
        )
    )

    OTP_REQUEST_WINDOW_SECONDS = int(
        os.getenv(
            "OTP_REQUEST_WINDOW_SECONDS",
            "3600",
        )
    )

    OTP_MAX_REQUESTS_PER_WINDOW = int(
        os.getenv(
            "OTP_MAX_REQUESTS_PER_WINDOW",
            "5",
        )
    )

    OTP_KEY_PREFIX = os.getenv(
        "OTP_KEY_PREFIX",
        "xuoroni:otp",
    )

    OTP_HASH_SECRET = os.getenv(
        "OTP_HASH_SECRET",
        JWT_SECRET_KEY,
    )

    DEV_OTP_CODE = os.getenv(
        "DEV_OTP_CODE",
        "",
    )

    AUTO_ENSURE_INDEXES = _env_bool(
        "AUTO_ENSURE_INDEXES",
        True,
    )


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
    AUTO_ENSURE_INDEXES = False


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
