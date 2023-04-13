"""TcEx Framework Module"""
# standard library
import logging
import os
import shutil
import subprocess  # nosec
import sys
from functools import cached_property
from pathlib import Path
from urllib.parse import quote, urlsplit

# third-party
from semantic_version import Version

# first-party
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.cli.model.key_value_model import KeyValueModel
from tcex_cli.render.render import Render

# get logger
_logger = logging.getLogger(__name__.split('.', maxsplit=1)[0])


class DepsCli(CliABC):
    """Dependencies Handling Module."""

    def __init__(
        self,
        app_builder: bool,
        branch: str,
        dev: bool,
        no_cache_dir: bool,
        pre: bool,
        proxy_host: str | None,
        proxy_port: int | None,
        proxy_user: str | None,
        proxy_pass: str | None,
    ):
        """Initialize instance properties."""
        super().__init__()
        self.app_builder = app_builder
        self.branch = branch
        self.dev = dev
        self.no_cache_dir = no_cache_dir
        self.pre = pre
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_user = proxy_user
        self.proxy_pass = proxy_pass

        if not self.proxy_host and os.environ.get('https_proxy'):
            parsed_proxy_url = urlsplit(os.environ.get('https_proxy'))
            self.proxy_host = parsed_proxy_url.hostname
            self.proxy_port = parsed_proxy_url.port
            self.proxy_user = parsed_proxy_url.username
            self.proxy_pass = parsed_proxy_url.password

        # properties
        self.env = self._env
        self.latest_version = None
        self.log = _logger
        self.output: list[KeyValueModel] = []
        self.proxy_enabled = False
        self.requirements_fqfn_branch = None

        # update tcex.json
        self.app.tj.update.multiple()

    def _build_command(self) -> list[str]:
        """Build the pip command for installing dependencies."""
        # support temp (branch) requirements.txt file
        _requirements_fqfn = str(self.requirements_fqfn)
        if self.requirements_fqfn_branch:
            _requirements_fqfn = str(self.requirements_fqfn_branch)

        exe_command = [
            str(self.python_executable),
            '-m',
            'pip',
            'install',
            '-r',
            _requirements_fqfn,
            '--ignore-installed',
            '--quiet',
            '--target',
            self.deps_dir.name,
        ]
        if self.no_cache_dir:
            exe_command.append('--no-cache-dir')
            self.output.append(KeyValueModel(key='Allow cached-dir Release', value='False'))
        if self.pre:
            exe_command.append('--pre')
            self.output.append(KeyValueModel(key='Allow "pre" Release', value='True'))
        if self.proxy_enabled:
            # trust the pypi hosts to avoid ssl errors
            trusted_hosts = ['pypi.org', 'pypi.python.org', 'files.pythonhosted.org']

            for host in trusted_hosts:
                exe_command.append('--trusted-host')
                exe_command.append(host)

        return exe_command

    @property
    def _env(self):
        """Return the environment variables."""
        _env = os.environ.copy()

        # add ci env
        ci_token = os.getenv('CI_JOB_TOKEN')
        if ci_token:
            _env.update({'CI_JOB_TOKEN': ci_token})

        return _env

    def _remove_previous(self):
        """Remove previous deps directory recursively."""
        shutil.rmtree(str(self.deps_dir), ignore_errors=True)

    def configure_proxy(self):
        """Configure proxy settings using environment variables."""
        if os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY'):
            # don't change proxy settings if the OS already has them configured.
            return

        if self.proxy_host is not None and self.proxy_port is not None:
            # proxy url without auth
            proxy_url = f'{self.proxy_host}:{self.proxy_port}'
            if self.proxy_user is not None and self.proxy_pass is not None:
                proxy_user = quote(self.proxy_user, safe='~')
                proxy_pass = quote(self.proxy_pass, safe='~')

                # proxy url with auth
                proxy_url = f'{proxy_user}:{proxy_pass}@{proxy_url}'

            # update proxy properties
            self.proxy_enabled = True
            self.env.update(
                {
                    'HTTP_PROXY': f'http://{proxy_url}',
                    'HTTPS_PROXY': f'http://{proxy_url}',
                }
            )

            # add proxy setting to output
            self.output.append(
                KeyValueModel(
                    key='Using Proxy Server', value=f'{self.proxy_host}:{self.proxy_port}'
                )
            )

    def create_requirements_lock(self):
        """Create the requirements.lock file."""
        with Path('requirements.lock').open(mode='w', encoding='utf-8') as fh:
            # add lock file creation to output
            self.output.append(KeyValueModel(key='Lock File Created', value='requirements.lock'))
            fh.write(self.requirements_lock)
            fh.write('')

    def create_temp_requirements(self):
        """Create a temporary requirements.txt.

        This allows testing against a git branch instead of pulling from pypi.
        """
        _requirements_fqfn = Path('requirements.txt')
        if self.has_requirements_lock:
            _requirements_fqfn = Path('requirements.lock')

        # Replace tcex version with develop branch of tcex
        with _requirements_fqfn.open(encoding='utf-8') as fh:
            current_requirements = fh.read().strip().split('\n')

        self.requirements_fqfn_branch = Path(f'temp-{_requirements_fqfn}')
        with self.requirements_fqfn_branch.open(mode='w', encoding='utf-8') as fh:
            requirements = []
            for line in current_requirements:
                if not line:
                    continue
                if line.startswith('tcex'):
                    line = (
                        'git+https://github.com/ThreatConnect-Inc/tcex.git@'
                        f'{self.branch}#egg=tcex'
                    )
                requirements.append(line)
            fh.write('\n'.join(requirements))

        # display branch setting
        self.output.append(KeyValueModel(key='Using Branch', value=self.branch))

    @property
    def has_requirements_lock(self):
        """Return True if requirements.lock exists."""
        return Path('requirements.lock').exists()

    def download_deps(self, exe_command: list[str]):
        """Download the dependencies (run pip)."""
        # recommended -> https://pip.pypa.io/en/latest/user_guide/#using-pip-from-your-program
        p = subprocess.Popen(  # pylint: disable=consider-using-with
            exe_command,
            shell=False,  # nosec
            # stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )
        _, err = p.communicate()  # pylint: disable=unused-variable

        if p.returncode != 0:
            # display error
            err = err.decode('utf-8')
            Render.panel.failure(f'Failure: {err}')

    def install_deps(self):
        """Install Required Libraries using pip."""
        error = False  # track if any errors have occurred and if so, don't create lock file.

        # check for requirements.txt
        if not self.requirements_fqfn.is_file():
            Render.panel.failure(f'A {self.requirements_fqfn} file is required to install modules.')

        # update requirements_dev.txt file
        self.update_requirements_dev_txt()

        # remove deps directory from previous runs
        self._remove_previous()

        # build the sub process command
        exe_command = self._build_command()

        # display tcex version
        self.output.append(
            KeyValueModel(key='App TcEx Version', value=str(self.app.ij.model.sdk_version))
        )

        # display command setting
        self.output.append(KeyValueModel(key='Pip Command', value=f'''{' '.join(exe_command)}'''))

        if self.app_builder is False:
            with Render.progress_bar_deps() as progress:
                progress.add_task('Downloading Dependencies', total=None)

                self.download_deps(exe_command)
        else:
            self.download_deps(exe_command)

        if self.requirements_fqfn_branch:
            # remove temp requirements.txt file
            self.requirements_fqfn_branch.unlink()

        if self.has_requirements_lock is False:
            if error:
                Render.panel.warning('Not creating requirements.lock file due to errors.')
            else:
                self.create_requirements_lock()

    @cached_property
    def python_executable(self) -> Path:
        """Return the python executable."""
        tcex_python_path = os.getenv('TCEX_PYTHON_PATH', None)
        return Path(tcex_python_path) / 'python' if tcex_python_path else Path(sys.executable)

    @cached_property
    def requirements_fqfn(self):
        """Return the appropriate requirements.txt file."""
        if self.dev:
            _requirements_file = Path('requirements_dev.txt')
        elif self.has_requirements_lock:
            _requirements_file = Path('requirements.lock')
        else:
            _requirements_file = Path('requirements.txt')

        # add deps directory to output
        self.output.append(KeyValueModel(key='Dependencies Directory', value=self.deps_dir.name))

        # add requirements file to output
        self.output.append(
            KeyValueModel(
                key='Requirement File',
                value=f'[dark_orange]{str(_requirements_file)}[/dark_orange]',
            )
        )
        return _requirements_file

    @property
    def requirements_lock(self) -> str:
        """Return python packages for requirements.txt."""
        _requirements = self.requirements_lock_data()
        # sort packages alphabetically
        return '\n'.join(sorted(_requirements.splitlines()))

    def requirements_lock_data(self) -> str:
        """Return the Python packages for the provided directory."""
        deps_dir_path = self.app_path / self.deps_dir
        cmd = f'pip freeze --path "{deps_dir_path}"'
        self.log.debug(f'event=get-requirements-lock-data, cmd={cmd}')
        try:
            output = subprocess.run(  # pylint: disable=subprocess-run-check
                cmd, shell=True, capture_output=True  # nosec
            )
        except Exception as ex:
            self.log.error(f'event=pip-freeze, error="{ex}"')
            Render.panel.failure('Failure: could not get requirements lock data.')

        if output.returncode != 0:
            self.log.error(f'event=pip-freeze, stderr="{output.stderr}"')

        return output.stdout.decode('utf-8')

    @property
    def target_python_version(self) -> Version | None:
        """Return the python version that deps/pip will run with.

        On App builder this could be a different version than this CLI command is running with.
        """
        version = None
        try:
            p = subprocess.Popen(  # pylint: disable=consider-using-with # nosec
                [self.python_executable, '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = p.communicate()

            if p.returncode == 0:
                output = stdout.decode('utf-8').strip().split(' ')[1]
                version = Version(output)
        except Exception as ex:
            # best effort
            self.log.error(f'event=get-python-version, error="{ex}"')

        return version

    @staticmethod
    def update_requirements_dev_txt():
        """Update the requirements_dev.txt file to support lock file."""
        if os.path.isfile('requirements_dev.txt'):
            with open('requirements_dev.txt', mode='r+', encoding='utf-8') as fh:
                _lines = ''
                for line in fh.readlines():
                    _lines += line.replace('requirements.txt', 'requirements.lock')

                # write back
                fh.seek(0)
                fh.write(_lines)
                fh.truncate()

    def validate_python_version(self):
        """Validate the python version."""
        tpv = self.target_python_version
        if tpv is not None:
            target_major_minor = f'{tpv.major}.{tpv.minor}'

            # temp logic until all TC instances are on version 7.2
            language_major_minor = self.app.ij.model.language_version
            if isinstance(language_major_minor, Version):
                language_major_minor = (
                    f'{language_major_minor.major}.{language_major_minor.minor}'  # type: ignore
                )

            if target_major_minor != language_major_minor:
                Render.panel.failure(
                    (
                        ' • The App languageVersion defined in the install.json '
                        'file does not match the current Python version.\n'
                        f' • defined-version={language_major_minor} '
                        f'!= current-version={target_major_minor}.'
                    ),
                )
