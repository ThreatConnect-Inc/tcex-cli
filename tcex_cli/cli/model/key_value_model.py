"""TcEx Framework Module"""

# third-party
from pydantic.v1 import BaseModel


class KeyValueModel(BaseModel):
    """Model Definition"""

    key: str
    value: str
