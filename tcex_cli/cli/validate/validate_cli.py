"""TcEx Framework Module"""

# standard library
import ast
import json
import os
import sys
import traceback
from pathlib import Path

# third-party
from pydantic import ValidationError

# first-party
from tcex_cli.app.config.job_json import JobJson
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.cli.model.validation_data_model import ValidationDataModel, ValidationItemModel

try:
    # standard library
    import sqlite3
except ModuleNotFoundError:
    # this module is only required for certain CLI commands
    pass


class ValidateCli(CliABC):
    """Validate syntax and schemas.

    * Python and JSON file syntax
    * install.json schema
    * layout.json schema
    """

    def __init__(self, ignore_validation: bool):
        """Initialize instance properties."""
        super().__init__()
        self.ignore_validation = ignore_validation

        # class properties
        self.invalid_json_files = []
        self.validation_data = ValidationDataModel(
            errors=[],
            fileSyntax=[],
            layouts=[],
            schema_=[],
            feeds=[],
        )

    def check_install_json(self):
        """Check all install.json files for valid schema."""
        if 'install.json' in self.invalid_json_files:
            return

        status = True
        try:
            self.app.ij.model
        except ValidationError as ex:
            self.invalid_json_files.append(self.app.ij.fqfn.name)
            status = False
            for error in json.loads(ex.json()):
                location = [str(location) for location in error.get('loc')]
                self.validation_data.errors.append(
                    '''Schema validation failed for install.json. '''
                    f'''{error.get('msg')}: {' -> '.join(location)}'''
                )
        except ValueError:
            # any JSON decode error will be caught during syntax validation
            return

        self.validation_data.schema_.append(
            ValidationItemModel(**{'name': self.app.ij.fqfn.name, 'status': status})
        )

    def check_job_json(self):
        """Validate feed files for feed job apps."""
        if 'install.json' in self.invalid_json_files:
            # can't proceed if install.json can't be read
            return

        if not self.app.ij.model.feeds:
            # if no jobs, skip!
            return

        # use developer defined app version (deprecated) or package_version from InstallJson model
        app_version = self.app.tj.model.package.app_version or self.app.ij.model.package_version
        program_name = (f'{self.app.tj.model.package.app_name}_{app_version}').replace('_', ' ')
        status = True
        for feed in self.app.ij.model.feeds or []:
            if feed.job_file in self.invalid_json_files:
                # no need to check if schema if json is invalid
                continue

            jj = JobJson(filename=feed.job_file)

            # validate the job file exists
            if not jj.fqfn.is_file():
                self.validation_data.errors.append(
                    f'Schema validation failed for {feed.job_file}. '
                    'The job.json file could not be found.'
                )
                continue

            try:
                # validate the schema
                jj.model
            except ValidationError as ex:
                status = False
                for error in json.loads(ex.json()):
                    location = [str(location) for location in error.get('loc')]
                    self.validation_data.errors.append(
                        f'''Schema validation failed for {feed.job_file}. '''
                        f'''{error.get('msg')}: {' -> '.join(location)}'''
                    )

            # validate program name
            if status is True and jj.model.program_name != program_name:
                status = False
                self.validation_data.errors.append(
                    f'Schema validation failed for {feed.job_file}. '
                    f'The job.json programName {jj.model.program_name} != {program_name}.'
                )

            # validate program version
            if status is True and jj.model.program_version != self.app.ij.model.program_version:
                status = False
                self.validation_data.errors.append(
                    f'Schema validation failed for {feed.job_file}. The job.json program'
                    f'Version {jj.model.program_version} != {self.app.ij.model.program_version}.'
                )

            self.validation_data.schema_.append(
                ValidationItemModel(**{'name': feed.job_file, 'status': status})
            )

    def check_layout_json(self):
        """Check all layout.json files for valid schema."""
        if not self.app.lj.has_layout or 'layout.json' in self.invalid_json_files:
            return

        status = True
        try:
            self.app.lj.model
        except ValidationError as ex:
            self.invalid_json_files.append(self.app.ij.fqfn.name)
            status = False
            for error in json.loads(ex.json()):
                location = [str(location) for location in error.get('loc')]
                self.validation_data.errors.append(
                    f'''Schema validation failed for layout.json. '''
                    f'''{error.get('msg')}: {' -> '.join(location)}'''
                )
        except ValueError:
            # any JSON decode error will be caught during syntax validation
            return

        self.validation_data.schema_.append(
            ValidationItemModel(**{'name': self.app.lj.fqfn.name, 'status': status})
        )

        if status is True:
            self.check_layout_params()

    def check_layout_params(self):
        """Check that the layout.json is consistent with install.json.

        The layout.json files references the params.name from the install.json file.  The method
        will validate that no reference appear for inputs in install.json that don't exist.
        """
        # do not track hidden or serviceConfig inputs as they should not be in layouts.json
        ij_input_names = list(self.app.ij.model.filter_params(service_config=False, hidden=False))

        ij_output_names = []
        if self.app.ij.model.playbook:
            ij_output_names = [o.name for o in self.app.ij.model.playbook.output_variables or []]

        # Check for duplicate inputs
        for name in self.app.ij.validate.validate_duplicate_input():
            self.validation_data.errors.append(
                f'Duplicate input name found in install.json ({name})'
            )
            status = False

        # Check for duplicate sequence numbers
        for sequence in self.app.ij.validate.validate_duplicate_sequence():
            self.validation_data.errors.append(
                f'Duplicate sequence number found in install.json ({sequence})'
            )
            status = False

        # Check for duplicate outputs variables
        for output in self.app.ij.validate.validate_duplicate_output():
            self.validation_data.errors.append(
                f'Duplicate output variable name found in install.json ({output})'
            )
            status = False

        if 'sqlite3' in sys.modules:
            # create temporary inputs tables
            self.app.permutation.db_create_table(self.app.permutation.input_table, ij_input_names)

        # inputs
        status = True
        for i in self.app.lj.model.inputs:
            for p in i.parameters:
                if p.name not in ij_input_names:
                    # update validation data errors
                    self.validation_data.errors.append(
                        'Layouts input.parameters[].name validations failed '
                        f'("{p.name}" is defined in layout.json, '
                        'but hidden or not found in install.json).'
                    )
                    status = False
                else:
                    # any item in list afterwards is a problem
                    ij_input_names.remove(p.name)

                if 'sqlite3' in sys.modules:
                    if p.display:
                        display_query = (
                            f'SELECT * FROM {self.app.permutation.input_table}'  # nosec
                            f' WHERE {p.display}'
                        )
                        try:
                            self.app.permutation.db_conn.execute(display_query.replace('"', ''))
                        except sqlite3.Error:  # type: ignore
                            self.validation_data.errors.append(
                                'Layouts input.parameters[].display validations failed '
                                f'("{p.display}" query is an invalid statement).'
                            )
                            status = False

        # update validation data for module
        self.validation_data.layouts.append(
            ValidationItemModel(**{'name': 'inputs', 'status': status})
        )

        if ij_input_names:
            input_names = ','.join(ij_input_names)
            # update validation data errors
            self.validation_data.errors.append(
                f'Layouts input.parameters[].name validations failed ("{input_names}" '
                'values from install.json were not included in layout.json.'
            )
            status = False

        # outputs
        status = True
        for o in self.app.lj.model.outputs:
            if o.name not in ij_output_names:
                # update validation data errors
                self.validation_data.errors.append(
                    f'Layouts output validations failed ({o.name} is defined '
                    'in layout.json, but not found in install.json).'
                )
                status = False

            if 'sqlite3' in sys.modules:
                if o.display:
                    display_query = (
                        f'SELECT * FROM {self.app.permutation.input_table} '  # nosec
                        f'WHERE {o.display}'
                    )
                    try:
                        self.app.permutation.db_conn.execute(display_query.replace('"', ''))
                    except sqlite3.Error:  # type: ignore
                        self.validation_data.errors.append(
                            f"""Layouts outputs.display validations failed ("{o.display}" """
                            f"""query is an invalid statement)."""
                        )
                        status = False

        # update validation data for module
        self.validation_data.layouts.append(
            ValidationItemModel(**{'name': 'outputs', 'status': status})
        )

    def check_syntax(self, app_path=None):
        """Run syntax on each ".py" and ".json" file.

        Args:
            app_path (str, optional): The path of Python files.
        """
        fqpn = Path(app_path or os.getcwd())

        for fqfn in sorted(fqpn.iterdir()):
            error = None
            status = True
            if fqfn.name.endswith('.py'):
                try:
                    with fqfn.open(mode='rb') as fh:
                        ast.parse(fh.read(), filename=fqfn.name)
                except SyntaxError:
                    status = False

                    # cleanup output
                    e = []
                    for line in traceback.format_exc().split('\n')[-5:-2]:
                        e.append(line.strip())
                    error = ' '.join(e)

            elif fqfn.name.endswith('.json'):
                try:
                    with fqfn.open() as fh:
                        json.load(fh)
                except ValueError as e:
                    # update tracker for common files
                    self.invalid_json_files.append(fqfn.name)
                    status = False
                    error = e
            else:
                # skip unsupported file types
                continue

            if error:
                # update validation data errors
                self.validation_data.errors.append(
                    f'Syntax validation failed for {fqfn.name} ({error}).'
                )

            # store status for this file
            self.validation_data.fileSyntax.append(
                ValidationItemModel(**{'name': fqfn.name, 'status': status})
            )

    def interactive(self):
        """[App Builder] Run in interactive mode."""
        while True:
            line = sys.stdin.readline().strip()
            if line == 'quit':
                sys.exit()
            elif line == 'validate':
                self.check_syntax()
                self.check_install_json()
                self.check_layout_json()
                self.check_job_json()
                self.interactive_output()

                # reset - between runs
                self.validation_data = ValidationDataModel(
                    errors=[],
                    fileSyntax=[],
                    layouts=[],
                    schema_=[],
                    feeds=[],
                )

    def interactive_output(self):
        """[App Builder] Print JSON output."""
        print(json.dumps({'validation_data': self.validation_data.dict()}))
