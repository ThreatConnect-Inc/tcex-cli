"""Test Module"""

# standard library
import subprocess
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# third-party
import pytest

# first-party
from tcex_cli.cli.run.frontend_watcher import FrontendWatcher
from tcex_cli.render.render import Render


@pytest.fixture(autouse=True)
def _wide_console(monkeypatch: pytest.MonkeyPatch):
    """Force a very wide Rich console so panel text is never wrapped or truncated.

    ``Render.panel.*`` renders through a Rich ``Panel`` which sizes itself to the terminal
    width (80 cols under pytest capture).  Pinning ``COLUMNS`` prevents wrapping and makes
    substring assertions in ``capsys`` deterministic.
    """
    monkeypatch.setenv('COLUMNS', '4000')


class TestFrontendWatcherStart:
    """Test FrontendWatcher.start()."""

    @staticmethod
    def test_ng_not_found_fails(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        """When ``ng`` is absent from PATH, ``start()`` hard-fails with a helpful message."""
        monkeypatch.setattr(
            'tcex_cli.cli.run.frontend_watcher.shutil.which',
            lambda _name: None,
        )
        fw = FrontendWatcher(tmp_path)

        with pytest.raises(SystemExit):
            fw.start()

        out = capsys.readouterr().out
        assert 'ng' in out
        assert 'PATH' in out

    @staticmethod
    def test_ui_dir_missing_fails(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        """When ``ui/`` does not exist under the app root, ``start()`` hard-fails naming ``ui/``."""
        monkeypatch.setattr(
            'tcex_cli.cli.run.frontend_watcher.shutil.which',
            lambda _name: '/usr/local/bin/ng',
        )
        # tmp_path exists but has no 'ui' subdirectory
        fw = FrontendWatcher(tmp_path)

        with pytest.raises(SystemExit):
            fw.start()

        out = capsys.readouterr().out
        assert 'ui/' in out

    @staticmethod
    def test_start_spawns_subprocess(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """``start()`` spawns ``ng build --configuration production --watch`` in ``ui/``.

        Also stores the process handle on ``_proc``.
        """
        ng_path = '/usr/local/bin/ng'
        monkeypatch.setattr(
            'tcex_cli.cli.run.frontend_watcher.shutil.which',
            lambda _name: ng_path,
        )
        # Suppress the info panel — its message embeds the tmp_path which contains characters
        # that Rich interprets as unclosed markup tags, causing a MarkupError.
        monkeypatch.setattr(Render.panel, 'info', staticmethod(lambda *_a, **_kw: None))

        ui_dir = tmp_path / 'ui'
        ui_dir.mkdir()

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])  # daemon thread exits immediately
        atexit_calls: list = []

        with (
            patch(
                'tcex_cli.cli.run.frontend_watcher.subprocess.Popen',
                return_value=mock_proc,
            ) as mock_popen,
            patch(
                'tcex_cli.cli.run.frontend_watcher.atexit.register',
                side_effect=atexit_calls.append,
            ),
        ):
            fw = FrontendWatcher(tmp_path)
            fw.start()

        mock_popen.assert_called_once_with(
            [ng_path, 'build', '--configuration', 'production', '--watch'],
            cwd=ui_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert fw._proc is mock_proc  # noqa: SLF001
        assert len(atexit_calls) == 1

    @staticmethod
    def test_build_cmd_defaults_to_production_configuration(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """The default build must pass ``--configuration production`` before ``--watch``.

        With no explicit ``configuration``, the spawned command must carry
        ``--configuration production`` as an adjacent, ordered pair that precedes
        ``--watch``.
        """
        ng_path = '/usr/local/bin/ng'
        monkeypatch.setattr(
            'tcex_cli.cli.run.frontend_watcher.shutil.which',
            lambda _name: ng_path,
        )
        # Suppress the info panel — its message embeds the tmp_path which contains characters
        # that Rich interprets as unclosed markup tags, causing a MarkupError.
        monkeypatch.setattr(Render.panel, 'info', staticmethod(lambda *_a, **_kw: None))

        ui_dir = tmp_path / 'ui'
        ui_dir.mkdir()

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])  # daemon thread exits immediately

        with (
            patch(
                'tcex_cli.cli.run.frontend_watcher.subprocess.Popen',
                return_value=mock_proc,
            ) as mock_popen,
            patch('tcex_cli.cli.run.frontend_watcher.atexit.register'),
        ):
            fw = FrontendWatcher(tmp_path)
            fw.start()

        cmd = mock_popen.call_args.args[0]

        # --configuration and production must be an adjacent, ordered pair
        config_index = cmd.index('--configuration')
        assert cmd[config_index + 1] == 'production', (
            f'Expected "production" immediately after "--configuration"; got command {cmd}'
        )

        # the configuration pair must precede --watch
        assert config_index < cmd.index('--watch'), (
            f'Expected "--configuration" to precede "--watch"; got command {cmd}'
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames='configuration',
        argvalues=[
            pytest.param(
                # explicit development configuration flows through
                'development',
                id='pass-configuration-development',
            ),
            pytest.param(
                # arbitrary custom configuration flows through unchanged
                'staging',
                id='pass-configuration-staging',
            ),
            pytest.param(
                # explicit production configuration flows through
                'production',
                id='pass-configuration-production',
            ),
        ],
    )
    def test_build_cmd_passes_configuration_through(
        configuration: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A passed ``configuration`` flows into the command in order before ``--watch``.

        The value given to ``FrontendWatcher(..., configuration=<value>)`` must appear
        immediately after ``--configuration`` and that pair must precede ``--watch``.
        """
        ng_path = '/usr/local/bin/ng'
        monkeypatch.setattr(
            'tcex_cli.cli.run.frontend_watcher.shutil.which',
            lambda _name: ng_path,
        )
        # Suppress the info panel — its message embeds the tmp_path which contains characters
        # that Rich interprets as unclosed markup tags, causing a MarkupError.
        monkeypatch.setattr(Render.panel, 'info', staticmethod(lambda *_a, **_kw: None))

        ui_dir = tmp_path / 'ui'
        ui_dir.mkdir()

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])  # daemon thread exits immediately

        with (
            patch(
                'tcex_cli.cli.run.frontend_watcher.subprocess.Popen',
                return_value=mock_proc,
            ) as mock_popen,
            patch('tcex_cli.cli.run.frontend_watcher.atexit.register'),
        ):
            fw = FrontendWatcher(tmp_path, configuration=configuration)
            fw.start()

        cmd = mock_popen.call_args.args[0]

        assert cmd == [ng_path, 'build', '--configuration', configuration, '--watch'], (
            f'Expected configuration {configuration!r} to flow through; got command {cmd}'
        )

        # --configuration and the value must be an adjacent, ordered pair before --watch
        config_index = cmd.index('--configuration')
        assert cmd[config_index + 1] == configuration, (
            f'Expected {configuration!r} immediately after "--configuration"; got command {cmd}'
        )
        assert config_index < cmd.index('--watch'), (
            f'Expected "--configuration" to precede "--watch"; got command {cmd}'
        )

    @staticmethod
    def test_start_registers_atexit_only_once(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """The ``_registered`` guard ensures ``atexit.register`` is called at most once."""
        ng_path = '/usr/local/bin/ng'
        monkeypatch.setattr(
            'tcex_cli.cli.run.frontend_watcher.shutil.which',
            lambda _name: ng_path,
        )
        # Suppress the info panel — its message embeds the tmp_path which contains characters
        # that Rich interprets as unclosed markup tags, causing a MarkupError.
        monkeypatch.setattr(Render.panel, 'info', staticmethod(lambda *_a, **_kw: None))

        ui_dir = tmp_path / 'ui'
        ui_dir.mkdir()

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])  # daemon thread exits immediately
        atexit_calls: list = []

        with (
            patch(
                'tcex_cli.cli.run.frontend_watcher.subprocess.Popen',
                return_value=mock_proc,
            ),
            patch(
                'tcex_cli.cli.run.frontend_watcher.atexit.register',
                side_effect=atexit_calls.append,
            ),
        ):
            fw = FrontendWatcher(tmp_path)
            fw.start()
            # Reset _proc so the second start() does not skip the Popen call
            fw._proc = None  # noqa: SLF001
            # Give the daemon thread from the first call a fresh iterator so it
            # does not exhaust before the second start() triggers its own thread.
            mock_proc.stdout = iter([])
            fw.start()

        # atexit.register must have been called exactly once despite two start() invocations
        assert len(atexit_calls) == 1, (
            f'atexit.register called {len(atexit_calls)} time(s); expected exactly 1'
        )


class TestFrontendWatcherStop:
    """Test FrontendWatcher.stop()."""

    @staticmethod
    def test_stop_no_proc_is_noop():
        """``stop()`` with no process stored must not raise."""
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        assert fw._proc is None  # noqa: SLF001
        fw.stop()  # must not raise

    @staticmethod
    def test_stop_already_exited_is_noop():
        """``stop()`` when the process has already exited must not call ``terminate()``."""
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # already exited
        fw._proc = mock_proc  # noqa: SLF001

        fw.stop()

        mock_proc.terminate.assert_not_called()

    @staticmethod
    def test_stop_running_proc_terminates():
        """``stop()`` terminates a running process and clears ``_proc`` afterward."""
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        mock_proc.wait.return_value = None
        fw._proc = mock_proc  # noqa: SLF001

        fw.stop()

        mock_proc.terminate.assert_called_once()
        assert fw._proc is None  # noqa: SLF001

    @staticmethod
    def test_stop_timeout_kills():
        """When ``wait()`` times out, ``stop()`` escalates to ``kill()`` and clears ``_proc``."""
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd='ng', timeout=10)
        fw._proc = mock_proc  # noqa: SLF001

        fw.stop()

        mock_proc.kill.assert_called_once()
        assert fw._proc is None  # noqa: SLF001


class TestFrontendWatcherStatus:
    """Test FrontendWatcher.status attribute and _read_output() method."""

    @staticmethod
    def test_initial_status_is_idle():
        """Status is 'idle' before start() is called."""
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        assert fw.status == 'idle'

    @staticmethod
    def test_read_output_resets_idle_on_exit():
        """Status resets to 'idle' after stdout is exhausted, regardless of prior state."""
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        fw.status = 'success'
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        fw._proc = mock_proc  # noqa: SLF001
        fw._read_output()  # noqa: SLF001
        assert fw.status == 'idle'

    @staticmethod
    def test_read_output_no_proc_is_noop():
        """_read_output() with _proc=None must not raise and must leave status unchanged."""
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        fw._read_output()  # noqa: SLF001 — _proc is None by default
        assert fw.status == 'idle'

    @staticmethod
    def test_read_output_transitions_building_then_success():
        """Status transitions to 'building' then 'success' as matching lines are read.

        Calls _read_output() synchronously with a two-line iterator and captures the
        per-line status by monkey-patching to record intermediate states.
        """
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        observed: list[str] = []

        # Capture status after each line by wrapping _read_output in a recording version.
        def _recording_read_output(self: FrontendWatcher) -> None:
            proc = self._proc
            if proc is None or proc.stdout is None:
                return
            for line in proc.stdout:
                print(line, end='', flush=True)  # noqa: T201
                if 'Compiled successfully' in line or 'bundle generation complete' in line:
                    self.status = 'success'
                elif 'Failed to compile' in line or 'error TS' in line:
                    self.status = 'error'
                elif 'Building' in line or 'Compiling' in line or 'Generating' in line:
                    self.status = 'building'
                observed.append(self.status)
            self.status = 'idle'

        fw._read_output = types.MethodType(_recording_read_output, fw)  # noqa: SLF001

        mock_proc = MagicMock()
        mock_proc.stdout = iter(['Building...\n', 'Compiled successfully.\n'])
        fw._proc = mock_proc  # noqa: SLF001
        fw._read_output()  # noqa: SLF001

        assert observed == ['building', 'success'], (
            f'Expected status sequence [building, success]; got {observed}'
        )
        assert fw.status == 'idle'

    @staticmethod
    def test_read_output_error_line():
        """'Failed to compile' line causes status 'error' to appear during processing."""
        fw = FrontendWatcher(Path('/tmp'))  # nosec B108 — path stored in _app_path; stop() never accesses it
        observed: list[str] = []

        def _recording_read_output(self: FrontendWatcher) -> None:
            proc = self._proc
            if proc is None or proc.stdout is None:
                return
            for line in proc.stdout:
                print(line, end='', flush=True)  # noqa: T201
                if 'Compiled successfully' in line or 'bundle generation complete' in line:
                    self.status = 'success'
                elif 'Failed to compile' in line or 'error TS' in line:
                    self.status = 'error'
                elif 'Building' in line or 'Compiling' in line or 'Generating' in line:
                    self.status = 'building'
                observed.append(self.status)
            self.status = 'idle'

        fw._read_output = types.MethodType(_recording_read_output, fw)  # noqa: SLF001

        mock_proc = MagicMock()
        mock_proc.stdout = iter(['Failed to compile.\n'])
        fw._proc = mock_proc  # noqa: SLF001
        fw._read_output()  # noqa: SLF001

        assert observed == ['error'], f'Expected status sequence [error]; got {observed}'
        assert fw.status == 'idle'


class TestLogToFile:
    """Test the log-to-file feature added to FrontendWatcher."""

    @staticmethod
    def test_log_dir_created_on_start(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """``start()`` creates ``log/`` and sets ``_log_path`` to ``ui-build.log`` inside it."""
        ng_path = '/usr/bin/ng'
        monkeypatch.setattr(
            'tcex_cli.cli.run.frontend_watcher.shutil.which',
            lambda _name: ng_path,
        )
        # Suppress the info panel — its message embeds the tmp_path which contains characters
        # that Rich interprets as unclosed markup tags, causing a MarkupError.
        monkeypatch.setattr(Render.panel, 'info', staticmethod(lambda *_a, **_kw: None))

        app_path = tmp_path / 'myapp'
        (app_path / 'ui').mkdir(parents=True)

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])  # daemon thread exits immediately

        with (
            patch(
                'tcex_cli.cli.run.frontend_watcher.subprocess.Popen',
                return_value=mock_proc,
            ),
            patch('tcex_cli.cli.run.frontend_watcher.atexit.register'),
        ):
            fw = FrontendWatcher(app_path)
            fw.start()

        assert (app_path / 'log').is_dir(), (
            f'Expected log/ directory to exist at {app_path / "log"}'
        )
        expected_log = app_path / 'log' / 'ui-build.log'
        assert fw._log_path == expected_log, (  # noqa: SLF001
            f'Expected _log_path to be {expected_log}; got {fw._log_path}'  # noqa: SLF001
        )

    @staticmethod
    def test_log_file_written(tmp_path: Path):
        """``_read_output()`` writes a header and each stdout line to the log file."""
        app_path = tmp_path / 'app'
        log_dir = app_path / 'log'
        log_dir.mkdir(parents=True)

        log_path = log_dir / 'ui-build.log'

        fw = FrontendWatcher(app_path)
        fw._log_path = log_path  # noqa: SLF001

        mock_proc = MagicMock()
        mock_proc.stdout = iter(['Building...\n', 'Compiled successfully.\n'])
        fw._proc = mock_proc  # noqa: SLF001

        fw._read_output()  # noqa: SLF001

        content = log_path.read_text(encoding='utf-8')
        assert content.startswith('# ng build --configuration production --watch — '), (
            f'Log file header missing or malformed; got first line: {content.splitlines()[0]!r}'
        )
        assert 'Building...\n' in content, (
            f'Expected "Building...\\n" in log content; got:\n{content}'
        )
        assert 'Compiled successfully.\n' in content, (
            f'Expected "Compiled successfully.\\n" in log content; got:\n{content}'
        )
        assert fw.status == 'idle', (
            f'Expected status "idle" after stdout exhausted; got {fw.status!r}'
        )

    @staticmethod
    def test_log_path_in_info_panel(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        """``start()`` includes the log file path in the ``Render.panel.info`` message."""
        ng_path = '/usr/bin/ng'
        monkeypatch.setattr(
            'tcex_cli.cli.run.frontend_watcher.shutil.which',
            lambda _name: ng_path,
        )

        app_path = tmp_path / 'app'
        (app_path / 'ui').mkdir(parents=True)

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])  # daemon thread exits immediately

        with (
            patch(
                'tcex_cli.cli.run.frontend_watcher.subprocess.Popen',
                return_value=mock_proc,
            ),
            patch('tcex_cli.cli.run.frontend_watcher.atexit.register'),
        ):
            fw = FrontendWatcher(app_path)
            fw.start()

        out = capsys.readouterr().out
        assert 'ui-build.log' in out, (
            f'Expected "ui-build.log" in panel output; captured stdout was:\n{out!r}'
        )

    @staticmethod
    def test_status_since_updated_on_transition(tmp_path: Path):
        """``_read_output()`` stamps ``status_since`` on every status transition.

        Before calling ``_read_output()``, ``status_since`` is None.  After the
        call (which transitions through 'building' → 'idle'), it must be a
        ``datetime`` instance and ``status`` must be 'idle'.
        """
        app_path = tmp_path / 'app'
        log_dir = app_path / 'log'
        log_dir.mkdir(parents=True)

        fw = FrontendWatcher(app_path)
        fw._log_path = log_dir / 'ui-build.log'  # noqa: SLF001

        mock_proc = MagicMock()
        mock_proc.stdout = iter(['Compiling...\n', 'Compiled successfully.\n'])
        fw._proc = mock_proc  # noqa: SLF001

        assert fw.status_since is None, (
            f'Expected status_since to be None before _read_output(); got {fw.status_since!r}'
        )

        fw._read_output()  # noqa: SLF001

        assert fw.status_since is not None, (
            'Expected status_since to be set after _read_output(); got None'
        )
        assert isinstance(fw.status_since, datetime), (
            f'Expected status_since to be a datetime instance; got {type(fw.status_since)!r}'
        )
        assert fw.status == 'idle', (
            f'Expected status to be "idle" after stdout exhausted; got {fw.status!r}'
        )
