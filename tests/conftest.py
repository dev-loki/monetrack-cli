import os
from pathlib import Path

import pytest

# Force isolated test database path before any other imports
test_dir = Path("/tmp/monetrack_tests")
test_dir.mkdir(parents=True, exist_ok=True)
os.environ["MONETRACK_DB_PATH"] = str(test_dir / "test_monetrack.db")

import sqlite3  # noqa: E402


class CloseOnExitConnection:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value: object):
        if name == "_conn":
            super().__setattr__(name, value)
        else:
            setattr(self._conn, name, value)

    def __enter__(self) -> "CloseOnExitConnection":
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        try:
            self._conn.__exit__(exc_type, exc_val, exc_tb)  # type: ignore
        finally:
            self._conn.close()


original_connect = sqlite3.connect
sqlite3.connect = lambda *args, **kwargs: CloseOnExitConnection(original_connect(*args, **kwargs))  # type: ignore

from monetrack.ports.db_adapter import SQLiteDatabaseAdapter  # noqa: E402
from monetrack.services.portfolio_service import PortfolioService  # noqa: E402


@pytest.fixture(autouse=True)
def clean_test_db() -> None:
    import gc

    # Force collection of unreferenced SQLite connections to close their file descriptors
    gc.collect()

    # Reset/clear test database before each test
    db_path = Path(os.environ["MONETRACK_DB_PATH"])
    if db_path.exists():
        # Clean up existing connection pools/garbage
        gc.collect()
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
