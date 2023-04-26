"""TcEx Framework Module"""

# standard library
import sys
from importlib.metadata import version as get_version
from pathlib import Path

# third-party
import typer

# first-party
from tcex_cli.cli.deploy import deploy
from tcex_cli.cli.deps import deps
from tcex_cli.cli.package import package
from tcex_cli.cli.spec_tool import spec_tool
from tcex_cli.cli.template import init, list_, update
from tcex_cli.cli.validate import validate
from tcex_cli.render.render import Render


def update_system_path():
    """Update the system path to ensure project modules and dependencies can be found."""
    if Path('deps').is_dir():
        sys.path.insert(0, 'deps')


def version_callback(
    version: bool = typer.Option(False, '--version', help='Display the version and exit.')
):
    """Display the version and exit."""
    if version is True:
        # update system path
        update_system_path()

        version_data = {}
        # display the tcex version
        try:
            version_data['TcEx'] = get_version('tcex')
        except ImportError:
            pass

        # display the tcex version
        try:
            version_data['TcEx App Testing'] = get_version('tcex-app-testing')
        except ImportError:
            pass

        # display the tcex version
        version_data['TcEx CLI'] = get_version('tcex-cli')

        Render.table.key_value('Version Data', version_data)
        raise typer.Exit()


# initialize typer
app = typer.Typer(callback=version_callback, invoke_without_command=True)
app.command('deploy')(deploy.command)
app.command('deps')(deps.command)
app.command('init')(init.command)
app.command('list')(list_.command)
app.command('package')(package.command)
app.command('spec-tool')(spec_tool.command)
app.command('update')(update.command)
app.command('validate')(validate.command)

# add tcex-app-testing CLI command as `tcex test` if installed, this provides easy access
# to create test cases. the alternative is to run `tcex-app-testing` CLI directly.
try:
    # update system path
    update_system_path()

    # third-party
    from tcex_app_testing.cli.cli import app as app_test  # type: ignore

    app.add_typer(
        app_test,
        name='test',
        short_help='Run App tests commands.',
    )
except ImportError:
    pass


if __name__ == '__main__':
    app()
