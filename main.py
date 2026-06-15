import datetime
import shlex

import click
import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.formatted_text import HTML
from rich import print as rprint
from rich.console import Console
from rich.table import Table

import db

# Initialize Typer app
app = typer.Typer(
    help="MonetRack CLI: Track your investments, valuations, and earnings.",
    rich_markup_mode="rich",
)
asset_app = typer.Typer(help="Manage assets (P2P platforms, stocks, ETFs, etc.)")
app.add_typer(asset_app, name="asset")

console = Console()


def build_completer() -> NestedCompleter:
    """Build the nested autocomplete structure from current assets and commands."""
    try:
        assets = db.list_assets()
        asset_names = {}
        for a in assets:
            name = a["name"]
            asset_names[name] = None
            if " " in name:
                asset_names[f'"{name}"'] = None
            if a["isin"]:
                asset_names[a["isin"]] = None
            if a["wkn"]:
                asset_names[a["wkn"]] = None
    except Exception:
        asset_names = {}

    return NestedCompleter.from_nested_dict(
        {
            "invest": asset_names,
            "withdraw": asset_names,
            "snapshot": asset_names,
            "stats": {
                "--by": {"asset", "type", "month"},
                "-b": {"asset", "type", "month"},
                "--asset": asset_names,
                "-a": asset_names,
                "--month": None,
                "-m": None,
            },
            "asset": {
                "create": None,
                "list": None,
            },
            "help": None,
            "exit": None,
            "quit": None,
        }
    )


def interactive_shell():
    """Launch the interactive command shell with autocompletion."""
    rprint("\n[bold magenta]MonetRack Interactive Shell[/bold magenta]")
    rprint(
        "[dim]Type [bold white]help[/bold white] for command usage, "
        "or [bold white]exit[/bold white]/[bold white]quit[/bold white] to leave.[/dim]\n"
    )

    session = PromptSession(completer=build_completer())

    while True:
        try:
            prompt_html = HTML(
                "<ansibold><ansimagenta>monetrack</ansibold></ansimagenta><ansicyan>&gt;</ansicyan> "
            )
            text = session.prompt(prompt_html)
        except KeyboardInterrupt:
            # Clear line on Ctrl+C and continue
            continue
        except EOFError:
            # Exit on Ctrl+D
            break

        text = text.strip()
        if not text:
            continue

        try:
            args = shlex.split(text)
        except ValueError as e:
            rprint(f"[red]Error parsing arguments: {e!s}[/red]")
            continue

        if not args:
            continue

        if args[0] in ["exit", "quit"]:
            break

        if args[0] == "help":
            try:
                app(args=["--help"], standalone_mode=False)
            except Exception:
                pass
            continue

        try:
            app(args=args, standalone_mode=False)

            # If an asset was created, update the autocomplete database
            if len(args) >= 2 and args[0] == "asset" and args[1] == "create":
                session.completer = build_completer()
        except click.exceptions.Exit:
            pass
        except click.exceptions.Abort:
            rprint("[yellow]Aborted.[/yellow]")
        except click.ClickException as e:
            rprint(f"[red]Error: {e}[/red]")
        except Exception as e:
            rprint(f"[red]Unhandled error: {e!s}[/red]")

    rprint("[magenta]Goodbye![/magenta]")


@app.callback(invoke_without_command=True)
def initialize(ctx: typer.Context):
    """Ensure the database is initialized and handle interactive mode."""
    db.init_db()
    if ctx.invoked_subcommand is None:
        interactive_shell()


# --- Formatting Helpers ---


def format_balance(val: float) -> str:
    """Format regular balances cleanly (only red if negative)."""
    if val < -0.005:
        return f"[red]-€{-val:,.2f}[/red]"
    return f"€{val:,.2f}"


def format_earnings(val: float) -> str:
    """Format profit/loss with explicit signs and colors (green/red)."""
    if val > 0.005:
        return f"[green]+€{val:,.2f}[/green]"
    elif val < -0.005:
        return f"[red]-€{-val:,.2f}[/red]"
    else:
        return f"[dim]€{val:,.2f}[/dim]"


def format_roi(val: float) -> str:
    """Format ROI percentages with signs and colors."""
    if val > 0.005:
        return f"[green]+{val:.2f}%[/green]"
    elif val < -0.005:
        return f"[red]{val:.2f}%[/red]"
    else:
        return "[dim]0.00%[/dim]"


# --- Input Validation & Helpers ---


