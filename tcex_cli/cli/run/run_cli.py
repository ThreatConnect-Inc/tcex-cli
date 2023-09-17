"""TcEx Framework Module"""
# standard library
import sys
from pathlib import Path

# first-party
from tcex_cli.app.config.install_json import InstallJson
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.cli.run.launch_organization import LaunchOrganization
from tcex_cli.cli.run.launch_playbook import LaunchPlaybook
from tcex_cli.cli.run.launch_service_api import LaunchServiceApi
from tcex_cli.cli.run.launch_service_custom_trigger import LaunchServiceCustomTrigger
from tcex_cli.cli.run.launch_service_webhook_trigger import LaunchServiceWebhookTrigger
from tcex_cli.cli.run.model.app_api_service_model import AppApiServiceModel
from tcex_cli.cli.run.model.app_webhook_trigger_service_model import AppWebhookTriggerServiceModel
from tcex_cli.render.render import Render


class RunCli(CliABC):
    """Validate syntax and schemas."""

    def __init__(self):
        """Initialize instance properties."""
        super().__init__()

        # properties
        self.ij = InstallJson()
        self.panel_title = 'blue'

        # validate in App directory
        self._validate_in_app_directory()

    def _display_api_settings(self, api_inputs: AppApiServiceModel | AppWebhookTriggerServiceModel):
        """Display API settings."""
        Render.panel.info(
            (
                'Current API Service Settings:\n'
                f'host: [{self.accent}]{api_inputs.api_service_host}[/{self.accent}]\n'
                f'port: [{self.accent}]{api_inputs.api_service_port}[/{self.accent}]\n\n'
                'API default settings can be overridden with these environment variables:\n'
                f'  - [{self.accent}]API_SERVICE_HOST[/{self.accent}]\n'
                f'  - [{self.accent}]API_SERVICE_PORT[/{self.accent}]'
            ),
            'API Settings',
        )

    def _validate_in_app_directory(self):
        """Return True if in App directory."""
        if not Path('app.py').is_file() or not Path('run.py').is_file():
            Render.panel.failure('Not in App directory.')

    def debug(self, debug_port: int):
        """Run the App in debug mode."""
        # third-party
        import debugpy  # pylint: disable=import-outside-toplevel

        Render.panel.info(
            f'Waiting for debugger to attach to port: [{self.accent}]{debug_port}[/{self.accent}].',
            title='[blue]Debug[/blue]',
        )

        debugpy.listen(debug_port)
        debugpy.wait_for_client()

    def exit_cli(self, exit_code):
        """Exit the CLI command."""
        Render.panel.info(f'{exit_code}', f'[{self.panel_title}]Exit Code[/]')
        sys.exit(exit_code)

    def run(self, config_json: Path):
        """Run the App"""

        match self.ij.model.runtime_level.lower():
            case 'apiservice':
                Render.panel.info('Launching API Service', f'[{self.panel_title}]Running App[/]')
                launch_app = LaunchServiceApi(config_json)
                self._display_api_settings(launch_app.model.inputs)
                launch_app.setup()
                exit_code = launch_app.launch()
                self.exit_cli(exit_code)

            case 'feedapiservice':
                Render.panel.info(
                    'Launching Feed API Service', f'[{self.panel_title}]Running App[/]'
                )
                launch_app = LaunchServiceApi(config_json)
                launch_app.setup()
                exit_code = launch_app.launch()
                self.exit_cli(exit_code)

            case 'organization':
                Render.panel.info('Launching Job App', f'[{self.panel_title}]Running App[/]')
                launch_app = LaunchOrganization(config_json)
                exit_code = launch_app.launch()
                launch_app.print_input_data()
                self.exit_cli(exit_code)

            case 'playbook':
                Render.panel.info('Launching Playbook App', f'[{self.panel_title}]Running App[/]')
                launch_app = LaunchPlaybook(config_json)
                launch_app.stage()
                exit_code = launch_app.launch()
                launch_app.print_input_data()
                launch_app.print_output_data()
                self.exit_cli(exit_code)

            case 'triggerservice':
                Render.panel.info(
                    'Launching Trigger Service', f'[{self.panel_title}]Running App[/]'
                )
                launch_app = LaunchServiceCustomTrigger(config_json)
                launch_app.setup()
                exit_code = launch_app.launch()
                self.exit_cli(exit_code)

            case 'webhooktriggerservice':
                Render.panel.info(
                    'Launching Webhook Trigger Service', f'[{self.panel_title}]Running App[/]'
                )
                launch_app = LaunchServiceWebhookTrigger(config_json)
                self._display_api_settings(launch_app.model.inputs)
                launch_app.setup()
                exit_code = launch_app.launch()
                self.exit_cli(exit_code)
