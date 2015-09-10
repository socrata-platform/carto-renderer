# pylint: disable=missing-docstring,line-too-long,import-error,abstract-method
import json
import platform
import string
import urllib

from base64 import b64encode
from hypothesis import assume, given
from hypothesis.strategies import integers, lists, text
from mapbox_vector_tile import encode as tile_encode
from pytest import raises
from tornado.web import RequestHandler

try:
    from unittest import mock   # pylint: disable=no-name-in-module
except ImportError:
    import mock

try:
    unicode
except NameError:               # pragma: no cover
    # pylint: disable=redefined-builtin,invalid-name
    unicode = str

from carto_renderer import service, errors
from carto_renderer.service import GEOM_TYPES, build_wkt

POINT_LISTS = lists(integers(), 2, 2, 2)
SHELL_LISTS = lists(POINT_LISTS, 1, 10, 100)


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

    def __call__(self):
        return self

    def fetch(self, path, callback):
        assert path.endswith(urllib.quote_plus(self.style))
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
        self.jbody = None
        self.http_client = None
        self.style_host = None
        self.style_port = None

    def extract_jbody(self):
        if self.jbody:
            return self.jbody
        else:
            return service.RenderHandler.extract_jbody(self)


@given(integers())
def test_build_wkt_invalid(geom_code):
    unused = []

    assume(geom_code not in GEOM_TYPES)
    wkt = build_wkt(geom_code, unused)
    assert wkt is None


@given(POINT_LISTS)
def test_build_wkt_point(coordinates):
    coords = [[c * 16 for c in coordinates]]
    wkt = build_wkt(1, coords)
    assert wkt is not None
    assert wkt == 'POINT({})'.format(render_pair(coordinates))


@given(SHELL_LISTS)
def test_build_wkt_line_string(points):
    coords = [[c * 16 for c in coord] for coord in points]
    wkt = build_wkt(2, coords)
    assert wkt is not None
    point_str = ','.join([render_pair(p) for p in points])
    assert wkt == 'LINE_STRING(({}))'.format(point_str)


@given(lists(SHELL_LISTS, 1, 3, 100))
def test_build_wkt_line_polygon(shells):
    coords = [[[c * 16 for c in coord]
               for coord in points] for points in shells]
    wkt = build_wkt(3, coords)
    assert wkt is not None
    point_str = [','.join([render_pair(p) for p in points])
                 for points in shells]
    assert wkt == 'POLYGON((({})))'.format('),('.join(point_str))


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
    assert ver.finished


def test_base_handler_bad_req():
    # pylint: disable=no-member

    with raises(errors.BadRequest) as no_ct:
        base = BaseStrHandler()
        base.extract_jbody()
    assert "invalid content-type" in no_ct.value.message.lower()

    with raises(errors.BadRequest) as bad_ct:
        base = BaseStrHandler()
        base.request.headers['content-type'] = 'unexpected type!'
        base.extract_jbody()
    assert "invalid content-type" in bad_ct.value.message.lower()

    with raises(errors.BadRequest) as bad_json:
        base = BaseStrHandler()
        base.request.headers['content-type'] = 'application/json'
        base.extract_jbody()
    assert "could not parse" in bad_json.value.message.lower()


def test_render_handler_bad_req():
    keys = ["bpbf", "zoom", "style"]

    with raises(errors.JsonKeyError) as empty_json:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/json'
        render.body = '{}'
        render.post()
    for k in keys:
        assert k in empty_json.value.message.lower()

    with raises(errors.JsonKeyError) as no_style:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/json'
        render.body = '{"zoom": "", "body": ""}'
        render.post()
    for k in keys:
        assert k in no_style.value.message.lower()

    with raises(errors.JsonKeyError) as no_zoom:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/json'
        render.body = '{"style": "", "bpbf": ""}'
        render.post()
    for k in keys:
        assert k in no_zoom.value.message.lower()

    with raises(errors.JsonKeyError) as no_bpbf:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/json'
        render.body = '{"style": "", "zoom": ""}'
        render.post()
    for k in keys:
        assert k in no_bpbf.value.message.lower()

    with raises(errors.BadRequest) as bad_zoom:
        render = RenderStrHandler()
        render.request.headers['content-type'] = 'application/json'
        render.body = '{"style": "", "zoom": "", "bpbf": ""}'
        render.post()
    assert "zoom" in bad_zoom.value.message.lower()
    assert "int" in bad_zoom.value.message.lower()


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
        "name": "main",
        "features": [
            {
                "geometry": "POINT(50 50)",
                "properties": {}
            }
        ]
    }
    tile = b64encode(tile_encode([layer]))
    handler.jbody = {'zoom': 14, 'style': css, 'bpbf': tile}
    handler.http_client = MockClient(css, xml)
    handler.style_host = str(host)
    handler.style_port = str(port)

    handler.post()

    if platform.system() == 'Darwin':  # pragma: no cover
        expected = (
            'iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAABOklEQVR' +
            '4nO3VsQ2AMAxFwYTsv1kYgkkcECMg8YvcSe5fY7s1' + ('A' * 332) +
            'vqmRLgAiZr1TR7oE+N2z/Od1H4CeLgEifH8A2MIC2WYLFCJC8r4AAAA' +
            'ASUVORK5CYII=')
    elif platform.system() == 'Linux':  # pragma: no cover
        expected = (
            'iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAABPUlEQVR' +
            '4nO3VsQ2AMBAEQWP678wU4QZowX5qQOICZqTPL9pvDQ' + ('A' * 330) +
            'gHfWmV4ARIxVd1cEenoJ8LknANesABzpJUCE7w8Av7AByiMLAy0uJsQ' +
            'AAAAASUVORK5CYII=')
    else:                       # pragma: no cover
        raise NotImplementedError("Unknown platform!")

    assert handler.finished
    assert handler.was_written_b64() == expected


@given(text(alphabet=string.printable),
       text(alphabet=string.printable))
def test_render_handler_no_xml(host, port):
    css = '#main{marker-line-color:#00C;marker-width:1}'
    layer = {
        "name": "main",
        "features": [
            {
                "geometry": "POINT(50 50)",
                "properties": {}
            }
        ]
    }
    tile = b64encode(tile_encode([layer]))

    handler = RenderStrHandler()
    handler.jbody = {'zoom': 14, 'style': css, 'bpbf': tile}
    handler.http_client = MockClient(css, None)
    handler.style_host = str(host)
    handler.style_port = str(port)

    with raises(errors.ServiceError) as no_xml:
        handler.post()

    assert "style-renderer" in no_xml.value.message.lower()
