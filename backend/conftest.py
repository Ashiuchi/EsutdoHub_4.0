import pytest
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require external services (Ollama, Gemini)",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-integration"):
        skip = pytest.mark.skip(reason="Requer --run-integration e serviços externos (Ollama/Gemini)")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
