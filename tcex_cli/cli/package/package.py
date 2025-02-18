"""TcEx Framework Module"""

# standard library
from datetime import datetime
from pathlib import Path
from typing import Optional

# third-party
import typer

# first-party
from tcex_cli.cli.package.package_cli import PackageCli
from tcex_cli.cli.validate.validate_cli import ValidateCli
from tcex_cli.render.render import Render

# vars
default_branch = 'v2'

# typer does not yet support PEP 604, but pyupgrade will enforce
# PEP 604. this is a temporary workaround until support is added.
IntOrNone = Optional[int]
StrOrNone = Optional[str]


def command(
    app_builder: bool = typer.Option(  # pylint: disable=unused-argument
        False, help='(Advanced) If true, this command was run from App Builder.'
    ),
    excludes: str = typer.Option(
        '', help='File and directories to exclude from build in a comma-separated list.'
    ),
    ignore_validation: bool = typer.Option(
        False, help='If true, validation errors will not prevent package.'
    ),
    json_output: bool = typer.Option(
        False, help='If true, the output of the validation will be returned in JSON format.'
    ),
    output_dir: Path = typer.Option(
        'target', help='(Advanced) Directory name (relative to App) to write the App package.'
    ),
):
    """Package the current App.

    This command will write an <app name>.tcx file to the output_dir (default: target). This
    App package can be directly installed into ThreatConnect.
    """
    excludes_ = [e.strip() for e in excludes.split(',') if e]

    start_time = datetime.now()

    cli_v = ValidateCli(ignore_validation)
    try:

        def _table_validation_summary():
            """Render validation summary."""
            # render results
            Render.table_validation_summary(
                'File Syntax Validation', cli_v.validation_data.fileSyntax
            )
            Render.table_validation_summary(
                'Config Schema Validation', cli_v.validation_data.schema_
            )
            Render.table_validation_summary('Layout Validation', cli_v.validation_data.layouts)
            Render.table_validation_summary('Feeds Validation', cli_v.validation_data.feeds)
            Render.panel.list('Validation Errors', cli_v.validation_data.errors, 'bold red')

        cli_v.update_system_path()
        cli_v.check_syntax()
        cli_v.check_install_json()
        cli_v.check_layout_json()
        cli_v.check_job_json()
        if not json_output:
            _table_validation_summary()
        if cli_v.exit_code != 0:
            raise typer.Exit(code=cli_v.exit_code)

        # package App
        run = PackageCli(excludes_, ignore_validation, output_dir)
        run.start_time = start_time
        run.validation_data = cli_v.validation_data
        run.package()
        if json_output:
            run.interactive_output()
        else:
            Render.table_package_summary('Package Summary', run.app_metadata)
    except Exception as ex:
        cli_v.log.exception('Failed to run "tcex package" command.')
        Render.panel.failure(f'Exception: {ex}')
