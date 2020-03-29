"""
Error classes for this service.
"""

from carto_renderer.util import get_logger


class ServiceError(Exception):
    """
    Base class for errors in this service.
    """
    def __init__(self, message, status_code, request_body=None):
        self.status_code = status_code
        self.request_body = request_body
        self.message = message
        logger = get_logger(self)
        if request_body:
            logger.error('Fatal Error (%d): "%s"; body: "%s"',
                         status_code, message, request_body)
        else:
            logger.error('Fatal Error (%d): "%s"', status_code, message)


class BadRequest(ServiceError):
    """
    Base class for 400 errors.
    """
    def __init__(self, message, request_body=None):
        super(BadRequest, self).__init__(message,
                                         400,
                                         request_body=request_body)


class PayloadKeyError(ServiceError):
    """
    Error to throw when keys are missing.
    """
    msg = "Request JSON must contain the keys '{}' and '{}'."

    def __init__(self, keys, blob):
        message = ''

        beg = keys[:-1]
        message = PayloadKeyError.msg.format("', '".join(beg), keys[-1])

        super(PayloadKeyError, self).__init__(message, 400, request_body=blob)
