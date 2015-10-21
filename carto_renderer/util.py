"""
Miscalenous utility functions and classes.
"""

from tornado.options import options


class LogWrapper(object):
    """
    A logging wrapper that includes log environment automatically.
    """
    ENV = {'X-Socrata-RequestId': None}

    class Lazy(object):         # pylint: disable=too-few-public-methods
        """
        Lazy evaluation wrapper around a thunk.
        """
        def __init__(self, thunk):
            self.thunk = thunk

        def __str__(self):
            return str(self.thunk())

    def __init__(self, underlying):
        self.underlying = underlying

    def debug(self, *args):
        """Log a debug statement."""
        self.underlying.debug(*args, extra=LogWrapper.ENV)

    def info(self, *args):
        """Log an info statement."""
        self.underlying.info(*args, extra=LogWrapper.ENV)

    def warn(self, *args):
        """Log a warning."""
        self.underlying.warn(*args, extra=LogWrapper.ENV)

    def error(self, *args):
        """Log an error."""
        self.underlying.error(*args, extra=LogWrapper.ENV)

    def exception(self, *args):
        """Log an exception."""
        self.underlying.exception(*args, extra=LogWrapper.ENV)


def get_logger(obj=None):
    """
    Return a (wrapped) logger with appropriate name.
    """
    import logging

    tail = '.' + obj.__class__.__name__ if obj else ''
    return LogWrapper(logging.getLogger(__package__ + tail))


def init_logging():             # pragma: no cover
    """
    Initialize logging from config.
    """
    import logging
    import sys

    root_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(thread)d] %(name)s %(message)s')

    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setLevel(options.log_level)
    root_handler.setFormatter(root_formatter)

    root = logging.getLogger()
    root.setLevel(options.log_level)
    root.addHandler(root_handler)

    carto_formatter = logging.Formatter(options.log_format)

    carto_handler = logging.StreamHandler(sys.stdout)
    carto_handler.setLevel(options.log_level)
    carto_handler.setFormatter(carto_formatter)

    carto = get_logger().underlying
    carto.setLevel(options.log_level)
    carto.propagate = 0
    carto.addHandler(carto_handler)
