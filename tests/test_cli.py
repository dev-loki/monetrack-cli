from pathlib import Path

from typer.testing import CliRunner

from monetrack.application.cli import app

runner = CliRunner()


def test_cli_asset_flow() -> None:
    # 1. Create asset
    res = runner.invoke(app, ["asset", "create", "Bondora Go", "--type", "p2p"])
    assert res.exit_code == 0
    assert "Success: Created asset" in res.output

    # 2. List assets
    res = runner.invoke(app, ["asset", "list"])
    assert res.exit_code == 0
    assert "Bondora Go" in res.output

    # 3. Rename asset
    res = runner.invoke(app, ["asset", "rename", "Bondora Go", "Bondora Super"])
    assert res.exit_code == 0
    assert "Success: Renamed asset" in res.output

    # 4. Archive asset
    res = runner.invoke(app, ["asset", "archive", "Bondora Super"])
    assert res.exit_code == 0
    assert "Success: Archived asset" in res.output

    # 5. List assets (without archived)
    res = runner.invoke(app, ["asset", "list"])
    assert "Bondora Super" not in res.output

    # 6. List assets (with archived)
    res = runner.invoke(app, ["asset", "list", "-i"])
    assert "Bondora Super" in res.output

    # 7. Unarchive asset
    res = runner.invoke(app, ["asset", "unarchive", "Bondora Super"])
    assert res.exit_code == 0
    assert "Success: Unarchived asset" in res.output

    # 8. Delete asset (abort)
    res = runner.invoke(app, ["asset", "delete", "Bondora Super"], input="n\n")
    assert "Aborted" in res.output

    # 9. Delete asset (confirm)
    res = runner.invoke(app, ["asset", "delete", "Bondora Super", "-y"])
    assert res.exit_code == 0
    assert "Success: Deleted asset" in res.output


def test_cli_invalid_asset_type() -> None:
    res = runner.invoke(app, ["asset", "create", "InvalidAsset", "-t", "wrongtype"])
    assert res.exit_code == 1
    assert "Error: Invalid type" in res.output


def test_cli_empty_list() -> None:
    res = runner.invoke(app, ["asset", "list"])
    assert res.exit_code == 0
    assert "No assets found" in res.output


def test_cli_transactions_and_stats() -> None:
    runner.invoke(app, ["asset", "create", "Stock1", "-t", "stock"])

    # Invest
    res = runner.invoke(app, ["invest", "Stock1", "100.00", "-d", "2025-01-01"])
    assert res.exit_code == 0
    assert "Success: Recorded €100.00 investment" in res.output

    # Withdraw warning
    res = runner.invoke(app, ["withdraw", "Stock1", "150.00", "-d", "2025-01-02"])
    assert res.exit_code == 0
    assert "Warning: Withdrawing €150.00 exceeds" in res.output

    # Snapshot
    res = runner.invoke(app, ["snapshot", "Stock1", "120.00", "-d", "2025-01-03"])
    assert res.exit_code == 0
    assert "Success: Logged valuation of €120.00" in res.output

    # Stats default (by asset)
    res = runner.invoke(app, ["stats"])
    assert res.exit_code == 0
    assert "Asset Performance Summary" in res.output
    assert "Stock1" in res.output

    # Stats by type
    res = runner.invoke(app, ["stats", "-b", "type"])
    assert res.exit_code == 0
    assert "Performance by Asset Type" in res.output
    assert "Asset Type Allocation Chart" in res.output

    # Stats by month
    res = runner.invoke(app, ["stats", "-b", "month"])
    assert res.exit_code == 0
    assert "Monthly Earnings Report" in res.output

    # History
    res = runner.invoke(app, ["history"])
    assert res.exit_code == 0
    assert "Portfolio History" in res.output


def test_cli_invalid_date_or_month() -> None:
    # Create asset first so resolve_asset_or_exit passes
    runner.invoke(app, ["asset", "create", "Stock1", "-t", "stock"])

    # Invalid date
    res = runner.invoke(app, ["invest", "Stock1", "100", "-d", "invalid-date"])
    assert res.exit_code == 1
    assert "Error: Invalid date format" in res.output

    # Invalid month filter
    res = runner.invoke(app, ["stats", "-m", "invalid-month"])
    assert res.exit_code == 1
    assert "Error: Month filter must be in YYYY-MM format" in res.output


