"""Test Module"""

# third-party
import pytest

# first-party
from tcex_cli.cli.run.launch_abc import LaunchABC


class TestWatchFilter:
    """Test LaunchABC._watch_filter as a pure staticmethod.

    ``_watch_filter`` is called by ``watchfiles`` with a ``Change`` enum value and an absolute
    path string.  We pass ``None`` as the first argument — the signature accepts ``object`` so
    any value is valid — and exercise the three layers of exclusion:

    1. Dotfiles / dot-directories always suppressed.
    2. Paths through an excluded dir (``_WATCH_EXCLUDED_DIRS``) or a ``lib_*`` dir suppressed.
    3. Only ``.py`` / ``.json`` extensions pass.
    """

    @staticmethod
    @pytest.mark.parametrize(
        argnames='path,expected',
        argvalues=[
            pytest.param(
                # plain .py file with no excluded components
                '/app/my_app.py',
                True,
                id='pass-py-top-level',
            ),
            pytest.param(
                # .json file with no excluded components
                '/app/config.json',
                True,
                id='pass-json-top-level',
            ),
            pytest.param(
                # .py file nested under a non-excluded subdirectory
                '/app/src/handlers/webhook.py',
                True,
                id='pass-py-nested-clean-dir',
            ),
            pytest.param(
                # .md extension is not in _WATCH_EXTENSIONS
                '/app/README.md',
                False,
                id='fail-md-extension',
            ),
            pytest.param(
                # .yaml extension is not in _WATCH_EXTENSIONS
                '/app/data.yaml',
                False,
                id='fail-yaml-extension',
            ),
            pytest.param(
                # 'log' is in _WATCH_EXCLUDED_DIRS
                '/app/log/app.py',
                False,
                id='fail-log-dir',
            ),
            pytest.param(
                # 'deps' is in _WATCH_EXCLUDED_DIRS
                '/app/deps/requests/models.py',
                False,
                id='fail-deps-dir',
            ),
            pytest.param(
                # '__pycache__' is in _WATCH_EXCLUDED_DIRS
                '/app/__pycache__/my_app.cpython-311.pyc',
                False,
                id='fail-pycache-dir',
            ),
            pytest.param(
                # 'ui' is in _WATCH_EXCLUDED_DIRS
                '/app/ui/src/index.ts',
                False,
                id='fail-ui-dir',
            ),
            pytest.param(
                # 'ui_build' is in _WATCH_EXCLUDED_DIRS
                '/app/ui_build/bundle.js',
                False,
                id='fail-ui-build-dir',
            ),
            pytest.param(
                # 'node_modules' is in _WATCH_EXCLUDED_DIRS
                '/app/node_modules/lodash/index.js',
                False,
                id='fail-node-modules-dir',
            ),
            pytest.param(
                # '.git' is in _WATCH_EXCLUDED_DIRS
                '/app/.git/COMMIT_EDITMSG',
                False,
                id='fail-git-dir',
            ),
            pytest.param(
                # 'lib_latest' starts with 'lib_'
                '/app/lib_latest/tcex/app/app.py',
                False,
                id='fail-lib-latest-dir',
            ),
            pytest.param(
                # 'lib_4.0' starts with 'lib_'
                '/app/lib_4.0/tcex/app/app.py',
                False,
                id='fail-lib-versioned-dir',
            ),
            pytest.param(
                # dotfile — name starts with '.'
                '/app/.env',
                False,
                id='fail-dotfile',
            ),
            pytest.param(
                # dotfile inside an excluded 'log' dir — either guard alone is sufficient
                '/app/log/.test_app_params.json',
                False,
                id='fail-log-dir-and-dotfile',
            ),
            pytest.param(
                # 'in' is in _WATCH_EXCLUDED_DIRS
                '/app/in/input.json',
                False,
                id='fail-in-dir',
            ),
            pytest.param(
                # 'out' is in _WATCH_EXCLUDED_DIRS
                '/app/out/output.json',
                False,
                id='fail-out-dir',
            ),
        ],
    )
    def test_watch_filter(path: str, expected: bool):
        """``_watch_filter(None, path)`` returns the expected boolean for every input row."""
        result = LaunchABC._watch_filter(None, path)  # noqa: SLF001
        assert result is expected, (
            f'_watch_filter(None, {path!r}) returned {result!r}, expected {expected!r}'
        )
