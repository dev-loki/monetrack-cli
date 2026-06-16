from pathlib import Path

import pytest

from monetrack.services.portfolio_service import PortfolioService


def test_service_initialization(portfolio_service: PortfolioService) -> None:
    # init_db is run in fixture, but calling again covers it
    portfolio_service.init_db()


def test_service_asset_operations(portfolio_service: PortfolioService) -> None:
    asset_id = portfolio_service.create_asset(
        name="Asset 1",
        asset_type="stock",
        isin="US123",
        wkn="A123",
        comment="Stock Comment",
    )
    assert asset_id == 1

    assets = portfolio_service.list_assets(include_archived=True)
    assert len(assets) == 1
    assert assets[0].name == "Asset 1"

    found = portfolio_service.find_asset("Asset 1")
    assert found is not None
    assert found.isin == "US123"

    portfolio_service.rename_asset(asset_id, "Renamed Asset")
    found_renamed = portfolio_service.find_asset("Renamed Asset")
    assert found_renamed is not None

    portfolio_service.archive_asset(asset_id, True)
    active = portfolio_service.list_assets(include_archived=False)
    assert len(active) == 0

    portfolio_service.archive_asset(asset_id, False)
    active_now = portfolio_service.list_assets(include_archived=False)
    assert len(active_now) == 1

    portfolio_service.delete_asset(asset_id)
    assert portfolio_service.find_asset("Renamed Asset") is None


def test_service_transactions_and_snapshots(portfolio_service: PortfolioService) -> None:
    a_id = portfolio_service.create_asset(name="Test", asset_type="p2p")

    tx_id = portfolio_service.add_transaction(a_id, "invest", 100.0, "2025-01-01", "invest tx")
    assert tx_id == 1

    snap_id = portfolio_service.add_snapshot(a_id, 110.0, "2025-01-05", "valuation snap")
    assert snap_id == 1

    stats = portfolio_service.get_asset_stats(a_id)
    assert stats.net_invested == 100.0
    assert stats.current_value == 110.0
    assert stats.earnings == 10.0

    glob = portfolio_service.get_global_summary()
    assert glob.net_invested == 100.0

    monthly = portfolio_service.get_monthly_stats()
    assert len(monthly) >= 1
    assert monthly[0].earnings == 10.0

    asset_monthly = portfolio_service.get_asset_monthly_stats(a_id, "2025-01")
    assert asset_monthly.earnings == 10.0

    t_stats = portfolio_service.get_type_stats()
    assert t_stats["p2p"]["current_value"] == 110.0

    history = portfolio_service.get_history()
    assert len(history) == 2


def test_service_export_and_import(portfolio_service: PortfolioService, tmp_path: Path) -> None:
    a_id = portfolio_service.create_asset(
        name="Asset Export",
        asset_type="etf",
        isin="DE000",
        wkn="WKN000",
        comment="export comment",
    )
    portfolio_service.archive_asset(a_id, True)
    portfolio_service.add_transaction(a_id, "invest", 100.0, "2025-01-01", "export tx")
    portfolio_service.add_snapshot(a_id, 120.0, "2025-01-05", "export snap")

    export_dir = tmp_path / "export_csv"
    portfolio_service.export_to_csv(export_dir)

    assert (export_dir / "assets.csv").exists()
    assert (export_dir / "transactions.csv").exists()
    assert (export_dir / "snapshots.csv").exists()

    # Clear DB
    portfolio_service.delete_asset(a_id)

    # Import back
    import_stats = portfolio_service.import_from_csv(export_dir)
    assert import_stats["assets"] == 1
    assert import_stats["transactions"] == 1
    assert import_stats["snapshots"] == 1

    imported_asset = portfolio_service.find_asset("Asset Export")
    assert imported_asset is not None
    assert imported_asset.isin == "DE000"

    # Test importing when asset already exists
    import_stats_again = portfolio_service.import_from_csv(export_dir)
    assert import_stats_again["assets"] == 0  # no new asset created
    assert import_stats_again["transactions"] == 1  # tx imported again

    # Import from an empty directory should return 0 imports without raising errors
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    empty_stats = portfolio_service.import_from_csv(empty_dir)
    assert empty_stats == {"assets": 0, "transactions": 0, "snapshots": 0}


def test_service_update_operations(portfolio_service: PortfolioService) -> None:
    a_id = portfolio_service.create_asset(name="Old Asset", asset_type="stock")
    tx_id = portfolio_service.add_transaction(a_id, "invest", 100.0, "2025-01-01")
    snap_id = portfolio_service.add_snapshot(a_id, 105.0, "2025-01-02")

    portfolio_service.update_asset(a_id, name="New Asset")
    portfolio_service.update_transaction(tx_id, amount=150.0)
    portfolio_service.update_snapshot(snap_id, value=160.0)

    found = portfolio_service.find_asset("New Asset")
    assert found is not None

    stats = portfolio_service.get_asset_stats(a_id)
    assert stats.net_invested == 150.0
    assert stats.current_value == 160.0


