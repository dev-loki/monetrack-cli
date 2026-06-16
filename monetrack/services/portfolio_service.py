import csv
import datetime
from pathlib import Path

from monetrack.domain.models import (
    Asset,
    AssetStats,
    AssetType,
    GlobalSummary,
    HistoryEvent,
    MonthlyStats,
    Snapshot,
    Transaction,
    TransactionType,
)
from monetrack.ports.db_port import DatabasePort


class PortfolioService:
    def __init__(self, db: DatabasePort):
        self.db = db

    def init_db(self) -> None:
        self.db.init_db()

    def _validate_date(self, date_str: str) -> None:
        try:
            datetime.date.fromisoformat(date_str)
        except ValueError as err:
            raise ValueError(f"Invalid date format '{date_str}'. Must be YYYY-MM-DD.") from err

    def create_asset(
        self,
        name: str,
        asset_type: AssetType | str,
        isin: str | None = None,
        wkn: str | None = None,
        comment: str | None = None,
    ) -> int:
        if not name or not name.strip():
            raise ValueError("Asset name cannot be empty.")
        atype = AssetType(asset_type) if isinstance(asset_type, str) else asset_type
        asset = Asset(
            id=None,
            name=name,
            type=atype,
            isin=isin or "",
            wkn=wkn or "",
            comment=comment or "",
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
        tx_type: TransactionType | str,
        amount: float,
        timestamp: str,
        comment: str | None = None,
    ) -> int:
        if amount <= 0:
            raise ValueError("Transaction amount must be greater than zero.")
        self._validate_date(timestamp)
        tx = Transaction(
            id=None,
            asset_id=asset_id,
            timestamp=timestamp,
            type=TransactionType(tx_type),
            amount=amount,
            comment=comment or "",
        )
        return self.db.add_transaction(tx)

    def add_snapshot(
        self,
        asset_id: int,
        value: float,
        timestamp: str,
        comment: str | None = None,
    ) -> int:
        if value < 0:
            raise ValueError("Snapshot value cannot be negative.")
        self._validate_date(timestamp)
        snap = Snapshot(
            id=None,
            asset_id=asset_id,
            timestamp=timestamp,
            value=value,
            comment=comment or "",
        )
        return self.db.add_snapshot(snap)

    def get_asset_stats(self, asset_id: int) -> AssetStats:
        txs = [t for t in self.db.list_transactions() if t.asset_id == asset_id]
        snaps = [s for s in self.db.list_snapshots() if s.asset_id == asset_id]

        invest_sum = sum(t.amount for t in txs if t.type == TransactionType.INVEST)
        withdraw_sum = sum(t.amount for t in txs if t.type == TransactionType.WITHDRAW)
        net_invested = invest_sum - withdraw_sum

        if snaps:
            latest = snaps[-1]
            current_value = latest.value
            last_val_date = latest.timestamp
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
        assets = self.db.list_assets(include_archived=include_archived)
        txs = self.db.list_transactions()
        snaps = self.db.list_snapshots()

        txs_by_asset = {}
        for t in txs:
            txs_by_asset.setdefault(t.asset_id, []).append(t)

        snaps_by_asset = {}
        for s in snaps:
            snaps_by_asset.setdefault(s.asset_id, []).append(s)

        total_net_invested = 0.0
        total_current_value = 0.0
        total_earnings = 0.0
        total_invested = 0.0
        total_withdrawn = 0.0

        for asset in assets:
            if asset.id is None:
                continue
            a_txs = txs_by_asset.get(asset.id, [])
            a_snaps = snaps_by_asset.get(asset.id, [])

            invest_sum = sum(t.amount for t in a_txs if t.type == TransactionType.INVEST)
            withdraw_sum = sum(t.amount for t in a_txs if t.type == TransactionType.WITHDRAW)
            net_invested = invest_sum - withdraw_sum

            if a_snaps:
                current_value = a_snaps[-1].value
            else:
                current_value = net_invested

            earnings = current_value - net_invested

            total_net_invested += net_invested
            total_current_value += current_value
            total_earnings += earnings
            total_invested += invest_sum
            total_withdrawn += withdraw_sum

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

    def _get_single_valuation(
        self,
        asset_id: int,
        before_timestamp: str,
        snapshots_by_asset: dict[int, list[Snapshot]],
        transactions_by_asset: dict[int, list[Transaction]],
    ) -> float:
        snaps = snapshots_by_asset.get(asset_id, [])
        latest_snap = None
        for snap in snaps:
            if snap.timestamp >= before_timestamp:
                break
            latest_snap = snap

        start_time = latest_snap.timestamp if latest_snap else ""
        snap_value = latest_snap.value if latest_snap else 0.0

        txs = transactions_by_asset.get(asset_id, [])
        flow = 0.0
        for tx in txs:
            if tx.timestamp >= before_timestamp:
                break
            if tx.timestamp > start_time:
                match tx.type:
                    case TransactionType.INVEST:
                        flow += tx.amount
                    case TransactionType.WITHDRAW:
                        flow -= tx.amount

        return snap_value + flow

    def _get_valuation_before_in_memory(
        self,
        asset_id: int | None,
        before_timestamp: str,
        assets_map: dict[int, Asset],
        snapshots_by_asset: dict[int, list[Snapshot]],
        transactions_by_asset: dict[int, list[Transaction]],
        include_archived: bool = False,
    ) -> float:
        if asset_id is not None:
            return self._get_single_valuation(asset_id, before_timestamp, snapshots_by_asset, transactions_by_asset)

        total_val = 0.0
        for a_id, asset in assets_map.items():
            if not include_archived and asset.is_archived:
                continue
            total_val += self._get_single_valuation(a_id, before_timestamp, snapshots_by_asset, transactions_by_asset)
        return total_val

    def get_monthly_stats(self, asset_id: int | None = None, include_archived: bool = False) -> list[MonthlyStats]:
        assets = self.db.list_assets(include_archived=True)
        assets_map: dict[int, Asset] = {a.id: a for a in assets if a.id is not None}
        txs = self.db.list_transactions()
        snaps = self.db.list_snapshots()

        allowed_asset_ids = {a.id for a in assets if a.id is not None and (include_archived or not a.is_archived)}

        if asset_id is not None:
            txs = [t for t in txs if t.asset_id == asset_id]
            snaps = [s for s in snaps if s.asset_id == asset_id]
        else:
            txs = [t for t in txs if t.asset_id in allowed_asset_ids]
            snaps = [s for s in snaps if s.asset_id in allowed_asset_ids]

        months_set = set()
        for t in txs:
            months_set.add(t.timestamp[:7])
        for s in snaps:
            months_set.add(s.timestamp[:7])

        months = sorted(list(months_set))

        txs_by_asset = {}
        for t in txs:
            txs_by_asset.setdefault(t.asset_id, []).append(t)
        snaps_by_asset = {}
        for s in snaps:
            snaps_by_asset.setdefault(s.asset_id, []).append(s)

        stats_list = []
        for month in months:
            start_time = f"{month}-01"
            next_m = self._get_next_month(month)
            end_time = f"{next_m}-01"

            v_start = self._get_valuation_before_in_memory(
                asset_id, start_time, assets_map, snaps_by_asset, txs_by_asset, include_archived
            )
            v_end = self._get_valuation_before_in_memory(
                asset_id, end_time, assets_map, snaps_by_asset, txs_by_asset, include_archived
            )

            invest = sum(
                t.amount
                for t in txs
                if t.timestamp >= start_time and t.timestamp < end_time and t.type == TransactionType.INVEST
            )
            withdraw = sum(
                t.amount
                for t in txs
                if t.timestamp >= start_time and t.timestamp < end_time and t.type == TransactionType.WITHDRAW
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
        txs = [t for t in self.db.list_transactions() if t.asset_id == asset_id]
        snaps = [s for s in self.db.list_snapshots() if s.asset_id == asset_id]

        txs_by_asset = {asset_id: txs}
        snaps_by_asset = {asset_id: snaps}

        assets = self.db.list_assets(include_archived=True)
        assets_map: dict[int, Asset] = {a.id: a for a in assets if a.id == asset_id and a.id is not None}

        start_time = f"{month}-01"
        next_m = self._get_next_month(month)
        end_time = f"{next_m}-01"

        v_start = self._get_valuation_before_in_memory(
            asset_id, start_time, assets_map, snaps_by_asset, txs_by_asset, include_archived=True
        )
        v_end = self._get_valuation_before_in_memory(
            asset_id, end_time, assets_map, snaps_by_asset, txs_by_asset, include_archived=True
        )

        invest = sum(
            t.amount
            for t in txs
            if t.timestamp >= start_time and t.timestamp < end_time and t.type == TransactionType.INVEST
        )
        withdraw = sum(
            t.amount
            for t in txs
            if t.timestamp >= start_time and t.timestamp < end_time and t.type == TransactionType.WITHDRAW
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
        assets = self.db.list_assets(include_archived=include_archived)
        txs = self.db.list_transactions()
        snaps = self.db.list_snapshots()

        txs_by_asset = {}
        for t in txs:
            txs_by_asset.setdefault(t.asset_id, []).append(t)
        snaps_by_asset = {}
        for s in snaps:
            snaps_by_asset.setdefault(s.asset_id, []).append(s)

        by_type: dict[str, dict[str, float]] = {}

        for asset in assets:
            if asset.id is None:
                continue
            t = str(asset.type)

            a_txs = txs_by_asset.get(asset.id, [])
            a_snaps = snaps_by_asset.get(asset.id, [])

            invest_sum = sum(tx.amount for tx in a_txs if tx.type == TransactionType.INVEST)
            withdraw_sum = sum(tx.amount for tx in a_txs if tx.type == TransactionType.WITHDRAW)
            net_invested = invest_sum - withdraw_sum

            if a_snaps:
                current_value = a_snaps[-1].value
            else:
                current_value = net_invested

            earnings = current_value - net_invested

            if t not in by_type:
                by_type[t] = {
                    "net_invested": 0.0,
                    "current_value": 0.0,
                    "earnings": 0.0,
                    "total_invested": 0.0,
                    "total_withdrawn": 0.0,
                }
            by_type[t]["net_invested"] += net_invested
            by_type[t]["current_value"] += current_value
            by_type[t]["earnings"] += earnings
            by_type[t]["total_invested"] += invest_sum
            by_type[t]["total_withdrawn"] += withdraw_sum

        for data in by_type.values():
            data["roi"] = (data["earnings"] / data["net_invested"] * 100.0) if data["net_invested"] > 0 else 0.0

        return by_type

    def get_history(self, asset_id: int | None = None, event_type: str | None = None) -> list[HistoryEvent]:
        return self.db.get_history(asset_id=asset_id, event_type=event_type)

    def update_asset(
        self,
        asset_id: int,
        name: str | None = None,
        type: AssetType | str | None = None,
        isin: str | None = None,
        wkn: str | None = None,
        comment: str | None = None,
    ) -> None:
        if name is not None and (not name or not name.strip()):
            raise ValueError("Asset name cannot be empty.")
        atype = AssetType(type) if isinstance(type, str) else type
        self.db.update_asset(asset_id, name, atype, isin, wkn, comment)

    def update_transaction(
        self,
        tx_id: int,
        amount: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
        type: TransactionType | str | None = None,
    ) -> None:
        if amount is not None and amount <= 0:
            raise ValueError("Transaction amount must be greater than zero.")
        if timestamp is not None:
            self._validate_date(timestamp)
        ttype = TransactionType(type) if isinstance(type, str) else type
        self.db.update_transaction(tx_id, amount, timestamp, comment, ttype)

    def update_snapshot(
        self,
        snap_id: int,
        value: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
    ) -> None:
        if value is not None and value < 0:
            raise ValueError("Snapshot value cannot be negative.")
        if timestamp is not None:
            self._validate_date(timestamp)
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
                writer.writerow([a.id, a.name, a.type.value, a.isin, a.wkn, a.comment, 1 if a.is_archived else 0])

        # 2. Export transactions & snapshots
        txs = self.db.list_transactions()
        with open(export_dir / "transactions.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "asset_id", "timestamp", "type", "amount", "comment"])
            for tx in txs:
                writer.writerow([tx.id, tx.asset_id, tx.timestamp, tx.type.value, tx.amount, tx.comment])

        snaps = self.db.list_snapshots()
        with open(export_dir / "snapshots.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "asset_id", "timestamp", "value", "comment"])
            for snap in snaps:
                writer.writerow([snap.id, snap.asset_id, snap.timestamp, snap.value, snap.comment])

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
                        isin = row.get("isin") or ""
                        wkn = row.get("wkn") or ""
                        comment = row.get("comment") or ""
                        is_archived = int(row.get("is_archived", 0))

                        new_asset = Asset(
                            id=None,
                            name=name,
                            type=AssetType(row["type"]),
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
                        comment = row.get("comment") or ""
                        tx = Transaction(
                            id=None,
                            asset_id=new_asset_id,
                            timestamp=row["timestamp"],
                            type=TransactionType(row["type"]),
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
                        comment = row.get("comment") or ""
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
