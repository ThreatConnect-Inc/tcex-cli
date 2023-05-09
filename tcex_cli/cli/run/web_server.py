"""TcEx Framework Module"""
# standard library
import http.server
import json
import logging
import socketserver
from collections.abc import Callable
from threading import Thread

# third-party
import paho.mqtt.client as mqtt
import redis

# first-party
from tcex_cli.cli.run.model.app_api_service_model import AppApiServiceModel
from tcex_cli.cli.run.model.app_webhook_trigger_service_model import AppWebhookTriggerServiceModel
from tcex_cli.cli.run.request_handler_api import RequestHandlerApi
from tcex_cli.cli.run.request_handler_webhook import RequestHandlerWebhook
from tcex_cli.logger.trace_logger import TraceLogger
from tcex_cli.message_broker.mqtt_message_broker import MqttMessageBroker

# get tcex logger
_logger: TraceLogger = logging.getLogger(__name__.split('.', maxsplit=1)[0])  # type: ignore


class WebServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """HTTP Server for testing API Services"""

    allow_reuse_address = True

    def __init__(
        self,
        inputs: AppApiServiceModel | AppWebhookTriggerServiceModel,
        message_broker: MqttMessageBroker,
        publish: Callable,
        redis_client: redis.Redis,
        request_handler: type[RequestHandlerApi] | type[RequestHandlerWebhook],
        tc_token: Callable,
    ):
        """Initialize instance properties"""
        super().__init__(
            (inputs.api_service_host, inputs.api_service_port),
            request_handler,
        )
        self.inputs = inputs
        self.message_broker = message_broker
        self.publish = publish
        self.redis_client = redis_client
        self.tc_token = tc_token

        # properties
        self.active_requests = {}
        self.active_responses = {}
        self.log = _logger

        # start server thread
        service = Thread(group=None, target=self.run, name='SimpleServerThread', daemon=True)
        service.start()

    def on_message(self, client: mqtt.Client, userdata, message):  # pylint: disable=unused-argument
        """Handle message broker on_message events."""
        try:
            msg = json.loads(message.payload)
        except ValueError as ex:
            raise RuntimeError(f'Could not parse API service response JSON. ({message})') from ex

        # only process RunService Acknowledged commands.
        ack_type = (msg.get('type') or '').lower()
        command = msg.get('command').lower()
        if command == 'acknowledged' and ack_type in ['runservice', 'webhookevent']:
            self.active_responses[msg['requestKey']] = msg

            # release Event create in run_service_api_request_handler->call_service
            self.active_requests.pop(msg.get('requestKey')).set()

    def run(self):
        """Run the server in threat."""
        self.serve_forever()

    def setup(self):
        """Configure the  server."""
        self.message_broker.add_on_message_callback(
            callback=self.on_message, topics=[self.inputs.tc_svc_client_topic]
        )
