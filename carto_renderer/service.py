#!/usr/bin/env python
"""
Service to render pngs from vector tiles using Carto CSS.
"""

from tornado import web
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
from tornado.options import define, parse_command_line, options
import mapnik                   # pylint: disable=import-error
import msgpack

from urllib import quote_plus

import base64
import json

from carto_renderer.errors import BadRequest, PayloadKeyError, ServiceError
from carto_renderer.version import BUILD_TIME, SEMANTIC

__package__ = 'carto_renderer'  # pylint: disable=redefined-builtin

# Variables for Vector Tiles.
BASE_ZOOM = 29
TILE_ZOOM_FACTOR = 16
TILE_SIZE = 256


class LogWrapper(object):
    """
    A logging wrapper that includes log environment automatically.
    """
    ENV = {'X-Socrata-RequestId': None}

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


def render_png(tile, zoom, xml, overscan):
    map_tile_size = TILE_SIZE + (overscan * 2)
    # mapnik is installed in a non-standard way.
    # It confuses pylint.
    # pylint: disable=no-member
    """
    Render the tile for the given zoom
    """
    logger = get_logger()
    ctx = mapnik.Context()

    map_tile = mapnik.Map(map_tile_size, map_tile_size)
    # scale_denom = 1 << (BASE_ZOOM - int(zoom or 1))
    # scale_factor = scale_denom / map_tile.scale_denominator()
    # map_tile.zoom(scale_factor)  # Is overriden by zoom_to_box.

    mapnik.load_map_from_string(map_tile, xml)

    box_min = -overscan
    box_max = TILE_SIZE + overscan - 1
    map_tile.zoom_to_box(mapnik.Box2d(box_min, box_min, box_max, box_max))

    for (name, features) in tile.items():
        name = name.encode('ascii', 'ignore')
        source = mapnik.MemoryDatasource()
        map_layer = mapnik.Layer(name)
        map_layer.datasource = source

        for feature in features:
            feat = mapnik.Feature(ctx, 0)

            try:
                feat.add_geometries_from_wkb(feature)
                wkt = None
            except RuntimeError:
                logger.error('Invalid WKB: %s', wkt)

            source.add_feature(feat)

        map_layer.styles.append(name)
        map_tile.layers.append(map_layer)

    image = mapnik.Image(TILE_SIZE, TILE_SIZE)
    # tile, image, scale, offset_x, offset_y
    mapnik.render(map_tile, image, 1, overscan, overscan)

    return image.tostring('png')


class BaseHandler(web.RequestHandler):
    # pylint: disable=abstract-method
    """
    Convert ServiceErrors to HTTP errors.
    """
    def extract_body(self):
        """
        Extract the body from self.request as a dictionary.
        """
        logger = get_logger()

        request_id = self.request.headers.get('x-socrata-requestid', '')
        LogWrapper.ENV['X-Socrata-RequestId'] = request_id

        content_type = self.request.headers.get('content-type', '').lower()
        if not content_type.startswith('application/octet-stream'):
            message = 'Invalid Content-Type: "{ct}"; ' + \
                      'expected"application/octet-stream"'
            logger.warn('Invalid Content-Type: "%s"', content_type)
            raise BadRequest(message.format(ct=content_type))

        body = self.request.body

        try:
            extracted = msgpack.loads(body)
        except Exception:
            logger.warn('Invalid message')
            raise BadRequest('Could not parse message.', body)
        return extracted

    def _handle_request_exception(self, err):
        """
        Convert ServiceErrors to HTTP errors.
        """
        logger = get_logger()

        payload = {}
        logger.exception(err)
        if isinstance(err, ServiceError):
            status_code = err.status_code
            if err.request_body:
                payload['request_body'] = err.request_body
        else:
            status_code = 500

        payload['resultCode'] = status_code
        payload['message'] = err.message

        self.clear()
        self.set_status(status_code)
        self.write(json.dumps(payload))
        self.finish()


