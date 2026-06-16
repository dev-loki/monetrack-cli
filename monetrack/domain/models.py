from dataclasses import dataclass
from enum import StrEnum


class AssetType(StrEnum):
    P2P = "p2p"
    STOCK = "stock"
    ETF = "etf"
    CRYPTO = "crypto"
    OTHER = "other"


class TransactionType(StrEnum):
    INVEST = "invest"
    WITHDRAW = "withdraw"


@dataclass(slots=True)
class Asset:
    id: int | None
    name: str
    type: AssetType
    isin: str = ""
    wkn: str = ""
    comment: str = ""
    is_archived: bool = False


@dataclass(slots=True)
class Transaction:
    id: int | None
    asset_id: int
    timestamp: str
    type: TransactionType
    amount: float
    comment: str = ""


@dataclass(slots=True)
class Snapshot:
    id: int | None
    asset_id: int
    timestamp: str
    value: float
    comment: str = ""


@dataclass(slots=True)
class AssetStats:
    net_invested: float
    current_value: float
    earnings: float
    roi: float
    last_valuation_date: str
    total_invested: float
    total_withdrawn: float


@dataclass(slots=True)
class GlobalSummary:
    net_invested: float
    current_value: float
    earnings: float
    roi: float
    total_invested: float
    total_withdrawn: float
    asset_count: int


@dataclass(slots=True)
class MonthlyStats:
    month: str
    valuation_start: float
    valuation_end: float
    invested: float
    withdrawn: float
    net_flow: float
    earnings: float


@dataclass(slots=True)
class HistoryEvent:
    source: str  # 'transaction' or 'snapshot'
    id: int
    timestamp: str
    event_type: str  # invest, withdraw, snapshot
    value: float
    comment: str
    asset_name: str
