# pylint: disable=missing-docstring,line-too-long,import-error,abstract-method
import json
import mock
import platform
import string

from base64 import b64encode
from hypothesis import given
from hypothesis.strategies import integers, text
from pytest import raises
from tornado.web import RequestHandler
from urllib import quote_plus

from carto_renderer import service, errors


def tile_encode(layer):
    def buildFeature(feature):
        return {
            'wkbs': b64encode(feature['wkbs']),
            'attributes': b64encode(json.dumps(feature['attributes']))
        }

    return {k: [buildFeature(f) for f in feats] for k, feats in layer.items()}


def to_wkb(wkt):
    from mapnik import Path, wkbByteOrder  # pylint: disable=no-name-in-module
    return Path.from_wkt(wkt).to_wkb(wkbByteOrder.XDR)


def render_pair(pair):
    assert len(pair) == 2
    return "{} {}".format(pair[0], pair[1])


class MockClient(object):
    # pylint: disable=too-few-public-methods
    class MockResp(object):
        def __init__(self, body):
            self.body = body

    def __init__(self, style, xml):
        self.resp = MockClient.MockResp(xml)
        self.style = style

    def fetch(self, req, callback):
        assert req.body.decode('utf-8').find(quote_plus(self.style)) > -1
        callback(self.resp)


class StringHandler(RequestHandler):
    # pylint: disable=super-init-not-called
    def __init__(self, **kwargs):
        super(StringHandler, self).__init__(mock.MagicMock(),
                                            mock.MagicMock(),
                                            **kwargs)
        self.written = []
        self.finished = False
        self.status_code = None
        self.status_reason = None
        self.request = self
        self.headers = {}
        self.body = None

    # Stop @web.asynchronous from swallowing exceptions!
    def _stack_context_handle_exception(self, *_):
        raise

    def clear(self):
        self.written = []

    def write(self, chunk):
        if chunk is not None:
            self.written.append(chunk)

    def finish(self, chunk=None):
        self.write(chunk)
        self.finished = True

    def set_status(self, code, reason=None):
        self.status_code = code
        self.status_reason = reason

    def was_written(self):
        return u''.join([unicode(s) for s in self.written])

    def was_written_b64(self):
        return u''.join([b64encode(s) for s in self.written])


class BaseStrHandler(service.BaseHandler, StringHandler):
    pass


class VersionStrHandler(service.VersionHandler, StringHandler):
    pass


class RenderStrHandler(service.RenderHandler, StringHandler):
    def initialize(self):
        pass

    def __init__(self):
        StringHandler.__init__(self)
        self.body = None
        self.http_client = None
        self.style_host = None
        self.style_port = None

    def extract_body(self):
        if self.body is None:
            return service.RenderHandler.extract_body(self)
        else:
            return self.body


@given(text(), integers(), text())
def test_base_handler(message, status, body):
    # pylint: disable=no-member,protected-access
    base = BaseStrHandler()

    service_err = errors.ServiceError(message, status, request_body=body)
    base._handle_request_exception(service_err)

    assert base.status_code == status
    assert json.dumps(message) in base.was_written()
    if body:
        assert json.dumps(body) in base.was_written()

    runtime_err = RuntimeError(message)
    base._handle_request_exception(runtime_err)
    assert base.status_code == 500
    assert json.dumps(message) in base.was_written()


def test_version_handler():
    ver = VersionStrHandler()
    ver.get()                   # pylint: disable=no-member
    assert 'health' in ver.was_written()
    assert 'alive' in ver.was_written()
    assert 'version' in ver.was_written()
    assert 'pythonVersion' in ver.was_written()
    assert 'buildTime' in ver.was_written()
    assert ver.finished


def test_base_handler_bad_req():
    # pylint: disable=no-member

    with raises(errors.BadRequest) as no_ct:
        base = BaseStrHandler()
        base.extract_body()
    assert "invalid content-type" in no_ct.value.message.lower()

    with raises(errors.BadRequest) as bad_ct:
        base = BaseStrHandler()
        base.request.headers['content-type'] = 'unexpected type!'
        base.extract_body()
    assert "invalid content-type" in bad_ct.value.message.lower()

    with raises(errors.BadRequest) as bad_json:
        base = BaseStrHandler()
        base.request.headers['content-type'] = 'application/octet-stream'
        base.extract_body()
    assert "could not parse" in bad_json.value.message.lower()


