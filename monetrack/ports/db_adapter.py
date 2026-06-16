import os
import sqlite3
from pathlib import Path

from monetrack.domain.models import (
    Asset,
    AssetStats,
    GlobalSummary,
    HistoryEvent,
    MonthlyStats,
    Snapshot,
    Transaction,
)


class SQLiteDatabaseAdapter:
    def __init__(self, db_path: Path | None = None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = self._resolve_db_path()

    def _resolve_db_path(self) -> Path:
        """Resolve the database storage path adhering to XDG specification."""
        env_path = os.environ.get("MONETRACK_DB_PATH")
        if env_path:
            p = Path(env_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p

        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            base_dir = Path(xdg_data_home)
        else:
            base_dir = Path.home() / ".local" / "share"

        app_dir = base_dir / "monetrack"
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / "monetrack.db"

    def get_connection(self) -> sqlite3.Connection:
        """Create a connection to the SQLite database with Foreign Keys enabled."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize the SQLite schema and perform migrations."""
        with self.get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT CHECK(type IN ('p2p', 'stock', 'etf', 'crypto', 'other')) NOT NULL DEFAULT 'other',
                isin TEXT,
                wkn TEXT,
                comment TEXT,
                is_archived INTEGER DEFAULT 0 CHECK(is_archived IN (0, 1))
            );
            """)

            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(assets)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "is_archived" not in columns:
                conn.execute("ALTER TABLE assets ADD COLUMN is_archived INTEGER DEFAULT 0 CHECK(is_archived IN (0, 1))")

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

    def create_asset(self, asset: Asset) -> int:
        """Insert a new asset into the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO assets (name, type, isin, wkn, comment, is_archived) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    asset.name,
                    asset.type.lower(),
                    asset.isin,
                    asset.wkn,
                    asset.comment,
                    1 if asset.is_archived else 0,
                ),
            )
            conn.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("Database insert failed: lastrowid is None")
            return cursor.lastrowid

    def list_assets(self, include_archived: bool = False) -> list[Asset]:
        """Return all registered assets."""
        with self.get_connection() as conn:
            if include_archived:
                rows = conn.execute("SELECT * FROM assets ORDER BY name ASC").fetchall()
            else:
                rows = conn.execute("SELECT * FROM assets WHERE is_archived = 0 ORDER BY name ASC").fetchall()
            return [
                Asset(
                    id=row["id"],
                    name=row["name"],
                    type=row["type"],
                    isin=row["isin"],
                    wkn=row["wkn"],
                    comment=row["comment"],
                    is_archived=bool(row["is_archived"]),
                )
                for row in rows
            ]

    def find_asset(self, query: str) -> Asset | None:
        """Find a unique asset by Name (case-insensitive), ID, ISIN, or WKN."""
        with self.get_connection() as conn:
            row = None
            if query.isdigit():
                row = conn.execute("SELECT * FROM assets WHERE id = ?", (int(query),)).fetchone()

            if not row:
                row = conn.execute(
                    "SELECT * FROM assets WHERE LOWER(name) = LOWER(?) "
                    "OR LOWER(isin) = LOWER(?) OR LOWER(wkn) = LOWER(?)",
                    (query, query, query),
                ).fetchone()

            if not row:
                row = conn.execute("SELECT * FROM assets WHERE name LIKE ? LIMIT 1", (f"%{query}%",)).fetchone()

            if row:
                return Asset(
                    id=row["id"],
                    name=row["name"],
                    type=row["type"],
                    isin=row["isin"],
                    wkn=row["wkn"],
                    comment=row["comment"],
                    is_archived=bool(row["is_archived"]),
                )
            return None

    def delete_asset(self, asset_id: int) -> None:
        """Delete an asset and all associated transactions/snapshots."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            conn.commit()

    def rename_asset(self, asset_id: int, new_name: str) -> None:
        """Rename an asset."""
        with self.get_connection() as conn:
            conn.execute("UPDATE assets SET name = ? WHERE id = ?", (new_name, asset_id))
            conn.commit()

    def archive_asset(self, asset_id: int, is_archived: bool) -> None:
        """Archive or unarchive an asset."""
        val = 1 if is_archived else 0
        with self.get_connection() as conn:
            conn.execute("UPDATE assets SET is_archived = ? WHERE id = ?", (val, asset_id))
            conn.commit()

    def add_transaction(self, tx: Transaction) -> int:
        """Log an investment or withdrawal transaction."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO transactions (asset_id, type, amount, timestamp, comment) VALUES (?, ?, ?, ?, ?)",
                (tx.asset_id, tx.type.lower(), tx.amount, tx.timestamp, tx.comment),
            )
            conn.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("Database insert failed: lastrowid is None")
            return cursor.lastrowid

    def add_snapshot(self, snap: Snapshot) -> int:
        """Log a valuation snapshot."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO snapshots (asset_id, value, timestamp, comment) VALUES (?, ?, ?, ?)",
                (snap.asset_id, snap.value, snap.timestamp, snap.comment),
            )
            conn.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("Database insert failed: lastrowid is None")
            return cursor.lastrowid

    def get_asset_stats(self, asset_id: int) -> AssetStats:
        """Calculate Net Invested, Current Value, and Earnings for a single asset."""
        with self.get_connection() as conn:
            invest_sum = (
                conn.execute(
                    "SELECT SUM(amount) FROM transactions WHERE asset_id = ? AND type = 'invest'",
                    (asset_id,),
                ).fetchone()[0]
                or 0.0
            )

            withdraw_sum = (
                conn.execute(
                    "SELECT SUM(amount) FROM transactions WHERE asset_id = ? AND type = 'withdraw'",
                    (asset_id,),
                ).fetchone()[0]
                or 0.0
            )

            net_invested = invest_sum - withdraw_sum

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

            return AssetStats(
                net_invested=net_invested,
                current_value=current_value,
                earnings=earnings,
                roi=roi,
                last_valuation_date=last_val_date,
                total_invested=invest_sum,
                total_withdrawn=withdraw_sum,
            )

    def get_global_summary(self, include_archived: bool = False) -> GlobalSummary:
        """Calculate overall statistics across all assets."""
        assets = self.list_assets(include_archived=include_archived)
        total_net_invested = 0.0
        total_current_value = 0.0
        total_earnings = 0.0
        total_invested = 0.0
        total_withdrawn = 0.0

        for asset in assets:
            if asset.id is None:
                continue
            stats = self.get_asset_stats(asset.id)
            total_net_invested += stats.net_invested
            total_current_value += stats.current_value
            total_earnings += stats.earnings
            total_invested += stats.total_invested
            total_withdrawn += stats.total_withdrawn

        total_roi = (total_earnings / total_net_invested * 100.0) if total_net_invested > 0 else 0.0

        return GlobalSummary(
            net_invested=total_net_invested,
            current_value=total_current_value,
            earnings=total_earnings,
            roi=total_roi,
            total_invested=total_invested,
            total_withdrawn=total_withdrawn,
            asset_count=len(assets),
        )

    def _get_next_month(self, yyyy_mm: str) -> str:
        year, month = map(int, yyyy_mm.split("-"))
        if month == 12:
            return f"{year + 1:04d}-01"
        else:
            return f"{year:04d}-{month + 1:02d}"

    def get_valuation_before(
        self, conn: sqlite3.Connection, asset_id: int | None, before_timestamp: str, include_archived: bool = False
    ) -> float:
        """Calculate the valuation of asset(s) at/before a specific timestamp."""
        if asset_id is not None:
            return self._get_single_asset_valuation_before(conn, asset_id, before_timestamp)

        if include_archived:
            assets = conn.execute("SELECT id FROM assets").fetchall()
        else:
            assets = conn.execute("SELECT id FROM assets WHERE is_archived = 0").fetchall()
        total_val = 0.0
        for asset in assets:
            total_val += self._get_single_asset_valuation_before(conn, asset["id"], before_timestamp)
        return total_val

    def _get_single_asset_valuation_before(
        self, conn: sqlite3.Connection, asset_id: int, before_timestamp: str
    ) -> float:
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

    def get_all_months(
        self, conn: sqlite3.Connection, asset_id: int | None = None, include_archived: bool = False
    ) -> list[str]:
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
            if include_archived:
                row = conn.execute("""
                    SELECT MIN(min_t) as global_min, MAX(max_t) as global_max FROM (
                        SELECT MIN(timestamp) as min_t, MAX(timestamp) as max_t FROM transactions
                        UNION ALL
                        SELECT MIN(timestamp) as min_t, MAX(timestamp) as max_t FROM snapshots
                    )
                """).fetchone()
            else:
                row = conn.execute("""
                    SELECT MIN(min_t) as global_min, MAX(max_t) as global_max FROM (
                        SELECT MIN(t.timestamp) as min_t, MAX(t.timestamp) as max_t FROM transactions t
                        JOIN assets a ON t.asset_id = a.id WHERE a.is_archived = 0
                        UNION ALL
                        SELECT MIN(s.timestamp) as min_t, MAX(s.timestamp) as max_t FROM snapshots s
                        JOIN assets a ON s.asset_id = a.id WHERE a.is_archived = 0
                    )
                """).fetchone()

        if not row or not row["global_min"]:
            return []

        min_date = row["global_min"][:7]
        max_date = row["global_max"][:7]

        from datetime import datetime

        current_month = datetime.now().strftime("%Y-%m")
        if current_month > max_date:
            max_date = current_month

        months = []
        curr = min_date
        while curr <= max_date:
            months.append(curr)
            curr = self._get_next_month(curr)
        return months

    def get_monthly_stats(self, asset_id: int | None = None, include_archived: bool = False) -> list[MonthlyStats]:
        with self.get_connection() as conn:
            months = self.get_all_months(conn, asset_id, include_archived)
            stats_list = []

            for month in months:
                start_time = f"{month}-01"
                next_m = self._get_next_month(month)
                end_time = f"{next_m}-01"

                v_start = self.get_valuation_before(conn, asset_id, start_time, include_archived)
                v_end = self.get_valuation_before(conn, asset_id, end_time, include_archived)

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
                    if include_archived:
                        invest = (
                            conn.execute(
                                "SELECT SUM(amount) FROM transactions WHERE type = 'invest' AND "
                                "timestamp >= ? AND timestamp < ?",
                                (start_time, end_time),
                            ).fetchone()[0]
                            or 0.0
                        )

                        withdraw = (
                            conn.execute(
                                "SELECT SUM(amount) FROM transactions WHERE type = 'withdraw' AND "
                                "timestamp >= ? AND timestamp < ?",
                                (start_time, end_time),
                            ).fetchone()[0]
                            or 0.0
                        )
                    else:
                        invest = (
                            conn.execute(
                                "SELECT SUM(t.amount) FROM transactions t JOIN assets a ON t.asset_id = a.id "
                                "WHERE t.type = 'invest' AND a.is_archived = 0 "
                                "AND t.timestamp >= ? AND t.timestamp < ?",
                                (start_time, end_time),
                            ).fetchone()[0]
                            or 0.0
                        )

                        withdraw = (
                            conn.execute(
                                "SELECT SUM(t.amount) FROM transactions t JOIN assets a ON t.asset_id = a.id "
                                "WHERE t.type = 'withdraw' AND a.is_archived = 0 "
                                "AND t.timestamp >= ? AND t.timestamp < ?",
                                (start_time, end_time),
                            ).fetchone()[0]
                            or 0.0
                        )

                net_flow = invest - withdraw
                earnings = v_end - v_start - net_flow

                stats_list.append(
                    MonthlyStats(
                        month=month,
                        valuation_start=v_start,
                        valuation_end=v_end,
                        invested=invest,
                        withdrawn=withdraw,
                        net_flow=net_flow,
                        earnings=earnings,
                    )
                )

            return stats_list

    def get_asset_monthly_stats(self, asset_id: int, month: str) -> MonthlyStats:
        with self.get_connection() as conn:
            start_time = f"{month}-01"
            next_m = self._get_next_month(month)
            end_time = f"{next_m}-01"

            v_start = self.get_valuation_before(conn, asset_id, start_time)
            v_end = self.get_valuation_before(conn, asset_id, end_time)

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

            return MonthlyStats(
                month=month,
                valuation_start=v_start,
                valuation_end=v_end,
                invested=invest,
                withdrawn=withdraw,
                net_flow=net_flow,
                earnings=earnings,
            )

    def get_type_stats(self, include_archived: bool = False) -> dict[str, dict[str, float]]:
        assets = self.list_assets(include_archived=include_archived)
        by_type: dict[str, dict[str, float]] = {}

        for asset in assets:
            if asset.id is None:
                continue
            t = asset.type
            stats = self.get_asset_stats(asset.id)

            if t not in by_type:
                by_type[t] = {
                    "net_invested": 0.0,
                    "current_value": 0.0,
                    "earnings": 0.0,
                    "total_invested": 0.0,
                    "total_withdrawn": 0.0,
                }

            by_type[t]["net_invested"] += stats.net_invested
            by_type[t]["current_value"] += stats.current_value
            by_type[t]["earnings"] += stats.earnings
            by_type[t]["total_invested"] += stats.total_invested
            by_type[t]["total_withdrawn"] += stats.total_withdrawn

        for _t, data in by_type.items():
            data["roi"] = (data["earnings"] / data["net_invested"] * 100.0) if data["net_invested"] > 0 else 0.0

        return by_type

    def get_history(self, asset_id: int | None = None, event_type: str | None = None) -> list[HistoryEvent]:
        """Retrieve chronological history of transactions and snapshots."""
        tx_where = []
        snap_where = []
        params = []

        if asset_id is not None:
            tx_where.append("t.asset_id = ?")
            snap_where.append("s.asset_id = ?")
            params.extend([asset_id, asset_id])

        if event_type is not None:
            if event_type == "snapshot":
                tx_where.append("1=0")
            else:
                tx_where.append("t.type = ?")
                params.append(event_type)
                snap_where.append("1=0")

        tx_where_str = " AND ".join(tx_where)
        tx_where_str = f"WHERE {tx_where_str}" if tx_where_str else ""

        snap_where_str = " AND ".join(snap_where)
        snap_where_str = f"WHERE {snap_where_str}" if snap_where_str else ""

        query = f"""
            SELECT 'transaction' as source, t.id as event_id, t.timestamp, t.type as event_type,
                   t.amount as value, t.comment, a.name as asset_name
            FROM transactions t
            JOIN assets a ON t.asset_id = a.id
            {tx_where_str}
            UNION ALL
            SELECT 'snapshot' as source, s.id as event_id, s.timestamp, 'snapshot' as event_type,
                   s.value, s.comment, a.name as asset_name
            FROM snapshots s
            JOIN assets a ON s.asset_id = a.id
            {snap_where_str}
            ORDER BY timestamp ASC, source DESC, event_id ASC
        """

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                HistoryEvent(
                    source=row["source"],
                    id=row["event_id"],
                    timestamp=row["timestamp"],
                    event_type=row["event_type"],
                    value=row["value"],
                    comment=row["comment"],
                    asset_name=row["asset_name"],
                )
                for row in rows
            ]

    def update_asset(
        self,
        asset_id: int,
        name: str | None = None,
        type: str | None = None,
        isin: str | None = None,
        wkn: str | None = None,
        comment: str | None = None,
    ) -> None:
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if type is not None:
            updates.append("type = ?")
            params.append(type)
        if isin is not None:
            updates.append("isin = ?")
            params.append(isin if isin != "" else None)
        if wkn is not None:
            updates.append("wkn = ?")
            params.append(wkn if wkn != "" else None)
        if comment is not None:
            updates.append("comment = ?")
            params.append(comment if comment != "" else None)

        if not updates:
            return

        params.append(asset_id)
        with self.get_connection() as conn:
            conn.execute(f"UPDATE assets SET {', '.join(updates)} WHERE id = ?", tuple(params))

    def update_transaction(
        self,
        tx_id: int,
        amount: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
        type: str | None = None,
    ) -> None:
        updates = []
        params = []
        if amount is not None:
            updates.append("amount = ?")
            params.append(amount)
        if timestamp is not None:
            updates.append("timestamp = ?")
            params.append(timestamp)
        if comment is not None:
            updates.append("comment = ?")
            params.append(comment if comment != "" else None)
        if type is not None:
            updates.append("type = ?")
            params.append(type)

        if not updates:
            return

        params.append(tx_id)
        with self.get_connection() as conn:
            res = conn.execute(f"UPDATE transactions SET {', '.join(updates)} WHERE id = ?", tuple(params))
            if res.rowcount == 0:
                raise ValueError(f"Transaction with ID {tx_id} not found.")

    def update_snapshot(
        self,
        snap_id: int,
        value: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
    ) -> None:
        updates = []
        params = []
        if value is not None:
            updates.append("value = ?")
            params.append(value)
        if timestamp is not None:
            updates.append("timestamp = ?")
            params.append(timestamp)
        if comment is not None:
            updates.append("comment = ?")
            params.append(comment if comment != "" else None)

        if not updates:
            return

        params.append(snap_id)
        with self.get_connection() as conn:
            res = conn.execute(f"UPDATE snapshots SET {', '.join(updates)} WHERE id = ?", tuple(params))
            if res.rowcount == 0:
                raise ValueError(f"Snapshot with ID {snap_id} not found.")

    def get_raw_connection(self) -> sqlite3.Connection:
        return self.get_connection()
