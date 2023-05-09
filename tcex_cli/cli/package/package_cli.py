"""TcEx Framework Module"""
# standard library
import fnmatch
import json
import os
import shutil
from pathlib import Path

# first-party
from tcex_cli.app.config.install_json import InstallJson
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.cli.model.app_metadata_model import AppMetadataModel
from tcex_cli.cli.model.validation_data_model import ValidationDataModel
from tcex_cli.pleb.cached_property import cached_property


class PackageCli(CliABC):
    """Package ThreatConnect Exchange App for deployment.

    This method will package the App for deployment to ThreatConnect Exchange. A
    validation of the App package will be automatically run before packaging.
    """

    def __init__(self, excludes: list[str] | None, ignore_validation: bool, output_dir: Path):
        """Initialize instance properties."""
        super().__init__()
        self._excludes = excludes or []
        self.ignore_validation = ignore_validation
        self.output_dir = output_dir

        # properties
        self.app_metadata: AppMetadataModel
        self.validation_data: ValidationDataModel

    @cached_property
    def _build_excludes_glob(self):
        """Return a list of files and folders that should be excluded during the build process."""
        # glob files/directories
        return [
            '__pycache__',
            '.pytest_cache',  # pytest cache directory
            '*.iml',  # PyCharm files
            '*.pyc',  # any pyc file
            '*.zip',  # any zip file
        ]

    @cached_property
    def _build_excludes_base(self):
        """Return a list of files/folders that should be excluded in the App base directory."""
        # base directory files/directories
        excludes = [
            self.output_dir,
            '.cache',  # local cache directory
            '.c9',  # C9 IDE
            '.coverage',  # coverage file
            '.coveragerc',  # coverage configuration file file
            '.cspell',  # cspell configuration file
            '.env',  # local environment file
            '.git',  # git directory
            '.gitignore',  # git ignore file
            '.gitlab-ci.yml',  # gitlab ci file
            '.gitmodules',  # git modules
            '.history',  # vscode history plugin
            '.idea',  # PyCharm
            '.pre-commit-config.yaml',  # pre-commit configuration file
            '.prettierrc.toml',  # prettier configuration file
            '.python-version',  # pyenv
            '.template_manifest.json',  # template manifest file
            '.vscode',  # Visual Studio Code
            'angular.json',  # angular configuration file
            'app.yaml',  # requirements builder configuration file
            'app_inputs*.json',  # local testing configuration file
            'artifacts',  # pytest in CI/CD
            'assets',  # pytest in BB Pipelines
            'cspell.json',  # cspell configuration file
            'deps_tests',  # testing dependencies
            'local-*',  # log directory
            'log',  # log directory
            'JIRA.html',  # documentation file
            'JIRA.md',  # documentation file
            'karma.conf.js',  # karma configuration file
            'package-lock.json',  # npm package lock file
            'package.json',  # npm package file
            'pyproject.toml',  # project configuration file
            'README.html',  # documentation file
            'run_local.py',  # local runner file
            'target',  # the target directory for builds
            'test-reports',  # pytest in CI/CD
            'tests',  # pytest test directory
        ]
        excludes.extend(self._excludes)
        excludes.extend(self.app.tj.model.package.excludes)
        return excludes

    @cached_property
    def build_fqpn(self) -> Path:
        """Return the fully qualified path name of the build directory."""
        build_fqpn = self.app_path / self.output_dir.name / 'build'
        build_fqpn.mkdir(exist_ok=True, parents=True)
        return build_fqpn

    def exclude_files(self, src: str, names: list):
        """Ignore exclude files in shutil.copytree (callback)."""
        exclude_list = self._build_excludes_glob
        if src == os.getcwd():
            # get excludes that are specific to the Apps base directory
            exclude_list = self._build_excludes_base

        excluded_files = []
        for n in names:
            for e in exclude_list:
                if fnmatch.fnmatch(n, e):
                    excluded_files.append(n)
        return excluded_files

    def interactive_output(self):
        """[App Builder] Print JSON output containing results of the package command."""
        print(
            json.dumps(
                {
                    'package_data': self.app_metadata.dict(),
                    'validation_data': self.validation_data.dict(),
                }
            )
        )

    def package(self):
        """Build the App package for deployment to ThreatConnect Exchange."""
        # copy project directory to temp location to use as template for multiple builds
        shutil.copytree(self.app_path, self.template_fqpn, False, ignore=self.exclude_files)

        # IMPORTANT:
        # The name of the folder in the zip is the *key* for an App. This
        # value must remain consistent for the App to upgrade successfully.
        app_name_version = (
            f'{self.app.tj.model.package.app_name}_{self.app.ij.model.package_version}'
        )

        # build app directory
        app_path_fqpn = self.build_fqpn / app_name_version
        if os.access(app_path_fqpn, os.W_OK):
            # cleanup any previous failed builds
            shutil.rmtree(app_path_fqpn)
        shutil.copytree(self.template_fqpn, app_path_fqpn)

        # load template install json
        ij_template = InstallJson(path=app_path_fqpn)

        # automatically update install.json in the package directory. specifically, update the
        # languageVersion and sdkVersion fields to match the current values.
        ij_template.update.multiple(sequence=False, valid_values=False, playbook_data_types=False)

        # zip file
        package_name = self.zip_file(self.app_path, app_name_version, self.build_fqpn)

        # create app metadata for output
        self.app_metadata = AppMetadataModel(
            name=self.app.tj.model.package.app_name,
            package_name=package_name,
            template_directory=self.template_fqpn.name,
            version=str(self.app.ij.model.program_version),
        )

        # cleanup build directory
        shutil.rmtree(app_path_fqpn)

    @cached_property
    def template_fqpn(self) -> Path:
        """Return the fully qualified path name of the template directory."""
        template_fqpn = self.build_fqpn / 'template'
        if os.access(template_fqpn, os.W_OK):
            # cleanup any previous failed builds
            shutil.rmtree(template_fqpn)
        return template_fqpn

    def zip_file(self, app_path: Path, app_name: str, tmp_path: Path) -> str:
        """Zip the App with tcex extension.

        Args:
            app_path: The path of the current project.
            app_name: The name of the App.
            tmp_path: The temp output path for the zip.
        """
        # zip build directory
        zip_fqpn = app_path / self.output_dir / app_name

        # create App package
        shutil.make_archive(str(zip_fqpn), format='zip', root_dir=tmp_path, base_dir=app_name)

        # rename the app swapping .zip for .tcx, some filename have "v1.0" which causes
        # the extra dot to be treated as an extension in pathlib.
        zip_fqfn = app_path / self.output_dir / f'{app_name}.zip'
        tcx_fqfn = app_path / self.output_dir / f'{app_name}.tcx'
        zip_fqfn.rename(tcx_fqfn)

        # update package data
        return str(tcx_fqfn)
