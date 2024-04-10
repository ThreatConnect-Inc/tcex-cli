"""TcEx Framework Module"""

# standard library
from typing import Optional

# third-party
import typer

# first-party
from tcex_cli.cli.migrate.migrate_cli import MigrateCli
from tcex_cli.render.render import Render

# typer does not yet support PEP 604, but pyupgrade will enforce
# PEP 604. this is a temporary workaround until support is added.
IntOrNone = Optional[int]
StrOrNone = Optional[str]


def command(
    forward_ref: bool = typer.Option(
        True, help='If true, show typing forward lookup reference that require updates.'
    ),
    update_code: bool = typer.Option(True, help='If true, apply code replacements.'),
):
    """Migrate App to TcEx 4 from TcEx 2/3."""
    cli = MigrateCli(
        forward_ref,
        update_code,
    )
    try:
        cli.walk_code()
    except Exception as ex:
        cli.log.exception('Failed to run "tcex deps" command.')
        Render.panel.failure(f'Exception: {ex}')
