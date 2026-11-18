from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as pa_dataset
from deltalake import CommitProperties, DeltaTable, write_deltalake

from drb_emu.errors import InvalidParameterValue
from drb_emu.lake.lake_path_resolver import LakePathResolver


class DeltaTableStore:

    def __init__(self, path_resolver: LakePathResolver):
        self.path_resolver = path_resolver
        self.write_modes = ("append", "overwrite", "error", "ignore")
        self.operation_metadata_key = "drb.operation"
        self.unix_epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def exists(self, location: str | Path) -> bool:
        return DeltaTable.is_deltatable(self._table_uri(location))

    def write(self, location: str | Path, data: pa.Table, mode: str, partition_by: tuple[str, ...] = (), operation: str | None = None) -> int:
        if mode not in self.write_modes:
            raise ValueError(f"Unsupported write mode '{mode}', expected one of {self.write_modes}")
        table_uri = self._table_uri(location)
        commit_properties = CommitProperties(custom_metadata={self.operation_metadata_key: operation}) if operation else None
        write_deltalake(table_uri, data, mode=mode, partition_by=list(partition_by) or None, commit_properties=commit_properties)
        return DeltaTable(table_uri).version()

    def open(self, location: str | Path, version: int | datetime | None = None) -> DeltaTable:
        if isinstance(version, datetime):
            version = self.version_at(location, version)
        return DeltaTable(self._table_uri(location), version=version)

    def version_at(self, location: str | Path, moment: datetime) -> int:
        moment_milliseconds = (moment - self.unix_epoch) // timedelta(milliseconds=1)
        committed_versions = [entry["version"] for entry in self.history(location) if entry.get("timestamp", 0) <= moment_milliseconds]
        if not committed_versions:
            raise InvalidParameterValue("DELTA_TIMESTAMP_BEFORE_FIRST_COMMIT", f"No version of {location} existed at {moment.isoformat()}")
        return max(committed_versions)

    def read(self, location: str | Path, version: int | datetime | None = None) -> pa.Table:
        return self.open(location, version).to_pyarrow_table()

    def dataset(self, location: str | Path, version: int | datetime | None = None) -> pa_dataset.Dataset:
        return self.open(location, version).to_pyarrow_dataset()

    def schema(self, location: str | Path) -> pa.Schema:
        return self.dataset(location).schema

    def partition_columns(self, location: str | Path) -> tuple[str, ...]:
        return tuple(self.open(location).metadata().partition_columns)

    def current_version(self, location: str | Path) -> int:
        return self.open(location).version()

    def history(self, location: str | Path, limit: int | None = None) -> list[dict]:
        return self.open(location).history(limit)

    def operation_of(self, history_entry: dict) -> str:
        return history_entry.get(self.operation_metadata_key) or history_entry.get("operation", "")

    def delete_rows(self, location: str | Path, predicate: str | None) -> dict:
        return self.open(location).delete(predicate)

    def restore(self, location: str | Path, target: int | datetime) -> dict:
        target_version = self.version_at(location, target) if isinstance(target, datetime) else target
        return self.open(location).restore(target_version)

    def optimize(self, location: str | Path) -> dict:
        return self.open(location).optimize.compact()

    def vacuum(self, location: str | Path, retention_hours: int | None) -> list[str]:
        return self.open(location).vacuum(retention_hours=retention_hours, dry_run=False, enforce_retention_duration=False)

    def detail(self, location: str | Path) -> dict:
        table = self.open(location)
        table_folder = self.path_resolver.resolve(location)
        data_files = [path for path in table_folder.rglob("*.parquet")]
        active_file_names = {Path(uri).name for uri in table.file_uris()}
        active_files = [path for path in data_files if path.name in active_file_names]
        return {
            "id": table.metadata().id,
            "created_at": table.metadata().created_time,
            "partition_columns": list(table.metadata().partition_columns),
            "num_files": len(active_files),
            "size_in_bytes": sum(path.stat().st_size for path in active_files),
            "version": table.version(),
        }

    def _table_uri(self, location: str | Path) -> str:
        return self.path_resolver.resolve(location).as_uri()
