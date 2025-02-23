"""TcEx Framework Module"""

# third-party
from pydantic.v1 import BaseModel


class AppMetadataModel(BaseModel):
    """Model Definition"""

    features: str
    name: str
    package_name: str
    package_size: str
    package_time: str
    template_directory: str
    version: str
