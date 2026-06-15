from unittest.mock import patch

import click
import typer
from prompt_toolkit.completion import NestedCompleter

from monetrack.application.interactive import build_completer, interactive_shell
from monetrack.services.portfolio_service import PortfolioService


def test_build_completer_empty(portfolio_service: PortfolioService) -> None:
    completer = build_completer(portfolio_service)
    assert completer is not None


def test_build_completer_with_assets(portfolio_service: PortfolioService) -> None:
    portfolio_service.create_asset(name="Bondora", asset_type="p2p", isin="IE1", wkn="W1")
    portfolio_service.create_asset(name="Trade MSCI", asset_type="etf")
    completer = build_completer(portfolio_service)
    assert completer is not None
    # Check that asset names are in the completer options
    options = completer.options
    assert "invest" in options
    invest_completer = options["invest"]
    assert isinstance(invest_completer, NestedCompleter)
    invest_options = invest_completer.options
    assert "Bondora" in invest_options
    assert '"Bondora"' not in invest_options  # no space in name
    assert '"Trade MSCI"' in invest_options  # has space in name


def test_build_completer_exception(portfolio_service: PortfolioService) -> None:
    with patch.object(portfolio_service, "list_assets", side_effect=Exception("DB error")):
        completer = build_completer(portfolio_service)
        assert completer is not None
        assert "invest" in completer.options


def test_interactive_shell_flows(portfolio_service: PortfolioService) -> None:
    app = typer.Typer()

    @app.command(name="testcmd")
    def test_cmd():
        pass

    # 1. Test basic exits and empty inputs
    prompts = ["", "exit"]
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=prompts):
        interactive_shell(portfolio_service, app)

    # 2. Test quit and help
    prompts = ["help", "quit"]
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=prompts):
        interactive_shell(portfolio_service, app)

    # 3. Test EOFError
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=EOFError()):
        interactive_shell(portfolio_service, app)

    # 4. Test KeyboardInterrupt followed by exit
    prompts = [KeyboardInterrupt(), "exit"]
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=prompts):
        interactive_shell(portfolio_service, app)

    # 5. Test invalid shlex arguments
    prompts = ['"unclosed quote', "exit"]
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=prompts):
        interactive_shell(portfolio_service, app)


def test_interactive_shell_exceptions(portfolio_service: PortfolioService) -> None:
    app = typer.Typer()

    @app.command(name="fail-exit")
    def fail_exit():
        raise click.exceptions.Exit()

    @app.command(name="fail-abort")
    def fail_abort():
        raise click.exceptions.Abort()

    @app.command(name="fail-click")
    def fail_click():
        raise click.ClickException("Click error")

    @app.command(name="fail-generic")
    def fail_generic():
        raise ValueError("Generic error")

    prompts = ["fail-exit", "fail-abort", "fail-click", "fail-generic", "exit"]
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=prompts):
        interactive_shell(portfolio_service, app)


def test_interactive_shell_completer_refresh(portfolio_service: PortfolioService) -> None:
    app = typer.Typer()

    @app.command(name="import")
    def import_cmd():
        pass

    @app.command(name="asset")
    def asset_cmd(sub: str):
        pass

    prompts = ["import", "asset create", "exit"]
    # Verify it builds completer on refresh events
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=prompts):
        with patch("monetrack.application.interactive.build_completer") as mock_build:
            interactive_shell(portfolio_service, app)
            # The completer is built initially + refreshed 2 times = 3 calls
            assert mock_build.call_count == 3


def test_interactive_shell_special_inputs(portfolio_service: PortfolioService) -> None:
    app = typer.Typer()
    prompts = ["some-input", "exit"]
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=prompts):
        with patch("shlex.split", side_effect=[[], ["exit"]]):
            interactive_shell(portfolio_service, app)


def test_interactive_shell_help_exception(portfolio_service: PortfolioService) -> None:
    app = typer.Typer()
    prompts = ["help", "exit"]
    with patch("prompt_toolkit.PromptSession.prompt", side_effect=prompts):
        with patch.object(app, "__call__", side_effect=Exception("mock help error")):
            interactive_shell(portfolio_service, app)
