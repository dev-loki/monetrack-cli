from dataclasses import dataclass


@dataclass
class Asset:
    id: int | None
    name: str
    type: str  # p2p, stock, etf, crypto, other
    isin: str | None = None
    wkn: str | None = None
    comment: str | None = None
    is_archived: bool = False


@dataclass
class Transaction:
    id: int | None
    asset_id: int
    timestamp: str
    type: str  # invest, withdraw
    amount: float
    comment: str | None = None


@dataclass
class Snapshot:
    id: int | None
    asset_id: int
    timestamp: str
    value: float
    comment: str | None = None


@dataclass
class AssetStats:
    net_invested: float
    current_value: float
    earnings: float
    roi: float
    last_valuation_date: str
    total_invested: float
    total_withdrawn: float


@dataclass
class GlobalSummary:
    net_invested: float
    current_value: float
    earnings: float
    roi: float
    total_invested: float
    total_withdrawn: float
    asset_count: int


@dataclass
class MonthlyStats:
    month: str
    valuation_start: float
    valuation_end: float
    invested: float
    withdrawn: float
    net_flow: float
    earnings: float


@dataclass
class HistoryEvent:
    source: str  # 'transaction' or 'snapshot'
    id: int
    timestamp: str
    event_type: str  # invest, withdraw, snapshot
    value: float
    comment: str | None
    asset_name: str
