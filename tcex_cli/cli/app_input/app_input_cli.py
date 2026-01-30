"""TcEx Framework Module"""

# standard library
import json
import logging
from functools import cached_property
from pathlib import Path
from typing import Any

# first-party
from tcex_cli.app.config.install_json import InstallJson
from tcex_cli.app.config.model.install_json_model import ParamsModel
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.render.render import Render

# get logger
_logger = logging.getLogger(__name__.split('.', maxsplit=1)[0])


class AppInputCli(CliABC):
    """App Input Handling Module."""

    def __init__(self, include_optional: bool = False):
        """Initialize instance properties."""
        super().__init__()

        self.include_optional = include_optional
        self.ij = InstallJson()

        # properties
        self.inputs = {}
        self.kvstore = {}

    def add_input(self, name: str, value: str):
        """."""
        self.inputs[name] = value
        Render.panel.info(f'[green]Added parameter: {name} with value: {value}[/green]')

    def add_kvstore(self, variable: str, value: Any):
        """."""
        self.kvstore[variable] = value
        Render.panel.info(f'[green]Added kvstore variable: {variable} with value: {value}[/green]')

    def get_param_default(self, param: ParamsModel) -> Any:
        """Get the default value for the parameter."""
        try:
            return json.loads(param.default)
        except (json.JSONDecodeError, TypeError):
            panel_msg = f'Error parsing input for {param.name} -> {param.default}'
            Render.panel.failure(panel_msg)

    def get_playbook_datatype(self, param: ParamsModel) -> str:
        """Get the playbook data type for the parameter."""
        if param.type == 'KeyValueList':
            return 'KeyValueArray'

        playbook_data_types = self.get_playbook_datatypes(param)
        match len(playbook_data_types):
            case 0:
                return 'String'

            case 1:
                return playbook_data_types[0]

            case _:
                return self.prompt_user_for_playbook_datatype(playbook_data_types)

    def get_playbook_datatypes(self, param: ParamsModel) -> list[str]:
        """Get the playbook data types for the parameter."""
        if 'Any' in param.playbook_data_type:
            if len(param.playbook_data_type) > 1:
                Render.panel.warning(
                    f'Parameter {param.name} has multiple playbookDataTypes, but "Any" is '
                    'included. Using "Any" should not be combined with other types.'
                )
            return [
                'Binary',
                'BinaryArray',
                'KeyValue',
                'KeyValueArray',
                'String',
                'StringArray',
                'TCEntity',
                'TCEntityArray',
            ]

        return param.playbook_data_type or []

    def get_stage_value(self, param: ParamsModel, playbook_datatype: str, variable: str):
        """Get the value for the parameter based on its type."""
        example_value = self.playbook_datatype_map.get(playbook_datatype)
        if example_value is None:
            panel_msg = f'Unsupported playbookDataType for {param.name}: {playbook_datatype}'
            Render.panel.failure(panel_msg)

        match param.type:
            case 'KeyValueList':
                if param.default:
                    self.add_kvstore(variable, self.get_param_default(param))
                else:
                    self.add_kvstore(variable, example_value)

            case 'String':
                if param.default:
                    self.add_kvstore(variable, param.default)
                else:
                    self.add_kvstore(variable, example_value)

    @staticmethod
    def get_variable(param: ParamsModel, playbook_datatype: str) -> str:
        """Get the variable name for the parameter."""
        return f'#App:1022:{param.name}!{playbook_datatype}'

    @cached_property
    def playbook_datatype_map(self):
        """Map of playbook data types to sample values."""
        return {
            'Any': 'sampleString',
            'Binary': '<base64 encoded string>',
            'BinaryArray': ['<base64 encoded string>'],
            'KeyValue': {'key': 'sampleKey', 'value': 'sampleValue'},
            'KeyValueArray': [{'key': 'sampleKey', 'value': 'sampleValue'}],
            'String': 'sampleString',
            'StringArray': ['sampleString'],
            'TCEntity': {'id': '123', 'type': 'Address', 'value': '1.1.1.1'},
            'TCEntityArray': [{'id': '123', 'type': 'Address', 'value': '1.1.1.1'}],
        }

    def prompt_user_for_playbook_datatype(self, playbook_data_types: list[str]) -> str:
        """Prompt user for playbookDataType."""
        return Render.prompt.ask(
            'This input has multiple playbookDataTypes, please choose one: ',
            choices=playbook_data_types,
            default=playbook_data_types[0],
            show_choices=True,
            show_default=True,
        )

    def prompt_user_for_optional_params(self, param: ParamsModel) -> bool:
        """Prompt user for whether to include optional parameters."""
        include_optional = Render.prompt.ask(
            f'Include optional parameter "{param.name}": ',
            choices=['y', 'n'],
            default='n',
            show_choices=True,
            show_default=True,
        )
        if include_optional is None:
            return False
        return include_optional == 'y'

    def generate_app_inputs(self):
        """Generate the app_inputs.json file."""
        for param in self.ij.model.params or []:
            Render.panel.info(f'[blue]Processing parameter: {param.name}[/blue]')

            # Handle boolean with a true default value, this makes it required
            if param.type == 'Boolean':
                param.required = True

            # Handle optional parameters
            if param.required is False and not self.include_optional:
                optional_choice = self.prompt_user_for_optional_params(param)
                if optional_choice is False:
                    _logger.info(f'Skipping optional parameter: {param.name}')
                    continue

            match param.type:
                # Boolean values cannot be staged
                case 'Boolean':
                    if param.default is not None:
                        self.add_input(param.name, str(param.default).lower())
                    else:
                        self.add_input(param.name, 'false|true')

                case 'Choice' | 'EditChoice' | 'MultiChoice':
                    if param.default:
                        self.add_input(param.name, param.default)
                    else:
                        self.add_input(param.name, '|'.join(param.valid_values))

                case 'EditChoice' | 'KeyValueList' | 'String':
                    # get the appropriate playbook data type
                    playbook_data_type = self.get_playbook_datatype(param)

                    # create a variable to stage
                    variable = self.get_variable(param, playbook_data_type)

                    # always add the input with the value as the variable
                    self.add_input(param.name, variable)

                    # get the value and add the staged data
                    self.get_stage_value(param, playbook_data_type, variable=variable)

        output = {'inputs': self.inputs, 'stage': {'kvstore': self.kvstore}}
        self.write_output_file(output)

    def write_output_file(self, output: dict):
        """Write the output to a JSON file."""
        # Write to a single file
        output_file = Path('app_inputs.json')
        if output_file.exists():
            overwrite = Render.prompt.input(
                f'{output_file} already exists. Overwrite? (y/N): ',
                prompt_default='N',
                subtitle='File will be overwritten if you enter "y".',
            )
            # ask user if they want to overwrite the file
            # overwrite = input(f'{output_file} already exists. Overwrite? (y/N): ').strip().lower()
            if overwrite not in ('y', 'Y', 'yes', 'YES'):
                Render.panel.failure('Aborted. File not overwritten.')
            output_file.unlink()

        with output_file.open('w') as f:
            json.dump(output, f, indent=4)
