"""TcEx Framework Module"""

import atexit
import contextlib
import re
import shutil
import subprocess  # nosec B404 -- subprocess used with static, list-form args and no shell (see nosec B603 on the call sites)
import threading
from datetime import UTC, datetime
from pathlib import Path

from rich.markup import escape

from tcex_cli.render.render import Render


class FrontendWatcher:
    """Manage an `ng build --configuration <configuration> --watch` subprocess.

    Used for App UI development.

    Start the watcher with :meth:`start`; it will be stopped automatically at
    process exit via :func:`atexit`.  Call :meth:`stop` explicitly to terminate
    early (e.g. on Ctrl-C).
    """

    def __init__(self, app_path: Path, configuration: str = 'production'):
        """Initialize instance properties.

        Args:
            app_path: Absolute path to the App root directory (usually ``Path.cwd()``).
            configuration: Angular build configuration passed to
                ``ng build --configuration <configuration> --watch``.
        """
        self._app_path = app_path
        self._configuration = configuration
        self._log_path: Path | None = None
        self._proc: subprocess.Popen | None = None  # type: ignore[type-arg]
        self._registered = False
        self.status: str = 'idle'
        self.status_since: datetime | None = None

    def start(self) -> None:
        """Start the watcher in the App's ``ui/`` subdirectory.

        Runs ``ng build --configuration <configuration> --watch``.

        Hard-errors (via :func:`~tcex_cli.render.render.Render.panel.failure`) when:

        * ``ng`` is not found on ``PATH`` — install ``@angular/cli`` globally first.
        * The ``ui/`` subdirectory does not exist under the App root.
        """
        # validate ng is available
        ng_path = shutil.which('ng')
        if ng_path is None:
            Render.panel.failure(
                '`ng` was not found on PATH.\n'
                'Install the Angular CLI with:\n'
                '  npm install -g @angular/cli\n'
                'then re-run `tcex run --watch-frontend`.'
            )

        ui_dir = self._app_path / 'ui'
        if not ui_dir.is_dir():
            Render.panel.failure(
                f'`ui/` directory not found under {escape(f"[{self._app_path}]")}.\n'
                '`--watch-frontend` requires an Angular project in the `ui/` subdirectory.'
            )

        log_dir = self._app_path / 'log'
        log_dir.mkdir(parents=True, exist_ok=True)

        cmd: list[str] = [ng_path, 'build', '--configuration', self._configuration, '--watch']
        log_filename = 'ui-build.log'
        panel_msg = (
            f'Starting `ng build --configuration {self._configuration} --watch` '
            f'in {escape(f"[{ui_dir}]")}.\n'
            f'Build output → {escape(f"[{log_dir / log_filename}]")}'
        )

        self._log_path = log_dir / log_filename

        Render.panel.info(panel_msg, '[blue]Frontend[/blue]')

        self._proc = subprocess.Popen(  # nosec B603 — ng_path validated by shutil.which(); args list is controlled
            cmd,
            cwd=ui_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        threading.Thread(target=self._read_output, daemon=True, name='NgOutputReader').start()

        # register stop() to run at process exit (idempotent — only register once)
        if not self._registered:
            atexit.register(self.stop)
            self._registered = True

    def _read_output(self) -> None:
        """Read ng stdout; update status, emit panels, write to log file."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        log_path = self._log_path
        ctx = log_path.open('w', encoding='utf-8') if log_path else contextlib.nullcontext()
        with ctx as lf:
            if lf is not None:
                ts = datetime.now(tz=UTC).isoformat(timespec='seconds')
                header = f'ng build --configuration {self._configuration} --watch'
                lf.write(f'# {header} — {ts}\n')
            for line in proc.stdout:
                if lf is not None:
                    lf.write(line)
                    lf.flush()
                # Key-event panel emissions
                if 'bundle generation complete' in line or 'Compiled successfully' in line:
                    timing = ''
                    m = re.search(r'\[\d+\.\d+ seconds\]', line)
                    if m:
                        timing = f' {m.group()}'
                    if self.status != 'success':
                        Render.panel.info(
                            f'[bold green]Build complete{timing}[/bold green]',
                            '[blue]Frontend[/blue]',
                        )
                    self.status = 'success'
                    self.status_since = datetime.now(tz=UTC)
                elif 'Failed to compile' in line or 'error TS' in line:
                    if self.status != 'error':
                        Render.panel.info(
                            '[bold red]Build failed[/bold red] — see log/ui-build.log for details.',
                            '[blue]Frontend[/blue]',
                        )
                    self.status = 'error'
                    self.status_since = datetime.now(tz=UTC)
                elif 'Building' in line or 'Compiling' in line or 'Generating' in line:
                    if self.status != 'building':
                        Render.panel.info('Building...', '[blue]Frontend[/blue]')
                    self.status = 'building'
                    self.status_since = datetime.now(tz=UTC)
                elif 'Watch mode enabled' in line or 'Watching for file changes' in line:
                    Render.panel.info(
                        'Watching for file changes.',
                        '[blue]Frontend[/blue]',
                    )
                elif 'Changes detected' in line and '✔' not in line and '✓' not in line:
                    Render.panel.info(
                        'Changes detected — rebuilding...',
                        '[blue]Frontend[/blue]',
                    )
        self.status = 'idle'
        self.status_since = datetime.now(tz=UTC)

    def stop(self) -> None:
        """Terminate the ``ng`` subprocess if it is still running."""
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return

        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        finally:
            self._proc = None
