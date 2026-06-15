import os
import sqlite3
from pathlib import Path
from typing import Any


def get_db_path() -> Path:
    """Resolve the database storage path adhering to XDG specification."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        base_dir = Path(xdg_data_home)
    else:
        base_dir = Path.home() / ".local" / "share"

    app_dir = base_dir / "monetrack"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "monetrack.db"


def get_connection() -> sqlite3.Connection:
    """Create a connection to the SQLite database with Foreign Keys enabled."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    # Return rows as dicts for convenience
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the SQLite schema."""
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT CHECK(type IN ('p2p', 'stock', 'etf', 'crypto', 'other')) NOT NULL DEFAULT 'other',
            isin TEXT,
            wkn TEXT,
            comment TEXT
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            type TEXT CHECK(type IN ('invest', 'withdraw')) NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            comment TEXT,
            FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            value REAL NOT NULL CHECK(value >= 0),
            comment TEXT,
            FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
        );
        """)
        conn.commit()


# --- Asset Operations ---


def create_asset(
    name: str,
    asset_type: str,
    isin: str | None = None,
    wkn: str | None = None,
    comment: str | None = None,
) -> int:
    """Insert a new asset into the database."""

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO assets (name, type, isin, wkn, comment) VALUES (?, ?, ?, ?, ?)",
            (name, asset_type.lower(), isin, wkn, comment),
        )
        conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("Database insert failed: lastrowid is None")
        return cursor.lastrowid


def list_assets() -> list[dict[str, Any]]:
    """Return all registered assets."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM assets ORDER BY name ASC").fetchall()
        return [dict(row) for row in rows]


def find_asset(query: str) -> dict[str, Any] | None:
    """Find a unique asset by Name (case-insensitive), ID, ISIN, or WKN."""
    with get_connection() as conn:
        # Check if query is an integer ID
        if query.isdigit():
            row = conn.execute(
                "SELECT * FROM assets WHERE id = ?", (int(query),)
            ).fetchone()
            if row:
                return dict(row)

        # Match case-insensitively on name, isin, or wkn
        row = conn.execute(
            "SELECT * FROM assets WHERE LOWER(name) = LOWER(?) OR LOWER(isin) = LOWER(?) OR LOWER(wkn) = LOWER(?)",
            (query, query, query),
        ).fetchone()
        if row:
            return dict(row)

        # Fuzzy match on name if exact match fails
        row = conn.execute(
            "SELECT * FROM assets WHERE name LIKE ? LIMIT 1", (f"%{query}%",)
        ).fetchone()
        if row:
            return dict(row)

        return None


# --- Transaction & Snapshot Operations ---


def add_transaction(
    asset_id: int,
    tx_type: str,
    amount: float,
    timestamp: str,
    comment: str | None = None,
) -> int:
    """Log an investment or withdrawal transaction."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transactions (asset_id, type, amount, timestamp, comment) VALUES (?, ?, ?, ?, ?)",
            (asset_id, tx_type.lower(), amount, timestamp, comment),
        )
        conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("Database insert failed: lastrowid is None")
        return cursor.lastrowid


