"""TcEx Framework Module"""

# standard library
from threading import Thread

# third-party
from rich.console import Console
from rich.layout import Layout
from rich.live import Live

# first-party
from tcex_cli.cli.run.launch_service_common_trigger_abc import LaunchServiceCommonTriggersABC
from tcex_cli.cli.run.model.app_trigger_service_model import AppTriggerInputModel
from tcex_cli.pleb.cached_property import cached_property


class LaunchServiceCustomTrigger(LaunchServiceCommonTriggersABC):
    """Launch an App"""

    @cached_property
    def model(self) -> AppTriggerInputModel:
        """Return the App inputs."""
        return AppTriggerInputModel(**self.construct_model_inputs())

    def live_data_display(self):
        """Display live data."""
        console = Console()
        layout = Layout()

        # Divide the "screen" in to three parts
        layout.split(
            Layout(self.live_data_table(), name='main', ratio=1),
            Layout(self.live_data_commands(), name='commands', ratio=1),
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
                layout['main'].update(self.live_data_table())
                layout['commands'].update(self.live_data_commands())
                self.event.clear()

    def setup(self, debug: bool = False):
        """Configure the API Web Server."""
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
