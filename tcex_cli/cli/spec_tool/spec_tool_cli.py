"""TcEx Framework Module"""
# standard library
import os
import shutil
import subprocess  # nosec

# third-party
from pydantic import ValidationError

# first-party
from tcex_cli.app.config import AppSpecYml
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.cli.spec_tool.gen_app_input import GenAppInput
from tcex_cli.cli.spec_tool.gen_app_spec_yml import GenAppSpecYml
from tcex_cli.cli.spec_tool.gen_install_json import GenInstallJson
from tcex_cli.cli.spec_tool.gen_job_json import GenJobJson
from tcex_cli.cli.spec_tool.gen_layout_json import GenLayoutJson
from tcex_cli.cli.spec_tool.gen_readme_md import GenReadmeMd
from tcex_cli.cli.spec_tool.gen_tcex_json import GenTcexJson
from tcex_cli.render.render import Render
from tcex_cli.util.code_operation import CodeOperation


class SpecToolCli(CliABC):
    """Generate App Config Files"""

    def __init__(self, overwrite: bool = False):
        """Initialize instance properties."""
        super().__init__()
        self.overwrite = overwrite

        # properties
        self.accent = 'dark_orange'
        self.app_spec_filename = 'app_spec.yml'
        self.asy = AppSpecYml()
        self.report_data = {}
        self.summary_data: dict[str, str] = {}

        # rename app.yaml to app_spec.yml
        self.rename_app_file('app.yaml', 'app_spec.yml')

    def _check_has_spec(self):
        """Validate that the app_spec.yml file exists."""
        if not self.asy.has_spec:
            Render.panel.failure(
                f'No {self.asy.fqfn.name} file found.\nTry running `tcex spec-tool '
                f'--app-spec` first to generate the {self.asy.fqfn.name} specification file.'
            )

    @property
    def _git_installed(self) -> bool:
        """Check if git is installed."""
        installed = True
        try:
            #  pylint: disable=consider-using-with
            subprocess.Popen('git', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # nosec
        except OSError:
            installed = False

        self.log.debug(f'action=check-git-installed, results={installed}')
        return installed

    def _git_mv_file(self, src_filename: str, dest_filename: str) -> bool:
        """Attempt to rename file with git mv."""
        moved = True
        try:
            #  pylint: disable=consider-using-with
            cmd = subprocess.Popen(  # nosec
                ['git', 'mv', src_filename, dest_filename],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _ = cmd.communicate()[0]
            moved = cmd.returncode == 0
        except OSError:
            moved = False

        self.log.debug(
            f'action=mv-file, src-filename={src_filename}, '
            f'dest-filename={dest_filename}, results={moved}'
        )
        return moved

    def generate_app_input(self):
        """Generate the app_input.py file."""
        # force migration of app.yaml file
        _ = self.asy.model.app_id

        gen = GenAppInput()
        code = gen.generate()
        self.write_app_file(gen.filename, CodeOperation.format_code('\n'.join(code)))
        if gen.report_mismatch:
            _reports = []
            for r in gen.report_mismatch:
                _reports.append(
                    {
                        'key': 'Mismatch',
                        'value': r,
                    }
                )
            self.report_data['Mismatch Report'] = _reports

    def generate_app_spec(self):
        """Generate the app_spec.yml file."""
        gen = GenAppSpecYml()
        try:
            config = gen.generate()
        except ValidationError as ex:
            Render.panel.failure(f'Failed Generating app_spec.yml:\n{ex}')

        self.write_app_file(gen.filename, f'{config}\n')

    def generate_install_json(self):
        """Generate the install.json file."""
        gen = GenInstallJson(self.asy)
        # check that app_spec.yml exists
        self._check_has_spec()

        try:
            ij = gen.generate()
        except ValidationError as ex:
            self.log.exception('Failed Generating install.json')
            Render.panel.failure(f'Failed Generating install.json:\n{ex}')

        # exclude_defaults - if False then all unused fields are added in - not good.
        # exclude_none - this should be safe to leave as True.
        # exclude_unset - this should be safe to leave as True.
        config = ij.json(
            by_alias=True,
            exclude_defaults=True,
            exclude_none=True,
            exclude_unset=True,
            indent=2,
            sort_keys=True,
        )
        self.write_app_file(gen.filename, f'{config}\n')

    def generate_layout_json(self):
        """Generate the layout.json file."""
        gen = GenLayoutJson(self.asy)
        if any([self.app.ij.model.is_playbook_app, self.app.ij.model.is_trigger_app]):
            # check that app_spec.yml exists
            self._check_has_spec()

            if self.asy.model.requires_layout:
                try:
                    lj = gen.generate()
                except ValidationError as ex:
                    self.log.exception('Failed Generating layout.json')
                    Render.panel.failure(f'Failed Generating layout.json:\n{ex}')

                # exclude_defaults - if False then all unused fields are added in - not good.
                # exclude_none - this should be safe to leave as True.
                # exclude_unset - this should be safe to leave as True.
                config = lj.json(
                    by_alias=True,
                    exclude_defaults=True,
                    exclude_none=True,
                    exclude_unset=True,
                    indent=2,
                    sort_keys=True,
                )
                self.write_app_file(gen.filename, f'{config}\n')

    def generate_job_json(self):
        """Generate the job.json file."""
        gen = GenJobJson(self.asy)
        if self.asy.model.is_feed_app:
            # check that app_spec.yml exists
            self._check_has_spec()

            try:
                for filename, job in gen.generate():
                    if job is not None:
                        config = job.json(
                            by_alias=True,
                            exclude_defaults=True,
                            exclude_none=True,
                            exclude_unset=True,
                            indent=2,
                            sort_keys=True,
                        )
                        self.write_app_file(filename, f'{config}\n')
            except ValidationError as ex:
                self.log.exception('Failed Generating job.json')
                Render.panel.failure(f'Failed Generating job.json:\n{ex}')

    def generate_readme_md(self):
        """Generate the README.me file."""
        # check that app_spec.yml exists
        self._check_has_spec()

        gen = GenReadmeMd(self.asy)
        readme_md = gen.generate()
        self.write_app_file(gen.filename, '\n'.join(readme_md))

    def generate_tcex_json(self):
        """Generate the tcex.json file."""
        gen = GenTcexJson(self.asy)
        # check that app_spec.yml exists
        self._check_has_spec()

        try:
            tj = gen.generate()
        except ValidationError as ex:
            self.log.exception('Failed Generating tcex.json')
            Render.panel.failure(f'Failed Generating tcex.json:\n{ex}')

        # exclude_defaults - if False then all unused fields are added in - not good.
        # exclude_none - this should be safe to leave as True.
        # exclude_unset - this should be safe to leave as True.
        config = tj.json(
            by_alias=True,
            exclude_defaults=True,
            exclude_none=True,
            exclude_unset=True,
            indent=2,
            sort_keys=True,
        )
        self.write_app_file(gen.filename, f'{config}\n')

    def rename_app_file(self, src_filename: str, dest_filename: str):
        """Rename the app.yaml file to app_spec.yml."""
        if os.path.isfile(src_filename):
            self.log.debug(
                f'action=rename-file, src-filename={src_filename}, dest-filename={dest_filename}'
            )

            moved = False
            if self._git_installed is True:
                # to not loose git history of the file
                moved = self._git_mv_file(src_filename, dest_filename)

            if moved is False:
                shutil.move('app.yaml', 'app_spec.yml')

    def write_app_file(self, file_name: str, contents: str):
        """Write contents to file."""
        action = 'Created'
        write_file = True
        if os.path.isfile(file_name):
            action = 'Updated'
            if self.overwrite is False:
                response = Render.prompt.input(
                    f'Overwrite existing [{self.accent}]{file_name}[/{self.accent}] file?',
                    prompt_default=f' (Default: [{self.accent}]no[/{self.accent}])',
                )
                if response != 'yes':
                    action = '[yellow]Skipped[/yellow]'
                    write_file = False

        if write_file is True:
            with open(file_name, 'w', encoding='utf-8') as f:
                f.write(contents)

        self.summary_data[file_name] = f'[green]{action}[/green]'