def test_render_handler_bad_req():
    keys = ["tile", "zoom", "style"]

    with raises(errors.PayloadKeyError) as empty_tile:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/octet-stream'
        render.body = {}
        render.post()
    for k in keys:
        assert k in empty_tile.value.message.lower()

    with raises(errors.PayloadKeyError) as no_style:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/octet-stream'
        render.body = {"zoom": "", "body": ""}
        render.post()
    for k in keys:
        assert k in no_style.value.message.lower()

    with raises(errors.PayloadKeyError) as no_zoom:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/octet-stream'
        render.body = {"style": "", "tile": ""}
        render.post()
    for k in keys:
        assert k in no_zoom.value.message.lower()

    with raises(errors.PayloadKeyError) as no_tile:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/octet-stream'
        render.body = {"style": "", "zoom": ""}
        render.post()
    for k in keys:
        assert k in no_tile.value.message.lower()

    with raises(errors.BadRequest) as bad_zoom:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/octet-stream'
        render.body = {"style": "", "zoom": "", "tile": "", "overscan": 32}
        render.post()


    with raises(errors.BadRequest) as bad_overscan:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/octet-stream'
        render.body = {"style": "", "zoom": "", "tile": "", "overscan": ""}
        render.post()


    assert "zoom" in bad_zoom.value.message.lower()
    assert "int" in bad_zoom.value.message.lower()
    assert "overscan" in bad_overscan.value.message.lower()


@given(text(alphabet=string.printable),
       text(alphabet=string.printable))
def test_render_handler(host, port):
    """
    This is a simple regression test, it only hits one case.
    """
    handler = RenderStrHandler()
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE Map[]>
    <Map>
      <Style name="main" filter-mode="first">
        <Rule>
          <MarkersSymbolizer stroke="#0000cc" width="1" />
        </Rule>
      </Style>
      <Layer name="main">
        <StyleName>main</StyleName>
      </Layer>
    </Map>
    """

    css = '#main{marker-line-color:#00C;marker-width:1}'
    layer = {
        "main": [{ "wkbs": to_wkb("POINT(50 50)"), "attributes": {} }]
    }

    tile = tile_encode(layer)
    print tile
    handler.body = {'zoom': 14, 'style': css, 'tile': tile, 'overscan' : 0}
    handler.http_client = MockClient(css, xml)
    handler.style_host = str(host)
    handler.style_port = str(port)

    handler.post()

    if platform.system() == 'Darwin':  # pragma: no cover
        expected = """iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAABPklEQVR4nO3WsQmAMBRF0Q+6Q6ps61xOEFLoQDHgCEF/cw68/pYvAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABYMPaIu2ZXACnaeHeV7BLgd/2YO+cT2LJLAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPjIAwKMClP4YvSFAAAAAElFTkSuQmCC"""  # noqa
    elif platform.system() == 'Linux':  # pragma: no cover
        expected = """iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAABPklEQVR4nO3WsQmAMBRF0Q+6Q6ps61xOEFLoQDHgCEF/cw68/pYvAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABYMPaIu2ZXACnaeHeV7BLgd/2YO+cT2LJLAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPjIAwKMClP4YvSFAAAAAElFTkSuQmCC"""  # noqa
    else:                       # pragma: no cover
        raise NotImplementedError("Unknown platform!")

    assert handler.finished
    assert handler.was_written_b64() == expected


@given(text(alphabet=string.printable),
       text(alphabet=string.printable))
def test_render_handler_no_xml(host, port):
    css = '#main{marker-line-color:#00C;marker-width:1}'
    layer = {
        "main": [{ "wkbs": to_wkb("POINT(50 50)"), "attributes": {} }]
    }

    tile = tile_encode(layer)

    handler = RenderStrHandler()
    handler.body = {'zoom': 14, 'style': css, 'tile': tile, 'overscan': 32}
    handler.http_client = MockClient(css, None)
    handler.style_host = str(host)
    handler.style_port = str(port)

    with raises(errors.ServiceError) as no_xml:
        handler.post()

    assert "style-renderer" in no_xml.value.message.lower()


def test_render_png_ignores_bad_wkb():
    if platform.system() == 'Darwin':  # pragma: no cover
        expected = """iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAABFUlEQVR4nO3BMQEAAADCoPVP7WsIoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAeAMBPAABPO1TCQAAAABJRU5ErkJggg=="""  # noqa
    elif platform.system() == 'Linux':  # pragma: no cover
        expected = """iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAABFUlEQVR4nO3BMQEAAADCoPVP7WsIoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAeAMBPAABPO1TCQAAAABJRU5ErkJggg=="""  # noqa
    else:                       # pragma: no cover
        raise NotImplementedError("Unknown platform!")

    tile = {
        "main": [{
            "wkbs": 'INVALID',
            "attributes": {}
        }]
    }

    xml = """<?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE Map[]>
    <Map>
      <Style name="main" filter-mode="first">
        <Rule>
          <MarkersSymbolizer stroke="#0000cc" width="1" />
        </Rule>
      </Style>
      <Layer name="main">
        <StyleName>main</StyleName>
      </Layer>
    </Map>
    """

    actual = service.render_png(tile, 1, xml, 0)

    assert b64encode(actual) == expected
