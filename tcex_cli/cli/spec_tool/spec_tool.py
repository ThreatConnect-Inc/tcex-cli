"""TcEx Framework Module"""

# third-party
import typer

# first-party
from tcex_cli.cli.spec_tool.spec_tool_cli import SpecToolCli
from tcex_cli.render.render import Render


def command(
    all_: bool = typer.Option(False, '--all', help='Generate all configuration files.'),
    # TODO: the app_input logic needs to be updated for Python 3.11
    # app_input: bool = typer.Option(False, help='Generate app_input.py.'),
    app_spec: bool = typer.Option(False, help='Generate app_spec.yml.'),
    install_json: bool = typer.Option(False, help='Generate install.json.'),
    job_json: bool = typer.Option(False, help='Generate job.json.'),
    layout_json: bool = typer.Option(False, help='Generate layout.json.'),
    readme_md: bool = typer.Option(False, help='Generate README.md.'),
    overwrite: bool = typer.Option(False, help='Force overwrite of config file.'),
    tcex_json: bool = typer.Option(False, help='Generate tcex.json.'),
):
    """Generate App configuration file.

    Generate one or more configuration files for the App.
    """
    cli = SpecToolCli(overwrite)
    try:
        if app_spec is True:
            cli.generate_app_spec()
        else:
            if install_json is True or all_ is True:
                cli.generate_install_json()

            if layout_json is True or all_ is True:
                cli.generate_layout_json()

            if job_json is True or all_ is True:
                cli.generate_job_json()

            if tcex_json is True or all_ is True:
                cli.generate_tcex_json()

            # if app_input is True or all_ is True:
            #     cli.generate_app_input()

            if readme_md is True or all_ is True:
                cli.generate_readme_md()

        Render.table.key_value('SpecTool Report', cli.summary_data)  # type: ignore
    except Exception as ex:
        cli.log.exception('Failed to run "tcex spec-tool" command.')
        Render.panel.failure(f'Exception: {ex}')
