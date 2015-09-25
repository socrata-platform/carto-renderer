#!/usr/bin/env python
"""
Service to render pngs from vector tiles using Carto CSS.
"""

from tornado import web
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
from tornado.options import define, parse_command_line, options
import mapbox_vector_tile
# Only installed for Python 2.
# (Installing for Python 3 is difficult, but possible...)
import mapnik                   # pylint: disable=import-error

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus  # pylint: disable=no-name-in-module

import base64
import collections
import json


from carto_renderer.errors import BadRequest, JsonKeyError, ServiceError
from carto_renderer.version import BUILD_TIME, SEMANTIC

__package__ = 'carto_renderer'  # pylint: disable=redefined-builtin

GEOM_TYPES = {
    1: 'POINT',
    2: 'LINE_STRING',
    3: 'POLYGON'
}

# Variables for Vector Tiles.
BASE_ZOOM = 29
TILE_ZOOM_FACTOR = 16


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


def build_wkt(geom_code, geometries):
    """
    Build a Well Known Text of the appropriate type.

    Returns None on failure.
    """
    logger = get_logger()
    geom_type = GEOM_TYPES.get(geom_code, 'UNKNOWN')

    def collapse(coords):
        """
        Helper, collapses lists into strings with appropriate parens.
        """
        if len(coords) < 1:
            return '()'

        first = coords[0]
        if not isinstance(first, collections.Iterable):
            return ' '.join([str(c / TILE_ZOOM_FACTOR) for c in coords])
        else:
            return '(' + (','.join([collapse(c) for c in coords])) + ')'

    collapsed = collapse(geometries)

    if geom_type == 'UNKNOWN':
        logger.warn(u'Unknown geometry code: %s', geom_code)
        return None

    if geom_type != 'POINT':
        collapsed = '(' + collapsed + ')'

    return geom_type + collapsed


def render_png(tile, zoom, xml):
    # mapnik is installed in a non-standard way.
    # It confuses pylint.
    # pylint: disable=no-member
    """
    Render the tile for the given zoom
    """
    logger = get_logger()
    ctx = mapnik.Context()

    map_tile = mapnik.Map(256, 256)
    # scale_denom = 1 << (BASE_ZOOM - int(zoom or 1))
    # scale_factor = scale_denom / map_tile.scale_denominator()

    # map_tile.zoom(scale_factor)  # Is overriden by zoom_to_box.
    mapnik.load_map_from_string(map_tile, xml)
    map_tile.zoom_to_box(mapnik.Box2d(0, 0, 255, 255))

    for (name, features) in tile.items():
        name = name.encode('ascii', 'ignore')
        source = mapnik.MemoryDatasource()
        map_layer = mapnik.Layer(name)
        map_layer.datasource = source

        for feature in features:
            wkt = build_wkt(feature['type'], feature['geometry'])
            logger.debug('wkt: %s', wkt)
            feat = mapnik.Feature(ctx, 0)

            if wkt:
                try:
                    feat.add_geometries_from_wkt(wkt)
                except RuntimeError:
                    logger.error('Invalid WKT: %s', wkt)
                    raise

            source.add_feature(feat)

        map_layer.styles.append(name)
        map_tile.layers.append(map_layer)

    image = mapnik.Image(map_tile.width, map_tile.height)
    mapnik.render(map_tile, image)

    return image.tostring('png')


class BaseHandler(web.RequestHandler):
    # pylint: disable=abstract-method
    """
    Convert ServiceErrors to HTTP errors.
    """
    def extract_jbody(self):
        """
        Extract the json body from self.request.
        """
        logger = get_logger()

        request_id = self.request.headers.get('x-socrata-requestid', '')
        LogWrapper.ENV['X-Socrata-RequestId'] = request_id

        content_type = self.request.headers.get('content-type', '')
        if not content_type.lower().startswith('application/json'):
            message = 'Invalid Content-Type: "{ct}"; ' + \
                      'expected "application/json"'
            logger.warn('Invalid Content-Type: "%s"', content_type)
            raise BadRequest(message.format(ct=content_type))

        body = self.request.body

        try:
            jbody = json.loads(body)
        except Exception:
            logger.warn('Invalid JSON')
            raise BadRequest('Could not parse JSON.', body)
        return jbody

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

    Expects a JSON blob with 'style', 'zoom', and 'bpbf' values.
    """
    keys = ['bpbf', 'zoom', 'style']

    def initialize(self, http_client, style_host, style_port):
        """Magic Tornado __init__ replacement."""
        self.http_client = http_client  # pragma: no cover
        self.style_host = style_host    # pragma: no cover
        self.style_port = style_port    # pragma: no cover

    @web.asynchronous
    def post(self):
        """
        Actually render the png.

        Expects a JSON blob with 'style', 'zoom', and 'bpbf' values.
        """
        logger = get_logger()

        jbody = self.extract_jbody()

        if not all([k in jbody for k in self.keys]):
            logger.warn('Invalid JSON: %s', jbody)
            raise JsonKeyError(self.keys, jbody)
        else:
            try:
                zoom = int(jbody['zoom'])
            except:
                logger.warn('Invalid JSON; zoom must be an integer: %s', jbody)
                raise BadRequest('"zoom" must be an integer.',
                                 request_body=jbody)
            path = 'http://{host}:{port}/style?style={css}'.format(
                host=self.style_host,
                port=self.style_port,
                css=quote_plus(jbody['style']))

            pbf = base64.b64decode(jbody['bpbf'])
            tile = mapbox_vector_tile.decode(pbf)

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

                logger.info('zoom: %d, len(pbf): %d, len(xml): %d',
                            zoom,
                            len(pbf),
                            len(xml))
                self.write(render_png(tile, zoom, xml))
                self.finish()

            self.http_client.fetch(path, callback=handle_response)


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
