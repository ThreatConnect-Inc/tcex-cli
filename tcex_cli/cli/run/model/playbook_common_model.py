"""TcEx Framework Module"""

# third-party
from pydantic import BaseSettings, Extra


class PlaybookCommonModel(BaseSettings):
    """Model Definition"""

    tc_cache_kvstore_id: int = 10
    tc_kvstore_host: str = 'localhost'
    tc_kvstore_port: int = 6379
    tc_kvstore_type: str = 'Redis'
    tc_playbook_kvstore_id: int = 0

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        validate_assignment = True
