"""TcEx Framework Module"""
# standard library
from pathlib import Path

# third-party
import typer

# first-party
from tcex_cli.cli.run.run_cli import RunCli
from tcex_cli.render.render import Render


def command(
    config_json: Path = typer.Option(
        'app_inputs.json', help='An OPTIONAL configuration file containing App Inputs.'
    ),
    debug: bool = typer.Option(False, help='Run App in VS Code debug mode.'),
    debug_port: int = typer.Option(
        5678, help='The port to use for the debug server. This must match the launch.json file.'
    ),
):
    """Run the App."""
    cli = RunCli()
    try:
        cli.update_system_path()

        # run in debug mode
        if debug is True:
            cli.debug(debug_port)

        # run the App
        cli.run(config_json)

    except Exception as ex:
        cli.log.exception('Failed to run "tcex run" command.')
        Render.panel.failure(f'Exception: {ex}')
