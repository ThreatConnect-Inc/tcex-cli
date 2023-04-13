"""TcEx Framework Module"""

# third-party
from rich import print  # pylint: disable=redefined-builtin
from rich.console import Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.rule import Rule
from rich.table import Column, Table

# first-party
from tcex_cli.cli.model.app_metadata_model import AppMetadataModel
from tcex_cli.cli.model.validation_data_model import ValidationItemModel
from tcex_cli.cli.template.model.template_config_model import TemplateConfigModel
from tcex_cli.util.render.render import Render as RenderUtil


class Render(RenderUtil):
    """TcEx Framework Module"""

    @classmethod
    def progress_bar_deps(cls) -> Progress:
        """Return a progress bar."""
        return Progress(
            cls.progress_text_column(), cls.progress_bar_column(), expand=True, transient=True
        )

    @classmethod
    def progress_bar_download(cls) -> Progress:
        """Return a progress bar."""
        return Progress(cls.progress_text_column(), cls.progress_bar_column(), expand=True)

    @classmethod
    def progress_bar_column(cls) -> BarColumn:
        """Return a progress bar column."""
        return BarColumn(
            bar_width=None,
            complete_style=f'{cls.accent}',
            finished_style=f'{cls.accent}',
            pulse_style='dodger_blue2',
            style=f'dim {cls.accent}',
            table_column=Column(ratio=2),
        )

    @classmethod
    def progress_text_column(cls) -> TextColumn:
        """Return a progress bar column."""
        return TextColumn('{task.description}', table_column=Column(ratio=1))

    @classmethod
    def table_package_summary(cls, title: str, summary_data: AppMetadataModel):
        """Render package summary table."""
        table = Table(
            expand=True,
            border_style='dim',
            show_edge=False,
            show_header=False,
        )

        table.add_column(
            'File',
            justify='left',
            max_width=20,
            min_width=20,
            style=cls.accent2,
            no_wrap=True,
        )
        table.add_column(
            'Status',
            max_width=80,
            min_width=80,
            justify='left',
            style='bold',
        )

        for name, value in summary_data.dict().items():
            name = name.replace('_', ' ').title()
            table.add_row(name, value)

        # render panel->table
        if summary_data:
            print(Panel(table, border_style='', title=title, title_align=cls.title_align))

    @classmethod
    def table_template_list(
        cls, template_data: dict[str, list[TemplateConfigModel]], branch: str | None
    ):
        """Render template list table."""
        for template_type, templates in template_data.items():
            panels = []
            for i, template in enumerate(templates, start=1):
                table = Table(
                    expand=True,
                    show_edge=False,
                    show_header=False,
                )

                table.add_column(
                    'key',
                    justify='left',
                    max_width=20,
                    min_width=20,
                    style='dodger_blue2',
                    no_wrap=True,
                )
                table.add_column(
                    'value',
                    max_width=80,
                    min_width=80,
                    justify='left',
                    style='bold',
                )

                table.add_row('Template', f'[{cls.accent}]{template.name}[/{cls.accent}]')
                table.add_row('Contributor', template.contributor)
                table.add_row('Summary', f'[italic]{template.summary}[/italic]')

                # generate the install command
                ic = template.install_command
                if branch != 'v2':
                    ic += f' --branch {branch}'
                table.add_row('Install Command', f'[{cls.accent}]{ic}[/{cls.accent}]')

                panels.append(table)
                if i < len(templates):
                    panels.append(Rule(style='dim'))

            panel_group = Group(*panels)
            panel_title = template_type.replace('_', ' ').title()
            print(
                Panel(
                    panel_group,
                    border_style='',
                    title=f'{panel_title} Templates',
                    title_align=cls.title_align,
                )
            )

    @staticmethod
    def table_validation_summary(title: str, summary_data: list[ValidationItemModel]):
        """Render validation summary table."""
        table = Table(
            expand=True,
            border_style='dim',
            show_edge=False,
            show_header=False,
        )

        table.add_column(
            'File',
            justify='left',
            max_width=40,
            min_width=40,
            style='dodger_blue2',
            no_wrap=True,
        )
        table.add_column(
            'Status',
            max_width=60,
            min_width=60,
            justify='left',
            style='bold',
        )

        for item in summary_data:
            table.add_row(item.name, f'[{item.status_color}]{item.status_value}')

        # render panel->table
        if summary_data:
            print(Panel(table, border_style='', title=title, title_align='left'))
