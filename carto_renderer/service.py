#!/usr/bin/env python
"""
Service to render pngs from vector tiles using Carto CSS.
"""

from tornado import web
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.ioloop import IOLoop
from tornado.options import define, parse_command_line, options
import mapnik                   # pylint: disable=import-error
import msgpack

from urllib import quote_plus

import base64
import json

from carto_renderer.errors import BadRequest, PayloadKeyError, ServiceError
from carto_renderer.util import get_logger, init_logging, LogWrapper
from carto_renderer.version import BUILD_TIME, SEMANTIC

__package__ = 'carto_renderer'  # pylint: disable=redefined-builtin

# Variables for Vector Tiles.
BASE_ZOOM = 29
TILE_ZOOM_FACTOR = 16
TILE_SIZE = 256


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
            except RuntimeError:
                from mapnik import Path  # pylint: disable=no-name-in-module
                try:
                    wkt = Path.from_wkb(feature).to_wkt()
                    logger.error('Invalid feature: %s', wkt)
                except RuntimeError:
                    logger.error('Corrupt feature: %s', feature.encode('hex'))

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
        logger = get_logger(self)

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
        logger = get_logger(self)

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

        logger = get_logger(self)

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
        logger = get_logger(self)

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

            tile = geobody['tile']

            # Hack for compat with Base64 and MsgPack.  Should be
            # ripped out after TileServer goes out.
            try:
                first_byte = ord(geobody['tile'].items()[0][1][0][0])

                if first_byte not in [0, 1]:
                    tile = {layer: [base64.b64decode(wkb) for wkb in wkbs]
                        for layer, wkbs in geobody['tile'].items()}
            except IndexError:
                pass
            # End Base64 backwards compatibility hack.

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

                logger.info('zoom: %d, num features: %d, len(xml): %d',
                            zoom,
                            sum([len(layer) for layer in tile.values()]),
                            len(xml))
                logger.debug('xml: %s',
                             LogWrapper.Lazy(lambda: xml.replace('\n', ' ')))

                self.write(render_png(tile, zoom, xml, overscan))
                self.finish()

            headers = LogWrapper.ENV \
                if LogWrapper.ENV['X-Socrata-RequestId'] is not None \
                else {}

            req = HTTPRequest(path, headers=headers)
            self.http_client.fetch(req, callback=handle_response)


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
           '[%(X-Socrata-RequestId)s] %(name)s %(message)s')
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
