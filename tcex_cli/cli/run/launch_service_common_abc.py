"""TcEx Framework Module"""

# standard library
from abc import ABC
from pathlib import Path
from threading import Event, Thread

# third-party
import paho.mqtt.client as mqtt
from rich.panel import Panel
from rich.table import Table

# first-party
from tcex_cli.cli.run.launch_abc import LaunchABC
from tcex_cli.message_broker.mqtt_message_broker import MqttMessageBroker
from tcex_cli.pleb.cached_property import cached_property


class LaunchServiceCommonABC(LaunchABC, ABC):
    """Launch Class for all Service type Apps."""

    def __init__(self, config_json: Path):
        """Initialize instance properties."""
        super().__init__(config_json)

        # properties
        self.event = Event()
        self.display_thread: Thread
        self.message_data: list[dict[str, str]] = []
        self.stop_server = False

    def live_data_commands(self):
        """Display live data."""

        table = Table(expand=True, pad_edge=True, show_edge=False, show_lines=False)
        table.add_column('Datetime')
        table.add_column('Channel')
        table.add_column('Command')
        table.add_column('Type')

        try:
            for md in self.message_data[::-1]:
                table.add_row(
                    md['msg_time'],
                    md['channel'],
                    md['command'],
                    md['type'],
                )
        except Exception:
            self.log.exception('Error in live_data_command_table')

        return Panel(
            table,
            border_style='',
            title=f'[{self.panel_title}]Commands[/]',
            title_align='left',
        )

    @cached_property
    def message_broker(self):
        """Return an instance of the Message Broker."""
        broker = MqttMessageBroker(
            self.model.inputs.tc_svc_broker_host,  # type: ignore
            self.model.inputs.tc_svc_broker_port,  # type: ignore
            self.model.inputs.tc_svc_broker_timeout,  # type: ignore
        )
        broker.register_callbacks()
        return broker

    def message_broker_listen(self):
        """List for message coming from broker."""
        self.message_broker.add_on_connect_callback(self.on_connect)

        t = Thread(name='broker-listener', target=self.message_broker.connect, args=(), daemon=True)
        t.start()

    # pylint: disable=unused-argument
    def on_connect(self, client: mqtt.Client, userdata, flags, rc: int):
        """Handle message broker on_connect events."""
        # subscribe to topics
        self.message_broker.client.subscribe(self.model.inputs.tc_svc_client_topic)  # type: ignore
        self.message_broker.client.subscribe(self.model.inputs.tc_svc_server_topic)  # type: ignore
        self.log.info('Connected to message broker and subscribing to client topic.')

    def publish(self, message: str, topic: str):
        """Publish message on server channel."""
        self.message_broker.publish(message, topic)
