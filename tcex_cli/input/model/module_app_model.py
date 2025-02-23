"""TcEx Framework Module"""

# third-party
from pydantic.v1 import Extra

from .api_model import ApiModel
from .path_model import PathModel
from .playbook_common_model import PlaybookCommonModel
from .playbook_model import PlaybookModel
from .proxy_model import ProxyModel


class ModuleAppModel(ApiModel, PathModel, PlaybookCommonModel, PlaybookModel, ProxyModel):
    """Model Definition

    This model provides all the inputs required by the "tcex.app" module.
    """

    class Config:
        """Model Config"""

        extra = Extra.ignore
