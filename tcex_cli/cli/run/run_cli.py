"""TcEx Framework Module"""

import json
import os
import sys
from pathlib import Path

from rich.markup import escape

from tcex_cli.app.config.install_json import InstallJson
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.cli.run.frontend_watcher import FrontendWatcher
from tcex_cli.cli.run.launch_organization import LaunchOrganization
from tcex_cli.cli.run.launch_playbook import LaunchPlaybook
from tcex_cli.cli.run.launch_service_api import LaunchServiceApi
from tcex_cli.cli.run.launch_service_custom_trigger import LaunchServiceCustomTrigger
from tcex_cli.cli.run.launch_service_webhook_trigger import LaunchServiceWebhookTrigger
from tcex_cli.cli.run.model.app_api_service_model import (
    API_SERVICE_HOST_DEFAULT,
    API_SERVICE_PORT_DEFAULT,
    AppApiServiceModel,
)
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

        # set os environment variables
        os.environ['TCEX_RUN_LOCAL'] = '1'

    def _display_api_settings(
        self,
        api_inputs: AppApiServiceModel | AppWebhookTriggerServiceModel,
    ) -> None:
        """Display API settings panel."""
        content = (
            'Current API Service Settings:\n'
            f'host: [{self.accent}]{api_inputs.api_service_host}[/{self.accent}]\n'
            f'port: [{self.accent}]{api_inputs.api_service_port}[/{self.accent}]\n\n'
            'API default settings can be overridden with these environment variables:\n'
            f'  - [{self.accent}]API_SERVICE_HOST[/{self.accent}]'
            f'  (default: {API_SERVICE_HOST_DEFAULT})\n'
            f'  - [{self.accent}]API_SERVICE_PORT[/{self.accent}]'
            f'  (default: {API_SERVICE_PORT_DEFAULT})'
        )
        Render.panel.info(content, 'API Settings')

    def _validate_in_app_directory(self):
        """Return True if in App directory."""
        if not Path('app.py').is_file() or not Path('run.py').is_file():
            Render.panel.failure('Not in App directory.')

    def debug(self, debug_port: int):
        """Run the App in debug mode."""

        import debugpy  # noqa: T100, PLC0415

        Render.panel.info(
            f'Waiting for debugger to attach to port: [{self.accent}]{debug_port}[/{self.accent}].',
            title='[blue]Debug[/blue]',
        )

        debugpy.listen(debug_port)  # noqa: T100
        debugpy.wait_for_client()  # noqa: T100

    def exit_cli(self, exit_code):
        """Exit the CLI command."""
        Render.panel.info(f'{exit_code}', f'[{self.panel_title}]Exit Code[/]')
        sys.exit(exit_code)

    @staticmethod
    def _read_config_description(config_file: Path) -> str:
        """Return the best-effort description from a config file's raw JSON."""
        try:
            data = json.loads(config_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return ''
        if isinstance(data, dict):
            description = data.get('description')
            if isinstance(description, str):
                return description
        return ''

    def _select_config_from_dir(self, config_dir: Path) -> Path:
        """Render a menu of app_inputs.d/ candidates and return the selected file."""
        candidates = sorted(config_dir.glob('*.json'))
        if not candidates:
            Render.panel.failure(
                'No app_inputs.json found. Provide app_inputs.json, pass --config <file>, '
                'or add a config under app_inputs.d/.'
            )

        # render the list of available configs (index, filename, description)
        items = [
            (i, candidate.stem, self._read_config_description(candidate))
            for i, candidate in enumerate(candidates, start=1)
        ]
        Render.table_app_inputs_d(items)

        # prompt the user to select a config by number
        choices = [str(i) for i in range(1, len(candidates) + 1)]
        answer = Render.prompt.ask('Select a config to run', choices=choices, default='1')
        if not answer:
            Render.panel.failure('No config selected.')

        selected = candidates[int(answer) - 1]
        if not selected.is_file():
            Render.panel.failure(f'Config file not found [{selected}].')
        return selected

    def resolve_config(self, config_json: Path | None) -> Path:  # noqa: RET503
        """Resolve the config file to use, applying the precedence order.

        Precedence:
            1. an explicit ``--config <file>`` (must exist) wins and skips the menu;
            2. else ``app_inputs.json`` if present;
            3. else an ``app_inputs.d/`` selection menu (if it holds any ``*.json``);
            4. else a helpful failure.

        Every returned path is a verified existing file.
        """
        # explicit --config wins (including app_inputs.d/<file>.json) and skips the menu
        if config_json is not None:
            if not config_json.is_file():
                Render.panel.failure(f'Config file not found [{config_json}].')
            return config_json

        # legacy single-config default
        app_inputs_json = Path('app_inputs.json')
        if app_inputs_json.is_file():
            return app_inputs_json

        # multi-config directory
        config_dir = Path('app_inputs.d')
        if config_dir.is_dir():
            return self._select_config_from_dir(config_dir)

        Render.panel.failure(
            'No app_inputs.json found. Provide app_inputs.json, pass --config <file>, '
            'or add a config under app_inputs.d/.'
        )

    def _display_running_info(
        self,
        inputs: AppApiServiceModel | AppWebhookTriggerServiceModel,
    ) -> None:
        """Print a static summary panel when the live display TUI is disabled."""
        from importlib.metadata import PackageNotFoundError  # noqa: PLC0415
        from importlib.metadata import version as pkg_version  # noqa: PLC0415

        try:
            tcex_ver = pkg_version('tcex')
        except PackageNotFoundError:
            tcex_ver = 'not installed'

        server_url = f'http://{inputs.api_service_host}:{inputs.api_service_port}'
        dashboard_url = f'{server_url}/_tcex/'
        tc_instance = escape(str(inputs.tc_api_path))
        app_name = escape(str(self.ij.model.display_name))
        app_version = escape(str(self.ij.model.program_version))

        content = (
            f'App:          [{self.accent}]{app_name}[/{self.accent}] v{app_version}\n'
            f'TcEx:         [{self.accent}]{tcex_ver}[/{self.accent}]\n'
            f'TC Instance:  [{self.accent}]{tc_instance}[/{self.accent}]\n'
            f'Server:       [{self.accent}]{server_url}[/{self.accent}]\n'
            f'Dashboard:    [{self.accent}]{dashboard_url}[/{self.accent}]'
        )
        Render.panel.info(content, f'[{self.panel_title}]Running[/]')

    def run(
        self,
        config_json: Path | None,
        debug: bool = False,
        *,
        watch_backend: bool = False,
        watch_frontend: bool = False,
        ui_configuration: str = 'production',
        live_display: bool = False,
    ):
        """Run the App"""
        # start the Angular frontend watcher if requested
        frontend_watcher: FrontendWatcher | None = None
        if watch_frontend:
            frontend_watcher = FrontendWatcher(Path.cwd(), configuration=ui_configuration)
            frontend_watcher.start()

        # resolve the config to use (single owner of resolution)
        resolved = self.resolve_config(config_json)

        # --watch-backend only applies to long-running service Apps.  Playbook and Organization
        # Apps exit after a single run; watch mode would loop them without benefit.
        _short_lived = {'playbook', 'organization', 'system'}
        if watch_backend and self.ij.model.runtime_level.lower() in _short_lived:
            Render.panel.warning(
                f'--watch-backend is not supported for '
                f'{self.ij.model.runtime_level} Apps (they exit after each run). '
                'Continuing without file-watching.'
            )
            watch_backend = False

        match self.ij.model.runtime_level.lower():
            case 'apiservice':
                Render.panel.info('Launching API Service', f'[{self.panel_title}]Running App[/]')
                launch_app = LaunchServiceApi(
                    resolved, watch_backend=watch_backend, frontend_watcher=frontend_watcher
                )
                self._display_api_settings(launch_app.model.inputs)
                if not live_display:
                    self._display_running_info(launch_app.model.inputs)
                launch_app.setup(debug, live_display=live_display)
                exit_code = launch_app.launch()

            case 'feedapiservice':
                Render.panel.info(
                    'Launching Feed API Service', f'[{self.panel_title}]Running App[/]'
                )
                launch_app = LaunchServiceApi(
                    resolved, watch_backend=watch_backend, frontend_watcher=frontend_watcher
                )
                launch_app.setup(debug, live_display=live_display)
                exit_code = launch_app.launch()

            case 'organization' | 'system':
                Render.panel.info('Launching Job App', f'[{self.panel_title}]Running App[/]')
                launch_app = LaunchOrganization(resolved, watch_backend=watch_backend)
                exit_code = launch_app.launch()
                launch_app.print_input_data()

            case 'playbook':
                launch_app = LaunchPlaybook(resolved, watch_backend=watch_backend)
                launch_app.validate_inputs()
                launch_app.stage()
                exit_code = launch_app.launch()
                launch_app.print_input_data()
                launch_app.print_output_data()

            case 'triggerservice':
                Render.panel.info(
                    'Launching Trigger Service', f'[{self.panel_title}]Running App[/]'
                )
                launch_app = LaunchServiceCustomTrigger(resolved, watch_backend=watch_backend)
                launch_app.setup(debug)
                exit_code = launch_app.launch()

            case 'webhooktriggerservice':
                Render.panel.info(
                    'Launching Webhook Trigger Service', f'[{self.panel_title}]Running App[/]'
                )
                launch_app = LaunchServiceWebhookTrigger(
                    resolved, watch_backend=watch_backend, frontend_watcher=frontend_watcher
                )
                self._display_api_settings(launch_app.model.inputs)
                if not live_display:
                    self._display_running_info(launch_app.model.inputs)
                launch_app.setup(debug, live_display=live_display)
                exit_code = launch_app.launch()

            case _:
                Render.panel.failure(f'Invalid runtime level: {self.ij.model.runtime_level}')

        # exit execution
        self.exit_cli(exit_code)
