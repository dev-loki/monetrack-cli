import datetime
from typing import Any, cast

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from monetrack.application.formatters import (
    format_balance,
    format_earnings,
    format_roi,
    render_vertical_bar_chart,
)
from monetrack.application.interactive import interactive_shell
from monetrack.domain.models import Asset, HistoryEventType
from monetrack.ports.db_adapter import SQLiteDatabaseAdapter
from monetrack.services.portfolio_service import PortfolioService


class LazyServiceProxy:
    def __init__(self) -> None:
        self._service = None

    def _get_service(self) -> PortfolioService:
        if self._service is None:
            db_adapter = SQLiteDatabaseAdapter()
            self._service = PortfolioService(db_adapter)
        return self._service

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_service(), name)


service = cast(PortfolioService, LazyServiceProxy())

# Initialize Typer apps
app = typer.Typer(
    help="MonetRack CLI: Track your investments, valuations, and earnings.",
    rich_markup_mode="rich",
)
asset_app = typer.Typer(help="Manage assets (P2P platforms, stocks, ETFs, etc.)")
app.add_typer(asset_app, name="asset")

console = Console()


def resolve_asset_or_exit(query: str) -> Asset:
    """Find asset by identifier or exit with error."""
    asset = service.find_asset(query)
    if not asset:
        rprint(
            f"[red]Error: Asset '{query}' not found. Create it first using 'monetrack asset create \"{query}\"'[/red]"
        )
        raise typer.Exit(code=1) from None
    return asset


def validate_date_or_exit(date_str: str | None) -> str:
    """Validate ISO8601 date string or default to today's date."""
    if not date_str:
        return datetime.date.today().isoformat()
    try:
        datetime.date.fromisoformat(date_str)
        return date_str
    except ValueError as err:
        rprint(f"[red]Error: Invalid date format '{date_str}'. Must be YYYY-MM-DD.[/red]")
        raise typer.Exit(code=1) from err


@app.callback(invoke_without_command=True)
def initialize(ctx: typer.Context):
    """Ensure the database is initialized and handle interactive mode."""
    service.init_db()
    if ctx.invoked_subcommand is None:
        interactive_shell(service, app)


# --- Asset Commands ---


@asset_app.command(name="create")
def asset_create(
    name: str = typer.Argument(
        ...,
        help="Unique name of the asset (e.g. 'Bondora Go & Grow', 'Trade Republic MSCI World')",
    ),
    type: str = typer.Option("other", "--type", "-t", help="Asset type: p2p, stock, etf, crypto, other"),
    isin: str | None = typer.Option(
        None,
        "--isin",
        "-i",
        help="International Securities Identification Number (for stocks/ETFs)",
    ),
    wkn: str | None = typer.Option(None, "--wkn", "-w", help="Wertpapierkennnummer / WSN"),
    comment: str | None = typer.Option(None, "--comment", "-c", help="Optional description or comments"),
):
    """Create a new investment asset to track."""
    valid_types = ["p2p", "stock", "etf", "crypto", "other"]
    if type.lower() not in valid_types:
        rprint(f"[red]Error: Invalid type '{type}'. Must be one of: {', '.join(valid_types)}[/red]")
        raise typer.Exit(code=1) from None

    try:
        asset_id = service.create_asset(name, type, isin, wkn, comment)
        rprint(f"[green]Success: Created asset '[bold]{name}[/bold]' (ID: {asset_id})[/green]")
    except Exception as e:
        rprint(f"[red]Error: Could not create asset. {e!s}[/red]")
        raise typer.Exit(code=1) from e


@asset_app.command(name="list")
def asset_list(
    include_archived: bool = typer.Option(
        False, "--include-archived", "-i", help="Include archived assets in the list"
    ),
):
    """List all registered investment assets."""
    assets = service.list_assets(include_archived=include_archived)
    if not assets:
        rprint("[yellow]No assets found. Add one with 'monetrack asset create <name>'[/yellow]")
        return

    table = Table(title="Tracked Assets", title_style="bold magenta")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name", style="bold white")
    table.add_column("Type", style="yellow")
    table.add_column("ISIN", style="blue")
    table.add_column("WKN", style="blue")
    if include_archived:
        table.add_column("Archived", justify="center", style="red")
    table.add_column("Comment", style="dim")

    for a in assets:
        row_cells = [
            str(a.id),
            a.name,
            a.type.upper(),
            a.isin or "-",
            a.wkn or "-",
        ]
        if include_archived:
            row_cells.append("[red]Yes[/red]" if a.is_archived else "[dim]No[/dim]")
        row_cells.append(a.comment or "")
        table.add_row(*row_cells)

    console.print(table)


