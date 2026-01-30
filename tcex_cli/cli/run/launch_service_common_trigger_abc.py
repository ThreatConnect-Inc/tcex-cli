"""TcEx Framework Module"""

# standard library
import datetime
import json
import random
from abc import ABC
from pathlib import Path

# third-party
from rich.panel import Panel
from rich.table import Table

# first-party
from tcex_cli.app.config.install_json import InstallJson
from tcex_cli.cli.run.launch_service_common_abc import LaunchServiceCommonABC


class LaunchServiceCommonTriggersABC(LaunchServiceCommonABC, ABC):
    """Launch Class for all Service type Apps."""

    def __init__(self, config_json: Path):
        """Initialize instance properties."""
        super().__init__(config_json)

        # properties
        self.stop_server = False
        self.trigger_outputs: dict = {}

    def live_data_table(self):
        """Display live data."""

        table = Table(expand=True, show_edge=False, show_lines=False)
        table.add_column('Trigger ID')
        table.add_column('Inputs')
        table.add_column('Output')

        try:
            for trigger_id, inputs in enumerate(self.model.trigger_inputs):
                inputs_modified = inputs.copy()
                # remove tc_playbook_out_variables as it is not helpful in this context
                if 'tc_playbook_out_variables' in inputs_modified:
                    del inputs_modified['tc_playbook_out_variables']

                trigger_id_ = str(trigger_id)
                output = self.trigger_outputs.get(trigger_id_)
                table.add_row(
                    trigger_id_,
                    self.live_format_dict(inputs_modified),
                    self.live_format_dict(output),
                )
        except Exception:
            self.log.exception('Error in live_data_table')

        return Panel(
            table,
            border_style='',
            title=f'[{self.panel_title}]Trigger Inputs/Outputs[/]',
            title_align='left',
        )

    def process_client_channel(self, _client, _userdata, message):
        """Handle message broker on_message shutdown command events."""
        try:
            msg = json.loads(message.payload)
        except ValueError as ex:
            ex_msg = f'Could not parse API service response JSON. ({message})'
            raise RuntimeError(ex_msg) from ex

        command = msg.get('command').lower()
        self.message_data.append(
            {
                'channel': 'client',
                'command': command,
                'msg_time': datetime.datetime.now(datetime.UTC).isoformat(),
                'trigger_id': msg.get('triggerId'),
                'type': msg.get('type'),
            }
        )

        match command:
            case 'fireevent':
                trigger_id = str(msg['triggerId'])
                session_id = msg['sessionId']
                self.trigger_outputs[trigger_id] = self.output_data(session_id)

            case 'ready':
                self.publish_create_config()

        self.event.set()

    def process_server_channel(self, _client, _userdata, message):
        """Handle message broker on_message shutdown command events."""
        try:
            msg = json.loads(message.payload)
        except ValueError as ex:
            ex_msg = f'Could not parse API service response JSON. ({message})'
            raise RuntimeError(ex_msg) from ex

        command = msg.get('command').lower()
        self.message_data.append(
            {
                'channel': 'server',
                'command': command,
                'msg_time': datetime.datetime.now(datetime.UTC).isoformat(),
                'trigger_id': msg.get('triggerId'),
                'type': msg.get('type'),
            }
        )

        match command:
            case 'shutdown':
                self.stop_server = True

        self.event.set()

    def publish_create_config(self):
        """Publish create config message."""
        for trigger_id, t_input in enumerate(self.model.trigger_inputs):
            t_input['tc_playbook_out_variables'] = ','.join(InstallJson().tc_playbook_out_variables)
            self.publish(
                json.dumps(
                    {
                        'apiToken': self.tc_token(),
                        'expireSeconds': 9999999999,
                        'appId': random.randint(1, 300),  # nosec
                        'command': 'CreateConfig',
                        'triggerId': trigger_id,
                        'config': t_input,
                    }
                ),
                self.model.inputs.tc_svc_server_topic,  # type: ignore
            )
