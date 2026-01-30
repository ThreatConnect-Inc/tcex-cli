"""Test Module"""

# standard library
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
class TestTcexCliInit:
    """Test Module"""

    @staticmethod
    def _run_command(
        args: list[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> Result:
        """Create a working directory, chdir into it, and invoke the CLI command.

        Args:
            args: CLI arguments to pass to the tcex app command.
            tmp_path: Pytest fixture providing a temporary directory unique to each test.
            monkeypatch: Pytest fixture for modifying the working directory.

        Returns:
            The CLI invocation result.
        """
        working_dir = tmp_path / 'app_init'
        working_dir.mkdir()

        monkeypatch.chdir(working_dir)

        return runner.invoke(app, args)

    def test_tcex_init_organization_basic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clear_proxy_env_vars
    ):
        """Test init command for an organization app with the basic template.

        Args:
            tmp_path: Pytest fixture providing a temporary directory unique to each test.
            monkeypatch: Pytest fixture for modifying the working directory.
            clear_proxy_env_vars: Pytest fixture that removes proxy env vars.
        """
        result = self._run_command(
            ['init', '--type', 'organization', '--template', 'basic', '--force'],
            tmp_path,
            monkeypatch,
        )
        assert result.exit_code == 0, result.stdout

        # spot check a few template files
        assert Path('app.py').is_file()
        assert Path('install.json').is_file()
        assert Path('job_app.py').is_file()
        assert Path('tcex.json').is_file()

    def test_tcex_init_playbook_basic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clear_proxy_env_vars
    ):
        """Test init command for a playbook app with the basic template.

        Args:
            tmp_path: Pytest fixture providing a temporary directory unique to each test.
            monkeypatch: Pytest fixture for modifying the working directory.
            clear_proxy_env_vars: Pytest fixture that removes proxy env vars.
        """
        result = self._run_command(
            ['init', '--type', 'playbook', '--template', 'basic'], tmp_path, monkeypatch
        )
        assert result.exit_code == 0, result.stdout

        # spot check a few template files
        assert Path('app.py').is_file()
        assert Path('install.json').is_file()
        assert Path('playbook_app.py').is_file()
        assert Path('tcex.json').is_file()
