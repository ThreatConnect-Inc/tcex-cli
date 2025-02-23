"""TcEx Framework Module"""

# standard library
from pathlib import PosixPath

# third-party
from pydantic.v1 import Extra

# first-party
from tcex_cli.app.config import InstallJson
from tcex_cli.cli.run.model.common_app_input_model import CommonAppInputModel
from tcex_cli.cli.run.model.common_model import CommonModel
from tcex_cli.cli.run.model.playbook_common_model import PlaybookCommonModel
from tcex_cli.cli.run.model.playbook_model import PlaybookModel
from tcex_cli.input.field_type.sensitive import Sensitive


class AppPlaybookModel(CommonModel, PlaybookCommonModel, PlaybookModel):
    """Model Definition"""

    tc_playbook_out_variables: list[str] = InstallJson().tc_playbook_out_variables

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        json_encoders = {PosixPath: lambda v: str(v), Sensitive: lambda v: v.value}
        validate_assignment = True


class AppPlaybookInputModel(CommonAppInputModel):
    """Model Definition"""

    inputs: AppPlaybookModel
