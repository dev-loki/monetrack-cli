import shlex

import click
import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.formatted_text import HTML
from rich import print as rprint

from monetrack.services.portfolio_service import PortfolioService


def build_completer(service: PortfolioService) -> NestedCompleter:
    """Build the nested autocomplete structure from current assets and commands."""
    try:
        assets = service.list_assets(include_archived=True)
        asset_names = {}
        for a in assets:
            name = a.name
            asset_names[name] = None
            if " " in name:
                asset_names[f'"{name}"'] = None
            if a.isin:
                asset_names[a.isin] = None
            if a.wkn:
                asset_names[a.wkn] = None
    except Exception:
        asset_names = {}

    return NestedCompleter.from_nested_dict(
        {
            "invest": asset_names,
            "withdraw": asset_names,
            "snapshot": asset_names,
            "history": {
                "--asset": asset_names,
                "-a": asset_names,
                "--type": {"invest", "withdraw", "snapshot"},
                "-t": {"invest", "withdraw", "snapshot"},
            },
            "stats": {
                "--by": {"asset", "type", "month"},
                "-b": {"asset", "type", "month"},
                "--asset": asset_names,
                "-a": asset_names,
                "--month": None,
                "-m": None,
                "--include-archived": None,
                "-i": None,
            },
            "asset": {
                "create": None,
                "list": {
                    "--include-archived": None,
                    "-i": None,
                },
                "delete": asset_names,
                "rename": asset_names,
                "archive": asset_names,
                "unarchive": asset_names,
                "update": asset_names,
            },
            "update-transaction": None,
            "update-snapshot": None,
            "import": None,
            "export": None,
            "help": None,
            "exit": None,
            "quit": None,
        }
    )


def interactive_shell(service: PortfolioService, app: typer.Typer) -> None:
    """Launch the interactive command shell with autocompletion."""
    rprint("\n[bold magenta]MonetRack Interactive Shell[/bold magenta]")
    rprint(
        "[dim]Type [bold white]help[/bold white] for command usage, "
        "or [bold white]exit[/bold white]/[bold white]quit[/bold white] to leave.[/dim]\n"
    )

    session = PromptSession(completer=build_completer(service))

    while True:
        try:
            prompt_html = HTML("<ansibold><ansimagenta>monetrack</ansimagenta></ansibold><ansicyan>&gt;</ansicyan> ")
            text = session.prompt(prompt_html)
        except KeyboardInterrupt:
            continue
        except EOFError:
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

            if args[0] == "import" or (
                len(args) >= 2
                and args[0] == "asset"
                and args[1] in ["create", "delete", "archive", "unarchive", "rename", "update"]
            ):
                session.completer = build_completer(service)
        except click.exceptions.Exit:
            pass
        except click.exceptions.Abort:
            rprint("[yellow]Aborted.[/yellow]")
        except click.ClickException as e:
            rprint(f"[red]Error: {e}[/red]")
        except Exception as e:
            rprint(f"[red]Unhandled error: {e!s}[/red]")

    rprint("[magenta]Goodbye![/magenta]")
