import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import override

from monetrack.domain.models import (
    Asset,
    AssetType,
    HistoryEvent,
    HistoryEventSource,
    HistoryEventType,
    Snapshot,
    Transaction,
    TransactionType,
)
from monetrack.ports.db_port import DatabasePort


class SQLiteDatabaseAdapter(DatabasePort):
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
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def transaction(self):
        """Context manager that commits on success, rolls back on error, and closes the connection."""
        conn = self.get_connection()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @override
    def init_db(self) -> None:
        """Initialize the SQLite schema and perform migrations."""
        with self.transaction() as conn:
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

    @override
    def create_asset(self, asset: Asset) -> int:
        """Insert a new asset into the database."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO assets (name, type, isin, wkn, comment, is_archived) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    asset.name,
                    asset.type.value,
                    asset.isin if asset.isin != "" else None,
                    asset.wkn if asset.wkn != "" else None,
                    asset.comment if asset.comment != "" else None,
                    1 if asset.is_archived else 0,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Database insert failed: lastrowid is None")
            return cursor.lastrowid

    @override
    def list_assets(self, include_archived: bool = False) -> list[Asset]:
        """Return all registered assets."""
        with self.transaction() as conn:
            if include_archived:
                rows = conn.execute("SELECT * FROM assets ORDER BY name ASC").fetchall()
            else:
                rows = conn.execute("SELECT * FROM assets WHERE is_archived = 0 ORDER BY name ASC").fetchall()
            return [
                Asset(
                    id=row["id"],
                    name=row["name"],
                    type=AssetType(row["type"]),
                    isin=row["isin"] or "",
                    wkn=row["wkn"] or "",
                    comment=row["comment"] or "",
                    is_archived=bool(row["is_archived"]),
                )
                for row in rows
            ]

    @override
    def find_asset(self, query: str) -> Asset | None:
        """Find a unique asset by Name (case-insensitive), ID, ISIN, or WKN."""
        with self.transaction() as conn:
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
                    type=AssetType(row["type"]),
                    isin=row["isin"] or "",
                    wkn=row["wkn"] or "",
                    comment=row["comment"] or "",
                    is_archived=bool(row["is_archived"]),
                )
            return None

    @override
    def delete_asset(self, asset_id: int) -> None:
        """Delete an asset and all associated transactions/snapshots."""
        with self.transaction() as conn:
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))

    @override
    def rename_asset(self, asset_id: int, new_name: str) -> None:
        """Rename an asset."""
        with self.transaction() as conn:
            conn.execute("UPDATE assets SET name = ? WHERE id = ?", (new_name, asset_id))

    @override
    def archive_asset(self, asset_id: int, is_archived: bool) -> None:
        """Archive or unarchive an asset."""
        val = 1 if is_archived else 0
        with self.transaction() as conn:
            conn.execute("UPDATE assets SET is_archived = ? WHERE id = ?", (val, asset_id))

    @override
    def add_transaction(self, tx: Transaction) -> int:
        """Log an investment or withdrawal transaction."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO transactions (asset_id, type, amount, timestamp, comment) VALUES (?, ?, ?, ?, ?)",
                (tx.asset_id, tx.type.value, tx.amount, tx.timestamp, tx.comment if tx.comment != "" else None),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Database insert failed: lastrowid is None")
            return cursor.lastrowid

    @override
    def add_snapshot(self, snap: Snapshot) -> int:
        """Log a valuation snapshot."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO snapshots (asset_id, value, timestamp, comment) VALUES (?, ?, ?, ?)",
                (snap.asset_id, snap.value, snap.timestamp, snap.comment if snap.comment != "" else None),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Database insert failed: lastrowid is None")
            return cursor.lastrowid

    @override
    def list_transactions(self) -> list[Transaction]:
        """List all transactions."""
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM transactions ORDER BY timestamp ASC, id ASC").fetchall()
            return [
                Transaction(
                    id=row["id"],
                    asset_id=row["asset_id"],
                    timestamp=row["timestamp"],
                    type=TransactionType(row["type"]),
                    amount=row["amount"],
                    comment=row["comment"] or "",
                )
                for row in rows
            ]

    @override
    def list_snapshots(self) -> list[Snapshot]:
        """List all snapshots."""
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM snapshots ORDER BY timestamp ASC, id ASC").fetchall()
            return [
                Snapshot(
                    id=row["id"],
                    asset_id=row["asset_id"],
                    timestamp=row["timestamp"],
                    value=row["value"],
                    comment=row["comment"] or "",
                )
                for row in rows
            ]

    @override
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
            et_str = event_type.value if isinstance(event_type, TransactionType) else str(event_type)
            if et_str == "snapshot":
                tx_where.append("1=0")
            else:
                tx_where.append("t.type = ?")
                params.append(et_str)
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

        with self.transaction() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                HistoryEvent(
                    source=HistoryEventSource(row["source"]),
                    id=row["event_id"],
                    timestamp=row["timestamp"],
                    event_type=HistoryEventType(row["event_type"]),
                    value=row["value"],
                    comment=row["comment"] or "",
                    asset_name=row["asset_name"],
                )
                for row in rows
            ]

    @override
    def update_asset(
        self,
        asset_id: int,
        name: str | None = None,
        type: AssetType | None = None,
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
            params.append(type.value)
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
        with self.transaction() as conn:
            conn.execute(f"UPDATE assets SET {', '.join(updates)} WHERE id = ?", tuple(params))

    @override
    def update_transaction(
        self,
        tx_id: int,
        amount: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
        type: TransactionType | None = None,
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
            params.append(type.value)

        if not updates:
            return

        params.append(tx_id)
        with self.transaction() as conn:
            res = conn.execute(f"UPDATE transactions SET {', '.join(updates)} WHERE id = ?", tuple(params))
            if res.rowcount == 0:
                raise ValueError(f"Transaction with ID {tx_id} not found.")

    @override
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
        with self.transaction() as conn:
            res = conn.execute(f"UPDATE snapshots SET {', '.join(updates)} WHERE id = ?", tuple(params))
            if res.rowcount == 0:
                raise ValueError(f"Snapshot with ID {snap_id} not found.")
