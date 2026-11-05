"""Read analysis configuration without importing statistical dependencies."""

import tomllib

from parentedu.paths import CONFIG


def load_config() -> dict:
    """Load project parameters; unresolved research choices remain explicit."""
    with CONFIG.open("rb") as handle:
        return tomllib.load(handle)
