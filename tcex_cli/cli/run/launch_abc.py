"""TcEx Framework Module"""
# standard library
import json
import logging
import os
import random
import string
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

# third-party
import redis
from pydantic import BaseModel

# first-party
from tcex_cli.cli.run.model.common_app_input_model import CommonAppInputModel
from tcex_cli.cli.run.model.module_request_tc_model import ModuleRequestsTcModel
from tcex_cli.logger.trace_logger import TraceLogger
from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.render.render import Render
from tcex_cli.requests_tc import RequestsTc, TcSession
from tcex_cli.util import Util

# get tcex logger
_logger: TraceLogger = logging.getLogger(__name__.split('.', maxsplit=1)[0])  # type: ignore


class LaunchABC(ABC):
    """Run API Service Apps"""

    def __init__(self, config_json: Path):
        """Initialize instance properties."""
        self.config_json = config_json

        # properties
        self.accent = 'dark_orange'
        self.log = _logger
        self.panel_title = 'blue'
        self.stored_keyboard_settings: Any
        self.util = Util()

    def create_input_config(self, inputs: BaseModel):
        """Create files necessary to start a Service App."""
        data = inputs.json(exclude_none=False, exclude_unset=False, exclude_defaults=False)
        key = ''.join(random.choice(string.ascii_lowercase) for i in range(16))  # nosec
        encrypted_data = self.util.encrypt_aes_cbc(key, data)

        # ensure that the in directory exists
        inputs.tc_in_path.mkdir(parents=True, exist_ok=True)  # type: ignore

        # write the file in/.app_params.json
        app_params_json = inputs.tc_in_path / '.test_app_params.json'  # type: ignore
        with app_params_json.open(mode='wb') as fh:
            fh.write(encrypted_data)

        # Test code to write decrypted file for debugging
        # app_params_json_decrypted = inputs.tc_in_path / '.test_app_params-decrypted.json'
        # with app_params_json_decrypted.open(mode='w') as fh:
        #     fh.write(data)

        # when the App is launched the tcex.input module reads the encrypted
        # file created above # for inputs. in order to decrypt the file, this
        # process requires the key and filename to be set as environment variables.
        os.environ['TC_APP_PARAM_KEY'] = key
        os.environ['TC_APP_PARAM_FILE'] = str(app_params_json)

    @cached_property
    @abstractmethod
    def model(self) -> CommonAppInputModel:
        """Return the App inputs."""

    def print_input_data(self):
        """Print the App data."""
        input_data = self.live_format_dict(self.model.inputs.dict()).strip()
        Render.panel.info(f'{input_data}', f'[{self.panel_title}]Input Data[/]')

    def construct_model_inputs(self) -> dict:
        """Return the App inputs."""
        app_inputs = {}
        if self.config_json.is_file():
            with self.config_json.open('r', encoding='utf-8') as fh:
                try:
                    app_inputs = json.load(fh)
                except ValueError as ex:
                    print(f'Error loading app_inputs.json: {ex}')
                    sys.exit(1)
        return app_inputs

    def launch(self):
        """Launch the App."""

        # third-party
        from run import Run  # type: ignore # pylint: disable=import-error,import-outside-toplevel

        # run the app
        exit_code = 0
        try:
            # pylint: disable=protected-access
            if 'tcex.pleb.registry' in sys.modules:
                sys.modules['tcex.registry'].registry._reset()

            # create the config file
            self.create_input_config(self.model.inputs)

            run = Run()
            run.setup()
            run.launch()
            run.teardown()
        except SystemExit as e:
            exit_code = e.code

        self.log.info(f'step=run, event=app-exit, exit-code={exit_code}')
        return exit_code

    def live_format_dict(self, data: dict[str, str] | None):
        """Format dict for live output."""
        if data is None:
            return ''

        formatted_data = ''
        for key, value in sorted(data.items()):
            if isinstance(value, dict):
                value = json.dumps(value)
            if isinstance(value, str):
                value = value.replace('\n', '\\n')
            formatted_data += f'''{key}: [{self.accent}]{value}[/]\n'''
        return formatted_data

    @cached_property
    def module_requests_tc_model(self) -> ModuleRequestsTcModel:
        """Return the Module App Model."""
        return ModuleRequestsTcModel(**self.model.inputs.dict())

    def output_data(self, context: str) -> dict:
        """Return playbook/service output data."""
        output_data_ = self.redis_client.hgetall(context)
        if output_data_:
            output_data_ = {
                k: json.loads(v) for k, v in self.output_data_process(output_data_).items()
            }
            return output_data_
        return {}

    def output_data_process(self, output_data: dict) -> dict:
        """Process the output data."""
        output_data_: dict[str, dict | list | str] = {}
        for k, v in output_data.items():
            if isinstance(v, list):
                v = [i.decode('utf-8') if isinstance(i, bytes) else i for i in v]
            elif isinstance(v, bytes):
                v = v.decode('utf-8')
            elif isinstance(v, dict):
                v = self.output_data_process(v)
            output_data_[k.decode('utf-8')] = v
        return output_data_

    @cached_property
    def redis_client(self) -> redis.Redis:
        """Return the Redis client."""
        return redis.Redis(
            connection_pool=redis.ConnectionPool(
                host=self.model.inputs.tc_kvstore_host,
                port=self.model.inputs.tc_kvstore_port,
                db=self.model.inputs.tc_playbook_kvstore_id,
            )
        )

    # TODO: [bcs] fix model name :(
    @cached_property
    def session(self) -> TcSession:
        """Return requests Session object for TC admin account."""
        return RequestsTc(self.module_requests_tc_model).session  # type: ignore

    def tc_token(self, token_type: str = 'api'):  # nosec
        """Return a valid API token."""
        data = None
        token = None

        # retrieve token from API using HMAC auth
        # pylint: disable=no-member
        r = self.session.post(f'/internal/token/{token_type}', json=data, verify=True)
        if r.status_code == 200:
            token = r.json().get('data')
            self.log.info(
                f'step=setup, event=using-token, token={token}, token-elapsed={r.elapsed}'
            )
        else:
            self.log.error(f'step=setup, event=failed-to-retrieve-token error="{r.text}"')
        return token
