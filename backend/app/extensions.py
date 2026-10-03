from typing import Optional

from flask import Flask
from flask_cors import CORS
from flask_pymongo import PyMongo
from flask_socketio import SocketIO
from redis import Redis


mongo = PyMongo()
cors = CORS()

socketio = SocketIO(
    async_mode="threading",
)


class RedisExtension:
    def __init__(self):
        self.client: Optional[Redis] = None

    def init_app(self, app: Flask) -> None:
        self.client = Redis.from_url(
            app.config["REDIS_URL"],
            decode_responses=True,
        )

        app.extensions["xuoroni_redis"] = self

    def get_client(self) -> Redis:
        if self.client is None:
            raise RuntimeError(
                "Redis has not been initialized."
            )

        return self.client

    def ping(self) -> bool:
        try:
            return bool(
                self.get_client().ping()
            )
        except Exception:
            return False


redis_store = RedisExtension()


def init_extensions(app: Flask) -> None:
    mongo.init_app(app)

    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    app.config["FRONTEND_ORIGIN"]
                ]
            }
        },
        supports_credentials=True,
    )

    redis_store.init_app(app)

    socketio_options = {
        "cors_allowed_origins": [
            app.config["FRONTEND_ORIGIN"]
        ],
        "async_mode": "threading",
    }

    message_queue = app.config.get(
        "SOCKETIO_MESSAGE_QUEUE"
    )

    if message_queue:
        socketio_options["message_queue"] = (
            message_queue
        )

    socketio.init_app(
        app,
        **socketio_options,
    )
