from pathlib import Path


def pytest_configure() -> None:
    """Ensure the ignored, repo-configured basetemp parent exists."""

    Path("artifacts").mkdir(parents=True, exist_ok=True)
