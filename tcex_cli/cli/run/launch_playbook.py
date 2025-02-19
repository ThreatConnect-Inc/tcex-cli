"""Run App Local"""

# standard library
from pathlib import Path

# first-party
from tcex_cli.cli.run.launch_abc import LaunchABC
from tcex_cli.cli.run.model.app_playbook_model import AppPlaybookInputModel
from tcex_cli.cli.run.playbook_create import PlaybookCreate
from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.render.render import Render


class LaunchPlaybook(LaunchABC):
    """Launch an App"""

    def __init__(self, config_json: Path):
        """Initialize class properties."""
        super().__init__(config_json)
        self.playbook = PlaybookCreate(
            self.redis_client, self.model.inputs.tc_playbook_kvstore_context
        )

    @cached_property
    def model(self) -> AppPlaybookInputModel:
        """Return the App inputs."""
        inputs = self.construct_model_inputs()
        model = AppPlaybookInputModel(**inputs)
        model.stage.kvstore = inputs.get('stage', {}).get('kvstore', {})

        return model

    def stage(self):
        """Stage the variables in redis."""
        for key, value in self.model.stage.kvstore.items():
            self.playbook.any(key, value)

    def print_output_data(self):
        """Log the playbook output data."""
        output_data = self.live_format_dict(
            self.output_data(self.model.inputs.tc_playbook_kvstore_context)
        ).strip()
        Render.panel.info(f'{output_data}', f'[{self.panel_title}]Output Data[/]')
