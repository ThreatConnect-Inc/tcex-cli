"""TcEx Framework Module"""
# standard library
import http.server
import json
import time
from threading import Event
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

if TYPE_CHECKING:
    # first-party
    from tcex_cli.cli.run.web_server import WebServer  # CIRCULAR IMPORT


class RequestHandlerApi(http.server.BaseHTTPRequestHandler):
    """Request handler to forward request to API service.

    Required the following in WebServer class:
    - inputs
    - redis_client
    - publish
    - tc_token
    """

    server: 'WebServer'

    def _build_request(self, method: str) -> dict:
        """Return request built from incoming HTTP request.

        {
            "apiToken": "SVC:5:RgIo6v:1596670377509:95:vWO1zu8W0a2NyXctWORKMe/kA616P6Vk8dsYvG ... ",
            "appId": 95,
            "bodyVariable": "request.body",
            "command": "RunService",
            "expireSeconds": 1596670377,
            "headers": [
                {
                    "name": "Accept",
                    "value": "*/*"
                },
                {
                    "name": "User-Agent",
                    "value": "PostmanRuntime/7.26.2"
                },
                {
                    "name": "Content-Type",
                    "value": "application/json"
                }
            ],
            "method": "GET",
            "path": "/data",
            "queryParams": [
                {
                    "name": "max",
                    "value": "1000"
                }
            ],
            "requestKey": "c29927c8-b94d-4116-a397-e6eb7002f41c"
        }

        Args:
            method: The HTTP method.

        Returns:
            dict: The response to send to API service over message broker topic.
        """
        url_parts = urlparse(self.path)

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
        request_url = self.headers.get('Host', self.server.inputs.server_url)
        if request_url and not request_url.startswith(('http://', 'https://')):
            request_url = f'https://{request_url}'

        return {
            'apiToken': self.server.tc_token(),
            'appId': 95,
            'bodyVariable': 'request.body',
            'command': 'RunService',
            'expireSeconds': int(time.time() + 600),
            'headers': [{'name': name, 'value': value} for name, value in self.headers.items()],
            'method': method,
            'path': url_parts.path,
            'queryParams': params,
            'requestKey': request_key,
            'requestUrl': request_url,
            'remoteAddress': '127.0.0.1',
        }

    def _build_response(self, response: dict | None = None) -> None:
        """Build response data from API service response.

        {
            "bodyVariable": "response.body",
            "command": "Acknowledged",
            "headers": [
                {
                    "name": "x-cache",
                    "value": "MISS"
                },
                {
                    "name": "retry-after",
                    "value": "20"
                },
                {
                    "name": "content-type",
                    "value": "application/json"
                },
            ],
            "requestKey": "97190c5a-05e7-493d-8cb5-33844190eb72",
            "status": "Too Many Requests",
            "statusCode": "429",
            "type": "RunService"
        }

        Args:
            response: The response data from API service.
        """
        if response is None:
            self.send_error(500, message='No response sent on message broker client channel.')
            return

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

        self._build_response(response=response)

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

    def do_PUT(self):
        """Handle POST method."""
        return self.call_service('PUT')
