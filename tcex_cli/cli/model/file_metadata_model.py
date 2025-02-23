"""TcEx Framework Module"""

# standard library
from pathlib import Path

# third-party
from pydantic.v1 import BaseModel, Extra, Field


class FileMetadataModel(BaseModel, extra=Extra.allow):
    """Model Definition"""

    download_url: str | None = Field(
        None, description='The download url for the file. Directories will not have a download url.'
    )
    name: str = Field(..., description='The name of the file.')
    path: str = Field(..., description='The path of the file.')
    sha: str = Field(..., description='The sha of the file.')
    url: str = Field(..., description='The url of the file.')
    type: str = Field(..., description='The type (dir or file).')

    # local metadata
    relative_path: Path = Field(
        'tmp',
        description='The relative path of the file. This is the path from the root of the repo.',
    )
    template_name: str
    template_type: str
