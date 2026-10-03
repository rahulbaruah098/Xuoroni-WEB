import uuid

from flask import g, request


def register_middleware(app):
    @app.before_request
    def attach_request_id():
        incoming_request_id = request.headers.get(
            "X-Request-ID"
        )

        g.request_id = (
            incoming_request_id.strip()
            if incoming_request_id
            else str(uuid.uuid4())
        )

    @app.after_request
    def add_request_id_header(response):
        request_id = getattr(
            g,
            "request_id",
            None,
        )

        if request_id:
            response.headers["X-Request-ID"] = request_id

        return response