def test_service_valuation_scenarios_coverage(portfolio_service: PortfolioService) -> None:
    # 1. Coverage for December next month (line 181)
    a_id = portfolio_service.create_asset(name="Dec Asset", asset_type="stock")
    portfolio_service.add_transaction(a_id, "invest", 100.0, "2025-12-15")
    stats_dec = portfolio_service.get_monthly_stats(asset_id=a_id)
    assert len(stats_dec) == 1
    assert stats_dec[0].month == "2025-12"

    # 2. Coverage for:
    #   - Transaction after snapshot but before end date (lines 207-210)
    #   - Transaction after end date breaking loop (lines 212-213)
    b_id = portfolio_service.create_asset(name="Scenarios Asset", asset_type="crypto")
    portfolio_service.add_snapshot(b_id, 200.0, "2025-01-10")
    portfolio_service.add_transaction(b_id, "invest", 50.0, "2025-01-15")
    portfolio_service.add_transaction(b_id, "withdraw", 10.0, "2025-01-20")
    portfolio_service.add_transaction(b_id, "invest", 30.0, "2025-02-05")

    stats_scenarios = portfolio_service.get_monthly_stats(asset_id=b_id)
    assert len(stats_scenarios) >= 1
    jan_stats = next(s for s in stats_scenarios if s.month == "2025-01")
    assert jan_stats.valuation_end == 240.0

    # 3. Coverage for:
    #   - Withdraw when no snapshot exists (lines 220-221)
    c_id = portfolio_service.create_asset(name="Withdraw No Snap Asset", asset_type="other")
    portfolio_service.add_transaction(c_id, "withdraw", 20.0, "2025-01-10")
    stats_withdraw_no_snap = portfolio_service.get_monthly_stats(asset_id=c_id)
    jan_withdraw_stats = next(s for s in stats_withdraw_no_snap if s.month == "2025-01")
    assert jan_withdraw_stats.valuation_end == -20.0

    # 4. Coverage for:
    #   - Archived asset skipped during global monthly stats (line 241)
    d_id = portfolio_service.create_asset(name="Archived Asset", asset_type="etf")
    portfolio_service.archive_asset(d_id, True)
    portfolio_service.add_transaction(d_id, "invest", 100.0, "2025-01-05")
    portfolio_service.get_monthly_stats(include_archived=False)


def test_service_validation_errors(portfolio_service: PortfolioService) -> None:
    # 1. Invalid name on create
    with pytest.raises(ValueError, match="Asset name cannot be empty"):
        portfolio_service.create_asset("", "stock")
    with pytest.raises(ValueError, match="Asset name cannot be empty"):
        portfolio_service.create_asset("  ", "stock")

    # 2. Invalid transaction amount
    a_id = portfolio_service.create_asset("Asset Val", "stock")
    with pytest.raises(ValueError, match="Transaction amount must be greater than zero"):
        portfolio_service.add_transaction(a_id, "invest", 0.0, "2025-01-01")
    with pytest.raises(ValueError, match="Transaction amount must be greater than zero"):
        portfolio_service.add_transaction(a_id, "invest", -10.0, "2025-01-01")

    # 3. Invalid date format
    with pytest.raises(ValueError, match="Invalid date format"):
        portfolio_service.add_transaction(a_id, "invest", 10.0, "2025/01/01")

    # 4. Invalid snapshot value
    with pytest.raises(ValueError, match="Snapshot value cannot be negative"):
        portfolio_service.add_snapshot(a_id, -5.0, "2025-01-01")

    # 5. Invalid date format on snapshot
    with pytest.raises(ValueError, match="Invalid date format"):
        portfolio_service.add_snapshot(a_id, 100.0, "invalid-date")

    # 6. Invalid name on update_asset
    with pytest.raises(ValueError, match="Asset name cannot be empty"):
        portfolio_service.update_asset(a_id, name="")

    # 7. Invalid transaction amount on update
    tx_id = portfolio_service.add_transaction(a_id, "invest", 10.0, "2025-01-01")
    with pytest.raises(ValueError, match="Transaction amount must be greater than zero"):
        portfolio_service.update_transaction(tx_id, amount=0.0)

    # 8. Invalid date format on update_transaction
    with pytest.raises(ValueError, match="Invalid date format"):
        portfolio_service.update_transaction(tx_id, timestamp="invalid-date")

    # 9. Invalid snapshot value on update
    snap_id = portfolio_service.add_snapshot(a_id, 10.0, "2025-01-01")
    with pytest.raises(ValueError, match="Snapshot value cannot be negative"):
        portfolio_service.update_snapshot(snap_id, value=-1.0)

    # 10. Invalid date format on update_snapshot
    with pytest.raises(ValueError, match="Invalid date format"):
        portfolio_service.update_snapshot(snap_id, timestamp="invalid-date")
