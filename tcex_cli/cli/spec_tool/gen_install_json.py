"""TcEx Framework Module"""

# standard library
from importlib.metadata import version

# first-party
from tcex_cli.app.config import AppSpecYml
from tcex_cli.app.config.model import InstallJsonModel
from tcex_cli.cli.cli_abc import CliABC


class GenInstallJson(CliABC):
    """Generate App Config File"""

    def __init__(self, asy: AppSpecYml):
        """Initialize instance properties."""
        super().__init__()
        self.asy = asy

        # properties
        self.filename = 'install.json'

    def _add_standard_fields(self, install_json_data: dict):
        """Add field that apply to ALL App types."""
        try:
            tcex_version = version('tcex')
        except Exception:
            tcex_version = None

        install_json_data.update(
            {
                'allowOnDemand': self.asy.model.allow_on_demand,
                'apiUserTokenParam': self.asy.model.api_user_token_param,
                'appId': self.asy.model.app_id,
                'category': self.asy.model.category,
                'deprecatesApps': self.asy.model.deprecates_apps,
                'displayName': self.asy.model.display_name,
                'features': self.asy.model.features,
                'labels': self.asy.model.labels,
                'languageVersion': self.asy.model.language_version,
                'listDelimiter': self.asy.model.list_delimiter,
                'minServerVersion': str(self.asy.model.min_server_version),
                'params': [p.dict(by_alias=True) for p in self.asy.model.params],
                'programLanguage': self.asy.model.program_language,
                'programMain': self.asy.model.program_main,
                'programVersion': str(self.asy.model.program_version),
                'runtimeLevel': self.asy.model.runtime_level,
                'sdkVersion': tcex_version or self.asy.model.sdk_version,
            }
        )

    def _add_note(self, install_json_data: dict):
        """Add top level note to install.json."""
        _note = f'{self.asy.model.note}{self._note_per_action}\n'

        # some Apps have a serviceDetails section which needs to be appended to the App notes
        if self.asy.model.service_details is not None:
            _note += self.asy.model.service_details

        install_json_data['note'] = _note

    def _add_type_api_service_fields(self, install_json_data: dict):
        """Add field that apply to ALL App types."""
        if self.asy.model.is_api_service_app:
            install_json_data['displayPath'] = self.asy.model.display_path
            install_json_data['service'] = self.asy.model.service

    def _add_type_organization_fields(self, install_json_data: dict):
        """Add field that apply to ALL App types."""
        if self.asy.model.is_feed_app:
            if self.asy.model.organization is None:
                return

            # the nested job object is not part of the install.json,
            # it instead gets written to the *.job.json file.
            if self.asy.model.organization.feeds:
                _feeds = []
                for feed in self.asy.model.organization.feeds:
                    feed_dict = feed.dict(by_alias=True)
                    if feed_dict.get('job') is not None:
                        del feed_dict['job']
                    _feeds.append(feed_dict)
                install_json_data['feeds'] = _feeds

            # publish_out_files
            _publish_out_files = self.asy.model.organization.publish_out_files
            if _publish_out_files:
                install_json_data['publishOutFiles'] = _publish_out_files

            # repeating_minutes
            _repeating_minutes = self.asy.model.organization.repeating_minutes
            if _repeating_minutes:
                install_json_data['repeatingMinutes'] = _repeating_minutes

    def _add_type_playbook_fields(self, install_json_data: dict):
        """Add field that apply to ALL App types."""
        if self.asy.model.is_playbook_app or self.asy.model.is_trigger_app:
            install_json_data['allowRunAsUser'] = self.asy.model.allow_run_as_user
            install_json_data['playbook'] = {
                'outputPrefix': self.asy.model.output_prefix,
                'outputVariables': [
                    ov.dict(by_alias=True) for ov in self.asy.model.output_variables
                ],
                'type': self.asy.model.category,
            }
            if (
                self.asy.model.playbook
                and self.asy.model.playbook.retry
                and self.asy.model.playbook.retry.allowed is True
            ):
                install_json_data['playbook']['retry'] = self.asy.model.playbook.retry.dict(
                    by_alias=True
                )

    @property
    def _note_per_action(self):
        """Return note per action string."""
        # note per action is only supported on playbook Apps
        note_per_action = ''
        if self.asy.model.note_per_action:
            note_per_action = '\n\n'.join(self.asy.model.note_per_action_formatted)
        return note_per_action

    def generate(self):
        """Generate the install.json file data."""
        # all keys added to dict must be in camelCase
        install_json_data = {}

        # add standard fields
        self._add_standard_fields(install_json_data)

        # add note
        self._add_note(install_json_data)

        # add app type api service fields
        self._add_type_api_service_fields(install_json_data)

        # add app type organization fields
        self._add_type_organization_fields(install_json_data)

        # add app type organization fields
        self._add_type_playbook_fields(install_json_data)

        # update sequence numbers
        for sequence, param in enumerate(install_json_data.get('params', {}), start=1):
            param['sequence'] = sequence

        return InstallJsonModel(**install_json_data)
