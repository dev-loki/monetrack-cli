from monetrack.application.formatters import (
    format_balance,
    format_earnings,
    format_roi,
    render_vertical_bar_chart,
)
from monetrack.domain.models import MonthlyStats


def test_format_balance() -> None:
    assert format_balance(100.0) == "€100.00"
    assert format_balance(-50.56) == "[red]-€50.56[/red]"
    assert format_balance(-0.001) == "€-0.00"


def test_format_earnings() -> None:
    assert format_earnings(100.0) == "[green]+€100.00[/green]"
    assert format_earnings(-50.56) == "[red]-€50.56[/red]"
    assert format_earnings(0.001) == "[dim]€0.00[/dim]"


def test_format_roi() -> None:
    assert format_roi(5.56) == "[green]+5.56%[/green]"
    assert format_roi(-3.12) == "[red]-3.12%[/red]"
    assert format_roi(0.0) == "[dim]0.00%[/dim]"


def test_render_vertical_bar_chart_empty() -> None:
    assert render_vertical_bar_chart([]) == ""


def test_render_vertical_bar_chart_data() -> None:
    stats = [
        MonthlyStats(
            month="2025-01",
            valuation_start=0.0,
            valuation_end=100.0,
            invested=100.0,
            withdrawn=0.0,
            net_flow=100.0,
            earnings=10.0,
        ),
        MonthlyStats(
            month="2025-02",
            valuation_start=100.0,
            valuation_end=150.0,
            invested=50.0,
            withdrawn=100.0,
            net_flow=-50.0,
            earnings=-20.0,
        ),
        MonthlyStats(
            month="2025-03",
            valuation_start=150.0,
            valuation_end=150.0,
            invested=0.0,
            withdrawn=0.0,
            net_flow=0.0,
            earnings=0.0,
        ),
    ]

    chart = render_vertical_bar_chart(stats, height=4)
    assert "█" in chart
    assert "┴" in chart
    assert "┬" in chart
    assert "─" in chart
    assert "2" in chart
    assert "5" in chart
    assert "1" in chart


def test_render_vertical_bar_chart_zero_earnings() -> None:
    stats = [
        MonthlyStats(
            month="2025-01",
            valuation_start=0.0,
            valuation_end=0.0,
            invested=0.0,
            withdrawn=0.0,
            net_flow=0.0,
            earnings=0.0,
        )
    ]
    chart = render_vertical_bar_chart(stats, height=4)
    assert "─" in chart
