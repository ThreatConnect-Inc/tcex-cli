"""TcEx Framework Module"""

# standard library
from pathlib import Path

# third-party
from pydantic import BaseSettings, Extra


class PathModel(BaseSettings):
    """Model Definition"""

    tc_in_path: Path = Path('log')
    tc_log_path: Path = Path('log')
    tc_out_path: Path = Path('log')
    tc_temp_path: Path = Path('log')

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        validate_assignment = True
