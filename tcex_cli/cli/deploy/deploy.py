"""TcEx Framework Module"""

# standard library
from typing import Optional

# third-party
import typer

# first-party
from tcex_cli.cli.deploy.deploy_cli import DeployCli
from tcex_cli.render.render import Render

# typer does not yet support PEP 604, but pyupgrade will enforce
# PEP 604. this is a temporary workaround until support is added.
IntOrNone = Optional[int]
StrOrNone = Optional[str]


def command(
    server: str = typer.Argument(..., envvar='TC_DEPLOY_SERVER'),
    allow_all_orgs: bool = typer.Option(True, help='If true all orgs are able to use the App.'),
    allow_distribution: bool = typer.Option(
        True, help='If true the App is allowed to be distributed.'
    ),
    app_file: StrOrNone = typer.Option(
        None,
        help='The fully qualified path to App file. Will be auto-detected if not provided.',
    ),
    proxy_host: StrOrNone = typer.Option(None, help='(Advanced) Hostname for the proxy server.'),
    proxy_port: IntOrNone = typer.Option(None, help='(Advanced) Port number for the proxy server.'),
    proxy_user: StrOrNone = typer.Option(None, help='(Advanced) Username for the proxy server.'),
    proxy_pass: StrOrNone = typer.Option(None, help='(Advanced) Password for the proxy server.'),
):
    """CLI command for deploying Apps to ThreatConnect Exchange.

    This command REQUIRES the following environment variables to be set.

    * TC_API_PATH
    * TC_API_ACCESS_ID
    * TC_API_SECRET_KEY
    """
    cli = DeployCli(
        server,
        allow_all_orgs,
        allow_distribution,
        app_file,
        proxy_host,
        proxy_port,
        proxy_user,
        proxy_pass,
    )
    try:
        cli.deploy_app()
    except Exception as ex:
        cli.log.exception('Failed to run "tcex deploy" command.')
        Render.panel.failure(f'Exception: {ex}')
