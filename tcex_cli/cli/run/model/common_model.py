"""TcEx Framework Module"""

# first-party
from tcex_cli.cli.run.model.api_model import ApiModel
from tcex_cli.cli.run.model.batch_model import BatchModel
from tcex_cli.cli.run.model.logging_model import LoggingModel
from tcex_cli.cli.run.model.path_model import PathModel
from tcex_cli.cli.run.model.proxy_model import ProxyModel


class CommonModel(ApiModel, BatchModel, LoggingModel, PathModel, ProxyModel):
    """Model Definition"""

    class Config:
        """DataModel Config"""