@asset_app.command(name="delete")
def asset_delete(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN to delete"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt"),
):
    """Delete an asset and all its transaction/snapshot history."""
    asset = resolve_asset_or_exit(asset_query)
    if asset.id is None:
        raise typer.Exit(code=1)

    if not confirm:
        ans = typer.confirm(f"Are you sure you want to permanently delete asset '{asset.name}' and all its history?")
        if not ans:
            rprint("[yellow]Aborted.[/yellow]")
            return

    try:
        service.delete_asset(asset.id)
        rprint(f"[green]Success: Deleted asset '{asset.name}'[/green]")
    except Exception as e:
        rprint(f"[red]Error deleting asset: {e!s}[/red]")
        raise typer.Exit(code=1) from e


@asset_app.command(name="rename")
def asset_rename(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN to rename"),
    new_name: str = typer.Argument(..., help="New unique name for the asset"),
):
    """Rename an asset."""
    asset = resolve_asset_or_exit(asset_query)
    if asset.id is None:
        raise typer.Exit(code=1)

    try:
        service.rename_asset(asset.id, new_name)
        rprint(f"[green]Success: Renamed asset '{asset.name}' to '{new_name}'[/green]")
    except Exception as e:
        rprint(f"[red]Error renaming asset: {e!s}[/red]")
        raise typer.Exit(code=1) from e