def resolve_asset_or_exit(query: str):
    """Find asset by identifier or exit with error."""
    asset = db.find_asset(query)
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
        rprint(
            f"[red]Error: Invalid date format '{date_str}'. Must be YYYY-MM-DD.[/red]"
        )
        raise typer.Exit(code=1) from err


# --- Asset Commands ---


@asset_app.command(name="create")
def asset_create(
    name: str = typer.Argument(
        ...,
        help="Unique name of the asset (e.g. 'Bondora Go & Grow', 'Trade Republic MSCI World')",
    ),
    type: str = typer.Option(
        "other", "--type", "-t", help="Asset type: p2p, stock, etf, crypto, other"
    ),
    isin: str | None = typer.Option(
        None,
        "--isin",
        "-i",
        help="International Securities Identification Number (for stocks/ETFs)",
    ),
    wkn: str | None = typer.Option(
        None, "--wkn", "-w", help="Wertpapierkennnummer / WSN"
    ),
    comment: str | None = typer.Option(
        None, "--comment", "-c", help="Optional description or comments"
    ),
):
    """Create a new investment asset to track."""
    valid_types = ["p2p", "stock", "etf", "crypto", "other"]
    if type.lower() not in valid_types:
        rprint(
            f"[red]Error: Invalid type '{type}'. Must be one of: {', '.join(valid_types)}[/red]"
        )
        raise typer.Exit(code=1) from None

    try:
        asset_id = db.create_asset(name, type, isin, wkn, comment)
        rprint(
            f"[green]Success: Created asset '[bold]{name}[/bold]' (ID: {asset_id})[/green]"
        )
    except Exception as e:
        rprint(f"[red]Error: Could not create asset. {e!s}[/red]")
        raise typer.Exit(code=1) from e


@asset_app.command(name="list")
def asset_list():
    """List all registered investment assets."""
    assets = db.list_assets()
    if not assets:
        rprint(
            "[yellow]No assets found. Add one with 'monetrack asset create <name>'[/yellow]"
        )
        return

    table = Table(title="Tracked Assets", title_style="bold magenta")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name", style="bold white")
    table.add_column("Type", style="yellow")
    table.add_column("ISIN", style="blue")
    table.add_column("WKN", style="blue")
    table.add_column("Comment", style="dim")

    for a in assets:
        table.add_row(
            str(a["id"]),
            a["name"],
            a["type"].upper(),
            a["isin"] or "-",
            a["wkn"] or "-",
            a["comment"] or "",
        )

    console.print(table)


# --- Transaction & Snapshot Commands ---


@app.command(name="invest")
def invest(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN"),
    amount: float = typer.Argument(..., min=0.01, help="Amount to invest in EUR"),
    date: str | None = typer.Option(
        None, "--date", "-d", help="Date of investment (YYYY-MM-DD). Defaults to today."
    ),
    comment: str | None = typer.Option(
        None, "--comment", "-c", help="Optional comment"
    ),
):
    """Record an investment or deposit of funds into an asset."""
    asset = resolve_asset_or_exit(asset_query)
    tx_date = validate_date_or_exit(date)

    try:
        db.add_transaction(asset["id"], "invest", amount, tx_date, comment)
        rprint(
            f"[green]Success: Recorded [bold]€{amount:,.2f}[/bold] investment in '{asset['name']}' on {tx_date}[/green]"
        )
    except Exception as e:
        rprint(f"[red]Error: Could not record transaction. {e!s}[/red]")
        raise typer.Exit(code=1) from e


@app.command(name="withdraw")
def withdraw(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN"),
    amount: float = typer.Argument(..., min=0.01, help="Amount to withdraw in EUR"),
    date: str | None = typer.Option(
        None, "--date", "-d", help="Date of withdrawal (YYYY-MM-DD). Defaults to today."
    ),
    comment: str | None = typer.Option(
        None, "--comment", "-c", help="Optional comment"
    ),
):
    """Record a withdrawal or payout of funds from an asset."""
    asset = resolve_asset_or_exit(asset_query)
    tx_date = validate_date_or_exit(date)

    # Check if withdrawal exceeds net invested
    stats = db.get_asset_stats(asset["id"])
    if stats["net_invested"] < amount:
        rprint(
            f"[yellow]Warning: Withdrawing €{amount:,.2f} exceeds "
            f"net invested balance (€{stats['net_invested']:,.2f}).[/yellow]"
        )

    try:
        db.add_transaction(asset["id"], "withdraw", amount, tx_date, comment)
        rprint(
            f"[green]Success: Recorded [bold]€{amount:,.2f}[/bold] "
            f"withdrawal from '{asset['name']}' on {tx_date}[/green]"
        )
    except Exception as e:
        rprint(f"[red]Error: Could not record transaction. {e!s}[/red]")
        raise typer.Exit(code=1) from e


