"""TcEx Framework Module"""
# standard library
from threading import Thread

# third-party
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel

# first-party
from tcex_cli.cli.run.launch_service_common_trigger_abc import LaunchServiceCommonTriggersABC
from tcex_cli.cli.run.model.app_webhook_trigger_service_model import AppWebhookTriggerInputModel
from tcex_cli.cli.run.request_handler_webhook import RequestHandlerWebhook
from tcex_cli.cli.run.web_server import WebServer
from tcex_cli.pleb.cached_property import cached_property


class LaunchServiceWebhookTrigger(LaunchServiceCommonTriggersABC):
    """Launch an App"""

    @cached_property
    def api_web_server(self) -> WebServer:
        """Return an instance of the API Web Server."""
        return WebServer(
            self.model.inputs,
            self.message_broker,
            self.publish,
            self.redis_client,
            RequestHandlerWebhook,
            self.tc_token,
        )

    @cached_property
    def model(self) -> AppWebhookTriggerInputModel:
        """Return the App inputs."""
        return AppWebhookTriggerInputModel(**self.construct_model_inputs())

    def live_data_display(self):
        """Display live data."""
        console = Console()
        layout = Layout()

        # Divide the "screen" in to three parts
        header_minimum = len(self.model.trigger_inputs) + 2 if self.model.trigger_inputs else 3
        layout.split(
            Layout(self.live_data_header(), name='header', ratio=1, minimum_size=header_minimum),
            Layout(self.live_data_table(), name='main', ratio=10, minimum_size=3),
            Layout(self.live_data_commands(), name='commands', ratio=10, minimum_size=3),
        )

        with Live(
            layout,
            console=console,
            refresh_per_second=4,
            screen=True,
            vertical_overflow='ellipsis',
        ) as _:
            while True:
                self.event.wait()
                self.log.trace('Updating live data table.')
                layout['header'].update(self.live_data_header())
                layout['main'].update(self.live_data_table())
                layout['commands'].update(self.live_data_commands())
                self.event.clear()

    def live_data_header(self) -> Panel:
        """Display live header."""
        panel_data = []
        if self.model.trigger_inputs:
            for trigger_id, _ in enumerate(self.model.trigger_inputs):
                panel_data.append(
                    f'Running server: [{self.accent}]http://{self.model.inputs.api_service_host}'
                    f':{self.model.inputs.api_service_port}/{trigger_id}[/{self.accent}]'
                    f' - Trigger ID: [{self.accent}]{trigger_id}[/{self.accent}]'
                )
        else:
            panel_data = (
                f'Running server: [{self.accent}]http://{self.model.inputs.api_service_host}'
                f':{self.model.inputs.api_service_port}[/{self.accent}]'
            )

        return Panel(
            '\n'.join(panel_data),
            expand=True,
            title=f'[{self.panel_title}]HTTP Server[/]',
            title_align='left',
        )

    def setup(self, debug: bool = False):
        """Configure the API Web Server."""
        # setup web server
        self.api_web_server.setup()

        # start keyboard listener
        kl = Thread(target=self.keyboard_listener, name='KeyboardListener', daemon=True)
        kl.start()

        # start message broker listener
        self.message_broker_listen()

        # add call back to process server channel messages
        self.message_broker.add_on_message_callback(
            callback=self.process_client_channel,
            index=0,
            topics=[self.model.inputs.tc_svc_client_topic],
        )

        # add call back to process server channel messages
        self.message_broker.add_on_message_callback(
            callback=self.process_server_channel,
            index=0,
            topics=[self.model.inputs.tc_svc_server_topic],
        )

        # start live display
        if debug is False:
            self.display_thread = Thread(
                target=self.live_data_display, name='LiveDataDisplay', daemon=True
            )
            self.display_thread.start()
