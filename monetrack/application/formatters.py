from monetrack.domain.models import MonthlyStats


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


def render_vertical_bar_chart(monthly_stats: list[MonthlyStats], height: int = 6) -> str:
    """Render a vertical bar chart of monthly earnings."""
    if not monthly_stats:
        return ""

    earnings_list = [m.earnings for m in monthly_stats]
    months = [m.month for m in monthly_stats]

    max_val = max(abs(e) for e in earnings_list)
    if max_val <= 0.01:
        max_val = 1.0

    rows = []

    # Positive half
    for y in range(height, 0, -1):
        row_chars = []
        for e in earnings_list:
            if e > 0:
                val_h = round((e / max_val) * height)
                row_chars.append("[green]█[/green]" if val_h >= y else " ")
            else:
                row_chars.append(" ")
        rows.append("  " + "  ".join(row_chars))

    # Baseline
    baseline_chars = []
    for e in earnings_list:
        if e > 0:
            baseline_chars.append("┴")
        elif e < 0:
            baseline_chars.append("┬")
        else:
            baseline_chars.append("─")
    rows.append("──" + "──".join(baseline_chars))

    # Negative half
    for y in range(1, height + 1):
        row_chars = []
        for e in earnings_list:
            if e < 0:
                val_h = round((abs(e) / max_val) * height)
                row_chars.append("[red]█[/red]" if val_h >= y else " ")
            else:
                row_chars.append(" ")
        rows.append("  " + "  ".join(row_chars))

    # Slanted/vertical labels
    label_rows = ["", "", "", "", ""]
    for m in months:
        y_part = m[2:4]
        m_part = m[5:7]
        label_rows[0] += f" {y_part[0]} "
        label_rows[1] += f" {y_part[1]} "
        label_rows[2] += " - "
        label_rows[3] += f" {m_part[0]} "
        label_rows[4] += f" {m_part[1]} "

    for lr in label_rows:
        rows.append(" " + lr)

    return "\n".join(rows)
