"""TcEx Framework Module"""

# third-party
from pydantic.v1 import BaseModel, Field


class ValidationItemModel(BaseModel):
    """Model Definition"""

    name: str = Field(..., description='The name of the file.')
    status: bool = Field(..., description='The status of the file.')

    @property
    def status_color(self) -> str:
        """Return the color for the status."""
        return 'green' if self.status is True else 'red'

    @property
    def status_value(self) -> str:
        """Return the color for the status."""
        return 'passed' if self.status is True else 'failed'


class ValidationDataModel(BaseModel):
    """Model Definition"""

    errors: list[str] = Field([], description='List of errors.')
    fileSyntax: list[ValidationItemModel] = Field([], description='List of file syntax errors.')
    layouts: list[ValidationItemModel] = Field([], description='List of layout.json errors.')
    schema_: list[ValidationItemModel] = Field([], description='List of schema errors.')
    feeds: list[ValidationItemModel] = Field([], description='List of feeds errors.')
