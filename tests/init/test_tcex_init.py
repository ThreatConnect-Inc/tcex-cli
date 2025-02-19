"""Test Module"""

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
class TestTcexCliInit:
    """Test Module"""

    working_dir = Path.cwd() / 'app_init'

    def startup_method(self):
        """Configure startup before all tests."""
        # remove working directory if it exists
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def teardown_method(self):
        """Configure teardown before all tests."""
        # remove working directory if it exists
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def _run_command(self, args: list[str], monkeypatch: pytest.MonkeyPatch) -> Result:
        """Helper Method"""
        # create working directory
        self.working_dir.mkdir(exist_ok=True, parents=True)

        # change to testing directory
        monkeypatch.chdir(self.working_dir)

        result = runner.invoke(app, args)
        return result

    def test_tcex_init_organization_basic(self, monkeypatch: pytest.MonkeyPatch):
        """Test Case"""
        result = self._run_command(
            ['init', '--type', 'organization', '--template', 'basic', '--force'], monkeypatch
        )
        assert result.exit_code == 0, result.stdout

        # spot check a few template files
        assert os.path.isfile('app.py')
        assert os.path.isfile('install.json')
        assert os.path.isfile('job_app.py')
        assert os.path.isfile('tcex.json')

    def test_tcex_init_playbook_basic(self, monkeypatch: pytest.MonkeyPatch):
        """Test Case"""
        result = self._run_command(
            ['init', '--type', 'playbook', '--template', 'basic'], monkeypatch
        )
        assert result.exit_code == 0, result.stdout

        # spot check a few template files
        assert os.path.isfile('app.py')
        assert os.path.isfile('install.json')
        assert os.path.isfile('playbook_app.py')
        assert os.path.isfile('tcex.json')
