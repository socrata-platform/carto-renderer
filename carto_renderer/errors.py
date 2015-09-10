"""
Error classes for this service.
"""


class ServiceError(Exception):
    """
    Base class for errors in this service.
    """
    def __init__(self, message, status_code, request_body=None):
        super(ServiceError, self).__init__(message)
        self.status_code = status_code
        self.request_body = request_body


class BadRequest(ServiceError):
    """
    Base class for 400 errors.
    """
    def __init__(self, message, request_body=None):
        super(BadRequest, self).__init__(message,
                                         400,
                                         request_body=request_body)


class JsonKeyError(ServiceError):
    """
    Error to throw when keys are missing.
    """
    msg = "Request JSON must contain the keys '{}' and '{}'."

    def __init__(self, keys, blob):
        message = ''

        beg = keys[:-1]
        message = JsonKeyError.msg.format("', '".join(beg), keys[-1])

        super(JsonKeyError, self).__init__(message, 400, request_body=blob)