def test_cli_import_export(tmp_path: Path) -> None:
    runner.invoke(app, ["asset", "create", "Etf1", "-t", "etf"])
    runner.invoke(app, ["invest", "Etf1", "10.0"])

    export_dir = tmp_path / "cli_export"
    res = runner.invoke(app, ["export", str(export_dir)])
    assert res.exit_code == 0
    assert "Data exported successfully" in res.output

    # Test import missing dir
    res = runner.invoke(app, ["import", "/nonexistent_path_abc"])
    assert res.exit_code == 1

    # Test import success
    res = runner.invoke(app, ["import", str(export_dir)])
    assert res.exit_code == 0
    assert "Import completed successfully" in res.output


def test_cli_invalid_grouping() -> None:
    res = runner.invoke(app, ["stats", "-b", "invalidgroup"])
    assert res.exit_code == 1
    assert "Error: Invalid grouping" in res.output


def test_cli_empty_stats_and_history() -> None:
    # 1. Empty stats
    res = runner.invoke(app, ["stats"])
    assert "No assets tracked yet" in res.output

    # 2. Empty type stats
    res = runner.invoke(app, ["stats", "-b", "type"])
    assert "No assets tracked yet" in res.output

    # 3. Empty monthly stats
    res = runner.invoke(app, ["stats", "-b", "month"])
    assert "No transaction or snapshot history found" in res.output

    # 4. Empty history
    res = runner.invoke(app, ["history"])
    assert "No history events found matching the criteria" in res.output

    # 5. Empty monthly stats with filter
    res = runner.invoke(app, ["stats", "-b", "month", "-m", "2025-01"])
    assert "No transaction or snapshot history found" in res.output


def test_cli_stats_with_month_filter() -> None:
    runner.invoke(app, ["asset", "create", "Stock1", "-t", "stock"])
    runner.invoke(app, ["asset", "create", "Stock2", "-t", "stock"])
    runner.invoke(app, ["invest", "Stock1", "100.00", "-d", "2025-01-01"])

    res = runner.invoke(app, ["stats", "-m", "2025-01"])
    assert res.exit_code == 0
    assert "Asset Performance for Month: 2025-01" in res.output

    res = runner.invoke(app, ["stats", "-b", "month", "-m", "2025-01"])
    assert res.exit_code == 0
    assert "Monthly Earnings Report" in res.output

    res = runner.invoke(app, ["stats", "-b", "month", "-m", "2024-12"])
    assert res.exit_code == 0
    assert "No data found for month: 2024-12" in res.output


def test_cli_asset_not_found() -> None:
    res = runner.invoke(app, ["invest", "Nonexistent", "100"])
    assert res.exit_code == 1
    assert "Error: Asset 'Nonexistent' not found" in res.output

    res = runner.invoke(app, ["history", "-a", "Nonexistent"])
    assert res.exit_code == 1
    assert "Error: Asset 'Nonexistent' not found" in res.output


def test_cli_exceptions() -> None:
    from unittest.mock import patch

    # create
    with patch("monetrack.application.cli.service.create_asset", side_effect=Exception("create error")):
        res = runner.invoke(app, ["asset", "create", "FailAsset"])
        assert res.exit_code == 1
        assert "Error: Could not create asset" in res.output

    # delete
    runner.invoke(app, ["asset", "create", "DelAsset"])
    with patch("monetrack.application.cli.service.delete_asset", side_effect=Exception("delete error")):
        res = runner.invoke(app, ["asset", "delete", "DelAsset", "-y"])
        assert res.exit_code == 1
        assert "Error deleting asset" in res.output

    # rename
    runner.invoke(app, ["asset", "create", "RenAsset"])
    with patch("monetrack.application.cli.service.rename_asset", side_effect=Exception("rename error")):
        res = runner.invoke(app, ["asset", "rename", "RenAsset", "NewName"])
        assert res.exit_code == 1
        assert "Error renaming asset" in res.output

    # archive
    runner.invoke(app, ["asset", "create", "ArchAsset"])
    with patch("monetrack.application.cli.service.archive_asset", side_effect=Exception("archive error")):
        res = runner.invoke(app, ["asset", "archive", "ArchAsset"])
        assert res.exit_code == 1
        assert "Error archiving asset" in res.output

    # unarchive
    runner.invoke(app, ["asset", "create", "UnarchAsset"])
    with patch("monetrack.application.cli.service.archive_asset", side_effect=Exception("unarchive error")):
        res = runner.invoke(app, ["asset", "unarchive", "UnarchAsset"])
        assert res.exit_code == 1
        assert "Error unarchiving asset" in res.output

    # invest
    runner.invoke(app, ["asset", "create", "InvAsset"])
    with patch("monetrack.application.cli.service.add_transaction", side_effect=Exception("invest error")):
        res = runner.invoke(app, ["invest", "InvAsset", "100"])
        assert res.exit_code == 1
        assert "Error: Could not record transaction" in res.output

    # withdraw
    runner.invoke(app, ["asset", "create", "WithAsset"])
    runner.invoke(app, ["invest", "WithAsset", "500"])
    with patch("monetrack.application.cli.service.add_transaction", side_effect=Exception("withdraw error")):
        res = runner.invoke(app, ["withdraw", "WithAsset", "100"])
        assert res.exit_code == 1
        assert "Error: Could not record transaction" in res.output

    # snapshot
    runner.invoke(app, ["asset", "create", "SnapAsset"])
    with patch("monetrack.application.cli.service.add_snapshot", side_effect=Exception("snapshot error")):
        res = runner.invoke(app, ["snapshot", "SnapAsset", "100"])
        assert res.exit_code == 1
        assert "Error: Could not record snapshot" in res.output

    # export
    with patch("monetrack.application.cli.service.export_to_csv", side_effect=Exception("export error")):
        res = runner.invoke(app, ["export", "/tmp/doesntmatter"])
        assert res.exit_code == 1
        assert "Error during export" in res.output

    # import
    with patch("monetrack.application.cli.service.import_from_csv", side_effect=Exception("import error")):
        res = runner.invoke(app, ["import", "/tmp"])
        assert res.exit_code == 1
        assert "Error during import" in res.output


