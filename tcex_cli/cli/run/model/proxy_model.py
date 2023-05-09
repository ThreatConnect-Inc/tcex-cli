"""TcEx Framework Module"""
# pylint: disable=no-self-argument

# third-party
from pydantic import BaseSettings, Extra

# first-party
from tcex_cli.input.field_type.sensitive import Sensitive


class ProxyModel(BaseSettings):
    """Model Definition"""

    # proxy model
    tc_proxy_host: str | None = None
    tc_proxy_port: int | None = None
    tc_proxy_username: str | None = None
    tc_proxy_password: Sensitive | None = None
    tc_proxy_external: bool = False
    tc_proxy_tc: bool = False

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        validate_assignment = True
