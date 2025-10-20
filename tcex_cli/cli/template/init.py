"""TcEx Framework Module"""

# standard library
from pathlib import Path
from typing import Optional

# third-party
import typer

# first-party
from tcex_cli.cli.template.tcv_helper import TCVHelper
from tcex_cli.cli.template.template_cli import TemplateCli
from tcex_cli.render.render import Render

# vars
default_branch = 'v2'

# typer does not yet support PEP 604, but pyupgrade will enforce
# PEP 604. this is a temporary workaround until support is added.
IntOrNone = Optional[int]  # noqa: UP007
StrOrNone = Optional[str]  # noqa: UP007


def command(
    template_name: str = typer.Option(
        ..., '--template', help='The App template to be used.', prompt=True
    ),
    template_type: str = typer.Option(
        ..., '--type', help='The App type being initialized.', prompt=True
    ),
    clear: bool = typer.Option(
        default=False, help='Clear stored template cache in ~/.tcex/ directory.'
    ),
    force: bool = typer.Option(
        default=False, help='Force App init even if files exist in directory.'
    ),
    branch: str = typer.Option(
        default_branch, help='The git branch of the tcex-app-template repository to use.'
    ),
    app_builder: bool = typer.Option(
        default=False, help='Include .appbuilderconfig file in template download.'
    ),
    proxy_host: StrOrNone = typer.Option(None, help='(Advanced) Hostname for the proxy server.'),
    proxy_port: IntOrNone = typer.Option(None, help='(Advanced) Port number for the proxy server.'),
    proxy_user: StrOrNone = typer.Option(None, help='(Advanced) Username for the proxy server.'),
    proxy_pass: StrOrNone = typer.Option(None, help='(Advanced) Password for the proxy server.'),
):
    r"""Initialize a new App from a template.

    Templates can be found at: https://github.com/ThreatConnect-Inc/tcex-app-templates

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
    if list(Path.cwd().iterdir()) and force is False:
        Render.panel.failure(
            'The current directory does not appear to be empty. Apps should '
            'be initialized in an empty directory. If attempting to update an '
            'existing App then please try using the "tcex update" command instead.',
        )

    if clear:
        # clear the template cache
        cli.clear()

    try:
        if template_type == 'tie':
            tcv_helper = TCVHelper(cli)
            tcv_helper.init(branch, template_name, template_type)
            Render.table.key_value(
                'Initialization Summary',
                {
                    'Template Name': template_name,
                    'Template Type': template_type,
                    'Branch': branch,
                },
            )
            return

        Render.panel.info('Installing template files')
        downloads = cli.init(branch, template_name, template_type, app_builder)
        progress = Render.progress_bar_download()
        with progress:
            for item in progress.track(
                downloads,
                description='Downloading',
            ):
                cli.download_template_file(item)

        # update tcex.json file with template data, external App do not support tcex.json
        if template_type != 'external':
            cli.update_tcex_json()

            # update manifest
            cli.template_manifest_write()

        Render.table.key_value(
            'Initialization Summary',
            {
                'Template Name': template_name,
                'Template Type': template_type,
                'Files Downloaded': str(len(downloads)),
                'Branch': branch,
            },
        )

    except Exception as ex:
        cli.log.exception('Failed to run "tcex init" command.')
        Render.panel.failure(f'Exception: {ex}')
