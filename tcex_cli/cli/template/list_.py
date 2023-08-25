"""TcEx Framework Module"""

# standard library
from typing import Optional

# third-party
import typer

# first-party
from tcex_cli.cli.template.template_cli import TemplateCli
from tcex_cli.render.render import Render

# vars
default_branch = 'v2'

# typer does not yet support PEP 604, but pyupgrade will enforce
# PEP 604. this is a temporary workaround until support is added.
IntOrNone = Optional[int]
StrOrNone = Optional[str]


def command(
    template_type: StrOrNone = typer.Option(None, '--type', help='The App type being initialized.'),
    branch: str = typer.Option(
        default_branch, help='The git branch of the tcex-app-template repository to use.'
    ),
    proxy_host: StrOrNone = typer.Option(None, help='(Advanced) Hostname for the proxy server.'),
    proxy_port: IntOrNone = typer.Option(None, help='(Advanced) Port number for the proxy server.'),
    proxy_user: StrOrNone = typer.Option(None, help='(Advanced) Username for the proxy server.'),
    proxy_pass: StrOrNone = typer.Option(None, help='(Advanced) Password for the proxy server.'),
):
    """List templates

    The template name will be pulled from tcex.json by default. If the template option
    is provided it will be used instead of the value in the tcex.json file. The tcex.json
    file will also be updated with new values.

    Optional environment variables include:\n
    * PROXY_HOST\n
    * PROXY_PORT\n
    * PROXY_USER\n
    * PROXY_PASS\n
    """
    cli = TemplateCli(
        proxy_host,
        proxy_port,
        proxy_user,
        proxy_pass,
    )
    try:
        cli.list_(branch, template_type)
        Render.table_template_list(cli.template_data, branch)
        if cli.errors is True:
            Render.panel.warning(
                'Errors were encountered during command execution. Please '
                f'see logs at {cli.cli_out_path / "tcex.log"}.'
            )
    except Exception as ex:
        cli.log.exception('Failed to run "tcex list" command.')
        Render.panel.failure(f'Exception: {ex}')
