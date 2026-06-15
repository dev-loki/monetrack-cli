from monetrack.domain.models import Asset, Snapshot, Transaction


def test_asset_creation() -> None:
    asset = Asset(
        id=1,
        name="Test Asset",
        type="stock",
        isin="IE00B4L5Y983",
        wkn="A0RPWH",
        comment="Test comment",
        is_archived=False,
    )
    assert asset.id == 1
    assert asset.name == "Test Asset"
    assert asset.type == "stock"
    assert asset.isin == "IE00B4L5Y983"
    assert asset.wkn == "A0RPWH"
    assert asset.comment == "Test comment"
    assert not asset.is_archived


def test_transaction_creation() -> None:
    tx = Transaction(
        id=1,
        asset_id=1,
        timestamp="2025-01-01",
        type="invest",
        amount=100.0,
        comment="Tx comment",
    )
    assert tx.id == 1
    assert tx.asset_id == 1
    assert tx.timestamp == "2025-01-01"
    assert tx.type == "invest"
    assert tx.amount == 100.0
    assert tx.comment == "Tx comment"


def test_snapshot_creation() -> None:
    snap = Snapshot(
        id=1,
        asset_id=1,
        timestamp="2025-01-01",
        value=150.0,
        comment="Snap comment",
    )
    assert snap.id == 1
    assert snap.asset_id == 1
    assert snap.timestamp == "2025-01-01"
    assert snap.value == 150.0
    assert snap.comment == "Snap comment"
