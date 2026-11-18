from pathlib import Path

import pyarrow as pa
import pytest

from drb_emu.lake import DeltaTableStore, LakePathResolver
from drb_emu.sql import DuckDBSession
from drb_emu.workspace import Workspace


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
def workspace(tmp_path: Path):
    drb_workspace = Workspace(tmp_path / "lake", tmp_path / "metastore" / "metastore.db")
    yield drb_workspace
    drb_workspace.close()


@pytest.fixture
def orders() -> pa.Table:
    return pa.table({
        "order_id": pa.array([1, 2, 3], pa.int64()),
        "amount": pa.array([10.0, 20.5, 7.25], pa.float64()),
        "country": pa.array(["PL", "DE", "PL"], pa.string()),
    })
