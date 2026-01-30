"""Conftest for testing."""

# third-party
import pytest
from dotenv import load_dotenv

load_dotenv()

PROXY_ENV_VARS = (
    'TC_PROXY_HOST',
    'TC_PROXY_PORT',
    'TC_PROXY_USER',
    'TC_PROXY_USERNAME',
    'TC_PROXY_PASS',
    'TC_PROXY_PASSWORD',
)


@pytest.fixture()
def clear_proxy_env_vars(monkeypatch: pytest.MonkeyPatch):
    """Clear all proxy-related environment variables.

    Use this fixture in tests that should not route requests through a proxy.
    Env vars are automatically restored after the test completes.

    Args:
        monkeypatch: Pytest fixture for modifying environment variables.
    """
    for var in PROXY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
