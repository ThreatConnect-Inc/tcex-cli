"""Tests for LaunchABC._spawn_app_subprocess()."""

# standard library
import subprocess
import sys
from unittest.mock import MagicMock

# third-party
import pytest

# first-party
from tcex_cli.cli.run.launch_abc import LaunchABC
from tcex_cli.pleb.cached_property import cached_property


class _ConcreteLaunch(LaunchABC):
    """Minimal concrete subclass for unit-testing LaunchABC internals."""

    @cached_property
    def model(self):
        """Return the App inputs model — not implemented; tests stub this via monkeypatch."""
        raise NotImplementedError


def _make_instance(monkeypatch: pytest.MonkeyPatch) -> _ConcreteLaunch:
    """Return a bare ``_ConcreteLaunch`` instance with all side-effect attributes stubbed.

    Uses ``object.__new__`` to bypass ``LaunchABC.__init__``, which requires Redis and a valid
    App config file.  Only the attributes touched by ``_spawn_app_subprocess`` are populated
    (``model`` and ``log``, both stubbed as ``MagicMock`` objects).

    Args:
        monkeypatch: The pytest monkeypatch fixture used to stub out ``create_input_config``.

    Returns:
        A minimally-configured ``_ConcreteLaunch`` ready to call ``_spawn_app_subprocess`` on.
    """
    instance = object.__new__(_ConcreteLaunch)

    # Stub create_input_config so it does not try to write encrypted param files.
    monkeypatch.setattr(_ConcreteLaunch, 'create_input_config', lambda *_args, **_kwargs: None)

    # ``_spawn_app_subprocess`` accesses ``self.model.inputs`` via ``create_input_config``.
    # Since create_input_config is a no-op above, model.inputs is never accessed; however
    # a MagicMock is set to satisfy any hasattr/attribute look-ups that may occur.
    mock_model = MagicMock()
    # Use object.__setattr__ because cached_property may intercept normal setattr.
    object.__setattr__(instance, 'model', mock_model)

    # ``_spawn_app_subprocess`` emits a diagnostic ``self.log.info(...)`` before spawning.
    # In production ``self.log`` is set in ``LaunchABC.__init__``; bypassed here, so stub it.
    object.__setattr__(instance, 'log', MagicMock())

    return instance


class TestSpawnAppSubprocess:
    """Test that ``_spawn_app_subprocess`` calls ``subprocess.Popen`` correctly.

    Each test monkeypatches ``subprocess.Popen`` so no real subprocess is spawned and
    inspects the arguments forwarded to it.  ``Popen`` is called with a positional argv list
    (``call_args.args[0]``) and an ``env=`` keyword argument (``call_args.kwargs['env']``).
    """

    @staticmethod
    def test_popen_called_once(monkeypatch: pytest.MonkeyPatch) -> None:
        """``subprocess.Popen`` is called exactly once when ``_spawn_app_subprocess`` is invoked.

        Verifies that a single child process is spawned per call and that the diagnostic
        ``self.log.info(...)`` probe fires exactly once alongside it.
        """
        mock_popen = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(subprocess, 'Popen', mock_popen)

        instance = _make_instance(monkeypatch)
        instance._spawn_app_subprocess()  # noqa: SLF001

        mock_popen.assert_called_once()
        instance.log.info.assert_called_once()

    @staticmethod
    def test_argv_structure(monkeypatch: pytest.MonkeyPatch) -> None:
        """First positional arg (argv) must be ``[sys.executable, '-c', <runner>]``.

        Ensures the spawned child uses the venv Python (``sys.executable``), the ``-c`` flag,
        and a runner string that bootstraps the App entry-point via ``from run import Run``.
        """
        mock_popen = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(subprocess, 'Popen', mock_popen)

        instance = _make_instance(monkeypatch)
        instance._spawn_app_subprocess()  # noqa: SLF001

        argv = mock_popen.call_args.args[0]

        assert argv[0] == sys.executable, f'Expected argv[0]={sys.executable!r}, got {argv[0]!r}'
        assert argv[1] == '-c', f'Expected argv[1]=-c, got {argv[1]!r}'
        runner_string = argv[2]
        assert 'from run import Run' in runner_string, (
            f'Runner string does not contain "from run import Run": {runner_string!r}'
        )

    @staticmethod
    def test_env_contains_tcex_pythonpath(monkeypatch: pytest.MonkeyPatch) -> None:
        """The ``env=`` kwarg must be a dict containing a non-empty ``_TCEX_PYTHONPATH``.

        ``_TCEX_PYTHONPATH`` is a private variable read by the runner string to extend
        ``sys.path`` in the child process.  It must be present and non-empty so the child
        can locate the App's ``run.py`` and its dependencies.
        """
        mock_popen = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(subprocess, 'Popen', mock_popen)

        instance = _make_instance(monkeypatch)
        instance._spawn_app_subprocess()  # noqa: SLF001

        env = mock_popen.call_args.kwargs['env']

        assert isinstance(env, dict), f'Expected env to be a dict, got {type(env)!r}'
        assert '_TCEX_PYTHONPATH' in env, (
            '_TCEX_PYTHONPATH key must be present in the env dict passed to subprocess.Popen'
        )
        python_path_value = env['_TCEX_PYTHONPATH']
        assert python_path_value, (
            f'_TCEX_PYTHONPATH must be a non-empty string, got {python_path_value!r}'
        )

    @staticmethod
    def test_returns_popen_handle(monkeypatch: pytest.MonkeyPatch) -> None:
        """``_spawn_app_subprocess()`` must return exactly the object ``subprocess.Popen`` returned.

        Confirms the method hands back the live ``Popen`` handle unchanged so callers can use
        ``.poll()``, ``.terminate()``, ``.wait()``, and ``.kill()`` on the real process.
        """
        popen_handle = MagicMock()
        mock_popen = MagicMock(return_value=popen_handle)
        monkeypatch.setattr(subprocess, 'Popen', mock_popen)

        instance = _make_instance(monkeypatch)
        result = instance._spawn_app_subprocess()  # noqa: SLF001

        assert result is popen_handle, f'Expected the subprocess.Popen return value, got {result!r}'
