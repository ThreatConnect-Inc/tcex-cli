"""TcEx Framework Module"""

# standard library
from functools import cached_property

# first-party
from tcex_cli.app.config.install_json import InstallJson

# from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.render.render import Render


class GenAppInputStatic:
    """Generate App Input code"""

    def __init__(self):
        """Initialize instance properties."""

        # class properties
        self.i1 = ' ' * 4
        self.i2 = ' ' * 8
        self.i3 = ' ' * 12
        self.i4 = ' ' * 16
        self.ij = InstallJson()

    @cached_property
    def app_base_model_class(self) -> str:
        """Return App Base Model class."""
        _class, _ = self.app_base_model_data
        return _class

    @property
    def app_base_model_class_comment(self) -> str:
        """Return Service Config Model class."""
        return f'{self.i1}"""Base model for the App containing any common inputs."""'

    @cached_property
    def app_base_model_data(self) -> tuple[str, str]:
        """Return App Base Model data."""
        match self.ij.model.runtime_level.lower():
            case 'apiservice':
                _class = 'AppApiServiceModel'
                _file = 'app_api_service_model'

            case 'feedapiservice':
                _class = 'AppFeedApiServiceModel'
                _file = 'app_feed_api_service_model'

            case 'organization':
                _class = 'AppOrganizationModel'
                _file = 'app_organization_model'

            case 'playbook':
                _class = 'AppPlaybookModel'
                _file = 'app_playbook_model'

            case 'triggerservice':
                _class = 'AppTriggerServiceModel'
                _file = 'app_trigger_service_model'

            case 'webhooktriggerservice':
                _class = 'AppWebhookTriggerServiceModel'
                _file = 'app_webhook_trigger_service_model'

            case _:
                Render.panel.failure(f'Invalid runtime level ({self.ij.model.runtime_level}).')

        return _class, _file

    @cached_property
    def app_base_model_import(self) -> str:
        """Return App Base Model import."""
        _class, _file = self.app_base_model_data
        return f'from tcex.input.model.{_file} import {_class}'

    @property
    def service_config_model_class_comment(self) -> str:
        """Return Service Config Model class."""
        return '\n'.join(
            [
                f'''{self.i1}"""Base model for the App containing any common inputs.''',
                '',
                f'''{self.i1}Trigger Service App inputs do not take playbookDataType.''',
                '',
                f'''{self.i1}This is the configuration input that is sent to the Service''',
                f'''{self.i1}on startup. The inputs that are configured in the Service''',
                f'''{self.i1}configuration in the Platform with serviceConfig: true''',
                f'''{self.i1}"""''',
                '',
                '',
            ]
        )

    def template_app_imports(
        self,
        field_type_modules: set[str],
        pydantic_modules: set[str],
        typing_modules: set[str],
    ) -> list:
        """Return app_inputs.py import data."""
        field_types_modules_ = ', '.join(sorted(list(field_type_modules)))
        pydantic_modules_ = ', '.join(sorted(list(pydantic_modules)))
        typing_modules_ = ', '.join(sorted(list(typing_modules)))

        # defined imports
        _imports = ['"""App Inputs"""']

        # add pyright ignore for field_type
        _imports.append('# pyright: reportGeneralTypeIssues=false\n')

        # add typing imports
        if typing_modules:
            _imports.append(f'from typing import {typing_modules_}')

        # add pydantic imports
        if pydantic_modules:
            _imports.append(f'from pydantic import {pydantic_modules_}')

        # add tcex Input
        _imports.append('from tcex.input.input import Input')

        # add field_type imports
        if field_types_modules_:
            _imports.append(f'from tcex.input.field_type import {field_types_modules_}')

        # add base model import
        _imports.append(self.app_base_model_import)

        # add import for service trigger Apps
        if self.ij.model.is_trigger_app:
            _imports.append('from tcex.input.model import CreateConfigModel')

        # add new lines
        _imports.extend(
            [
                '',
                '',
            ]
        )
        return _imports

    def template_app_inputs_class(self) -> list:
        """Return app_inputs.py AppInput class."""
        app_model = 'AppBaseModel'
        if self.ij.model.is_trigger_app:
            app_model = 'ServiceConfigModel'

        _code = [
            '''class AppInputs:''',
            f'''{self.i1}"""App Inputs"""''',
            '',
        ]

        # add __init__ method
        _code.extend(
            [
                f'''{self.i1}def __init__(self, inputs: Input):''',
                f'''{self.i2}"""Initialize instance properties."""''',
                f'''{self.i2}self.inputs = inputs''',
                '',
            ]
        )

        # add update_inputs method
        _code.extend(
            [
                '',
                f'''{self.i1}def update_inputs(self):''',
                f'''{self.i2}"""Add custom App model to inputs.''',
                '',
                (
                    f'''{self.i2}Input will be validate when the '''
                    '''model is added an any exceptions will'''
                ),
                f'''{self.i2}cause the App to exit with a status code of 1.''',
                f'''{self.i2}"""''',
                f'''{self.i2}self.inputs.add_model({app_model})''',
                '',
                '',
            ]
        )
        return _code

    def template_app_inputs_class_tc_action(self, class_model_map: dict) -> list:
        """Return app_inputs.py AppInput class for App with tc_action."""
        cmm = ''
        for action, class_name in class_model_map.items():
            action_name = action.lower().replace(' ', '_')
            cmm += f'\'{action_name}\': {class_name},'
        cmm = f'{{{cmm}}}'

        _code = [
            '''class AppInputs:''',
            f'''{self.i1}"""App Inputs"""''',
            '',
        ]

        # add __init__ method
        _code.extend(
            [
                f'''{self.i1}def __init__(self, inputs: Input):''',
                f'''{self.i2}"""Initialize instance properties."""''',
                f'''{self.i2}self.inputs = inputs''',
                '',
            ]
        )

        # add action_model_map method
        _code.extend(self.template_app_inputs_class_tc_action_model_map(cmm))

        # add get_model method
        _code.extend(
            [
                (
                    f'''{self.i1}def get_model(self, tc_action: str '''
                    '''| None = None) -> type[BaseModel]:'''
                ),
                f'''{self.i2}"""Return the model based on the current action."""''',
                (
                    f'''{self.i2}tc_action = tc_action or self.inputs.model_unresolved.tc_action'''
                    '''  # type: ignore'''
                ),
                f'''{self.i2}if tc_action is None:''',
                f'''{self.i3}raise RuntimeError('No action (tc_action) found in inputs.')''',
                '',
                f'''{self.i2}action_model = self.action_model_map(tc_action.lower())''',
                f'''{self.i2}if action_model is None:''',
                f'''{self.i3}# pylint: disable=broad-exception-raised''',
                f'''{self.i3}raise RuntimeError(''',
                f'''{self.i4}\'No model found for action: \'''',
                f'''{self.i4}f'{{self.inputs.model_unresolved.tc_action}}'  # type: ignore''',
                f'''{self.i3})''',
                '',
                f'''{self.i2}return action_model''',
                '',
            ]
        )

        # add update_inputs method
        _code.extend(
            [
                f'''{self.i1}def update_inputs(self):''',
                f'''{self.i2}"""Add custom App model to inputs.''',
                '',
                (
                    f'''{self.i2}Input will be validate when the model '''
                    '''is added an any exceptions will'''
                ),
                f'''{self.i2}cause the App to exit with a status code of 1.''',
                f'''{self.i2}"""''',
                f'''{self.i2}self.inputs.add_model(self.get_model())''',
                '',
                '',
            ]
        )
        return _code

    def template_app_inputs_class_tc_action_model_map(self, cmm: str) -> list:
        """Return the model map method"""
        return [
            f'''{self.i1}def action_model_map(self, tc_action: str) -> type[BaseModel]:''',
            f'''{self.i2}"""Return action model map."""''',
            f'''{self.i2}_action_model_map = {cmm}''',
            f'''{self.i2}tc_action_key = tc_action.lower().replace(' ', '_')''',
            f'''{self.i2}return _action_model_map.get(tc_action_key)''',
            '',
        ]

    @property
    def trigger_config_model_class_comment(self) -> str:
        """Return Trigger Config Model class."""
        return '\n'.join(
            [
                f'''{self.i1}"""Base model for Trigger (playbook) config.''',
                '',
                f'''{self.i1}Trigger Playbook inputs do not take playbookDataType.''',
                '',
                f'''{self.i1}This is the configuration input that gets sent to the service''',
                f'''{self.i1}when a Playbook is enabled (createConfig).''',
                f'''{self.i1}"""''',
                '',
                '',
            ]
        )

    @property
    def type_map(self):
        """Return input map."""
        return {
            'Any': {
                'optional': {'type': 'Any', 'field_type': None},
                'required': {'type': 'Any', 'field_type': None},
            },
            'Binary': {
                'optional': {'type': 'Binary', 'field_type': 'Binary'},
                'required': {'type': 'binary(allow_empty=False)', 'field_type': 'binary'},
            },
            'BinaryArray': {
                'optional': {'type': 'list[Binary]', 'field_type': 'Binary'},
                'required': {'type': 'list[binary(allow_empty=False)]', 'field_type': 'binary'},
            },
            'Choice': {
                'optional': {'type': 'Choice', 'field_type': 'Choice'},
                'required': {'type': 'Choice', 'field_type': 'Choice'},
            },
            'EditChoice': {
                'optional': {'type': 'EditChoice', 'field_type': 'EditChoice'},
                'required': {'type': 'EditChoice', 'field_type': 'EditChoice'},
            },
            'Encrypt': {
                'optional': {'type': 'Sensitive', 'field_type': 'Sensitive'},
                'required': {'type': 'sensitive(allow_empty=False)', 'field_type': 'sensitive'},
            },
            'KeyValue': {
                'optional': {'type': 'KeyValue', 'field_type': 'KeyValue'},
                'required': {'type': 'KeyValue', 'field_type': 'KeyValue'},
            },
            'KeyValueArray': {
                'optional': {'type': 'list[KeyValue]', 'field_type': 'KeyValue'},
                'required': {'type': 'list[KeyValue]', 'field_type': 'KeyValue'},
            },
            'KeyValueList': {
                'optional': {'type': 'list[KeyValue]', 'field_type': 'KeyValue'},
                'required': {'type': 'list[KeyValue]', 'field_type': 'KeyValue'},
            },
            'MultiChoice': {
                'optional': {'type': 'list[Choice]', 'field_type': 'Choice'},
                'required': {'type': 'list[Choice]', 'field_type': 'Choice'},
            },
            'String': {
                'optional': {'type': 'String', 'field_type': 'String'},
                'required': {'type': 'string(allow_empty=False)', 'field_type': 'string'},
            },
            'StringArray': {
                'optional': {'type': 'list[String]', 'field_type': 'String'},
                'required': {'type': 'list[string(allow_empty=False)]', 'field_type': 'string'},
            },
            'TCEntity': {
                'optional': {'type': 'TCEntity', 'field_type': 'TCEntity'},
                'required': {'type': 'TCEntity', 'field_type': 'TCEntity'},
            },
            'TCEntityArray': {
                'optional': {'type': 'list[TCEntity]', 'field_type': 'TCEntity'},
                'required': {'type': 'list[TCEntity]', 'field_type': 'TCEntity'},
            },
        }
