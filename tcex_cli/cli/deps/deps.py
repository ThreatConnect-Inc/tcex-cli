"""TcEx Framework Module"""

# standard library
from typing import Optional

# third-party
import typer

# first-party
from tcex_cli.cli.deps.deps_cli import DepsCli
from tcex_cli.render.render import Render

# vars
default_branch = 'v2'

# typer does not yet support PEP 604, but pyupgrade will enforce
# PEP 604. this is a temporary workaround until support is added.
IntOrNone = Optional[int]
StrOrNone = Optional[str]


def command(
    app_builder: bool = typer.Option(
        False, help='(Advanced) If true, this command was run from App Builder.'
    ),
    branch: str = typer.Option(
        default_branch,
        help=(
            'The git branch of the tcex repository to use. '
            'This override what is in the requirements.txt file.'
        ),
    ),
    no_cache_dir: bool = typer.Option(False, help='Do not use pip cache directory.'),
    pre: bool = typer.Option(False, help='Install pre-release packages.'),
    proxy_host: StrOrNone = typer.Option(None, help='(Advanced) Hostname for the proxy server.'),
    proxy_port: IntOrNone = typer.Option(None, help='(Advanced) Port number for the proxy server.'),
    proxy_user: StrOrNone = typer.Option(None, help='(Advanced) Username for the proxy server.'),
    proxy_pass: StrOrNone = typer.Option(None, help='(Advanced) Password for the proxy server.'),
):
    """Install dependencies defined in the requirements.txt file."""
    cli = DepsCli(
        app_builder,
        branch,
        no_cache_dir,
        pre,
        proxy_host,
        proxy_port,
        proxy_user,
        proxy_pass,
    )
    try:
        # validate python versions
        cli.validate_python_version()

        # configure proxy settings
        cli.configure_proxy()

        # if branch != default_branch:
        #     # create temp requirements.txt file pointing to tcex branch
        #     cli.create_temp_requirements()

        # install debs
        cli.install_deps()

        # install dev deps
        cli.install_deps_tests()

        # render output
        Render.table.key_value('Dependency Summary', [o.dict() for o in cli.output])
    except Exception as ex:
        cli.log.exception('Failed to run "tcex deps" command.')
        Render.panel.failure(f'Exception: {ex}')
