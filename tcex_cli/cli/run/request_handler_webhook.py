"""TcEx Framework Module"""

import http.server
import json
from threading import Event
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from tcex_cli.cli.run.dev_dashboard import _DEV_DASHBOARD_HTML

if TYPE_CHECKING:
    from tcex_cli.cli.run.web_server import WebServer  # CIRCULAR IMPORT


class RequestHandlerWebhook(http.server.BaseHTTPRequestHandler):
    """Request handler to forward request to API service."""

    server: 'WebServer'

    def _build_request(self, method: str) -> dict:
        """Return request built from incoming HTTP request."""
        url_parts = urlparse(self.path)
        trigger_id = url_parts.path.split('/')[1]
        if trigger_id:
            trigger_id = int(trigger_id)

        # query params
        params = []
        for name, value in parse_qs(url_parts.query).items():
            if isinstance(value, list):
                for v in value:
                    params.append({'name': name, 'value': v})
            else:
                params.append({'name': name, 'value': value})

        # forward request to service
        request_key = str(uuid4())

        content_length = int(self.headers.get('content-length', 0))
        if content_length:
            body = self.rfile.read(content_length)
            self.server.redis_client.hset(request_key, 'request.body', body)

        return {
            'appId': 95,
            'apiToken': self.server.tc_token(),
            'command': 'WebhookEvent',
            'expireSeconds': 1596817629,
            'headers': [{'name': name, 'value': value} for name, value in self.headers.items()],
            'method': method,
            'queryParams': params,
            'requestKey': request_key,
            'triggerId': trigger_id,
        }

    def _build_response(self) -> None:
        """Build response data from API service response."""
        # handle standard response
        self.send_response(200)

    def _build_response_marshall(self, response: dict) -> None:
        """Build response data from API service response."""
        # status code
        self.send_response(int(response['statusCode']))

        # headers
        for header in response['headers'] or []:
            self.send_header(header.get('name'), str(header.get('value')))
        self.end_headers()

        # body
        body = self.server.redis_client.hget(response['requestKey'], 'response.body')
        if body is not None:
            self.wfile.write(body)  # type: ignore

    def call_service(self, method: str):
        """Call the API Service

        Args:
            method: The HTTP method.
        """
        request = self._build_request(method)
        request_key = request['requestKey']

        # create lock and sve request
        event = Event()
        self.server.active_requests[request_key] = event

        # publish run service
        self.server.publish(
            message=json.dumps(request), topic=self.server.inputs.tc_svc_server_topic
        )

        # block for x seconds
        event.wait(60)
        response: dict = self.server.active_responses.pop(request_key, None)

        if response is None or response.get('statusCode') is None:
            self._build_response()
        else:
            self._build_response_marshall(response=response)

        return  # noqa: PLR1711

    def do_DELETE(self):  # noqa: N802, RUF100
        """Handle DELETE method."""
        return self.call_service('DELETE')

    def do_GET(self):  # noqa: N802, RUF100
        """Handle GET method."""
        if self.path.startswith('/_tcex/'):
            return self._handle_tcex(self.path)
        return self.call_service('GET')

    def _handle_tcex(self, path: str) -> None:
        """Route developer-dashboard requests."""
        clean = path.split('?', maxsplit=1)[0].rstrip('/')
        if clean in ('/_tcex', '/_tcex/index.html'):
            self._serve_html()
            return
        if clean == '/_tcex/status':
            self._serve_status()
            return
        self.send_error(404)

    def _serve_html(self) -> None:
        """Serve the dashboard HTML page."""
        body = _DEV_DASHBOARD_HTML.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_status(self) -> None:
        """Serve the JSON status payload."""
        if self.server.status_provider is None:
            body = b'{}'
        else:
            body = json.dumps(self.server.status_provider()).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress all HTTP access-log output; traffic is visible in the /_tcex/ dashboard."""

    def do_PATCH(self):  # noqa: N802, RUF100
        """Handle PATCH method."""
        return self.call_service('PATCH')

    def do_POST(self):  # noqa: N802, RUF100
        """Handle POST method."""
        return self.call_service('POST')
