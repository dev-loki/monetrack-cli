import sqlite3
from typing import Protocol

from monetrack.domain.models import (
    Asset,
    AssetStats,
    GlobalSummary,
    HistoryEvent,
    MonthlyStats,
    Snapshot,
    Transaction,
)


class DatabasePort(Protocol):
    def init_db(self) -> None:
        """Initialize database schema."""
        ...

    def create_asset(self, asset: Asset) -> int:
        """Create a new asset and return its ID."""
        ...

    def list_assets(self, include_archived: bool = False) -> list[Asset]:
        """List tracked assets."""
        ...

    def find_asset(self, query: str) -> Asset | None:
        """Find a single asset by name, ID, ISIN, or WKN."""
        ...

    def delete_asset(self, asset_id: int) -> None:
        """Permanently delete an asset and all related data."""
        ...

    def rename_asset(self, asset_id: int, new_name: str) -> None:
        """Rename an asset."""
        ...

    def archive_asset(self, asset_id: int, is_archived: bool) -> None:
        """Archive or unarchive an asset."""
        ...

    def add_transaction(self, tx: Transaction) -> int:
        """Add an investment or withdrawal transaction."""
        ...

    def add_snapshot(self, snap: Snapshot) -> int:
        """Add a valuation snapshot."""
        ...

    def get_asset_stats(self, asset_id: int) -> AssetStats:
        """Calculate performance stats for a single asset."""
        ...

    def get_global_summary(self, include_archived: bool = False) -> GlobalSummary:
        """Calculate overall statistics across all assets."""
        ...

    def get_monthly_stats(self, asset_id: int | None = None, include_archived: bool = False) -> list[MonthlyStats]:
        """Aggregate stats on a month-by-month basis."""
        ...

    def get_asset_monthly_stats(self, asset_id: int, month: str) -> MonthlyStats:
        """Calculate monthly stats for a single asset."""
        ...

    def get_type_stats(self, include_archived: bool = False) -> dict[str, dict[str, float]]:
        """Aggregate stats grouped by asset type."""
        ...

    def get_history(self, asset_id: int | None = None, event_type: str | None = None) -> list[HistoryEvent]:
        """Get chronological transaction and snapshot history."""
        ...

    def update_asset(
        self,
        asset_id: int,
        name: str | None = None,
        type: str | None = None,
        isin: str | None = None,
        wkn: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Update an existing asset's details."""
        ...

    def update_transaction(
        self,
        tx_id: int,
        amount: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
        type: str | None = None,
    ) -> None:
        """Update an existing transaction."""
        ...

    def update_snapshot(
        self,
        snap_id: int,
        value: float | None = None,
        timestamp: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Update an existing snapshot."""
        ...

    def get_raw_connection(self) -> sqlite3.Connection:
        """Return raw database connection for transactions/migrations."""
        ...
