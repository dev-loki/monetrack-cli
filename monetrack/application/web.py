from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from monetrack.domain.models import AssetType, TransactionType
from monetrack.ports.db_adapter import SQLiteDatabaseAdapter
from monetrack.services.portfolio_service import PortfolioService

app = FastAPI(
    title="MoneTrack API",
    description="Backend API for MoneTrack portfolio tracking dashboard",
    version="1.1.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy initialization of service
db_adapter = SQLiteDatabaseAdapter()
service = PortfolioService(db_adapter)
service.init_db()


# --- Pydantic Schemas ---
class AssetCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Asset name")
    type: str = Field(..., description="Asset type (p2p, stock, etf, crypto, other)")
    isin: str | None = None
    wkn: str | None = None
    comment: str | None = None


class TransactionCreateSchema(BaseModel):
    asset_id: int
    type: str = Field(..., description="Transaction type (invest, withdraw)")
    amount: float = Field(..., gt=0, description="Amount in EUR")
    timestamp: str = Field(..., description="Date formatted as YYYY-MM-DD")
    comment: str | None = None


class SnapshotCreateSchema(BaseModel):
    asset_id: int
    value: float = Field(..., ge=0, description="Current valuation value in EUR")
    timestamp: str = Field(..., description="Date formatted as YYYY-MM-DD")
    comment: str | None = None


# --- API Routes ---
@app.get("/api/summary")
def get_summary() -> dict[str, Any]:
    try:
        summary = service.get_global_summary()
        return {
            "net_invested": summary.net_invested,
            "current_value": summary.current_value,
            "earnings": summary.earnings,
            "roi": summary.roi,
            "total_invested": summary.total_invested,
            "total_withdrawn": summary.total_withdrawn,
            "asset_count": summary.asset_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/assets")
def get_assets() -> list[dict[str, Any]]:
    try:
        assets = service.list_assets()
        result = []
        for asset in assets:
            if asset.id is None:
                continue
            stats = service.get_asset_stats(asset.id)
            result.append(
                {
                    "id": asset.id,
                    "name": asset.name,
                    "type": asset.type.value,
                    "isin": asset.isin,
                    "wkn": asset.wkn,
                    "comment": asset.comment,
                    "stats": {
                        "net_invested": stats.net_invested,
                        "current_value": stats.current_value,
                        "earnings": stats.earnings,
                        "roi": stats.roi,
                    },
                }
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/assets", status_code=201)
def create_asset(data: AssetCreateSchema) -> dict[str, Any]:
    valid_types = [t.value for t in AssetType]
    if data.type.lower() not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type. Must be one of: {', '.join(valid_types)}",
        )
    try:
        asset_id = service.create_asset(
            name=data.name,
            asset_type=data.type.lower(),
            isin=data.isin,
            wkn=data.wkn,
            comment=data.comment,
        )
        return {"id": asset_id, "message": "Asset created successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: int) -> dict[str, str]:
    try:
        service.delete_asset(asset_id)
        return {"message": "Asset deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/transactions")
def get_transactions() -> list[dict[str, Any]]:
    try:
        txs = db_adapter.list_transactions()
        # sort by date descending
        txs = sorted(txs, key=lambda x: x.timestamp, reverse=True)
        return [
            {
                "id": tx.id,
                "asset_id": tx.asset_id,
                "timestamp": tx.timestamp,
                "type": tx.type.value,
                "amount": tx.amount,
                "comment": tx.comment,
            }
            for tx in txs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/transactions", status_code=201)
def create_transaction(data: TransactionCreateSchema) -> dict[str, Any]:
    valid_types = [t.value for t in TransactionType]
    if data.type.lower() not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transaction type. Must be one of: {', '.join(valid_types)}",
        )
    try:
        tx_id = service.add_transaction(
            asset_id=data.asset_id,
            tx_type=data.type.lower(),
            amount=data.amount,
            timestamp=data.timestamp,
            comment=data.comment,
        )
        return {"id": tx_id, "message": "Transaction logged successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/snapshots")
def get_snapshots() -> list[dict[str, Any]]:
    try:
        snaps = db_adapter.list_snapshots()
        # sort by date descending
        snaps = sorted(snaps, key=lambda x: x.timestamp, reverse=True)
        return [
            {
                "id": snap.id,
                "asset_id": snap.asset_id,
                "timestamp": snap.timestamp,
                "value": snap.value,
                "comment": snap.comment,
            }
            for snap in snaps
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/snapshots", status_code=201)
def create_snapshot(data: SnapshotCreateSchema) -> dict[str, Any]:
    try:
        snap_id = service.add_snapshot(
            asset_id=data.asset_id,
            value=data.value,
            timestamp=data.timestamp,
            comment=data.comment,
        )
        return {"id": snap_id, "message": "Valuation snapshot logged successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- Mount Static Files ---
static_path = Path(__file__).parent / "static"
if not static_path.exists():
    static_path.mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
