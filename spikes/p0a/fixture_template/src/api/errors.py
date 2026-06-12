class ApiError(Exception):
    status = 500


class NotFound(ApiError):
    status = 404


class Invalid(ApiError):
    status = 422
