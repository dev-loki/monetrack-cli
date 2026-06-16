import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from monetrack.domain.models import Asset, Snapshot, Transaction
from monetrack.ports.db_adapter import SQLiteDatabaseAdapter


def test_resolve_db_path_env() -> None:
    with patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/mock_xdg"}, clear=True):
        adapter = SQLiteDatabaseAdapter()
        assert adapter.db_path == Path("/tmp/mock_xdg/monetrack/monetrack.db")


def test_resolve_db_path_default() -> None:
    with patch.dict(os.environ, {}, clear=True):
        adapter = SQLiteDatabaseAdapter()
        expected = Path.home() / ".local" / "share" / "monetrack" / "monetrack.db"
        assert adapter.db_path == expected


def test_init_db_migration(tmp_path: Path) -> None:
    db_file = tmp_path / "migration.db"
    # Connect and create old table without is_archived
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, name TEXT UNIQUE, type TEXT)")
    conn.close()

    adapter = SQLiteDatabaseAdapter(db_path=db_file)
    adapter.init_db()

    # Check is_archived was added
    conn = adapter.get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(assets)")
    columns = [row["name"] for row in cursor.fetchall()]
    assert "is_archived" in columns
    conn.close()


def test_create_asset_failure(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    db_file = tmp_path / "fail.db"
    adapter = SQLiteDatabaseAdapter(db_path=db_file)
    adapter.init_db()

    asset = Asset(id=None, name="Test", type="other")
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = None
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    with patch.object(adapter, "get_connection", return_value=mock_conn):
        with pytest.raises(RuntimeError, match="Database insert failed"):
            adapter.create_asset(asset)


def test_create_and_find_asset(db_adapter: SQLiteDatabaseAdapter) -> None:
    asset = Asset(
        id=None,
        name="Bondora Go & Grow",
        type="p2p",
        isin="IE0001",
        wkn="A001",
        comment="Comment",
    )
    asset_id = db_adapter.create_asset(asset)
    assert asset_id == 1

    # Exact name lookup
    found = db_adapter.find_asset("Bondora Go & Grow")
    assert found is not None
    assert found.id == 1
    assert found.isin == "IE0001"
    assert found.wkn == "A001"

    # ISIN lookup
    found_isin = db_adapter.find_asset("IE0001")
    assert found_isin is not None
    assert found_isin.name == "Bondora Go & Grow"

    # WKN lookup
    found_wkn = db_adapter.find_asset("A001")
    assert found_wkn is not None
    assert found_wkn.name == "Bondora Go & Grow"

    # ID lookup using digit string
    found_id = db_adapter.find_asset("1")
    assert found_id is not None
    assert found_id.name == "Bondora Go & Grow"

    # Fuzzy/LIKE lookup
    found_fuzzy = db_adapter.find_asset("Bondora")
    assert found_fuzzy is not None
    assert found_fuzzy.name == "Bondora Go & Grow"

    # Not found
    assert db_adapter.find_asset("Nonexistent") is None


def test_list_and_archive_assets(db_adapter: SQLiteDatabaseAdapter) -> None:
    a1 = Asset(id=None, name="A1", type="p2p")
    a2 = Asset(id=None, name="A2", type="stock")
    db_adapter.create_asset(a1)
    id2 = db_adapter.create_asset(a2)

    db_adapter.archive_asset(id2, True)

    # list active
    active = db_adapter.list_assets(include_archived=False)
    assert len(active) == 1
    assert active[0].name == "A1"

    # list all
    all_assets = db_adapter.list_assets(include_archived=True)
    assert len(all_assets) == 2


def test_rename_and_delete_asset(db_adapter: SQLiteDatabaseAdapter) -> None:
    asset = Asset(id=None, name="Old Name", type="etf")
    asset_id = db_adapter.create_asset(asset)

    db_adapter.rename_asset(asset_id, "New Name")
    found = db_adapter.find_asset("New Name")
    assert found is not None
    assert found.name == "New Name"

    db_adapter.delete_asset(asset_id)
    assert db_adapter.find_asset("New Name") is None


def test_add_transaction_failure(db_adapter: SQLiteDatabaseAdapter) -> None:
    from unittest.mock import MagicMock

    tx = Transaction(id=None, asset_id=1, timestamp="2025-01-01", type="invest", amount=100.0)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = None
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    with patch.object(db_adapter, "get_connection", return_value=mock_conn):
        with pytest.raises(RuntimeError, match="Database insert failed"):
            db_adapter.add_transaction(tx)


def test_add_snapshot_failure(db_adapter: SQLiteDatabaseAdapter) -> None:
    from unittest.mock import MagicMock

    snap = Snapshot(id=None, asset_id=1, timestamp="2025-01-01", value=100.0)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = None
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    with patch.object(db_adapter, "get_connection", return_value=mock_conn):
        with pytest.raises(RuntimeError, match="Database insert failed"):
            db_adapter.add_snapshot(snap)


def test_stats_and_reporting(db_adapter: SQLiteDatabaseAdapter) -> None:
    a_id = db_adapter.create_asset(Asset(id=None, name="Asset1", type="p2p"))
    b_id = db_adapter.create_asset(Asset(id=None, name="Asset2", type="stock"))

    # Invest/Withdraw
    db_adapter.add_transaction(Transaction(id=None, asset_id=a_id, timestamp="2025-01-15", type="invest", amount=100.0))
    db_adapter.add_transaction(
        Transaction(id=None, asset_id=a_id, timestamp="2025-01-20", type="withdraw", amount=20.0)
    )
    db_adapter.add_transaction(Transaction(id=None, asset_id=b_id, timestamp="2025-01-25", type="invest", amount=200.0))

    # Single asset stats (no snapshot)
    stats_a = db_adapter.get_asset_stats(a_id)
    assert stats_a.net_invested == 80.0
    assert stats_a.current_value == 80.0
    assert stats_a.earnings == 0.0

    # Add snapshot
    db_adapter.add_snapshot(Snapshot(id=None, asset_id=a_id, timestamp="2025-01-31", value=95.0))
    stats_a_updated = db_adapter.get_asset_stats(a_id)
    assert stats_a_updated.current_value == 95.0
    assert stats_a_updated.earnings == 15.0
    assert stats_a_updated.roi == 18.75

    # Global summary
    glob = db_adapter.get_global_summary()
    assert glob.net_invested == 280.0
    assert glob.current_value == 295.0
    assert glob.earnings == 15.0

    # Monthly stats
    monthly = db_adapter.get_monthly_stats()
    assert len(monthly) >= 1
    assert monthly[0].month == "2025-01"
    assert monthly[0].invested == 300.0
    assert monthly[0].withdrawn == 20.0
    assert monthly[0].earnings == 15.0

    # Asset monthly stats
    asset_monthly = db_adapter.get_asset_monthly_stats(a_id, "2025-01")
    assert asset_monthly.earnings == 15.0

    # Type stats
    t_stats = db_adapter.get_type_stats()
    assert t_stats["p2p"]["current_value"] == 95.0
    assert t_stats["stock"]["current_value"] == 200.0


def test_get_history(db_adapter: SQLiteDatabaseAdapter) -> None:
    a_id = db_adapter.create_asset(Asset(id=None, name="Asset1", type="p2p"))
    db_adapter.add_transaction(Transaction(id=None, asset_id=a_id, timestamp="2025-01-15", type="invest", amount=100.0))
    db_adapter.add_snapshot(Snapshot(id=None, asset_id=a_id, timestamp="2025-01-20", value=105.0))

    hist_all = db_adapter.get_history()
    assert len(hist_all) == 2

    # Filter by asset
    hist_asset = db_adapter.get_history(asset_id=a_id)
    assert len(hist_asset) == 2

    # Filter by event type
    hist_snap = db_adapter.get_history(event_type="snapshot")
    assert len(hist_snap) == 1
    assert hist_snap[0].source == "snapshot"

    hist_invest = db_adapter.get_history(event_type="invest")
    assert len(hist_invest) == 1
    assert hist_invest[0].source == "transaction"


def test_get_raw_connection(db_adapter: SQLiteDatabaseAdapter) -> None:
    conn = db_adapter.get_raw_connection()
    real_conn = getattr(conn, "_conn", conn)
    assert isinstance(real_conn, sqlite3.Connection)


def test_db_adapter_none_asset_id(db_adapter: SQLiteDatabaseAdapter) -> None:
    from unittest.mock import patch

    with patch.object(db_adapter, "list_assets", return_value=[Asset(id=None, name="Mock", type="stock")]):
        summary = db_adapter.get_global_summary()
        assert summary.net_invested == 0.0

        type_stats = db_adapter.get_type_stats()
        assert not type_stats


def test_db_adapter_monthly_stats_scenarios(db_adapter: SQLiteDatabaseAdapter) -> None:
    # Empty DB
    assert db_adapter.get_monthly_stats() == []

    # With asset and archive scenarios
    a_id = db_adapter.create_asset(Asset(id=None, name="Asset1", type="p2p"))
    db_adapter.add_transaction(Transaction(id=None, asset_id=a_id, timestamp="2025-01-15", type="invest", amount=100.0))
    db_adapter.add_snapshot(Snapshot(id=None, asset_id=a_id, timestamp="2025-01-31", value=110.0))

    # Single asset monthly stats
    monthly_asset = db_adapter.get_monthly_stats(asset_id=a_id)
    assert len(monthly_asset) >= 1
    assert monthly_asset[0].earnings == 10.0

    # Include archived monthly stats
    monthly_archived = db_adapter.get_monthly_stats(include_archived=True)
    assert len(monthly_archived) >= 1
    assert monthly_archived[0].earnings == 10.0


def test_db_adapter_update_operations(db_adapter: SQLiteDatabaseAdapter) -> None:
    # 1. Update Asset
    a_id = db_adapter.create_asset(
        Asset(id=None, name="Old Name", type="stock", isin="ISIN1", wkn="WKN1", comment="Old comment")
    )
    db_adapter.update_asset(a_id, name="New Name", type="etf", isin="ISIN2", wkn="WKN2", comment="New comment")
    found = db_adapter.find_asset("New Name")
    assert found is not None
    assert found.type == "etf"
    assert found.isin == "ISIN2"
    assert found.wkn == "WKN2"
    assert found.comment == "New comment"

    # Test clearing values
    db_adapter.update_asset(a_id, isin="", wkn="", comment="")
    found_cleared = db_adapter.find_asset("New Name")
    assert found_cleared is not None
    assert found_cleared.isin is None
    assert found_cleared.wkn is None
    assert found_cleared.comment is None

    # Test empty update does nothing
    db_adapter.update_asset(a_id)

    # 2. Update Transaction
    tx = Transaction(id=None, asset_id=a_id, timestamp="2025-01-01", type="invest", amount=100.0, comment="tx")
    tx_id = db_adapter.add_transaction(tx)
    db_adapter.update_transaction(tx_id, amount=120.0, timestamp="2025-01-02", comment="new tx", type="withdraw")

    with db_adapter.get_connection() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        assert row["amount"] == 120.0
        assert row["timestamp"] == "2025-01-02"
        assert row["comment"] == "new tx"
        assert row["type"] == "withdraw"

    # Test clearing comment
    db_adapter.update_transaction(tx_id, comment="")
    with db_adapter.get_connection() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        assert row["comment"] is None

    # Test empty update
    db_adapter.update_transaction(tx_id)

    # Test non-existent transaction
    with pytest.raises(ValueError, match="Transaction with ID 9999 not found"):
        db_adapter.update_transaction(9999, amount=50.0)

    # 3. Update Snapshot
    snap = Snapshot(id=None, asset_id=a_id, timestamp="2025-01-01", value=100.0, comment="snap")
    snap_id = db_adapter.add_snapshot(snap)
    db_adapter.update_snapshot(snap_id, value=110.0, timestamp="2025-01-02", comment="new snap")

    with db_adapter.get_connection() as conn:
        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snap_id,)).fetchone()
        assert row["value"] == 110.0
        assert row["timestamp"] == "2025-01-02"
        assert row["comment"] == "new snap"

    # Test clearing comment
    db_adapter.update_snapshot(snap_id, comment="")
    with db_adapter.get_connection() as conn:
        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snap_id,)).fetchone()
        assert row["comment"] is None

    # Test empty update
    db_adapter.update_snapshot(snap_id)

    # Test non-existent snapshot
    with pytest.raises(ValueError, match="Snapshot with ID 9999 not found"):
        db_adapter.update_snapshot(9999, value=50.0)
