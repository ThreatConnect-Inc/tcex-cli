"""TcEx Framework Module"""

# standard library
from typing import Optional

# third-party
import typer

# first-party
from tcex_cli.cli.deps.deps_cli import DepsCli
from tcex_cli.render.render import Render

# typer does not yet support PEP 604, but pyupgrade will enforce
# PEP 604. this is a temporary workaround until support is added.
IntOrNone = Optional[int]  # noqa: UP007, UP045, RUF100
StrOrNone = Optional[str]  # noqa: UP007, UP045, RUF100


def command(
    app_builder: bool = typer.Option(
        default=False, help='(Advanced) If true, this command was run from App Builder.'
    ),
    branch: StrOrNone = typer.Option(
        None,
        help=('[deprecated] The git branch of the tcex repository to use. '),
    ),
    no_cache_dir: bool = typer.Option(default=False, help='Do not use pip cache directory.'),
    pre: bool = typer.Option(default=False, help='Install pre-release packages.'),
    proxy_host: StrOrNone = typer.Option(None, help='(Advanced) Hostname for the proxy server.'),
    proxy_port: IntOrNone = typer.Option(None, help='(Advanced) Port number for the proxy server.'),
    proxy_user: StrOrNone = typer.Option(None, help='(Advanced) Username for the proxy server.'),
    proxy_pass: StrOrNone = typer.Option(None, help='(Advanced) Password for the proxy server.'),
):
    r"""Install dependencies defined in the requirements.txt file.

    Optional environment variables include:\n
    * PROXY_HOST\n
    * PROXY_PORT\n
    * PROXY_USER\n
    * PROXY_PASS\n
    """
    cli = DepsCli(
        app_builder,
        no_cache_dir,
        pre,
        proxy_host,
        proxy_port,
        proxy_user,
        proxy_pass,
    )
    try:
        if branch:
            Render.panel.failure('The --branch arg is deprecated.')

        # validate python versions
        cli.validate_python_version()

        # configure proxy settings
        cli.configure_proxy()

        # install debs
        cli.install_deps()

        # install dev deps
        cli.install_deps_tests()

        # render output
        Render.table.key_value('Dependency Summary', [o.dict() for o in cli.output])
    except Exception as ex:
        cli.log.exception('Failed to run "tcex deps" command.')
        Render.panel.failure(f'Exception: {ex}')
