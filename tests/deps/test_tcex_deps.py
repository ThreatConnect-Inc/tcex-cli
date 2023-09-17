"""Bin Testing"""
# standard library
import os
import shutil
from pathlib import Path

# third-party
import pytest
from _pytest.fixtures import FixtureRequest
from click.testing import Result
from typer.testing import CliRunner

# first-party
from tcex_cli.cli.cli import app

# get instance of typer CliRunner for test case
runner = CliRunner()


@pytest.mark.run(order=2)
class TestTcexCliDeps:
    """Tcex CLI Testing."""

    def teardown_method(self):
        """Configure teardown before all tests."""
        deps_dir = Path('deps')
        shutil.rmtree(deps_dir, ignore_errors=True)

    def _remove_proxy_env_vars(self):
        """Remove proxy env vars"""
        os.environ.pop('TC_PROXY_HOST', None)
        os.environ.pop('TC_PROXY_PORT', None)
        os.environ.pop('TC_PROXY_USER', None)
        os.environ.pop('TC_PROXY_USERNAME', None)
        os.environ.pop('TC_PROXY_PASS', None)
        os.environ.pop('TC_PROXY_PASSWORD', None)

    def _run_command(
        self,
        args: list[str],
        new_app_dir: str,
        monkeypatch: pytest.MonkeyPatch,
        request: FixtureRequest,
    ) -> Result:
        """Test Case"""
        app_path = Path(request.fspath.dirname).parent / 'app' / 'tcpb' / 'app_1'  # type: ignore
        new_app_path = Path.cwd() / 'app' / 'tcpb' / new_app_dir
        shutil.copytree(app_path, new_app_path)

        # change to testing directory
        monkeypatch.chdir(new_app_path)

        try:
            result = runner.invoke(app, args)
            assert os.path.isdir(os.path.join('deps', 'tcex')), result.output
        finally:
            # clean up
            shutil.rmtree(new_app_path, ignore_errors=True)

        return result

    def test_tcex_deps_std(self, monkeypatch: pytest.MonkeyPatch, request: FixtureRequest):
        """Test Case"""
        # remove proxy env vars
        self._remove_proxy_env_vars()

        result = self._run_command(['deps'], 'app_std', monkeypatch, request)
        assert result.exit_code == 0

    def test_tcex_deps_branch(self, monkeypatch: pytest.MonkeyPatch, request: FixtureRequest):
        """Test Case"""
        # remove proxy env vars
        self._remove_proxy_env_vars()

        branch = 'develop'
        result = self._run_command(['deps', '--branch', branch], 'app_branch', monkeypatch, request)
        assert result.exit_code == 0

        # iterate over command output for validations
        for line in result.stdout.split('\n'):
            # validate that the correct branch is being used
            if 'Using Branch' in line:
                assert branch in line

            # validate that the correct branch is being used
            if 'Running' in line:
                assert 'temp-requirements.txt' in line

    def test_tcex_deps_proxy_env(self, monkeypatch: pytest.MonkeyPatch, request: FixtureRequest):
        """Test Case"""
        # proxy settings will be pulled from env vars
        result = self._run_command(['deps'], 'app_std', monkeypatch, request)
        assert result.exit_code == 0

    def test_tcex_deps_proxy_explicit(
        self, monkeypatch: pytest.MonkeyPatch, request: FixtureRequest
    ):
        """Test Case"""
        proxy_host = os.getenv('TC_PROXY_HOST')
        proxy_port = os.getenv('TC_PROXY_PORT')
        proxy_user = os.getenv('TC_PROXY_USERNAME') or os.getenv('TC_PROXY_USER')
        proxy_pass = os.getenv('TC_PROXY_PASSWORD') or os.getenv('TC_PROXY_PASS')

        command = ['deps', '--proxy-host', proxy_host, '--proxy-port', proxy_port]
        if proxy_user and proxy_pass:
            command.extend(['--proxy-user', proxy_user, '--proxy-pass', proxy_pass])

        result = self._run_command(command, 'app_proxy', monkeypatch, request)
        assert result.exit_code == 0

        # iterate over command output for validations
        for line in result.stdout.split('\n'):
            # validate that the correct branch is being used
            if 'Using Proxy Server' in line:
                assert proxy_host in line  # type: ignore
                assert proxy_port in line  # type: ignore
                break
        else:
            assert False, 'Proxy settings not found'
