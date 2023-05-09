"""TcEx Framework Module"""

# standard library
from uuid import uuid4

# third-party
from pydantic import BaseSettings, Extra

# first-party
from tcex_cli.app.config.install_json import InstallJson


class PlaybookModel(BaseSettings):
    """Model Definition"""

    tc_kvstore_host: str = 'localhost'
    tc_kvstore_port: int = 6379
    tc_kvstore_type: str = 'Mock'
    tc_playbook_kvstore_context: str = str(uuid4())
    tc_playbook_out_variables: list[str] = InstallJson().tc_playbook_out_variables

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        validate_assignment = True