def add_snapshot(
    asset_id: int, value: float, timestamp: str, comment: str | None = None
) -> int:
    """Log a valuation snapshot."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO snapshots (asset_id, value, timestamp, comment) VALUES (?, ?, ?, ?)",
            (asset_id, value, timestamp, comment),
        )
        conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("Database insert failed: lastrowid is None")
        return cursor.lastrowid


# --- Calculation & Reporting Engine ---


def get_asset_stats(asset_id: int) -> dict[str, Any]:
    """Calculate Net Invested, Current Value, and Earnings for a single asset."""
    with get_connection() as conn:
        # Sum of investments
        invest_sum = (
            conn.execute(
                "SELECT SUM(amount) FROM transactions WHERE asset_id = ? AND type = 'invest'",
                (asset_id,),
            ).fetchone()[0]
            or 0.0
        )

        # Sum of withdrawals
        withdraw_sum = (
            conn.execute(
                "SELECT SUM(amount) FROM transactions WHERE asset_id = ? AND type = 'withdraw'",
                (asset_id,),
            ).fetchone()[0]
            or 0.0
        )

        net_invested = invest_sum - withdraw_sum

        # Get latest snapshot
        latest_snapshot = conn.execute(
            "SELECT value, timestamp FROM snapshots WHERE asset_id = ? ORDER BY timestamp DESC, id DESC LIMIT 1",
            (asset_id,),
        ).fetchone()

        if latest_snapshot:
            current_value = latest_snapshot[0]
            last_val_date = latest_snapshot[1]
        else:
            current_value = net_invested
            last_val_date = "No snapshot"

        earnings = current_value - net_invested
        roi = (earnings / net_invested * 100.0) if net_invested > 0 else 0.0

        return {
            "net_invested": net_invested,
            "current_value": current_value,
            "earnings": earnings,
            "roi": roi,
            "last_valuation_date": last_val_date,
            "total_invested": invest_sum,
            "total_withdrawn": withdraw_sum,
        }


def get_global_summary() -> dict[str, Any]:
    """Calculate overall statistics across all assets."""
    assets = list_assets()
    total_net_invested = 0.0
    total_current_value = 0.0
    total_earnings = 0.0
    total_invested = 0.0
    total_withdrawn = 0.0

    for asset in assets:
        stats = get_asset_stats(asset["id"])
        total_net_invested += stats["net_invested"]
        total_current_value += stats["current_value"]
        total_earnings += stats["earnings"]
        total_invested += stats["total_invested"]
        total_withdrawn += stats["total_withdrawn"]

    total_roi = (
        (total_earnings / total_net_invested * 100.0) if total_net_invested > 0 else 0.0
    )

    return {
        "net_invested": total_net_invested,
        "current_value": total_current_value,
        "earnings": total_earnings,
        "roi": total_roi,
        "total_invested": total_invested,
        "total_withdrawn": total_withdrawn,
        "asset_count": len(assets),
    }


def get_next_month(yyyy_mm: str) -> str:
    """Increment YYYY-MM string by one month."""
    year, month = map(int, yyyy_mm.split("-"))
    if month == 12:
        return f"{year + 1:04d}-01"
    else:
        return f"{year:04d}-{month + 1:02d}"


def get_valuation_before(
    conn: sqlite3.Connection, asset_id: int | None, before_timestamp: str
) -> float:
    """Calculate the valuation of asset(s) at/before a specific timestamp."""
    if asset_id is not None:
        return _get_single_asset_valuation_before(conn, asset_id, before_timestamp)

    # Calculate sum of valuations for all assets
    assets = conn.execute("SELECT id FROM assets").fetchall()
    total_val = 0.0
    for asset in assets:
        total_val += _get_single_asset_valuation_before(
            conn, asset["id"], before_timestamp
        )
    return total_val


def _get_single_asset_valuation_before(
    conn: sqlite3.Connection, asset_id: int, before_timestamp: str
) -> float:
    """Helper to calculate a single asset's valuation at/before a specific timestamp."""
    row = conn.execute(
        "SELECT value, timestamp FROM snapshots WHERE asset_id = ? AND "
        "timestamp < ? ORDER BY timestamp DESC, id DESC LIMIT 1",
        (asset_id, before_timestamp),
    ).fetchone()

    if row:
        snap_value, snap_time = row["value"], row["timestamp"]
        flow = (
            conn.execute(
                "SELECT SUM(CASE WHEN type = 'invest' THEN amount ELSE -amount END) "
                "FROM transactions WHERE asset_id = ? AND timestamp > ? AND timestamp < ?",
                (asset_id, snap_time, before_timestamp),
            ).fetchone()[0]
            or 0.0
        )
        return snap_value + flow
    else:
        flow = (
            conn.execute(
                "SELECT SUM(CASE WHEN type = 'invest' THEN amount ELSE -amount END) "
                "FROM transactions WHERE asset_id = ? AND timestamp < ?",
                (asset_id, before_timestamp),
            ).fetchone()[0]
            or 0.0
        )
        return flow


def get_all_months(conn: sqlite3.Connection, asset_id: int | None = None) -> list[str]:
    """Get list of all months between first transaction/snapshot and current month."""
    if asset_id is not None:
        row = conn.execute(
            """
            SELECT MIN(min_t) as global_min, MAX(max_t) as global_max FROM (
                SELECT MIN(timestamp) as min_t, MAX(timestamp) as max_t FROM transactions WHERE asset_id = ?
                UNION ALL
                SELECT MIN(timestamp) as min_t, MAX(timestamp) as max_t FROM snapshots WHERE asset_id = ?
            )
        """,
            (asset_id, asset_id),
        ).fetchone()
    else:
        row = conn.execute("""
            SELECT MIN(min_t) as global_min, MAX(max_t) as global_max FROM (
                SELECT MIN(timestamp) as min_t, MAX(timestamp) as max_t FROM transactions
                UNION ALL
                SELECT MIN(timestamp) as min_t, MAX(timestamp) as max_t FROM snapshots
            )
        """).fetchone()

    if not row or not row["global_min"]:
        return []

    min_date = row["global_min"][:7]  # YYYY-MM
    max_date = row["global_max"][:7]  # YYYY-MM

    from datetime import datetime

    current_month = datetime.now().strftime("%Y-%m")
    if current_month > max_date:
        max_date = current_month

    months = []
    curr = min_date
    while curr <= max_date:
        months.append(curr)
        curr = get_next_month(curr)
    return months


