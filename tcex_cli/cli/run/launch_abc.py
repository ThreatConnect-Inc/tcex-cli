"""TcEx Framework Module"""

import atexit
import difflib
import json
import logging
import os
import re
import secrets
import socket
import string
import subprocess  # nosec B404 -- subprocess used with static, list-form args and no shell (see nosec B603 on the call sites)
import sys
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread

import redis
from fakeredis import TcpFakeServer
from pydantic import BaseModel

from tcex_cli.cli.run.model.common_app_input_model import CommonAppInputModel
from tcex_cli.cli.run.model.module_request_tc_model import ModuleRequestsTcModel
from tcex_cli.logger.trace_logger import TraceLogger
from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.render.render import Render
from tcex_cli.requests_tc import RequestsTc, TcSession
from tcex_cli.util import Util

# get tcex logger
_logger: TraceLogger = logging.getLogger(__name__.split('.', maxsplit=1)[0])  # type: ignore

# pattern to match ${env.VARIABLE_NAME} placeholders (shared by detection and substitution)
ENV_VAR_PATTERN = re.compile(r'(?P<env_pattern>\$\{env\.(?P<env_var_name>\w+)\})')

# ---------------------------------------------------------------------------
# File-watcher constants
# ---------------------------------------------------------------------------

#: File extensions that trigger an App restart in watch-backend mode.
_WATCH_EXTENSIONS: frozenset[str] = frozenset({'.py', '.json'})

#: Directory names that are excluded from the file watcher.
#: ``log`` is included because ``create_input_config`` writes ``log/.test_app_params.json``
#: on every spawn; excluding the directory prevents an infinite restart loop.
_WATCH_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        # App runtime directories
        'in',
        'out',
        'log',
        # Build / dependency directories
        'deps',
        'ui',
        'ui_build',
        # Python / tooling cache directories
        '__pycache__',
        '.mypy_cache',
        '.pytest_cache',
        '.hypothesis',
        '.tox',
        # VCS / IDE directories
        '.git',
        '.hg',
        '.svn',
        '.idea',
        # Node / web tooling
        '.venv',
        'node_modules',
    }
)


