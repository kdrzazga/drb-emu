from pathlib import Path

import pyarrow as pa
import pytest

from drb_emu.lake import DeltaTableStore, LakePathResolver
from drb_emu.sql import DuckDBSession


@pytest.fixture
def lake_root(tmp_path: Path) -> Path:
    root = tmp_path / "lake"
    root.mkdir()
    return root


@pytest.fixture
def path_resolver(lake_root: Path) -> LakePathResolver:
    return LakePathResolver(lake_root)


@pytest.fixture
def delta_store(path_resolver: LakePathResolver) -> DeltaTableStore:
    return DeltaTableStore(path_resolver)


@pytest.fixture
def session(delta_store: DeltaTableStore):
    with DuckDBSession(delta_store) as duckdb_session:
        yield duckdb_session


@pytest.fixture
def orders() -> pa.Table:
    return pa.table({
        "order_id": pa.array([1, 2, 3], pa.int64()),
        "amount": pa.array([10.0, 20.5, 7.25], pa.float64()),
        "country": pa.array(["PL", "DE", "PL"], pa.string()),
    })
