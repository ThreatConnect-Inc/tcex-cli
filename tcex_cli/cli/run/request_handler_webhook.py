"""TcEx Framework Module"""
# standard library
import http.server
import json
from threading import Event
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

if TYPE_CHECKING:
    # first-party
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
            self.wfile.write(body)

    def call_service(self, method: str):  # pylint: disable=useless-return
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

        return

    def do_DELETE(self):
        """Handle DELETE method."""
        return self.call_service('DELETE')

    def do_GET(self):
        """Handle GET method."""
        return self.call_service('GET')

    def do_PATCH(self):
        """Handle PATCH method."""
        return self.call_service('PATCH')

    def do_POST(self):
        """Handle POST method."""
        return self.call_service('POST')
