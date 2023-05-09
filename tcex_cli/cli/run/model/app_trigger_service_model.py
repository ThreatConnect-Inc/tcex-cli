"""TcEx Framework Module"""

# third-party
from pydantic import Extra

# first-party
from tcex_cli.cli.run.model.common_model import CommonModel
from tcex_cli.cli.run.model.playbook_common_model import PlaybookCommonModel
from tcex_cli.cli.run.model.service_model import ServiceModel
from tcex_cli.input.field_type.sensitive import Sensitive

json_encoders = {Sensitive: lambda v: v.value}  # pylint: disable=unnecessary-lambda


class AppTriggerServiceModel(CommonModel, PlaybookCommonModel, ServiceModel):
    """Model Definition"""

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        json_encoders = json_encoders
        validate_assignment = True