def test_cli_none_asset_id() -> None:
    from unittest.mock import patch

    from monetrack.domain.models import Asset

    with patch(
        "monetrack.application.cli.resolve_asset_or_exit",
        return_value=Asset(id=None, name="Mock", type="stock"),
    ):
        res = runner.invoke(app, ["asset", "delete", "Mock", "-y"])
        assert res.exit_code == 1

        res = runner.invoke(app, ["asset", "rename", "Mock", "New"])
        assert res.exit_code == 1

        res = runner.invoke(app, ["asset", "archive", "Mock"])
        assert res.exit_code == 1

        res = runner.invoke(app, ["asset", "unarchive", "Mock"])
        assert res.exit_code == 1

        res = runner.invoke(app, ["invest", "Mock", "100"])
        assert res.exit_code == 1

        res = runner.invoke(app, ["withdraw", "Mock", "100"])
        assert res.exit_code == 1

        res = runner.invoke(app, ["snapshot", "Mock", "100"])
        assert res.exit_code == 1

    with patch(
        "monetrack.application.cli.service.list_assets",
        return_value=[Asset(id=None, name="Mock", type="stock")],
    ):
        runner.invoke(app, ["stats"])
        runner.invoke(app, ["stats", "-m", "2025-01"])

        from monetrack.application.cli import show_single_asset_stats

        show_single_asset_stats(Asset(id=None, name="Mock", type="stock"))


def test_cli_interactive_initialization() -> None:
    from unittest.mock import patch

    with patch("monetrack.application.cli.interactive_shell") as mock_shell:
        res = runner.invoke(app, [])
        assert res.exit_code == 0
        mock_shell.assert_called_once()


def test_cli_main_entrypoint() -> None:
    from unittest.mock import patch

    from monetrack.application.cli import main

    with patch("monetrack.application.cli.app") as mock_app:
        main()
        mock_app.assert_called_once()


def test_cli_stats_details() -> None:
    runner.invoke(
        app,
        [
            "asset",
            "create",
            "Stock1",
            "-t",
            "stock",
            "-i",
            "US123",
            "-w",
            "A123",
            "-c",
            "Stock Comment",
        ],
    )
    runner.invoke(app, ["stats", "-b", "asset", "-a", "Stock1"])
    runner.invoke(app, ["stats", "-b", "type", "-a", "Stock1"])
    runner.invoke(app, ["history", "-a", "Stock1"])
    runner.invoke(app, ["history", "-t", "invalidtype"])


def test_cli_run_as_main() -> None:
    import runpy
    from unittest.mock import patch

    import pytest

    with patch("sys.argv", ["monetrack"]):
        with patch("prompt_toolkit.PromptSession.prompt", side_effect=EOFError()):
            with pytest.raises(SystemExit) as excinfo:
                runpy.run_module("monetrack.application.cli", run_name="__main__")
            assert excinfo.value.code == 0
