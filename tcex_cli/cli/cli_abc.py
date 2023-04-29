"""TcEx Framework Module"""
# standard library
import logging
import os
import sys
from abc import ABC
from functools import cached_property
from pathlib import Path

# third-party
from semantic_version import Version

# first-party
from tcex_cli.app.app import App
from tcex_cli.registry import registry
from tcex_cli.util import Util

# get logger
_logger = logging.getLogger(__name__.split('.', maxsplit=1)[0])


class CliABC(ABC):
    """Base Class for ThreatConnect command line tools."""

    def __init__(self):
        """Initialize instance properties."""
        # properties
        self.accent = 'dark_orange'
        self.app_path = Path.cwd()
        self.exit_code = 0
        self.i1 = ' ' * 4  # indent level 1
        self.i2 = ' ' * 8  # indent level 2
        self.i3 = ' ' * 12  # indent level 3
        self.log = _logger
        self.util = Util()

        # update system path
        self.update_system_path()

        # register commands
        registry.add_service(App, self.app)

    @cached_property
    def app(self) -> App:
        """Return instance of App."""
        return App()

    @cached_property
    def cli_out_path(self) -> Path:
        """Return the path to the tcex cli command out directory."""
        _out_path = Path(os.path.expanduser('~/.tcex'))
        _out_path.mkdir(exist_ok=True, parents=True)
        return _out_path

    @cached_property
    def deps_dir(self) -> Path:
        """Return the deps directory."""
        if self.app.ij.model.sdk_version < Version('4.0.0'):
            return Path('lib_latest')
        return Path('deps')

    def update_system_path(self):
        """Update the system path to ensure project modules and dependencies can be found."""
        # insert the deps or lib_latest directory into the system Path. this entry
        # will be bumped to index 1 after adding the current working directory.
        deps_dir_str = str(self.deps_dir.resolve())
        if not [p for p in sys.path if deps_dir_str in p]:
            sys.path.insert(0, deps_dir_str)

        # insert the current working directory into the system Path for
        # the App, ensuring that it is always the first entry in the list.
        cwd_str = str(Path.cwd())
        try:
            sys.path.remove(cwd_str)
        except ValueError:
            pass
        sys.path.insert(0, cwd_str)

        # reload install.json after path is update (get updated sdkVersion)
        self.app.clear_cache()
