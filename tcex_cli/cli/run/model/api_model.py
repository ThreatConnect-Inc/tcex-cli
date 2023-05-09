"""TcEx Framework Module"""
# pylint: disable=no-self-argument

# third-party
from pydantic import BaseSettings, Extra, validator

# first-party
from tcex_cli.app.config.install_json import InstallJson
from tcex_cli.input.field_type.sensitive import Sensitive


class ApiModel(BaseSettings):
    """Model Definition"""

    # api model
    api_default_org: str | None = None
    tc_api_access_id: str | None = None
    tc_api_path: str
    tc_api_secret_key: Sensitive | None = None
    tc_log_curl: bool = True
    tc_token: Sensitive | None
    tc_token_expires: int = 9999999999
    tc_verify: bool = False

    @validator('tc_token', always=True, pre=True)
    def one_set_of_credentials(cls, v, values):
        """Validate that one set of credentials is provided for the TC API."""
        _ij = InstallJson()

        # external Apps: require credentials and would not have an install.json file
        # organization (job) Apps: require credentials
        # playbook Apps: require credentials
        # service Apps: get token on createConfig message or during request
        if _ij.fqfn.is_file() is False or (
            _ij.model.is_playbook_app or _ij.model.is_organization_app
        ):
            if v is None and not all(
                [values.get('tc_api_access_id'), values.get('tc_api_secret_key')]
            ):
                raise ValueError(
                    'At least one set of ThreatConnect credentials must be provided '
                    '(tc_api_access_id/tc_api_secret key OR tc_token/tc_token_expires).'
                )
        return v

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        validate_assignment = True
