"""Run App Local"""

# pylint: disable=wrong-import-position

# first-party
from tcex_cli.cli.run.launch_abc import LaunchABC
from tcex_cli.cli.run.model.app_organization_model import AppOrganizationInputModel
from tcex_cli.pleb.cached_property import cached_property


class LaunchOrganization(LaunchABC):
    """Launch an App"""

    @cached_property
    def model(self) -> AppOrganizationInputModel:
        """Return the App inputs."""
        return AppOrganizationInputModel(**self.construct_model_inputs())
