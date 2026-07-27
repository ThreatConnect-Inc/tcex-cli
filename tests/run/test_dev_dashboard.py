"""Test Module — developer dashboard routing in RequestHandlerApi and RequestHandlerWebhook."""

# standard library
import http.server
import io
import json
from typing import Any
from unittest.mock import MagicMock, patch

# third-party
import pytest

# first-party
from tcex_cli.cli.run.dev_dashboard import _DEV_DASHBOARD_HTML
from tcex_cli.cli.run.request_handler_api import RequestHandlerApi
from tcex_cli.cli.run.request_handler_webhook import RequestHandlerWebhook

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handler(cls: type, path: str = '/_tcex/', status_provider: Any = None) -> Any:
    """Return a bare handler instance with mocked HTTP plumbing.

    Uses ``__new__`` to bypass the ``BaseHTTPRequestHandler.__init__`` which
    expects a real socket.  Only the attributes exercised by the dashboard
    methods are populated.
    """
    h = cls.__new__(cls)
    h.path = path
    h.server = MagicMock()
    h.server.status_provider = status_provider
    h.send_response = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h.send_error = MagicMock()
    h.wfile = io.BytesIO()
    return h


# ---------------------------------------------------------------------------
# _DEV_DASHBOARD_HTML constant
# ---------------------------------------------------------------------------


class TestDevDashboardHtml:
    """Tests for the _DEV_DASHBOARD_HTML module-level constant."""

    @staticmethod
    def test_html_is_non_empty_string():
        """_DEV_DASHBOARD_HTML is a non-empty string."""
        assert isinstance(_DEV_DASHBOARD_HTML, str)
        assert len(_DEV_DASHBOARD_HTML) > 0

    @staticmethod
    def test_html_contains_status_fetch_url():
        """The HTML references the /_tcex/status polling URL."""
        assert '/_tcex/status' in _DEV_DASHBOARD_HTML

    @staticmethod
    def test_html_contains_commands_table_id():
        """The HTML contains the tb-commands table-body id."""
        assert 'tb-commands' in _DEV_DASHBOARD_HTML

    @staticmethod
    def test_html_contains_requests_table_id():
        """The HTML contains the tb-requests table-body id."""
        assert 'tb-requests' in _DEV_DASHBOARD_HTML

    @staticmethod
    def test_html_contains_requests_responses_heading():
        """The HTML contains the combined Requests & Responses section heading."""
        assert 'Requests &amp; Responses' in _DEV_DASHBOARD_HTML

    @staticmethod
    def test_html_contains_rel_time_function():
        """The HTML contains the relTime helper for relative timestamps."""
        assert 'relTime' in _DEV_DASHBOARD_HTML

    @staticmethod
    def test_html_update_status_bar_takes_since_params():
        """The updateStatusBar signature includes server-provided since params.

        Verifies backendSince and frontendSince are declared as formal parameters.
        """
        expected = 'updateStatusBar(backend, frontend, backendSince, frontendSince)'
        assert expected in _DEV_DASHBOARD_HTML

    @staticmethod
    def test_html_render_all_passes_since_fields():
        """The renderAll function forwards server-side timestamp fields to updateStatusBar."""
        assert 'data.backend_since' in _DEV_DASHBOARD_HTML
        assert 'data.frontend_since' in _DEV_DASHBOARD_HTML

    @staticmethod
    def test_html_chip_html_escapes_label():
        """chipHTML() wraps label in escHtml() for XSS defense."""
        assert 'escHtml(label)' in _DEV_DASHBOARD_HTML

    @staticmethod
    def test_html_chip_html_escapes_state():
        """chipHTML() wraps state in escHtml() for XSS defense."""
        assert 'escHtml(state)' in _DEV_DASHBOARD_HTML


# ---------------------------------------------------------------------------
# _serve_html()
# ---------------------------------------------------------------------------


class TestServeHtml:
    """Tests for the _serve_html() method on both handler classes."""

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(
                # API handler
                RequestHandlerApi,
                id='api-handler',
            ),
            pytest.param(
                # Webhook handler
                RequestHandlerWebhook,
                id='webhook-handler',
            ),
        ],
    )
    def test_serve_html_returns_200(self, cls: type) -> None:
        """_serve_html() sends a 200 response with the dashboard HTML body."""
        h = _make_handler(cls, '/_tcex/')
        h._serve_html()  # noqa: SLF001
        h.send_response.assert_called_once_with(200)
        h.end_headers.assert_called_once()
        body = h.wfile.getvalue()
        assert b'doctype html' in body.lower(), f'Expected HTML doctype in body; got {body[:80]!r}'

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_serve_html_body_matches_constant(self, cls: type) -> None:
        """_serve_html() writes exactly _DEV_DASHBOARD_HTML encoded as UTF-8."""
        h = _make_handler(cls, '/_tcex/')
        h._serve_html()  # noqa: SLF001
        assert h.wfile.getvalue() == _DEV_DASHBOARD_HTML.encode()


# ---------------------------------------------------------------------------
# _serve_status()
# ---------------------------------------------------------------------------


