"""Run App Local"""
# pylint: disable=wrong-import-position

# standard library
import json
import sys

# first-party
from tcex_cli.cli.run.launch_abc import LaunchABC
from tcex_cli.cli.run.model.app_organization_model import AppOrganizationModel
from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.render.render import Render


class LaunchOrganization(LaunchABC):
    """Launch an App"""

    @cached_property
    def inputs(self) -> AppOrganizationModel:
        """Return the App inputs."""
        app_inputs = {}
        if self.config_json.is_file():
            with self.config_json.open('r', encoding='utf-8') as fh:
                try:
                    app_inputs = json.load(fh)
                except ValueError as ex:
                    print(f'Error loading app_inputs.json: {ex}')
                    sys.exit(1)

        return AppOrganizationModel(**app_inputs)

    def print_input_data(self):
        """Print the inputs."""
        input_data = self.live_format_dict(self.inputs.dict()).strip()
        Render.panel.info(f'{input_data}', f'[{self.panel_title}]Input Data[/]')
