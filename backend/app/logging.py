import logging
import os
import sys


def configure_logging(app):
    level_name = os.getenv(
        "LOG_LEVEL",
        "DEBUG" if app.debug else "INFO",
    ).upper()

    level = getattr(
        logging,
        level_name,
        logging.INFO,
    )

    handler = logging.StreamHandler(
        sys.stdout
    )

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    handler.setFormatter(
        formatter
    )

    root_logger = logging.getLogger()

    if not root_logger.handlers:
        root_logger.addHandler(
            handler
        )

    root_logger.setLevel(
        level
    )

    app.logger.setLevel(
        level
    )

    # Reduce low-level third-party log noise.
    logging.getLogger(
        "pymongo"
    ).setLevel(logging.WARNING)

    logging.getLogger(
        "redis"
    ).setLevel(logging.WARNING)

    logging.getLogger(
        "urllib3"
    ).setLevel(logging.WARNING)

    return app.logger
