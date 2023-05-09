"""TcEx Framework Module"""
# third-party
from pydantic import BaseSettings, Extra


class OrganizationModel(BaseSettings):
    """Model Definition"""

    tc_job_id: int | None = None

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        validate_assignment = True