@asset_app.command(name="archive")
def asset_archive(asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN to archive")):
    """Archive an asset so it is hidden from default stats lists."""
    asset = resolve_asset_or_exit(asset_query)
    if asset.id is None:
        raise typer.Exit(code=1)

    try:
        service.archive_asset(asset.id, True)
        rprint(f"[green]Success: Archived asset '{asset.name}'[/green]")
    except Exception as e:
        rprint(f"[red]Error archiving asset: {e!s}[/red]")
        raise typer.Exit(code=1) from e


@asset_app.command(name="unarchive")
def asset_unarchive(asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN to unarchive")):
    """Unarchive an asset to show it in stats again."""
    asset = resolve_asset_or_exit(asset_query)
    if asset.id is None:
        raise typer.Exit(code=1)

    try:
        service.archive_asset(asset.id, False)
        rprint(f"[green]Success: Unarchived asset '{asset.name}'[/green]")
    except Exception as e:
        rprint(f"[red]Error unarchiving asset: {e!s}[/red]")
        raise typer.Exit(code=1) from e


@asset_app.command(name="update")
def asset_update(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN to update"),
    name: str | None = typer.Option(None, "--name", "-n", help="New name for the asset"),
    type: str | None = typer.Option(None, "--type", "-t", help="New type for the asset"),
    isin: str | None = typer.Option(None, "--isin", "-i", help="New ISIN for the asset (use empty string to clear)"),
    wkn: str | None = typer.Option(None, "--wkn", "-w", help="New WKN for the asset (use empty string to clear)"),
    comment: str | None = typer.Option(
        None, "--comment", "-c", help="New comment for the asset (use empty string to clear)"
    ),
):
    """Update an existing asset's fields."""
    asset = resolve_asset_or_exit(asset_query)
    if asset.id is None:
        raise typer.Exit(code=1)

    if type is not None:
        valid_types = ["p2p", "stock", "etf", "crypto", "other"]
        if type.lower() not in valid_types:
            rprint(f"[red]Error: Invalid type '{type}'. Must be one of: {', '.join(valid_types)}[/red]")
            raise typer.Exit(code=1)

    try:
        service.update_asset(asset.id, name, type, isin, wkn, comment)
        rprint(f"[green]Success: Updated asset '{asset.name}'[/green]")
    except Exception as e:
        rprint(f"[red]Error updating asset: {e!s}[/red]")
        raise typer.Exit(code=1) from e


# --- Transaction & Snapshot Commands ---


@app.command(name="invest")
def invest(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN"),
    amount: float = typer.Argument(..., min=0.01, help="Amount to invest in EUR"),
    date: str | None = typer.Option(None, "--date", "-d", help="Date of investment (YYYY-MM-DD). Defaults to today."),
    comment: str | None = typer.Option(None, "--comment", "-c", help="Optional comment"),
):
    """Record an investment or deposit of funds into an asset."""
    asset = resolve_asset_or_exit(asset_query)
    tx_date = validate_date_or_exit(date)
    if asset.id is None:
        raise typer.Exit(code=1)

    try:
        service.add_transaction(asset.id, "invest", amount, tx_date, comment)
        rprint(
            f"[green]Success: Recorded [bold]€{amount:,.2f}[/bold] investment in '{asset.name}' on {tx_date}[/green]"
        )
    except Exception as e:
        rprint(f"[red]Error: Could not record transaction. {e!s}[/red]")
        raise typer.Exit(code=1) from e


@app.command(name="withdraw")
def withdraw(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN"),
    amount: float = typer.Argument(..., min=0.01, help="Amount to withdraw in EUR"),
    date: str | None = typer.Option(None, "--date", "-d", help="Date of withdrawal (YYYY-MM-DD). Defaults to today."),
    comment: str | None = typer.Option(None, "--comment", "-c", help="Optional comment"),
):
    """Record a withdrawal or payout of funds from an asset."""
    asset = resolve_asset_or_exit(asset_query)
    tx_date = validate_date_or_exit(date)
    if asset.id is None:
        raise typer.Exit(code=1)

    # Check if withdrawal exceeds net invested
    stats_data = service.get_asset_stats(asset.id)
    if stats_data.net_invested < amount:
        rprint(
            f"[yellow]Warning: Withdrawing €{amount:,.2f} exceeds "
            f"net invested balance (€{stats_data.net_invested:,.2f}).[/yellow]"
        )

    try:
        service.add_transaction(asset.id, "withdraw", amount, tx_date, comment)
        rprint(
            f"[green]Success: Recorded [bold]€{amount:,.2f}[/bold] withdrawal from '{asset.name}' on {tx_date}[/green]"
        )
    except Exception as e:
        rprint(f"[red]Error: Could not record transaction. {e!s}[/red]")
        raise typer.Exit(code=1) from e


@app.command(name="snapshot")
def snapshot(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN"),
    value: float = typer.Argument(..., min=0.0, help="Current total value of this asset in EUR"),
    date: str | None = typer.Option(
        None,
        "--date",
        "-d",
        help="Date of snapshot valuation (YYYY-MM-DD). Defaults to today.",
    ),
    comment: str | None = typer.Option(None, "--comment", "-c", help="Optional comment"),
):
    """Record a snapshot of the current total valuation of an asset."""
    asset = resolve_asset_or_exit(asset_query)
    snap_date = validate_date_or_exit(date)
    if asset.id is None:
        raise typer.Exit(code=1)

    try:
        service.add_snapshot(asset.id, value, snap_date, comment)
        rprint(
            f"[green]Success: Logged valuation of [bold]€{value:,.2f}[/bold] for '{asset.name}' on {snap_date}[/green]"
        )
    except Exception as e:
        rprint(f"[red]Error: Could not record snapshot. {e!s}[/red]")
        raise typer.Exit(code=1) from e


@app.command(name="update-transaction")
def update_transaction(
    tx_id: int = typer.Argument(..., help="ID of the transaction to update"),
    amount: float | None = typer.Option(None, "--amount", "-a", min=0.01, help="New transaction amount"),
    date: str | None = typer.Option(None, "--date", "-d", help="New date of transaction (YYYY-MM-DD)"),
    comment: str | None = typer.Option(None, "--comment", "-c", help="New comment (use empty string to clear)"),
    type: str | None = typer.Option(None, "--type", "-t", help="New type (invest or withdraw)"),
):
    """Update an existing transaction (investment or withdrawal)."""
    tx_date = None
    if date is not None:
        tx_date = validate_date_or_exit(date)

    if type is not None:
        if type.lower() not in ["invest", "withdraw"]:
            rprint(f"[red]Error: Invalid type '{type}'. Must be 'invest' or 'withdraw'[/red]")
            raise typer.Exit(code=1)

    try:
        service.update_transaction(tx_id, amount, tx_date, comment, type)
        rprint(f"[green]Success: Updated transaction ID {tx_id}[/green]")
    except Exception as e:
        rprint(f"[red]Error updating transaction: {e!s}[/red]")
        raise typer.Exit(code=1) from e


@app.command(name="update-snapshot")
def update_snapshot(
    snap_id: int = typer.Argument(..., help="ID of the snapshot to update"),
    value: float | None = typer.Option(None, "--value", "-v", min=0.0, help="New snapshot value"),
    date: str | None = typer.Option(None, "--date", "-d", help="New date of snapshot (YYYY-MM-DD)"),
    comment: str | None = typer.Option(None, "--comment", "-c", help="New comment (use empty string to clear)"),
):
    """Update an existing valuation snapshot."""
    snap_date = None
    if date is not None:
        snap_date = validate_date_or_exit(date)

    try:
        service.update_snapshot(snap_id, value, snap_date, comment)
        rprint(f"[green]Success: Updated snapshot ID {snap_id}[/green]")
    except Exception as e:
        rprint(f"[red]Error updating snapshot: {e!s}[/red]")
        raise typer.Exit(code=1) from e


# --- Statistics Commands ---


@app.command(name="stats")
def stats(
    by: str = typer.Option("asset", "--by", "-b", help="Grouping level: 'asset', 'type', or 'month'"),
    asset_query: str | None = typer.Option(
        None,
        "--asset",
        "-a",
        help="Filter statistics to a specific asset (ID, Name, ISIN, WKN)",
    ),
    month: str | None = typer.Option(None, "--month", "-m", help="Filter statistics to a specific month (YYYY-MM)"),
    include_archived: bool = typer.Option(
        False, "--include-archived", "-i", help="Include archived assets in statistics"
    ),
):
    """View portfolio statistics, asset breakdowns, and monthly earnings."""
    valid_groupings = ["asset", "type", "month"]
    if by.lower() not in valid_groupings:
        rprint(f"[red]Error: Invalid grouping '{by}'. Must be one of: {', '.join(valid_groupings)}[/red]")
        raise typer.Exit(code=1) from None

    target_asset = None
    if asset_query:
        target_asset = resolve_asset_or_exit(asset_query)

    if month:
        if len(month) != 7 or month[4] != "-":
            rprint("[red]Error: Month filter must be in YYYY-MM format.[/red]")
            raise typer.Exit(code=1) from None

    if by.lower() == "asset":
        if target_asset:
            show_single_asset_stats(target_asset)
        else:
            show_assets_stats_table(month_filter=month, include_archived=include_archived)

    elif by.lower() == "type":
        if target_asset:
            rprint("[yellow]Warning: Asset filter is ignored when grouping by type.[/yellow]")
        show_type_stats_table(include_archived=include_archived)

    elif by.lower() == "month":
        show_monthly_stats_table(target_asset=target_asset, month_filter=month, include_archived=include_archived)


@app.command(name="history")
def history(
    asset_query: str | None = typer.Option(
        None, "--asset", "-a", help="Filter history to a specific asset (ID, Name, ISIN, WKN)"
    ),
    event_type: str | None = typer.Option(
        None, "--type", "-t", help="Filter by event type: invest, withdraw, snapshot"
    ),
):
    """View a chronological history of transactions and snapshots."""
    asset_id = None
    if asset_query:
        asset = resolve_asset_or_exit(asset_query)
        asset_id = asset.id

    if event_type:
        event_type = event_type.lower()
        if event_type not in ["invest", "withdraw", "snapshot"]:
            rprint(f"[red]Error: Invalid type '{event_type}'. Must be one of: invest, withdraw, snapshot[/red]")
            raise typer.Exit(code=1) from None

    events = service.get_history(asset_id, event_type)
    if not events:
        rprint("[yellow]No history events found matching the criteria.[/yellow]")
        return

    table = Table(title="Portfolio History", title_style="bold magenta")
    table.add_column("Timestamp", justify="center", style="cyan")
    table.add_column("Asset Name", style="bold white")
    table.add_column("Event Type", justify="center")
    table.add_column("Value / Amount", justify="right")
    table.add_column("Comment", style="dim")

    for ev in events:
        match ev.event_type:
            case HistoryEventType.INVEST:
                ev_type_formatted = "[green]INVEST[/green]"
                val_formatted = f"[green]€{ev.value:,.2f}[/green]"
            case HistoryEventType.WITHDRAW:
                ev_type_formatted = "[red]WITHDRAW[/red]"
                val_formatted = f"[red]€{ev.value:,.2f}[/red]"
            case HistoryEventType.SNAPSHOT:
                ev_type_formatted = "[yellow]SNAPSHOT[/yellow]"
                val_formatted = f"€{ev.value:,.2f}"

        table.add_row(ev.timestamp, ev.asset_name, ev_type_formatted, val_formatted, ev.comment or "")

    console.print(table)


@app.command(name="export")
def export(directory: str = typer.Argument(..., help="Directory where CSV files will be saved")):
    """Export all assets, transactions, and snapshots to CSV files."""
    from pathlib import Path

    export_dir = Path(directory)
    try:
        service.export_to_csv(export_dir)
        rprint(f"[green]Success: Data exported successfully to CSVs in '{export_dir.absolute()}'[/green]")
    except Exception as e:
        rprint(f"[red]Error during export: {e!s}[/red]")
        raise typer.Exit(code=1) from e


@app.command(name="import")
def import_cmd(directory: str = typer.Argument(..., help="Directory containing CSV files to import")):
    """Import assets, transactions, and snapshots from CSV files."""
    from pathlib import Path

    import_dir = Path(directory)

    if not import_dir.exists() or not import_dir.is_dir():
        rprint(f"[red]Error: Import directory '{import_dir}' does not exist or is not a directory.[/red]")
        raise typer.Exit(code=1) from None

    try:
        stats_data = service.import_from_csv(import_dir)
        rprint("[green]Success: Import completed successfully.[/green]")
        rprint(f" - Imported assets: [bold]{stats_data['assets']}[/bold]")
        rprint(f" - Imported transactions: [bold]{stats_data['transactions']}[/bold]")
        rprint(f" - Imported snapshots: [bold]{stats_data['snapshots']}[/bold]")
    except Exception as e:
        rprint(f"[red]Error during import: {e!s}[/red]")
        raise typer.Exit(code=1) from e


# --- Sub-Renderers ---


def show_single_asset_stats(asset: Asset):
    """Print detailed performance metrics for a single asset."""
    if asset.id is None:
        return
    stats_data = service.get_asset_stats(asset.id)

    rprint(f"\n[bold magenta]Asset Performance Report: {asset.name}[/bold magenta]")
    rprint("[dim]--------------------------------------------------[/dim]")
    rprint(f"[bold]Asset ID:[/bold] {asset.id}")
    rprint(f"[bold]Type:[/bold]     {asset.type.upper()}")
    if asset.isin:
        rprint(f"[bold]ISIN:[/bold]     {asset.isin}")
    if asset.wkn:
        rprint(f"[bold]WKN:[/bold]      {asset.wkn}")
    if asset.comment:
        rprint(f"[bold]Comment:[/bold]  {asset.comment}")
    rprint("[dim]--------------------------------------------------[/dim]")

    rprint(f"[bold]Total Invested:[/bold]      €{stats_data.total_invested:,.2f}")
    rprint(f"[bold]Total Withdrawn:[/bold]     €{stats_data.total_withdrawn:,.2f}")
    rprint(f"[bold]Net Invested:[/bold]        €{stats_data.net_invested:,.2f}")
    rprint(
        f"[bold]Current Value:[/bold]       €{stats_data.current_value:,.2f} "
        f"[dim](As of {stats_data.last_valuation_date})[/dim]"
    )

    earning_str = format_earnings(stats_data.earnings)
    roi_str = format_roi(stats_data.roi)
    rprint(f"[bold]Total Earnings:[/bold]      {earning_str}")
    rprint(f"[bold]Return (ROI):[/bold]        {roi_str}")
    rprint("[dim]--------------------------------------------------[/dim]\n")


def show_assets_stats_table(month_filter: str | None = None, include_archived: bool = False):
    """Show list of assets with performance statistics."""
    assets = service.list_assets(include_archived=include_archived)
    if not assets:
        rprint("[yellow]No assets tracked yet.[/yellow]")
        return

    if month_filter:
        title = f"Asset Performance for Month: {month_filter}"
        table = Table(title=title, title_style="bold magenta", show_footer=True)
        table.add_column("ID", justify="right", style="cyan", footer="Total")
        table.add_column("Name", style="bold white", footer=f"{len(assets)} Assets")
        table.add_column("Type", style="yellow")
        table.add_column("Start Value", justify="right")
        table.add_column("Invested", justify="right")
        table.add_column("Withdrawn", justify="right")
        table.add_column("Net Flow", justify="right")
        table.add_column("End Value", justify="right")
        table.add_column("Earnings", justify="right")

        tot_start = 0.0
        tot_invest = 0.0
        tot_withdraw = 0.0
        tot_flow = 0.0
        tot_end = 0.0
        tot_earnings = 0.0

        for a in assets:
            if a.id is None:
                continue
            m_stats = service.get_asset_monthly_stats(a.id, month_filter)

            # Skip if starting/ending valuation and flows are all 0
            if (
                m_stats.valuation_start == 0
                and m_stats.valuation_end == 0
                and m_stats.invested == 0
                and m_stats.withdrawn == 0
            ):
                continue

            tot_start += m_stats.valuation_start
            tot_invest += m_stats.invested
            tot_withdraw += m_stats.withdrawn
            tot_flow += m_stats.net_flow
            tot_end += m_stats.valuation_end
            tot_earnings += m_stats.earnings

            table.add_row(
                str(a.id),
                a.name,
                a.type.upper(),
                format_balance(m_stats.valuation_start),
                format_balance(m_stats.invested),
                format_balance(m_stats.withdrawn),
                format_balance(m_stats.net_flow),
                format_balance(m_stats.valuation_end),
                format_earnings(m_stats.earnings),
            )

        table.columns[3].footer = format_balance(tot_start)
        table.columns[4].footer = format_balance(tot_invest)
        table.columns[5].footer = format_balance(tot_withdraw)
        table.columns[6].footer = format_balance(tot_flow)
        table.columns[7].footer = format_balance(tot_end)
        table.columns[8].footer = format_earnings(tot_earnings)

    else:
        title = "Asset Performance Summary"
        table = Table(title=title, title_style="bold magenta", show_footer=True)
        table.add_column("ID", justify="right", style="cyan", footer="Total")
        table.add_column("Name", style="bold white", footer=f"{len(assets)} Assets")
        table.add_column("Type", style="yellow")
        table.add_column("Net Invested", justify="right")
        table.add_column("Current Value", justify="right")
        table.add_column("Earnings", justify="right")
        table.add_column("ROI", justify="right")
        table.add_column("Last Valuation", justify="center")

        glob = service.get_global_summary(include_archived=include_archived)

        for a in assets:
            if a.id is None:
                continue
            stats_data = service.get_asset_stats(a.id)
            table.add_row(
                str(a.id),
                a.name,
                a.type.upper(),
                format_balance(stats_data.net_invested),
                format_balance(stats_data.current_value),
                format_earnings(stats_data.earnings),
                format_roi(stats_data.roi),
                stats_data.last_valuation_date,
            )

        table.columns[3].footer = format_balance(glob.net_invested)
        table.columns[4].footer = format_balance(glob.current_value)
        table.columns[5].footer = format_earnings(glob.earnings)
        table.columns[6].footer = format_roi(glob.roi)
        table.columns[7].footer = ""

    console.print(table)


def show_type_stats_table(include_archived: bool = False):
    """Show performance aggregated by asset type."""
    type_stats = service.get_type_stats(include_archived=include_archived)
    if not type_stats:
        rprint("[yellow]No assets tracked yet.[/yellow]")
        return

    table = Table(title="Performance by Asset Type", title_style="bold magenta", show_footer=True)
    table.add_column("Asset Type", style="bold yellow", footer="Total")
    table.add_column("Net Invested", justify="right")
    table.add_column("Current Value", justify="right")
    table.add_column("Earnings", justify="right")
    table.add_column("ROI", justify="right")

    glob = service.get_global_summary(include_archived=include_archived)

    for t, data in type_stats.items():
        table.add_row(
            t.upper(),
            format_balance(data["net_invested"]),
            format_balance(data["current_value"]),
            format_earnings(data["earnings"]),
            format_roi(data["roi"]),
        )

    table.columns[1].footer = format_balance(glob.net_invested)
    table.columns[2].footer = format_balance(glob.current_value)
    table.columns[3].footer = format_earnings(glob.earnings)
    table.columns[4].footer = format_roi(glob.roi)

    console.print(table)

    # Asset Allocation Bar Chart using block characters
    total_val = sum(data["current_value"] for data in type_stats.values())
    if total_val > 0.01:
        rprint("\n[bold magenta]Asset Type Allocation Chart[/bold magenta]")
        sorted_types = sorted(type_stats.items(), key=lambda item: item[1]["current_value"], reverse=True)
        for t, data in sorted_types:
            share = data["current_value"] / total_val
            pct = share * 100
            filled_len = round(share * 30)
            bar = "[magenta]█[/magenta]" * filled_len + "[dim]░[/dim]" * (30 - filled_len)
            rprint(f"  {t.upper():<8} : {bar} {pct:.1f}% ({format_balance(data['current_value'])})")


def show_monthly_stats_table(
    target_asset: Asset | None = None, month_filter: str | None = None, include_archived: bool = False
):
    """Show chronological monthly breakdown of earnings and flow."""
    asset_id = target_asset.id if target_asset else None
    name = target_asset.name if target_asset else "Overall Portfolio"

    monthly_stats = service.get_monthly_stats(asset_id, include_archived=include_archived)
    if not monthly_stats:
        rprint("[yellow]No transaction or snapshot history found.[/yellow]")
        return

    if month_filter:
        monthly_stats = [m for m in monthly_stats if m.month == month_filter]
        if not monthly_stats:
            rprint(f"[yellow]No data found for month: {month_filter}[/yellow]")
            return

    title = f"Monthly Earnings Report - {name}"
    table = Table(title=title, title_style="bold magenta", show_footer=True)
    table.add_column("Month", justify="center", style="cyan", footer="Total")
    table.add_column("Start Value", justify="right")
    table.add_column("Invested", justify="right")
    table.add_column("Withdrawn", justify="right")
    table.add_column("Net Flow", justify="right")
    table.add_column("End Value", justify="right")
    table.add_column("Earnings", justify="right")

    tot_invest = 0.0
    tot_withdraw = 0.0
    tot_flow = 0.0
    tot_earnings = 0.0

    for m in monthly_stats:
        tot_invest += m.invested
        tot_withdraw += m.withdrawn
        tot_flow += m.net_flow
        tot_earnings += m.earnings

        table.add_row(
            m.month,
            format_balance(m.valuation_start),
            format_balance(m.invested),
            format_balance(m.withdrawn),
            format_balance(m.net_flow),
            format_balance(m.valuation_end),
            format_earnings(m.earnings),
        )

    table.columns[1].footer = ""
    table.columns[2].footer = format_balance(tot_invest)
    table.columns[3].footer = format_balance(tot_withdraw)
    table.columns[4].footer = format_balance(tot_flow)
    table.columns[5].footer = ""
    table.columns[6].footer = format_earnings(tot_earnings)

    console.print(table)

    # Draw vertical bar chart of monthly earnings
    rprint("\n[bold magenta]Monthly Earnings History[/bold magenta]")
    chart_str = render_vertical_bar_chart(monthly_stats)
    if chart_str:
        rprint(chart_str)
        rprint("")


# Entry point helper for Typer setup
def main():
    app()


if __name__ == "__main__":
    main()
