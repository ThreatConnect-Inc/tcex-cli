"""TcEx Framework Module"""

# third-party
from pydantic.v1 import BaseModel, Extra

# first-party
from tcex_cli.cli.run.model.common_model import CommonModel


class InputsModel(CommonModel, extra=Extra.allow):
    """InputsModel"""


class StageModel(BaseModel):
    """Model Definition"""

    kvstore: dict[str, str | dict | list[str | dict]] = {}


class CommonAppInputModel(BaseModel):
    """Model Definition"""

    stage: StageModel
    trigger_inputs: list[dict] = []
    inputs: InputsModel