class TestServeStatus:
    """Tests for the _serve_status() method on both handler classes."""

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_serve_status_no_provider_returns_empty_dict(self, cls: type) -> None:
        """_serve_status() with status_provider=None returns an empty JSON object."""
        h = _make_handler(cls, '/_tcex/status', status_provider=None)
        h._serve_status()  # noqa: SLF001
        h.send_response.assert_called_once_with(200)
        body = json.loads(h.wfile.getvalue())
        assert body == {}, f'Expected empty dict; got {body!r}'

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_serve_status_with_provider_returns_provider_data(self, cls: type) -> None:
        """_serve_status() calls status_provider() and returns its JSON output."""
        data = {
            'backend': 'running',
            'frontend': None,
            'commands': [],
            'requests': [],
            'responses': [],
        }
        h = _make_handler(cls, '/_tcex/status', status_provider=lambda: data)
        h._serve_status()  # noqa: SLF001
        body = json.loads(h.wfile.getvalue())
        assert body['backend'] == 'running', f'backend field unexpected: {body!r}'
        assert body['commands'] == []


# ---------------------------------------------------------------------------
# _handle_tcex() routing
# ---------------------------------------------------------------------------


class TestHandleTcex:
    """Tests for the _handle_tcex() routing dispatcher on both handler classes."""

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_handle_tcex_root_serves_html(self, cls: type) -> None:
        """/_tcex/ (trailing slash) is routed to _serve_html() → 200."""
        h = _make_handler(cls, '/_tcex/')
        h._handle_tcex('/_tcex/')  # noqa: SLF001
        h.send_response.assert_called_once_with(200)
        assert b'doctype html' in h.wfile.getvalue().lower()

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_handle_tcex_status_serves_json(self, cls: type) -> None:
        """/_tcex/status is routed to _serve_status() → 200 with JSON body."""
        h = _make_handler(cls, '/_tcex/status', status_provider=None)
        h._handle_tcex('/_tcex/status')  # noqa: SLF001
        h.send_response.assert_called_once_with(200)
        body = json.loads(h.wfile.getvalue())
        assert body == {}

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_handle_tcex_unknown_path_returns_404(self, cls: type) -> None:
        """/_tcex/unknown sends a 404 error response."""
        h = _make_handler(cls, '/_tcex/unknown')
        h._handle_tcex('/_tcex/unknown')  # noqa: SLF001
        h.send_error.assert_called_once_with(404)

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_handle_tcex_strips_query_string(self, cls: type) -> None:
        """/_tcex/?foo=1 still serves HTML — query string is stripped before routing."""
        h = _make_handler(cls, '/_tcex/?foo=1')
        h._handle_tcex('/_tcex/?foo=1')  # noqa: SLF001
        h.send_response.assert_called_once_with(200)
        assert b'doctype html' in h.wfile.getvalue().lower()


# ---------------------------------------------------------------------------
# log_message() suppression
# ---------------------------------------------------------------------------


class TestLogMessage:
    """Tests for log_message() suppression of /_tcex/ polling noise."""

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_log_message_suppresses_tcex_polling(self, cls: type) -> None:
        """log_message() silently returns for args containing '/_tcex/'."""
        h = _make_handler(cls)
        with patch.object(http.server.BaseHTTPRequestHandler, 'log_message') as mock_super:
            h.log_message('%s', 'GET /_tcex/status HTTP/1.1')
            mock_super.assert_not_called()

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_log_message_suppresses_all_requests(self, cls: type) -> None:
        """log_message() silently suppresses all HTTP access-log entries."""
        h = _make_handler(cls)
        with patch.object(http.server.BaseHTTPRequestHandler, 'log_message') as mock_super:
            h.log_message('%s', 'GET /api/data HTTP/1.1')
            mock_super.assert_not_called()


# ---------------------------------------------------------------------------
# do_GET() interception
# ---------------------------------------------------------------------------


class TestDoGet:
    """Tests for do_GET() routing of /_tcex/ requests."""

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_do_get_intercepts_tcex_path(self, cls: type) -> None:
        """do_GET routes /_tcex/ to _handle_tcex() and never calls call_service()."""
        h = _make_handler(cls, '/_tcex/')
        with (
            patch.object(h, '_handle_tcex') as mock_handle,
            patch.object(h, 'call_service') as mock_call,
        ):
            h.do_GET()
            mock_handle.assert_called_once_with('/_tcex/')
            mock_call.assert_not_called()

    @pytest.mark.parametrize(
        argnames='cls',
        argvalues=[
            pytest.param(RequestHandlerApi, id='api-handler'),
            pytest.param(RequestHandlerWebhook, id='webhook-handler'),
        ],
    )
    def test_do_get_non_tcex_calls_service(self, cls: type) -> None:
        """do_GET routes non-/_tcex/ paths to call_service() and never calls _handle_tcex()."""
        h = _make_handler(cls, '/api/data')
        with (
            patch.object(h, '_handle_tcex') as mock_handle,
            patch.object(h, 'call_service') as mock_call,
        ):
            h.do_GET()
            mock_handle.assert_not_called()
            mock_call.assert_called_once_with('GET')
