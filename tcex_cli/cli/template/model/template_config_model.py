"""TcEx Framework Module"""

# pylint: disable=no-self-argument
# third-party
from pydantic import BaseModel, validator
from semantic_version import Version


class TemplateConfigModel(BaseModel):
    """Model definition for template.yaml configuration file"""

    contributor: str
    description: str
    name: str
    summary: str
    template_files: list[str] | None = []
    template_parents: list[str] = []
    type: str
    version: Version

    @validator('version', pre=True)
    def version_validator(cls, v):
        """Return a version object for "version" fields."""
        if v is not None:
            return Version(v)
        return v

    class Config:
        """DataModel Config"""

        arbitrary_types_allowed = True
        json_encoders = {Version: lambda v: str(v)}  # pylint: disable=unnecessary-lambda
        validate_assignment = True

    @property
    def install_command(self) -> str:
        """Return the install command for the template."""
        return f'tcex init --type {self.type} --template {self.name}'
