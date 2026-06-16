import csv
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
from monetrack.ports.db_port import DatabasePort


class PortfolioService:
    def __init__(self, db: DatabasePort):
        self.db = db

    def init_db(self) -> None:
        self.db.init_db()

    def create_asset(
        self,
        name: str,
        asset_type: str,
        isin: str | None = None,
        wkn: str | None = None,
        comment: str | None = None,
    ) -> int:
        asset = Asset(
            id=None,
            name=name,
            type=asset_type,
            isin=isin,
            wkn=wkn,
            comment=comment,
            is_archived=False,
        )
        return self.db.create_asset(asset)

    def list_assets(self, include_archived: bool = False) -> list[Asset]:
        return self.db.list_assets(include_archived=include_archived)

    def find_asset(self, query: str) -> Asset | None:
        return self.db.find_asset(query)

    def delete_asset(self, asset_id: int) -> None:
        self.db.delete_asset(asset_id)

    def rename_asset(self, asset_id: int, new_name: str) -> None:
        self.db.rename_asset(asset_id, new_name)

    def archive_asset(self, asset_id: int, is_archived: bool) -> None:
        self.db.archive_asset(asset_id, is_archived)

    def add_transaction(
        self,
        asset_id: int,
        tx_type: str,
        amount: float,
        timestamp: str,
        comment: str | None = None,
    ) -> int:
        tx = Transaction(
            id=None,
            asset_id=asset_id,
            timestamp=timestamp,
            type=tx_type,
            amount=amount,
            comment=comment,
        )
        return self.db.add_transaction(tx)

    def add_snapshot(
        self,
        asset_id: int,
        value: float,
        timestamp: str,
        comment: str | None = None,
    ) -> int:
        snap = Snapshot(
            id=None,
            asset_id=asset_id,
            timestamp=timestamp,
            value=value,
            comment=comment,
        )
        return self.db.add_snapshot(snap)

    def get_asset_stats(self, asset_id: int) -> AssetStats:
        return self.db.get_asset_stats(asset_id)

    def get_global_summary(self, include_archived: bool = False) -> GlobalSummary:
        return self.db.get_global_summary(include_archived=include_archived)

    def get_monthly_stats(self, asset_id: int | None = None, include_archived: bool = False) -> list[MonthlyStats]:
        return self.db.get_monthly_stats(asset_id=asset_id, include_archived=include_archived)

    def get_asset_monthly_stats(self, asset_id: int, month: str) -> MonthlyStats:
        return self.db.get_asset_monthly_stats(asset_id, month)

    def get_type_stats(self, include_archived: bool = False) -> dict[str, dict[str, float]]:
        return self.db.get_type_stats(include_archived=include_archived)

    def get_history(self, asset_id: int | None = None, event_type: str | None = None) -> list[HistoryEvent]:
        return self.db.get_history(asset_id=asset_id, event_type=event_type)

    def update_asset(
        self,
        asset_id: int,
        name: str | None = None,
        type: str | None = None,
        isin: str | None = None,
        wkn: str | None = None,
        comment: str | None = None,
    ) -> None:
        self.db.update_asset(asset_id, name, type, isin, wkn, comment)

    def update_transaction(
        self,
        tx_id: int,
        amount: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
        type: str | None = None,
    ) -> None:
        self.db.update_transaction(tx_id, amount, timestamp, comment, type)

    def update_snapshot(
        self,
        snap_id: int,
        value: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
    ) -> None:
        self.db.update_snapshot(snap_id, value, timestamp, comment)

    def export_to_csv(self, export_dir: Path) -> None:
        """Export database data to CSV files in the specified directory."""
        export_dir.mkdir(parents=True, exist_ok=True)

        # 1. Export assets
        assets = self.db.list_assets(include_archived=True)
        with open(export_dir / "assets.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "type", "isin", "wkn", "comment", "is_archived"])
            for a in assets:
                writer.writerow(
                    [a.id, a.name, a.type, a.isin or "", a.wkn or "", a.comment or "", 1 if a.is_archived else 0]
                )

        # 2. Export transactions & snapshots using raw connection
        with self.db.get_raw_connection() as conn:
            txs = conn.execute("SELECT * FROM transactions").fetchall()
            with open(export_dir / "transactions.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "asset_id", "timestamp", "type", "amount", "comment"])
                for row in txs:
                    writer.writerow(
                        [row["id"], row["asset_id"], row["timestamp"], row["type"], row["amount"], row["comment"] or ""]
                    )

            snaps = conn.execute("SELECT * FROM snapshots").fetchall()
            with open(export_dir / "snapshots.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "asset_id", "timestamp", "value", "comment"])
                for row in snaps:
                    writer.writerow([row["id"], row["asset_id"], row["timestamp"], row["value"], row["comment"] or ""])

    def import_from_csv(self, import_dir: Path) -> dict[str, int]:
        """Import assets, transactions, and snapshots from CSVs in the specified directory."""
        assets_file = import_dir / "assets.csv"
        txs_file = import_dir / "transactions.csv"
        snaps_file = import_dir / "snapshots.csv"

        asset_id_map = {}
        imported_assets = 0
        imported_txs = 0
        imported_snaps = 0

        # 1. Import assets
        if assets_file.exists():
            with open(assets_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row["name"]
                    existing = self.db.find_asset(name)
                    if existing:
                        new_id = existing.id
                    else:
                        isin = row.get("isin") or None
                        wkn = row.get("wkn") or None
                        comment = row.get("comment") or None
                        is_archived = int(row.get("is_archived", 0))

                        new_asset = Asset(
                            id=None,
                            name=name,
                            type=row["type"],
                            isin=isin,
                            wkn=wkn,
                            comment=comment,
                            is_archived=bool(is_archived),
                        )
                        new_id = self.db.create_asset(new_asset)
                        if is_archived:
                            self.db.archive_asset(new_id, True)
                        imported_assets += 1

                    if new_id is not None:
                        asset_id_map[int(row["id"])] = new_id

        # 2. Import transactions
        if txs_file.exists():
            with open(txs_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    old_asset_id = int(row["asset_id"])
                    new_asset_id = asset_id_map.get(old_asset_id)
                    if new_asset_id is not None:
                        comment = row.get("comment") or None
                        tx = Transaction(
                            id=None,
                            asset_id=new_asset_id,
                            timestamp=row["timestamp"],
                            type=row["type"],
                            amount=float(row["amount"]),
                            comment=comment,
                        )
                        self.db.add_transaction(tx)
                        imported_txs += 1

        # 3. Import snapshots
        if snaps_file.exists():
            with open(snaps_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    old_asset_id = int(row["asset_id"])
                    new_asset_id = asset_id_map.get(old_asset_id)
                    if new_asset_id is not None:
                        comment = row.get("comment") or None
                        snap = Snapshot(
                            id=None,
                            asset_id=new_asset_id,
                            timestamp=row["timestamp"],
                            value=float(row["value"]),
                            comment=comment,
                        )
                        self.db.add_snapshot(snap)
                        imported_snaps += 1

        return {"assets": imported_assets, "transactions": imported_txs, "snapshots": imported_snaps}
