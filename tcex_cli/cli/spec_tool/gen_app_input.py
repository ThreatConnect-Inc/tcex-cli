"""TcEx Framework Module"""
# standard library
import logging
import os
import re

# first-party
from tcex_cli.app.config.model.install_json_model import ParamsModel  # TYPE-CHECKING
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.cli.spec_tool.gen_app_input_static import GenAppInputStatic
from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.render.render import Render
from tcex_cli.util.code_operation import CodeOperation

# get logger
_logger = logging.getLogger(__name__.split('.', maxsplit=1)[0])


class GenAppInput(CliABC):
    """Generate App Config File"""

    def __init__(self):
        """Initialize instance properties."""
        super().__init__()

        # properties
        self._app_inputs_data: dict | None = None
        self.class_model_map = {}
        self.field_type_modules = self._get_current_field_types()
        self.filename = 'app_inputs.py'
        self.input_static = GenAppInputStatic()
        self.log = _logger
        self.typing_modules = set()
        self.pydantic_modules = {'BaseModel'}
        self.report_mismatch = []

    def _add_action_classes(self):
        """Add actions to the App."""
        for action in self._tc_actions:
            class_name = self._gen_tc_action_class_name(action)
            self.class_model_map[action] = class_name
            if isinstance(self._app_inputs_data, dict):
                self._app_inputs_data[class_name] = {}

    def _add_input_to_action_class(
        self, applies_to_all: bool, param_data: ParamsModel, tc_action: str | None = None
    ):
        """Add input data to Action class."""
        tc_action_class = 'AppBaseModel'
        if applies_to_all is False:
            tc_action_class = self._gen_tc_action_class_name(tc_action)
        self.app_inputs_data[tc_action_class][param_data.name] = param_data

    def class_comment(self, model_class: str) -> str:
        """Return the appropriate comment for the provided class."""
        _class_comment = f'{self.i1}"""Action Model"""'
        _comment_map = {
            'AppBaseModel': self.input_static.app_base_model_class_comment,
            'ServiceConfigModel': self.input_static.service_config_model_class_comment,
            'TriggerConfigModel': self.input_static.trigger_config_model_class_comment,
        }
        return _comment_map.get(model_class, _class_comment)

    @property
    def _code_app_inputs_data(self):
        """Return app_inputs.py input data."""
        _code = []
        # sorting of the inputs can only be done at this point
        for class_name, class_inputs in self.app_inputs_data.items():
            # determine the base class for the current action class
            base_class = 'AppBaseModel'
            class_comment = self.class_comment(class_name)
            if class_name in ['AppBaseModel', 'ServiceConfigModel']:
                base_class = self.input_static.app_base_model_class
            elif class_name == 'TriggerConfigModel':
                base_class = 'CreateConfigModel'

            _code.extend(
                [
                    f'class {class_name}({base_class}):',
                    f'{class_comment}',
                    '',
                ]
            )
            _always_array = []
            _entity_input = []
            for input_name, input_data in sorted(class_inputs.items()):
                # skip special inputs
                if input_name in ['tc_log_level']:
                    continue

                # add comment
                _comment = self._code_app_inputs_data_comments(input_data)
                if _comment is not None:
                    _code.append(_comment)

                # add finalized input code line
                _type_data = f'{self.i1}{input_name}: {self._gen_type(class_name, input_data)}'
                _code.append(_type_data)

                # check if validator are applicable to this input
                if self._validator_always_array_check(input_data) is True:
                    _always_array.append(f'\'{input_name}\'')

                if self._validator_entity_input_check(input_data) is True:
                    _entity_input.append(f'\'{input_name}\'')

            # validator - always_array
            if _always_array:
                self.field_type_modules.add('always_array')
                self.pydantic_modules.add('validator')
                _code.extend(self._validator_always_array(_always_array))

            # validator - entity_input
            if _entity_input:
                self.field_type_modules.add('entity_input')
                self.pydantic_modules.add('validator')
                _code.extend(self._validator_entity_input(_entity_input))

        # append 2 blank lines between classes
        _code.append('')
        _code.append('')
        return _code

    def _code_app_inputs_data_comments(self, input_data: ParamsModel) -> str | None:
        """Return comments for a single input."""
        # append comment for playbookDataTypes
        comments = []
        if input_data.playbook_data_type:
            playbook_data_type_str = '|'.join(input_data.playbook_data_type)
            comments.append(f'pbd: {playbook_data_type_str}')
        # append comment for validValues
        if input_data.valid_values:
            valid_values_str = '|'.join(input_data.valid_values)
            comments.append(f'vv: {valid_values_str}')

        if comments:
            comment = ', '.join(comments)
            comment_wrapped = self.util.wrap_string(comment, [' ', '|'], 80).split('\n')
            return '\n'.join([f'{self.i1}# {c}' for c in comment_wrapped])
        return None

    def _extract_type_from_definition(self, input_name: str, type_definition: str) -> str | None:
        """Extract the type from the type definition.

        string_allow_multiple: String | list[String] -> String | list[String]
        string_intel_type: str | None -> str | None
        """
        input_extract_pattern = (
            # match beginning white space on line
            r'(?:^\s+)?'
            # match input name
            rf'(?:{input_name}:\s)'
            # Capture Group: greedy capture until the end of the line
            r'(.*)$'
        )
        current_type = re.search(input_extract_pattern, type_definition)
        if current_type is not None:
            self.log.debug(
                f'action=extract-type-from-definition, current-type={current_type.group(1)}'
            )
            return current_type.group(1).strip()
        return None

    def _generate_app_inputs_to_action(self):
        """Generate App Input dict from install.json and layout.json."""
        if self.app.ij.model.is_trigger_app is True:
            # Process the following App types:
            # - playbook trigger service Apps
            for ij_data in self.app.ij.model.params_dict.values():
                class_name = 'Trigger Config'
                if ij_data.service_config is True:
                    class_name = 'Service Config'
                self._add_input_to_action_class(False, ij_data, class_name)
        elif self.app.lj.has_layout is False or not self._tc_actions:
            # Process the following App types:
            # - Job Apps
            # - Playbook App with no layout.json
            # - Playbook App with layout.json but no tc_actions
            for ij_data in self.app.ij.model.params_dict.values():
                self._add_input_to_action_class(True, ij_data)
        else:
            # Process the following App types:
            # - Playbook App with layout.json and tc_action input
            for tc_action in self._tc_actions:
                if tc_action == 'Advanced Request':
                    # AdvancedRequestModel is included in tcex
                    continue

                for input_data in self.app.permutation.get_action_inputs(tc_action):
                    applies_to_all = self.app.permutation.get_input_applies_to_all(input_data.name)
                    self._add_input_to_action_class(applies_to_all, input_data, tc_action)

                    self.log.debug(
                        f'''action=inputs-to-action, input-name={input_data.name}, '''
                        f'''applies-to-all={applies_to_all}'''
                    )

    @staticmethod
    def _gen_tc_action_class_name(tc_action: str | None) -> str | None:
        """Format the action to a proper class name."""
        if tc_action is not None:
            # split to make pascal case
            _parts = [p.title() for p in tc_action.replace('_', ' ').split(' ')]

            # title case each word
            tc_action = ''.join([f'{p.title()}' for p in _parts]) + 'Model'

            # remove all non-alphanumeric characters and underscores
            tc_action = re.sub(r'[^a-zA-Z0-9]', '', tc_action)
        return tc_action

    def _gen_type_compare(
        self, calculated_type: str, current_type: str | None, input_name: str
    ) -> str:
        """Retrieve the current type data for the current input."""
        if current_type is not None and calculated_type != current_type:
            self.report_mismatch.append(
                {'input': input_name, 'calculated': calculated_type, 'current': current_type}
            )
            self.log.warning(
                f'input={input_name}, current-type={current_type}, '
                f'calculated-type={calculated_type}, using=current-type'
            )
            return current_type
        return calculated_type

    def _gen_type(self, class_name: str, input_data: ParamsModel) -> str:
        """Determine the type value for the current input."""
        # calculate the field type for the current input
        calculated_type, field_types = self._get_type_calculated(input_data)
        current_type = self._get_type_current(class_name, input_data.name)

        # if the current type is not None, use the current type defined by the developer
        type_ = self._gen_type_compare(calculated_type, current_type, input_data.name)

        # add field types for import
        if type_ == calculated_type:
            for field_type in field_types:
                if field_type is not None:
                    # TODO: [low] should we define supported field types?
                    self.field_type_modules.add(field_type)

                    # # only add the field type if it is a defined field type
                    # if hasattr(FieldTypes, field_type):
                    #     self.field_type_modules.add(field_type)

        return type_

    def _get_type_calculated(self, input_data: ParamsModel) -> tuple[str, list]:
        """Calculate the type value for the current input."""
        # a list of field types that will be added to the import (e.g. DateTime, integer, String)
        field_types = []

        # calculate the lookup key for looking in GenAppInputStatic.type_map
        lookup_key = input_data.type
        required_key = 'optional' if input_data.required is False else 'required'
        if input_data.encrypt is True:
            lookup_key = 'Encrypt'

        # lookup input name in standards map to get pre-defined type.
        standard_name_type = self._standard_field_to_type_map(input_data.name)

        # get the type value and field type
        type_: str
        if standard_name_type is not None:
            type_ = standard_name_type['type']
            field_types.append(standard_name_type.get('field_type'))
        elif input_data.type == 'Boolean':
            type_ = 'bool'
        elif (
            input_data.encrypt is False
            and input_data.type == 'String'
            and input_data.playbook_data_type not in [[], None]
        ):
            type_, field_types = self._gen_type_from_playbook_data_type(
                required_key, input_data.playbook_data_type
            )
        else:
            try:
                type_ = self.input_static.type_map[lookup_key][required_key]['type']
                field_types = [self.input_static.type_map[lookup_key][required_key]['field_type']]
            except (AttributeError, KeyError) as ex:
                Render.panel.failure(f'Failed looking up type data for {input_data.type} ({ex}).')

        # for non-required inputs, make optional
        if input_data.required is False and input_data.type not in ('Boolean'):
            type_ = f'{type_} | None'

        # append default if one exists
        if input_data.type == 'Boolean':
            type_ += f' = {input_data.default or False}'

        return type_, field_types

    def _get_type_current(self, class_name: str, input_name: str) -> str | None:
        """Return the type from the current app_input.py file if found."""
        # parsing the previous app_inputs.py file for the type definition, this is a bit tricky
        # because the type definition can be in a number of different formats, so we need to
        # search for it in a number of different ways.
        # first, search for the input name in the class definition, if not found, search for the
        # type definition in the entire file. this is best effort, if we can't find the type
        # definition, we'll just use the calculated type.
        type_definition = CodeOperation.find_line_in_code(
            needle=rf'\s+{input_name}: ',
            code=self.app_inputs_contents,
            trigger_start=rf'^class {class_name}',
            trigger_stop=r'^class ',
        )

        # if we didn't find the type definition in the class definition, search the entire file
        if type_definition is None:
            type_definition = CodeOperation.find_line_in_code(
                needle=fr'\s+{input_name}: ', code=self.app_inputs_contents
            )

        # type_definition -> "string_encrypt: Sensitive | None"
        self.log.debug(
            f'action=find-definition, input-name={input_name}, '
            f'class-name={class_name}, type-definition={type_definition}'
        )

        # parse out the actual type
        if type_definition is not None:
            current_type = self._extract_type_from_definition(input_name, type_definition)
            if current_type is not None:
                return current_type

            self.log.warning(
                f'input found, but not matched: input={input_name}, '
                f'type_definition={type_definition}'
            )

        return None

    def _gen_type_from_playbook_data_type(
        self, required_key: str, playbook_data_types: list[str]
    ) -> tuple[str, list[str]]:
        """Return type based on playbook data type."""
        # TODO: [low] does anything special need to be done for Any type?
        if 'Any' in playbook_data_types:
            self.typing_modules.add('Any')

        if len(playbook_data_types) == 1:
            _field_types = [
                self.input_static.type_map[playbook_data_types[0]][required_key]['field_type']
            ]
            _types = self.input_static.type_map[playbook_data_types[0]][required_key]['type']
        else:
            _types = []
            _field_types = []
            for lookup_key in playbook_data_types:
                _field_types.append(
                    self.input_static.type_map[lookup_key][required_key]['field_type']
                )
                _types.append(self.input_static.type_map[lookup_key][required_key]['type'])
            _types = f'''{' | '.join(_types)}'''

        return _types, _field_types

    def _get_current_field_types(self) -> set[str]:
        """Return the current type from the type data

        imports: integer, String
        returns: ['integer', 'String']
        """
        types = []

        needle = 'from tcex.input.field_type import'
        type_definition = CodeOperation.find_line_in_code(
            needle=rf'^{needle}',
            code=self.app_inputs_contents,
        )
        if type_definition is not None:
            types = type_definition.replace(needle, '').strip().split(', ')
        return set(types)

    @staticmethod
    def _standard_field_to_type_map(input_name: str) -> dict | None:
        """Return the type for "standard" input fields."""
        _field_name_to_type_map = {
            'confidence_rating': {
                'type': 'integer(ge=0, le=100)',
                'field_type': 'integer',
            },
            'last_run': {
                'type': 'DateTime',
                'field_type': 'DateTime',
            },
            'max_historical_poll_start': {
                'type': 'DateTime',
                'field_type': 'DateTime',
            },
            'poll_interval': {
                'type': 'integer(gt=0)',
                'field_type': 'integer',
            },
            'threat_rating': {
                'type': 'integer(ge=0, le=5)',
                'field_type': 'integer',
            },
        }
        return _field_name_to_type_map.get(input_name)

    @property
    def _tc_actions(self):
        """Return tc_action input valid values."""
        _tc_action = self.app.ij.model.get_param('tc_action')
        if _tc_action is None:
            return []
        return _tc_action.valid_values

    def _validator_always_array(self, always_array: list[str]) -> list[str]:
        """Return code for always_array_validator."""
        _always_array = ', '.join(always_array)
        return [
            '',
            f'{self.i1}# ensure inputs that take single and array types always return an array',
            (
                f'{self.i1}_always_array = validator({_always_array}, allow_reuse=True, pre=True)'
                '(always_array(allow_empty=True, include_empty=False, '
                'include_null=False, split_csv=True))'
            ),
        ]

    def _validator_always_array_check(self, input_data: ParamsModel) -> bool:
        """Return True if Single and Multiple types used."""
        array_type = False
        single_type = False
        for _type in input_data.playbook_data_type:
            if _type in self.util.variable_playbook_array_types:
                array_type = True
            elif _type in self.util.variable_playbook_single_types:
                single_type = True

        return all([array_type, single_type])

    def _validator_entity_input(self, entity_input: list[str]) -> list[str]:
        """Return code for always_array_validator."""
        _entity_input = ', '.join(entity_input)
        return [
            '',
            f'{self.i1}# add entity_input validator for supported types',
            (
                f'''{self.i1}_entity_input = validator({_entity_input}, '''
                '''allow_reuse=True)(entity_input(only_field='value'))'''
            ),
        ]

    @staticmethod
    def _validator_entity_input_check(input_data: ParamsModel) -> bool:
        """Return True if Single and Multiple types used."""
        for _type in input_data.playbook_data_type:
            if _type in ['TCEntity', 'TCEntityArray']:
                return True
        return False

    @cached_property
    def app_inputs_contents(self):
        """Return app_inputs.py contents."""
        if os.path.isfile('app_inputs.py'):
            with open('app_inputs.py', encoding='utf-8') as f:
                return f.read()
        return ''

    @property
    def app_inputs_data(self) -> dict:
        """Return base App inputs data."""
        if self._app_inputs_data is None:
            if self.app.ij.model.is_trigger_app:
                self._app_inputs_data = {'ServiceConfigModel': {}, 'TriggerConfigModel': {}}
            else:
                self._app_inputs_data = {'AppBaseModel': {}}

            # add a model for each action (for layout based Apps)
            self._add_action_classes()
        return self._app_inputs_data

    def generate(self):
        """Generate App Config File"""
        self.log.debug('--- generate: App Inputs ---')

        # generate the App Inputs
        self._generate_app_inputs_to_action()

        # generate input code first so that imports can be added
        _code_inputs = self._code_app_inputs_data

        # create the app_inputs.py code
        code = self.input_static.template_app_imports(
            self.field_type_modules, self.pydantic_modules, self.typing_modules
        )
        code.extend(_code_inputs)
        if self.app.ij.model.get_param('tc_action') is None:
            code.extend(self.input_static.template_app_inputs_class())
        else:
            # the App support tc_action and should use the tc_action input class
            code.extend(self.input_static.template_app_inputs_class_tc_action(self.class_model_map))
        return code
