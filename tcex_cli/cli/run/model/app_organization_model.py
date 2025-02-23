"""TcEx Framework Module"""

# third-party
from pydantic.v1 import Extra

# first-party
from tcex_cli.cli.run.model.common_app_input_model import CommonAppInputModel
from tcex_cli.cli.run.model.common_model import CommonModel
from tcex_cli.cli.run.model.organization_model import OrganizationModel
from tcex_cli.input.field_type.sensitive import Sensitive

json_encoders = {Sensitive: lambda v: v.value}  # pylint: disable=unnecessary-lambda


class AppOrganizationModel(CommonModel, OrganizationModel):
    """Model Definition"""

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        json_encoders = json_encoders
        validate_assignment = True


class AppOrganizationInputModel(CommonAppInputModel):
    """Model Definition"""

    inputs: AppOrganizationModel