class LaunchABC(ABC):
    """Run API Service Apps"""

    def __init__(self, config_json: Path, watch_backend: bool = False):
        """Initialize instance properties.

        Args:
            config_json: Path to the resolved App inputs config file.
            watch_backend: When ``True``, the App is run as a subprocess and
                automatically restarted whenever a ``*.py`` or ``*.json`` file
                in the App directory changes.
        """
        self.config_json = config_json
        self._watch_backend = watch_backend

        # properties
        self.accent = 'dark_orange'
        self.log = _logger
        self.panel_title = 'blue'
        self.staged_keys = []
        self.util = Util()

        # dashboard status; updated by _run_supervisor() transitions
        self._backend_status: str | None = None
        self._backend_since: datetime | None = None

        # ensure redis is available
        self.redis_server()

    def create_input_config(self, inputs: BaseModel):
        """Create files necessary to start a Service App."""
        data = inputs.model_dump_json(
            exclude_none=False, exclude_unset=False, exclude_defaults=False
        )

        key = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(16))
        encrypted_data = self.util.encrypt_aes_cbc(key, data)

        # ensure that the in directory exists
        inputs.tc_in_path.mkdir(parents=True, exist_ok=True)  # type: ignore

        # write the file in/.app_params.json
        app_params_json = inputs.tc_in_path / '.test_app_params.json'  # type: ignore
        with app_params_json.open(mode='wb') as fh:
            fh.write(encrypted_data)

        # Test code to write decrypted file for debugging
        # app_params_json_decrypted = inputs.tc_in_path / '.test_app_params-decrypted.json'
        # with app_params_json_decrypted.open(mode='w') as fh:
        #     fh.write(data)

        # when the App is launched the tcex.input module reads the encrypted
        # file created above # for inputs. in order to decrypt the file, this
        # process requires the key and filename to be set as environment variables.
        os.environ['TC_APP_PARAM_KEY'] = key
        os.environ['TC_APP_PARAM_FILE'] = str(app_params_json)

    @cached_property
    @abstractmethod
    def model(self) -> CommonAppInputModel:
        """Return the App inputs."""

    def print_input_data(self):
        """Print the App data."""
        input_data = self.live_format_dict(self.model.inputs.model_dump()).strip()
        Render.panel.info(f'{input_data}', f'[{self.panel_title}]Input Data[/]')

    def _substitute_env_variables(self, data: str) -> str:
        """Substitute environment variables in the format ${env.VARIABLE_NAME}.

        Args:
            data: The data structure to process str

        Returns:
            The data structure with environment variables substituted
        """
        for match in ENV_VAR_PATTERN.finditer(data):
            env_pattern = match.group('env_pattern')
            env_var_name = match.group('env_var_name')
            # get os environment variable
            env_value = os.getenv(env_var_name, None)
            if env_value is not None:
                data = re.sub(re.escape(env_pattern), env_value, data)
        return data

    def _validate_env_variables(self, data: str):
        """Validate that every ${env.VARIABLE_NAME} placeholder resolves to a defined env var.

        Args:
            data: The raw config file text to scan for ${env.NAME} placeholders.
        """
        # collect referenced env var names that are not defined in the environment
        undefined = sorted(
            {
                match.group('env_var_name')
                for match in ENV_VAR_PATTERN.finditer(data)
                if os.getenv(match.group('env_var_name')) is None
            }
        )
        if undefined:
            lines = []
            for name in undefined:
                line = f'• ${{env.{name}}}'
                # best-effort "did you mean" suggestion against currently-defined env vars
                matches = difflib.get_close_matches(name, list(os.environ), n=1, cutoff=0.7)
                if matches:
                    line += f' - did you mean ${{env.{matches[0]}}}?'
                lines.append(line)

            message = (
                'The following ${env.NAME} placeholders reference environment variables that are '
                'not defined:\n\n'
                + '\n'.join(lines)
                + '\n\nThese values come from the local .env file / environment. Define the '
                'missing variable(s) or fix the typo, then run again.'
            )
            Render.panel.failure(message)

    def construct_model_inputs(self) -> dict:
        """Return the App inputs."""
        app_inputs = {}
        if self.config_json.is_file():
            try:
                app_inputs_string = self.config_json.read_text(encoding='utf-8')
                # fail fast on undefined ${env.X} before substitution / JSON parsing
                self._validate_env_variables(app_inputs_string)
                app_inputs_string = self._substitute_env_variables(app_inputs_string)
                app_inputs = json.loads(app_inputs_string)
            except ValueError as ex:
                Render.panel.failure(
                    f'Failed to parse JSON config file [{self.config_json}]:\n{ex}'
                )
        return app_inputs

    # ------------------------------------------------------------------
    # File-watcher helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _watch_filter(_: object, path: str) -> bool:
        """Return ``True`` when *path* should trigger an App restart.

        Called by ``watchfiles`` for every filesystem event.  Returning ``False``
        suppresses the event (the App is not restarted).

        Exclusion rules (checked in order):
        1. Dotfiles / dot-directories — always ignored.
        2. Any path component that is in ``_WATCH_EXCLUDED_DIRS`` or starts with
           ``lib_`` (SDK dependency trees such as ``lib_latest/`` or ``lib_4.x/``).
        3. Only ``.py`` and ``.json`` files trigger a restart.

        Args:
            _: The ``watchfiles.Change`` enum value (unused; accepts ``object``
               so the signature is contravariance-safe for the type checker).
               If ty emits a Callable-contravariance diagnostic, replace
               ``_: object`` with ``change: Change`` (import from watchfiles)
               and add ``# noqa: ARG001`` to silence the unused-arg warning.
            path: Absolute path string of the changed file.

        Returns:
            ``True`` if the change should trigger a restart, ``False`` otherwise.
        """
        p = Path(path)
        # exclude dotfiles (e.g. .test_app_params.json written by create_input_config)
        if p.name.startswith('.'):
            return False
        # exclude paths that pass through an excluded directory or an SDK lib directory
        for part in p.parts:
            if part in _WATCH_EXCLUDED_DIRS or part.startswith('lib_'):
                return False
        return p.suffix in _WATCH_EXTENSIONS

    def _compute_pythonpath(self) -> list[str]:
        """Return the ordered list of paths to inject into the App subprocess's ``sys.path``.

        Mirrors the logic in ``CliABC.update_system_path`` / ``CliABC.deps_dir`` using an
        existence-based check rather than the SDK version, so ``LaunchABC`` does not need
        to depend on ``CliABC``.

        Returns:
            A list of absolute path strings: ``[cwd, deps_or_lib_latest?]``.
        """
        app_path = Path.cwd()
        deps = app_path / 'deps'
        lib_latest = app_path / 'lib_latest'
        paths = [str(app_path)]
        if deps.exists():
            paths.append(str(deps.resolve()))
        elif lib_latest.exists():
            paths.append(str(lib_latest.resolve()))
        return paths

    def _spawn_app_subprocess(self) -> subprocess.Popen[bytes]:
        """Spawn a new App subprocess and return the ``subprocess.Popen`` handle.

        The subprocess runs the standard App entry-point::

            from run import Run

            r = Run()
            r.setup()
            r.launch()
            r.teardown()

        The App's ``sys.path`` is extended via the private ``_TCEX_PYTHONPATH``
        environment variable so the developer's own ``PYTHONPATH`` is preserved.

        The child is launched with ``subprocess.Popen`` using stdlib defaults
        (``close_fds=True``, inherited cwd, ``restore_signals=True``), running the
        venv Python (``sys.executable``) against a fixed static ``runner`` string.

        Returns:
            A live ``subprocess.Popen`` wrapping the spawned App process.
        """
        self.create_input_config(self.model.inputs)

        runner = (
            'import sys; '
            '[sys.path.insert(0, p) for p in reversed(__import__("os").environ.get('
            '"_TCEX_PYTHONPATH", "").split(__import__("os").pathsep)) if p]; '
            'from run import Run; r = Run(); r.setup(); r.launch(); r.teardown()'
        )

        env = os.environ.copy()
        python_path_parts = self._compute_pythonpath()
        existing = env.get('PYTHONPATH', '')
        if existing:
            python_path_parts.append(existing)
        env['_TCEX_PYTHONPATH'] = os.pathsep.join(python_path_parts)

        # sys.executable is the venv Python; the argv is a fixed static string (runner).
        self.log.info(
            f'step=run, event=spawn-app-subprocess, '
            f'executable="{sys.executable}", '
            f'app_bundle={".app/Contents/MacOS" in sys.executable}, '
            f'python_version="{sys.version.split()[0]}"'
        )
        return subprocess.Popen(  # nosec B603 — sys.executable is the venv Python; args are static
            [sys.executable, '-c', runner],
            env=env,
        )

    @staticmethod
    def _graceful_terminate(proc: subprocess.Popen[bytes]) -> None:
        """Terminate *proc* gracefully, escalating to SIGKILL after a timeout.

        Args:
            proc: The ``subprocess.Popen`` handle to terminate.
        """
        if proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    def _run_supervisor(self) -> int:
        """Run the App under the file-watcher supervisor loop.

        Spawns the App as a subprocess, watches the App directory for file
        changes, and restarts the subprocess whenever a watched file changes.
        Ctrl-C shuts everything down cleanly.

        Returns:
            The exit code of the last App subprocess.
        """
        import threading  # noqa: PLC0415

        from watchfiles import watch as wfiles_watch  # noqa: PLC0415

        change_event = threading.Event()
        stop_event = threading.Event()
        exit_code = 0
        proc: subprocess.Popen[bytes] | None = None

        def _watcher():
            for _ in wfiles_watch(
                Path.cwd(),
                watch_filter=self._watch_filter,
                stop_event=stop_event,
                yield_on_timeout=False,
                raise_interrupt=False,  # required: without this the daemon thread hangs on Ctrl-C
            ):
                change_event.set()

        watcher_thread = threading.Thread(target=_watcher, name='TcexFileWatcher', daemon=True)
        watcher_thread.start()

        try:
            while True:
                # Reset the flag at the top of each outer loop iteration so we correctly
                # distinguish file-change exits from natural app exits (see comment below).
                file_change_restart = False

                self._backend_status = 'starting'
                self._backend_since = datetime.now(tz=UTC)
                Render.panel.info('Starting App subprocess...', f'[{self.panel_title}]Backend[/]')
                proc = self._spawn_app_subprocess()
                self._backend_status = 'running'
                self._backend_since = datetime.now(tz=UTC)

                while proc.poll() is None:
                    if change_event.wait(timeout=0.5):
                        change_event.clear()
                        # Mark that this exit was triggered by a file change, not a natural exit.
                        # IMPORTANT: without this flag, after a file-change restart change_event
                        # is always False (it was cleared before _graceful_terminate), so the
                        # natural-exit guard below would also wait -- requiring the developer to
                        # save a second time to actually trigger a restart (double-wait bug).
                        file_change_restart = True
                        self._backend_status = 'restarting'
                        self._backend_since = datetime.now(tz=UTC)
                        Render.panel.info(
                            'File change detected -- restarting App...',
                            f'[{self.panel_title}]Backend[/]',
                        )
                        self._graceful_terminate(proc)
                        break

                exit_code = proc.returncode if proc.returncode is not None else 0
                self.log.info(f'step=supervisor, event=app-exit, exit-code={exit_code}')

                # Only wait for a file change if the App exited naturally (not via a file-change
                # restart).  Using file_change_restart here (rather than change_event.is_set())
                # is intentional: change_event was cleared before _graceful_terminate, so it
                # would always be False after a restart -- falling through to another wait.
                if not file_change_restart and not change_event.is_set():
                    self._backend_status = 'exited'
                    self._backend_since = datetime.now(tz=UTC)
                    Render.panel.info(
                        f'App exited (code {exit_code}). Watching for file changes...',
                        f'[{self.panel_title}]Backend[/]',
                    )
                    change_event.wait()
                    change_event.clear()
                    Render.panel.info(
                        'File change detected -- restarting App...',
                        f'[{self.panel_title}]Backend[/]',
                    )

        except KeyboardInterrupt:
            self._backend_status = 'stopped'
            self._backend_since = datetime.now(tz=UTC)
            stop_event.set()
            Render.panel.info('Stopping...', f'[{self.panel_title}]Backend[/]')
            if proc is not None and proc.poll() is None:
                self._graceful_terminate(proc)

        return exit_code

    def _launch_once(self) -> int:
        """Run the App in-process (the original launch behavior).

        Returns:
            The exit code from the App run.
        """
        from run import Run  # type: ignore # noqa: PLC0415

        # run the app
        exit_code = 0
        try:
            if 'tcex.pleb.registry' in sys.modules:
                sys.modules['tcex.registry'].registry._reset()  # noqa: SLF001

            # create the config file
            self.create_input_config(self.model.inputs)

            run = Run()
            run.setup()
            run.launch()
            run.teardown()
        except SystemExit as e:
            # SystemExit.code is int | str | None; coerce to int for a consistent return type
            raw = e.code
            exit_code = int(raw) if isinstance(raw, (int, str)) and raw is not None else 1

        self.log.info(f'step=run, event=app-exit, exit-code={exit_code}')
        return exit_code

    def launch(self) -> int:
        """Launch the App.

        Delegates to :meth:`_run_supervisor` when ``--watch-backend`` is active,
        otherwise runs the App in-process via :meth:`_launch_once`.

        Returns:
            The App exit code.
        """
        if self._watch_backend:
            return self._run_supervisor()
        return self._launch_once()

    def live_format_dict(self, data: dict[str, str] | None):
        """Format dict for live output."""
        if data is None:
            return ''

        formatted_data = ''
        for key, value in sorted(data.items()):
            value_ = value
            if isinstance(value, dict):
                value_ = json.dumps(value)
            if isinstance(value, str):
                value_ = value.replace('\n', '\\n')
            formatted_data += f"""{key}: [{self.accent}]{value_}[/]\n"""
        return formatted_data

    @cached_property
    def module_requests_tc_model(self) -> ModuleRequestsTcModel:
        """Return the Module App Model."""
        return ModuleRequestsTcModel(**self.model.inputs.model_dump())

    def output_data(self, context: str) -> dict:
        """Return playbook/service output data."""
        output_data_ = self.redis_client.hgetall(context)
        if output_data_:
            return {
                k: json.loads(v)
                for k, v in self.output_data_process(output_data_).items()
                if k not in self.staged_keys
            }
        return {}

    def output_data_process(self, output_data: dict) -> dict:
        """Process the output data."""
        output_data_: dict[str, dict | list | str] = {}
        for k, v in output_data.items():
            v_ = v
            if isinstance(v, list):
                v_ = [i.decode('utf-8') if isinstance(i, bytes) else i for i in v]
            elif isinstance(v, bytes):
                v_ = v.decode('utf-8')
            elif isinstance(v, dict):
                v_ = self.output_data_process(v)
            output_data_[k.decode('utf-8')] = v_
        return output_data_

    def redis_server(self):
        """Validate Redis is running or start a fake Redis server."""
        server_address = self.model.inputs.tc_kvstore_host
        server_port = self.model.inputs.tc_kvstore_port

        def is_port_in_use() -> bool:
            """Check if a port is in use."""
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex((server_address, server_port)) == 0

        if is_port_in_use():
            Render.panel.info(
                message=f'Running on {server_address}:{server_port}.',
                title=f'[{self.panel_title}]Redis Server[/]',
            )
        else:
            Render.panel.info(
                message=f'Running FakeRedis on {server_address}:{server_port}.',
                title=f'[{self.panel_title}]Redis Server[/]',
            )
            server_address = (server_address, server_port)
            tcp_fake_server = TcpFakeServer(server_address, server_type='redis')
            # probably not required, but behavior is appropriate
            tcp_fake_server.block_on_close = False
            # this fixes the issue with the server not shutting down properly
            tcp_fake_server.daemon_threads = True
            t = Thread(target=tcp_fake_server.serve_forever, daemon=True)
            t.start()

    @cached_property
    def redis_client(self) -> redis.Redis:
        """Return the Redis client."""
        redis_client = redis.Redis(
            connection_pool=redis.ConnectionPool(
                host=self.model.inputs.tc_kvstore_host,
                port=self.model.inputs.tc_kvstore_port,
                db=self.model.inputs.tc_playbook_kvstore_id,
            )
        )
        atexit.register(redis_client.close)
        return redis_client

    @cached_property
    def session(self) -> TcSession:
        """Return requests Session object for TC admin account."""
        return RequestsTc(self.module_requests_tc_model).session  # type: ignore

    def tc_token(self, token_type: str = 'api'):  # nosec B107 -- 'api' is a token type, not a password
        """Return a valid API token."""
        data = None
        http_success = 200
        token = None

        # retrieve token from API using HMAC auth
        r = self.session.post(f'/internal/token/{token_type}', json=data, verify=True)
        if r.status_code == http_success:
            token = r.json().get('data')
            self.log.info(
                f'step=setup, event=using-token, token=<redacted>, token-elapsed={r.elapsed}'
            )
        else:
            self.log.error(
                f'step=setup, event=failed-to-retrieve-token, '
                f'status={r.status_code}, reason={r.reason!r}'
            )
        return token