@app.command(name="snapshot")
def snapshot(
    asset_query: str = typer.Argument(..., help="Asset ID, Name, ISIN, or WKN"),
    value: float = typer.Argument(
        ..., min=0.0, help="Current total value of this asset in EUR"
    ),
    date: str | None = typer.Option(
        None,
        "--date",
        "-d",
        help="Date of snapshot valuation (YYYY-MM-DD). Defaults to today.",
    ),
    comment: str | None = typer.Option(
        None, "--comment", "-c", help="Optional comment"
    ),
):
    """Record a snapshot of the current total valuation of an asset."""
    asset = resolve_asset_or_exit(asset_query)
    snap_date = validate_date_or_exit(date)

    try:
        db.add_snapshot(asset["id"], value, snap_date, comment)
        rprint(
            f"[green]Success: Logged valuation of [bold]€{value:,.2f}[/bold] "
            f"for '{asset['name']}' on {snap_date}[/green]"
        )
    except Exception as e:
        rprint(f"[red]Error: Could not record snapshot. {e!s}[/red]")
        raise typer.Exit(code=1) from e


# --- Statistics & Reporting Command & Sub-Renderers ---


@app.command(name="stats")
def stats(
    by: str = typer.Option(
        "asset", "--by", "-b", help="Grouping level: 'asset', 'type', or 'month'"
    ),
    asset_query: str | None = typer.Option(
        None,
        "--asset",
        "-a",
        help="Filter statistics to a specific asset (ID, Name, ISIN, WKN)",
    ),
    month: str | None = typer.Option(
        None, "--month", "-m", help="Filter statistics to a specific month (YYYY-MM)"
    ),
):
    """View portfolio statistics, asset breakdowns, and monthly earnings."""
    valid_groupings = ["asset", "type", "month"]
    if by.lower() not in valid_groupings:
        rprint(
            f"[red]Error: Invalid grouping '{by}'. Must be one of: {', '.join(valid_groupings)}[/red]"
        )
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
            show_assets_stats_table(month_filter=month)

    elif by.lower() == "type":
        if target_asset:
            rprint(
                "[yellow]Warning: Asset filter is ignored when grouping by type.[/yellow]"
            )
        show_type_stats_table()

    elif by.lower() == "month":
        show_monthly_stats_table(target_asset=target_asset, month_filter=month)


# --- Sub-Renderers ---


def show_single_asset_stats(asset):
    """Print detailed performance metrics for a single asset."""
    stats = db.get_asset_stats(asset["id"])

    rprint(f"\n[bold magenta]Asset Performance Report: {asset['name']}[/bold magenta]")
    rprint("[dim]--------------------------------------------------[/dim]")
    rprint(f"[bold]Asset ID:[/bold] {asset['id']}")
    rprint(f"[bold]Type:[/bold]     {asset['type'].upper()}")
    if asset["isin"]:
        rprint(f"[bold]ISIN:[/bold]     {asset['isin']}")
    if asset["wkn"]:
        rprint(f"[bold]WKN:[/bold]      {asset['wkn']}")
    if asset["comment"]:
        rprint(f"[bold]Comment:[/bold]  {asset['comment']}")
    rprint("[dim]--------------------------------------------------[/dim]")

    rprint(f"[bold]Total Invested:[/bold]      €{stats['total_invested']:,.2f}")
    rprint(f"[bold]Total Withdrawn:[/bold]     €{stats['total_withdrawn']:,.2f}")
    rprint(f"[bold]Net Invested:[/bold]        €{stats['net_invested']:,.2f}")
    rprint(
        f"[bold]Current Value:[/bold]       €{stats['current_value']:,.2f} "
        f"[dim](As of {stats['last_valuation_date']})[/dim]"
    )

    earning_str = format_earnings(stats["earnings"])
    roi_str = format_roi(stats["roi"])
    rprint(f"[bold]Total Earnings:[/bold]      {earning_str}")
    rprint(f"[bold]Return (ROI):[/bold]        {roi_str}")
    rprint("[dim]--------------------------------------------------[/dim]\n")


