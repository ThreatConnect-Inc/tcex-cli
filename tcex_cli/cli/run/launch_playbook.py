"""Run App Local"""
# standard library
import json
import sys

# first-party
from tcex_cli.cli.run.launch_abc import LaunchABC
from tcex_cli.cli.run.model.app_playbook_model import AppPlaybookModel
from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.render.render import Render


class LaunchPlaybook(LaunchABC):
    """Launch an App"""

    @cached_property
    def inputs(self) -> AppPlaybookModel:
        """Return the App inputs."""
        app_inputs = {}
        if self.config_json.is_file():
            with self.config_json.open('r', encoding='utf-8') as fh:
                try:
                    app_inputs = json.load(fh)
                except ValueError as ex:
                    print(f'Error loading app_inputs.json: {ex}')
                    sys.exit(1)

        return AppPlaybookModel(**app_inputs)

    def print_input_data(self):
        """Print the inputs."""
        input_data = self.live_format_dict(self.inputs.dict()).strip()
        Render.panel.info(f'{input_data}', f'[{self.panel_title}]Input Data[/]')

    def print_output_data(self):
        """Log the playbook output data."""
        output_data = self.live_format_dict(
            self.output_data(self.inputs.tc_playbook_kvstore_context)
        ).strip()
        Render.panel.info(f'{output_data}', f'[{self.panel_title}]Output Data[/]')