def get_monthly_stats(asset_id: int | None = None) -> list[dict[str, Any]]:
    """Aggregate net invested, valuation, and earnings on a month-by-month basis."""
    with get_connection() as conn:
        months = get_all_months(conn, asset_id)
        stats_list = []

        for month in months:
            start_time = f"{month}-01"
            next_m = get_next_month(month)
            end_time = f"{next_m}-01"

            v_start = get_valuation_before(conn, asset_id, start_time)
            v_end = get_valuation_before(conn, asset_id, end_time)

            if asset_id is not None:
                invest = (
                    conn.execute(
                        "SELECT SUM(amount) FROM transactions WHERE asset_id = ? AND "
                        "type = 'invest' AND timestamp >= ? AND timestamp < ?",
                        (asset_id, start_time, end_time),
                    ).fetchone()[0]
                    or 0.0
                )

                withdraw = (
                    conn.execute(
                        "SELECT SUM(amount) FROM transactions WHERE asset_id = ? AND "
                        "type = 'withdraw' AND timestamp >= ? AND timestamp < ?",
                        (asset_id, start_time, end_time),
                    ).fetchone()[0]
                    or 0.0
                )
            else:
                invest = (
                    conn.execute(
                        "SELECT SUM(amount) FROM transactions WHERE type = 'invest' AND timestamp >= ? AND timestamp < ?",
                        (start_time, end_time),
                    ).fetchone()[0]
                    or 0.0
                )

                withdraw = (
                    conn.execute(
                        "SELECT SUM(amount) FROM transactions WHERE type = 'withdraw' AND timestamp >= ? AND timestamp < ?",
                        (start_time, end_time),
                    ).fetchone()[0]
                    or 0.0
                )

            net_flow = invest - withdraw
            earnings = v_end - v_start - net_flow

            stats_list.append(
                {
                    "month": month,
                    "valuation_start": v_start,
                    "valuation_end": v_end,
                    "invested": invest,
                    "withdrawn": withdraw,
                    "net_flow": net_flow,
                    "earnings": earnings,
                }
            )

        return stats_list


def get_type_stats() -> dict[str, dict[str, Any]]:
    """Aggregate stats grouped by asset type (p2p, stock, etf, crypto, other)."""
    assets = list_assets()
    by_type = {}

    for asset in assets:
        t = asset["type"]
        stats = get_asset_stats(asset["id"])

        if t not in by_type:
            by_type[t] = {
                "net_invested": 0.0,
                "current_value": 0.0,
                "earnings": 0.0,
                "total_invested": 0.0,
                "total_withdrawn": 0.0,
            }

        by_type[t]["net_invested"] += stats["net_invested"]
        by_type[t]["current_value"] += stats["current_value"]
        by_type[t]["earnings"] += stats["earnings"]
        by_type[t]["total_invested"] += stats["total_invested"]
        by_type[t]["total_withdrawn"] += stats["total_withdrawn"]

    for _t, data in by_type.items():
        data["roi"] = (
            (data["earnings"] / data["net_invested"] * 100.0)
            if data["net_invested"] > 0
            else 0.0
        )

    return by_type


def get_asset_monthly_stats(asset_id: int, month: str) -> dict[str, Any]:
    """Calculate valuation and earnings for a single asset during a specific month."""
    with get_connection() as conn:
        start_time = f"{month}-01"
        next_m = get_next_month(month)
        end_time = f"{next_m}-01"

        v_start = get_valuation_before(conn, asset_id, start_time)
        v_end = get_valuation_before(conn, asset_id, end_time)

        invest = (
            conn.execute(
                "SELECT SUM(amount) FROM transactions WHERE asset_id = ? AND "
                "type = 'invest' AND timestamp >= ? AND timestamp < ?",
                (asset_id, start_time, end_time),
            ).fetchone()[0]
            or 0.0
        )

        withdraw = (
            conn.execute(
                "SELECT SUM(amount) FROM transactions WHERE asset_id = ? AND "
                "type = 'withdraw' AND timestamp >= ? AND timestamp < ?",
                (asset_id, start_time, end_time),
            ).fetchone()[0]
            or 0.0
        )

        net_flow = invest - withdraw

        earnings = v_end - v_start - net_flow

        return {
            "valuation_start": v_start,
            "valuation_end": v_end,
            "invested": invest,
            "withdrawn": withdraw,
            "net_flow": net_flow,
            "earnings": earnings,
        }
