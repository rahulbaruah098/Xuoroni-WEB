from flask import (
    g,
    has_request_context,
    jsonify,
)


def error_response(
    code: str,
    message: str,
    status_code: int,
    *,
    details=None,
    request_id=None,
):
    if (
        request_id is None
        and has_request_context()
    ):
        request_id = getattr(
            g,
            "request_id",
            None,
        )

    payload = {
        "code": code,
        "message": message,
    }

    if details is not None:
        payload["details"] = details

    if request_id:
        payload["request_id"] = (
            request_id
        )

    return jsonify(
        payload
    ), status_code


def register_error_handlers(app):
    @app.errorhandler(400)
    def handle_bad_request(_error):
        return error_response(
            "BAD_REQUEST",
            "The request could not be processed.",
            400,
        )

    @app.errorhandler(404)
    def handle_not_found(_error):
        return error_response(
            "NOT_FOUND",
            "The requested resource was not found.",
            404,
        )

    @app.errorhandler(405)
    def handle_method_not_allowed(_error):
        return error_response(
            "METHOD_NOT_ALLOWED",
            "This HTTP method is not allowed for this resource.",
            405,
        )

    @app.errorhandler(413)
    def handle_payload_too_large(_error):
        return error_response(
            "PAYLOAD_TOO_LARGE",
            "The request payload is too large.",
            413,
        )

    @app.errorhandler(500)
    def handle_internal_server_error(_error):
        return error_response(
            "INTERNAL_SERVER_ERROR",
            "An unexpected server error occurred.",
            500,
        )
