"""TcEx Framework Module"""

# standard library
from pathlib import Path
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
    template_name: StrOrNone = typer.Option(
        None, '--template', help='Only provide this value if changing the saved value.'
    ),
    template_type: StrOrNone = typer.Option(None, '--type', help='The App type being initialized.'),
    branch: str = typer.Option(
        default_branch, help='The git branch of the tcex-app-template repository to use.'
    ),
    force: bool = typer.Option(
        False, help="Update files from template even if they haven't changed."
    ),
    proxy_host: StrOrNone = typer.Option(None, help='(Advanced) Hostname for the proxy server.'),
    proxy_port: IntOrNone = typer.Option(None, help='(Advanced) Port number for the proxy server.'),
    proxy_user: StrOrNone = typer.Option(None, help='(Advanced) Username for the proxy server.'),
    proxy_pass: StrOrNone = typer.Option(None, help='(Advanced) Password for the proxy server.'),
):
    """Update a project with the latest template files.

    Templates can be found at: https://github.com/ThreatConnect-Inc/tcex-app-templates

    The template name will be pulled from tcex.json by default. If the template option
    is provided it will be used instead of the value in the tcex.json file. The tcex.json
    file will also be updated with new values.
    """
    # external Apps do not support update
    if not Path('tcex.json').is_file():
        Render.panel.failure(
            'Update requires a tcex.json file, "external" App templates can not be update.',
        )

    cli = TemplateCli(
        proxy_host,
        proxy_port,
        proxy_user,
        proxy_pass,
    )
    try:
        downloads = cli.update(branch, template_name, template_type, force)
        if not downloads:
            Render.panel.info('No files to update.')
        else:
            progress = Render.progress_bar_download()
            with progress:
                for item in progress.track(
                    downloads,
                    description='Downloading',
                ):
                    cli.download_template_file(item)

        # update manifest
        cli.template_manifest_write()

        # update tcex.json file
        cli.update_tcex_json()

        Render.table.key_value(
            'Update Summary',
            {
                'Template Type': cli.app.tj.model.template_type,
                'Template Name': cli.app.tj.model.template_name,
                'Files Updated': str(len(downloads)),
                'Branch': branch,
            },
        )
    except Exception as ex:
        cli.log.exception('Failed to run "tcex update" command.')
        Render.panel.failure(f'Exception: {ex}')
