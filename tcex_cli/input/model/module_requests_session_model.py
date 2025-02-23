"""TcEx Framework Module"""

# third-party
from pydantic.v1 import Extra

from .api_model import ApiModel
from .proxy_model import ProxyModel


class ModuleRequestsSessionModel(ApiModel, ProxyModel):
    """Model Definition

    This model provides all the inputs required by the "tcex.requests_tc" module.
    """

    class Config:
        """Model Config"""

        extra = Extra.ignore
