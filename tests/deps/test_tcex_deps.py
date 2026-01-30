"""Bin Testing"""

# standard library
import os
import shutil
from pathlib import Path

# third-party
import pytest
from click.testing import Result
from typer.testing import CliRunner

# first-party
from tcex_cli.cli.cli import app

# get instance of typer CliRunner for test case
runner = CliRunner()


@pytest.mark.run(order=2)
class TestTcexCliDeps:
    """Tcex CLI Testing."""

    @staticmethod
    def _run_command(
        args: list[str],
        new_app_dir: str,
        tmp_path: Path,
        request: pytest.FixtureRequest,
        monkeypatch: pytest.MonkeyPatch,
    ) -> Result:
        """Copy fixture app to tmp_path, chdir, and invoke the CLI command.

        Args:
            args: CLI arguments to pass to the tcex app command.
            new_app_dir: Name of the subdirectory to create under tmp_path.
            tmp_path: Pytest fixture providing a temporary directory unique to each test.
            request: Pytest fixture for accessing test context and file paths.
            monkeypatch: Pytest fixture for modifying the working directory.

        Returns:
            The CLI invocation result.
        """
        app_path = request.path.parent.parent / 'app' / 'tcpb' / 'app_1'
        new_app_path = tmp_path / new_app_dir
        shutil.copytree(app_path, new_app_path)

        monkeypatch.chdir(new_app_path)

        return runner.invoke(app, args)

    def test_tcex_deps_std(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        request: pytest.FixtureRequest,
        clear_proxy_env_vars,
    ):
        """Test standard deps install without proxy or branch options.

        Args:
            tmp_path: Pytest fixture providing a temporary directory unique to each test.
            monkeypatch: Pytest fixture for modifying environment and working directory.
            request: Pytest fixture for accessing test context and file paths.
            clear_proxy_env_vars: Pytest fixture that removes proxy env vars.
        """
        result = self._run_command(['deps'], 'app_std', tmp_path, request, monkeypatch)
        assert result.exit_code == 0, result.output
        assert Path('deps/tcex').is_dir(), result.output

    def test_tcex_deps_branch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        request: pytest.FixtureRequest,
        clear_proxy_env_vars,
    ):
        """Test deps install using a specific branch.

        Args:
            tmp_path: Pytest fixture providing a temporary directory unique to each test.
            monkeypatch: Pytest fixture for modifying environment and working directory.
            request: Pytest fixture for accessing test context and file paths.
            clear_proxy_env_vars: Pytest fixture that removes proxy env vars.
        """
        branch = 'develop'
        result = self._run_command(
            ['deps', '--branch', branch], 'app_branch', tmp_path, request, monkeypatch
        )
        assert result.exit_code == 0, result.output
        assert Path('deps/tcex').is_dir(), result.output

        # iterate over command output for validations
        for line in result.stdout.split('\n'):
            # validate that the correct branch is being used
            if 'Using Branch' in line:
                assert branch in line

            # validate that the correct branch is being used
            if 'Running' in line:
                assert 'temp-requirements.txt' in line

    def test_tcex_deps_proxy_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
    ):
        """Test deps install with proxy settings pulled from environment variables.

        Args:
            tmp_path: Pytest fixture providing a temporary directory unique to each test.
            monkeypatch: Pytest fixture for modifying environment and working directory.
            request: Pytest fixture for accessing test context and file paths.
        """
        # proxy settings will be pulled from env vars
        result = self._run_command(['deps'], 'app_std', tmp_path, request, monkeypatch)
        assert result.exit_code == 0, result.output
        assert Path('deps/tcex').is_dir(), result.output

    def test_tcex_deps_proxy_explicit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
    ):
        """Test deps install with proxy settings passed as explicit CLI arguments.

        Args:
            tmp_path: Pytest fixture providing a temporary directory unique to each test.
            monkeypatch: Pytest fixture for modifying environment and working directory.
            request: Pytest fixture for accessing test context and file paths.
        """
        proxy_host = os.getenv('TC_PROXY_HOST')
        proxy_port = os.getenv('TC_PROXY_PORT')
        proxy_user = os.getenv('TC_PROXY_USERNAME') or os.getenv('TC_PROXY_USER')
        proxy_pass = os.getenv('TC_PROXY_PASSWORD') or os.getenv('TC_PROXY_PASS')

        command = ['deps', '--proxy-host', proxy_host, '--proxy-port', proxy_port]
        if proxy_user and proxy_pass:
            command.extend(['--proxy-user', proxy_user, '--proxy-pass', proxy_pass])

        result = self._run_command(command, 'app_proxy', tmp_path, request, monkeypatch)
        assert result.exit_code == 0, result.output
        assert Path('deps/tcex').is_dir(), result.output

        # iterate over command output for validations
        for line in result.stdout.split('\n'):
            # validate that the correct branch is being used
            if 'Using Proxy Server' in line:
                assert proxy_host in line  # type: ignore
                assert proxy_port in line  # type: ignore
                break
        else:
            assert False, 'Proxy settings not found'
