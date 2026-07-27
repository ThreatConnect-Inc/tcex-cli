"""TcEx Framework Module"""

from pathlib import Path

import typer

from tcex_cli.cli.run.run_cli import RunCli
from tcex_cli.render.render import Render


def command(
    config_json: Path | None = typer.Option(
        None,
        '--config',
        help=(
            'OPTIONAL App Inputs config file. Wins over app_inputs.json and the '
            'app_inputs.d/ menu; pass app_inputs.d/<name>.json to run that file directly.'
        ),
    ),
    debug: bool = typer.Option(default=False, help='Run App in VS Code debug mode.'),
    debug_port: int = typer.Option(
        5678, help='The port to use for the debug server. This must match the launch.json file.'
    ),
    watch_backend: bool = typer.Option(
        default=False,
        help=(
            'Monitor *.py and *.json files in the App directory and automatically restart '
            'the App subprocess on change. Incompatible with --debug.'
        ),
        envvar='TCEX_WATCH_BACKEND',
        rich_help_panel='Development',
    ),
    watch_frontend: bool = typer.Option(
        default=False,
        help=(
            'Run `ng build --configuration <value> --watch` in the App ui/ subdirectory '
            '(configuration from --ui-configuration, default production). '
            'Requires the Angular CLI (`npm install -g @angular/cli`) and a ui/ directory.'
        ),
        envvar='TCEX_WATCH_FRONTEND',
        rich_help_panel='Development',
    ),
    ui_configuration: str = typer.Option(
        'production',
        '--ui-configuration',
        help=(
            'Angular build configuration passed to `ng build --configuration <value> --watch` '
            'when --watch-frontend is set (e.g. production, development, or any configuration '
            'defined in the App ui/ angular.json). Invalid values are reported by `ng`.'
        ),
        envvar='TCEX_UI_CONFIGURATION',
        rich_help_panel='Development',
    ),
    live_display: bool = typer.Option(
        default=False,
        help=(
            'Enable the Rich terminal live-data display (requests, responses, commands). '
            'When omitted, a summary panel is printed and the web dashboard at '
            '/_tcex/ is the primary monitoring interface.'
        ),
    ),
):
    """Run the App.

    Configuration & secrets:

    Config resolution precedence: an explicit --config <file> wins and runs that file directly;
    else app_inputs.json if present; else a selection menu over app_inputs.d/*.json. Passing
    --config app_inputs.d/<name>.json runs that scenario without the menu (the unattended path).

    Values come from the local .env (loaded at CLI startup) in two ways: (1) ${env.VAR_NAME}
    placeholders inside the config JSON are substituted from the environment; (2) input model
    fields omitted from the JSON fall back to the environment / .env automatically (the run input
    models are pydantic BaseSettings with env_file='.env', case-insensitive) -- e.g.
    tc_api_access_id, tc_api_secret_key, tc_token, and the proxy and kvstore settings. Values
    present in the JSON take precedence over the .env fallback.

    There is ONE .env at the App root, shared by every file in app_inputs.d/: put credentials
    there once and keep per-scenario inputs in each app_inputs.d/<name>.json. Gotcha: an undefined
    ${env.VAR} is now a hard error -- the run stops and reports which variable to define or fix.

    Environment variables:

    The following environment variables (e.g. from the App .env) are honored by this command; the
    matching CLI option always wins when both are provided:

    - TCEX_WATCH_BACKEND -- bool, mirrors --watch-backend.
    - TCEX_WATCH_FRONTEND -- bool, mirrors --watch-frontend.
    - TCEX_UI_CONFIGURATION -- string, mirrors --ui-configuration (default production).
    - API_SERVICE_HOST -- API service host override (default localhost).
    - API_SERVICE_PORT -- API service port override (default 8042).
    """
    cli = RunCli()
    try:
        cli.update_system_path()

        # --debug and --watch-backend are mutually exclusive: debug attaches a debugger to an
        # in-process run while watch-backend requires a subprocess; warn and disable watch.
        if debug and watch_backend:
            Render.panel.warning(
                '--debug and --watch-backend are mutually exclusive. '
                '--watch-backend has been disabled; running in debug mode.'
            )
            watch_backend = False

        # run in debug mode
        if debug is True:
            cli.debug(debug_port)

        # run the App (RunCli.run resolves the config to use)
        cli.run(
            config_json,
            debug,
            watch_backend=watch_backend,
            watch_frontend=watch_frontend,
            ui_configuration=ui_configuration,
            live_display=live_display,
        )

    except Exception as ex:
        cli.log.exception('Failed to run "tcex run" command.')
        Render.panel.failure(f'Exception: {ex}')
