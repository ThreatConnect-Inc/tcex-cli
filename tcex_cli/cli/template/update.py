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
        None,
        '--template',
        help='The App template name (only when tcex.json is missing the value).',
    ),
    template_type: StrOrNone = typer.Option(
        None,
        '--type',
        help='The App type (only when tcex.json is missing the value).',
    ),
    clear: bool = typer.Option(
        default=False, help='Clear stored template cache in ~/.tcex/ directory.'
    ),
    force: bool = typer.Option(
        default=False, help="Update files from template even if they haven't changed."
    ),
    managed: bool = typer.Option(
        False,  # noqa: FBT003
        '--managed',
        help=(
            'Silently update only template-managed (boilerplate) files without '
            'prompting; all other files are left untouched and nothing is deleted.'
        ),
    ),
    safe: bool = typer.Option(
        default=False,
        help='Apply only non-conflicting updates. Never prompt. Write files you have '
        'modified to a plan file for a separate merge step.',
    ),
    plan_out: Path = typer.Option(
        Path('.tcex-update/plan.json'),
        help='Where to write the plan file when --safe is used. Relative paths are '
        'resolved against the current directory.',
    ),
    branch: str = typer.Option(
        default_branch, help='The git branch of the tcex-app-template repository to use.'
    ),
    authenticate: bool = typer.Option(
        False,  # noqa: FBT003
        '--authenticate',
        help=(
            'Authenticate to GitHub using the GITHUB_USER and GITHUB_PAT environment '
            'variables (for private template forks or to raise the API rate limit).'
        ),
    ),
    proxy_host: StrOrNone = typer.Option(None, help='(Advanced) Hostname for the proxy server.'),
    proxy_port: IntOrNone = typer.Option(None, help='(Advanced) Port number for the proxy server.'),
    proxy_user: StrOrNone = typer.Option(None, help='(Advanced) Username for the proxy server.'),
    proxy_pass: StrOrNone = typer.Option(None, help='(Advanced) Password for the proxy server.'),
):
    r"""Update a project with the latest template files.

    Templates can be found at: https://github.com/ThreatConnect-Inc/tcex-app-templates

    The template name and type are read from the project's tcex.json file.
    Use --template and --type only for legacy projects where tcex.json is
    missing those values.

    Use --managed for a silent, non-interactive run (e.g. scripting a
    tcex2->tcex4 migration): only template-managed (boilerplate) files are
    updated, all other files are left untouched, and nothing is deleted.

    With --safe, files you have not modified are updated as usual, but files
    you have modified are left untouched and recorded in a plan file along
    with the template version you last synced, so a separate step can perform
    a three-way merge. Nothing is overwritten and nothing is prompted.


    Optional environment variables include:\n
    * GITHUB_USER\n
    * GITHUB_PAT\n
    * PROXY_HOST\n
    * PROXY_PORT\n
    * PROXY_USER\n
    * PROXY_PASS\n
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
        authenticate=authenticate,
    )

    tj_model = cli.app.tj.model

    # If tcex.json already has template_name, --template must NOT be provided.
    if tj_model.template_name is not None and template_name is not None:
        Render.panel.failure(
            'The --template flag cannot be used when template_name is already '
            'set in tcex.json. Remove the flag or clear the value in tcex.json.',
        )

    # If tcex.json already has template_type, --type must NOT be provided.
    if tj_model.template_type is not None and template_type is not None:
        Render.panel.failure(
            'The --type flag cannot be used when template_type is already '
            'set in tcex.json. Remove the flag or clear the value in tcex.json.',
        )

    # --force overwrites modified files, --safe never touches them. Opposite policies.
    if force and safe:
        Render.panel.failure('The --force and --safe flags are mutually exclusive.')

    if clear:
        cli.clear_cache(branch)

    try:
        cli.update(
            branch,
            template_name,
            template_type,
            force=force,
            managed=managed,
            safe=safe,
            plan_out=plan_out,
        )

        # use the resolved values for the summary
        resolved_name = template_name or tj_model.template_name
        resolved_type = template_type or tj_model.template_type

        summary = {
            'Template Type': resolved_type,
            'Template Name': resolved_name,
            'Branch': branch,
        }
        if safe:
            summary['Plan File'] = str(plan_out)
        Render.table.key_value('Update Summary', summary)
    except Exception as ex:
        cli.log.exception('Failed to run "tcex update" command.')
        Render.panel.failure(f'Exception: {ex}')