class VersionHandler(BaseHandler):
    # pylint: disable=abstract-method
    """
    Return the version of the service, currently hardcoded.
    """
    import sys

    (major, minor, micro, _, _) = sys.version_info

    version = {'health': 'alive',
               'pythonVersion': '{}.{}.{}'.format(major, minor, micro),
               'version': SEMANTIC,
               'buildTime': BUILD_TIME}

    def get(self):
        """
        Return the version of the service, currently hardcoded.
        """
        request_id = self.request.headers.get('x-socrata-requestid', '')
        LogWrapper.ENV['X-Socrata-RequestId'] = request_id

        logger = get_logger()

        logger.info('Alive!')
        self.write(VersionHandler.version)
        self.finish()


class RenderHandler(BaseHandler):
    # pylint: disable=abstract-method, arguments-differ
    """
    Actually render the png.

    Expects a dictionary with 'style', 'zoom', and 'tile' values.
    """
    keys = ['tile', 'zoom', 'style']

    def initialize(self, http_client, style_host, style_port):
        """Magic Tornado __init__ replacement."""
        self.http_client = http_client  # pragma: no cover
        self.style_host = style_host    # pragma: no cover
        self.style_port = style_port    # pragma: no cover

    @web.asynchronous
    def post(self):
        """
        Actually render the png.

        Expects a JSON blob with 'style', 'zoom', and 'tile' values.
        """
        logger = get_logger()

        geobody = self.extract_body()

        if not all([k in geobody for k in self.keys]):
            logger.warn('Invalid JSON: %s', geobody)
            raise PayloadKeyError(self.keys, geobody)
        else:
            try:
                overscan = int(geobody['overscan'])
            except:
                logger.warn('Invalid JSON; overscan must be an integer: %s',
                            geobody)
                raise BadRequest('"overscan" must be an integer',
                                 request_body=geobody)

            try:
                zoom = int(geobody['zoom'])
            except:
                logger.warn('Invalid JSON; zoom must be an integer: %s',
                            geobody)
                raise BadRequest('"zoom" must be an integer.',
                                 request_body=geobody)

            path = 'http://{host}:{port}/style?style={css}'.format(
                host=self.style_host,
                port=self.style_port,
                css=quote_plus(geobody['style']))

            tile = {layer: [base64.b64decode(wkb) for wkb in wkbs]
                    for layer, wkbs in geobody['tile'].items()}

            def handle_response(response):
                """
                Process the XML returned by the style renderer.
                """
                if response.body is None:
                    raise ServiceError(
                        "Failed to contact style-renderer at '{url}'".format(
                            url=path),
                        503)

                xml = response.body

                logger.info('zoom: %d, len(tile): %d, len(xml): %d',
                            zoom,
                            len(tile),
                            len(xml))

                self.write(render_png(tile, zoom, xml, overscan))
                self.finish()

            self.http_client.fetch(path,
                                   callback=handle_response,
                                   headers=LogWrapper.ENV)


def init_logging():             # pragma: no cover
    """
    Initialize logging from config.
    """
    import logging
    import sys

    root_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(thread)d] ' +
        '%(name)s.%(funcName)s %(message)s')

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


def main():  # pragma: no cover
    """
    Actually fire up the web server.

    Listens on 4096.
    """
    define('port', default=4096)
    define('style_host', default='localhost')
    define('style_port', default=4097)
    define('log_level', default='INFO')
    define('log_format', default='%(asctime)s %(levelname)s [%(thread)d] ' +
           '[%(X-Socrata-RequestId)s] %(name)s.%(funcName)s %(message)s')
    parse_command_line()
    init_logging()

    routes = [
        web.url(r'/', web.RedirectHandler, {'url': '/version'}),
        web.url(r'/version', VersionHandler),
        web.url(r'/render', RenderHandler, {
            'style_host': options.style_host,
            'style_port': options.style_port,
            'http_client': AsyncHTTPClient()
        }),
    ]

    app = web.Application(routes)
    app.listen(options.port)
    logger = get_logger()
    logger.info('Listening on localhost:4096...')
    IOLoop.instance().start()

if __name__ == '__main__':  # pragma: no cover
    main()
