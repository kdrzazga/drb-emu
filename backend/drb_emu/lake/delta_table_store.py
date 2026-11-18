from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as pa_dataset
from deltalake import DeltaTable, write_deltalake

from drb_emu.lake.lake_path_resolver import LakePathResolver


class DeltaTableStore:

    def __init__(self, path_resolver: LakePathResolver):
        self.path_resolver = path_resolver
        self.write_modes = ("append", "overwrite", "error", "ignore")

    def exists(self, location: str | Path) -> bool:
        return DeltaTable.is_deltatable(self._table_uri(location))

    def write(self, location: str | Path, data: pa.Table, mode: str, partition_by: tuple[str, ...] = ()) -> int:
        if mode not in self.write_modes:
            raise ValueError(f"Unsupported write mode '{mode}', expected one of {self.write_modes}")
        table_uri = self._table_uri(location)
        write_deltalake(table_uri, data, mode=mode, partition_by=list(partition_by) or None)
        return DeltaTable(table_uri).version()

    def open(self, location: str | Path, version: int | None = None) -> DeltaTable:
        return DeltaTable(self._table_uri(location), version=version)

    def read(self, location: str | Path, version: int | None = None) -> pa.Table:
        return self.open(location, version).to_pyarrow_table()

    def dataset(self, location: str | Path, version: int | None = None) -> pa_dataset.Dataset:
        return self.open(location, version).to_pyarrow_dataset()

    def current_version(self, location: str | Path) -> int:
        return self.open(location).version()

    def history(self, location: str | Path, limit: int | None = None) -> list[dict]:
        return self.open(location).history(limit)

    def delete_rows(self, location: str | Path, predicate: str | None) -> dict:
        return self.open(location).delete(predicate)

    def _table_uri(self, location: str | Path) -> str:
        return self.path_resolver.resolve(location).as_uri()
