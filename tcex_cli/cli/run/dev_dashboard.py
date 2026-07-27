"""TcEx Framework Module"""

import importlib.resources


def _load_dashboard_html() -> str:
    """Load the dev dashboard HTML from the package data file.

    Returns:
        str: The full HTML content of the dev dashboard page.
    """
    ref = importlib.resources.files('tcex_cli.cli.run') / 'dev_dashboard.html'
    return ref.read_text(encoding='utf-8')


_DEV_DASHBOARD_HTML: str = _load_dashboard_html()
