"""TcEx Framework Module"""

# first-party
from tcex_cli.cli.run.model.api_model import ApiModel
from tcex_cli.cli.run.model.proxy_model import ProxyModel


class ModuleRequestsTcModel(ApiModel, ProxyModel):
    """Model Definition

    This model provides all the inputs required by the "tcex.request_tc" module.
    """
