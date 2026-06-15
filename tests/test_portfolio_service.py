from pathlib import Path

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
