import os
import tempfile
from pathlib import Path

import pytest

# Resolve portable temp directory for test database
temp_dir = Path(tempfile.gettempdir()) / "monetrack_tests"
temp_dir.mkdir(parents=True, exist_ok=True)
os.environ["MONETRACK_DB_PATH"] = str(temp_dir / "test_monetrack.db")

from monetrack.ports.db_adapter import SQLiteDatabaseAdapter  # noqa: E402
from monetrack.services.portfolio_service import PortfolioService  # noqa: E402


@pytest.fixture(autouse=True)
def clean_test_db() -> None:
    # Reset/clear test database before each test
    db_path = Path(os.environ["MONETRACK_DB_PATH"])
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass
    # Reinitialize
    adapter = SQLiteDatabaseAdapter(db_path=db_path)
    adapter.init_db()


@pytest.fixture
def temp_db_path() -> Path:
    return Path(os.environ["MONETRACK_DB_PATH"])


@pytest.fixture
def db_adapter() -> SQLiteDatabaseAdapter:
    # Return database adapter pointing to the clean database
    return SQLiteDatabaseAdapter()


@pytest.fixture
def portfolio_service(db_adapter: SQLiteDatabaseAdapter) -> PortfolioService:
    return PortfolioService(db_adapter)