def show_assets_stats_table(month_filter: str | None = None):
    """Show list of assets with performance statistics."""
    assets = db.list_assets()
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
            m_stats = db.get_asset_monthly_stats(a["id"], month_filter)

            # Skip if there's no starting valuation, ending valuation, and no transaction flow in the month
            if (
                m_stats["valuation_start"] == 0
                and m_stats["valuation_end"] == 0
                and m_stats["invested"] == 0
                and m_stats["withdrawn"] == 0
            ):
                continue

            tot_start += m_stats["valuation_start"]
            tot_invest += m_stats["invested"]
            tot_withdraw += m_stats["withdrawn"]
            tot_flow += m_stats["net_flow"]
            tot_end += m_stats["valuation_end"]
            tot_earnings += m_stats["earnings"]

            table.add_row(
                str(a["id"]),
                a["name"],
                a["type"].upper(),
                format_balance(m_stats["valuation_start"]),
                format_balance(m_stats["invested"]),
                format_balance(m_stats["withdrawn"]),
                format_balance(m_stats["net_flow"]),
                format_balance(m_stats["valuation_end"]),
                format_earnings(m_stats["earnings"]),
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

        glob = db.get_global_summary()

        for a in assets:
            stats = db.get_asset_stats(a["id"])
            table.add_row(
                str(a["id"]),
                a["name"],
                a["type"].upper(),
                format_balance(stats["net_invested"]),
                format_balance(stats["current_value"]),
                format_earnings(stats["earnings"]),
                format_roi(stats["roi"]),
                stats["last_valuation_date"],
            )

        table.columns[3].footer = format_balance(glob["net_invested"])
        table.columns[4].footer = format_balance(glob["current_value"])
        table.columns[5].footer = format_earnings(glob["earnings"])
        table.columns[6].footer = format_roi(glob["roi"])
        table.columns[7].footer = ""

    console.print(table)


def show_type_stats_table():
    """Show performance aggregated by asset type."""
    type_stats = db.get_type_stats()
    if not type_stats:
        rprint("[yellow]No assets tracked yet.[/yellow]")
        return

    table = Table(
        title="Performance by Asset Type", title_style="bold magenta", show_footer=True
    )
    table.add_column("Asset Type", style="bold yellow", footer="Total")
    table.add_column("Net Invested", justify="right")
    table.add_column("Current Value", justify="right")
    table.add_column("Earnings", justify="right")
    table.add_column("ROI", justify="right")

    glob = db.get_global_summary()

    for t, data in type_stats.items():
        table.add_row(
            t.upper(),
            format_balance(data["net_invested"]),
            format_balance(data["current_value"]),
            format_earnings(data["earnings"]),
            format_roi(data["roi"]),
        )

    table.columns[1].footer = format_balance(glob["net_invested"])
    table.columns[2].footer = format_balance(glob["current_value"])
    table.columns[3].footer = format_earnings(glob["earnings"])
    table.columns[4].footer = format_roi(glob["roi"])

    console.print(table)


def show_monthly_stats_table(
    target_asset: dict | None = None, month_filter: str | None = None
):
    """Show chronological monthly breakdown of earnings and flow."""
    asset_id = target_asset["id"] if target_asset else None
    name = target_asset["name"] if target_asset else "Overall Portfolio"

    monthly_stats = db.get_monthly_stats(asset_id)
    if not monthly_stats:
        rprint("[yellow]No transaction or snapshot history found.[/yellow]")
        return

    if month_filter:
        monthly_stats = [m for m in monthly_stats if m["month"] == month_filter]
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
        tot_invest += m["invested"]
        tot_withdraw += m["withdrawn"]
        tot_flow += m["net_flow"]
        tot_earnings += m["earnings"]

        table.add_row(
            m["month"],
            format_balance(m["valuation_start"]),
            format_balance(m["invested"]),
            format_balance(m["withdrawn"]),
            format_balance(m["net_flow"]),
            format_balance(m["valuation_end"]),
            format_earnings(m["earnings"]),
        )

    table.columns[1].footer = ""
    table.columns[2].footer = format_balance(tot_invest)
    table.columns[3].footer = format_balance(tot_withdraw)
    table.columns[4].footer = format_balance(tot_flow)
    table.columns[5].footer = ""
    table.columns[6].footer = format_earnings(tot_earnings)

    console.print(table)


# Entry point
if __name__ == "__main__":
    app()
