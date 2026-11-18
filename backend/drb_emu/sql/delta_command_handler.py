import json
from datetime import datetime, timezone

import pyarrow as pa
from sqlglot import exp

from drb_emu.catalog.catalog_objects import TableInfo
from drb_emu.catalog.object_names import TableName
from drb_emu.catalog.unity_catalog_service import UnityCatalogService
from drb_emu.errors import InvalidParameterValue
from drb_emu.lake import DeltaTableStore
from drb_emu.sql.statement_parser import EmulatorCommand
from drb_emu.sql.table_resolver import TableResolver


class DeltaCommandHandler:

    def __init__(self, catalog_service: UnityCatalogService, delta_store: DeltaTableStore, table_resolver: TableResolver):
        self.catalog_service = catalog_service
        self.delta_store = delta_store
        self.table_resolver = table_resolver

    def describe_history(self, describe: exp.Describe) -> pa.Table:
        table_info = self._delta_table(self.table_resolver.table_name(describe.this))
        history = self.delta_store.history(table_info.storage_location)
        return pa.table({
            "version": pa.array([entry.get("version") for entry in history], pa.int64()),
            "timestamp": pa.array([self._moment(entry.get("timestamp")) for entry in history], pa.timestamp("ms", tz="UTC")),
            "operation": pa.array([self.delta_store.operation_of(entry) for entry in history], pa.string()),
            "operationParameters": pa.array([json.dumps(entry.get("operationParameters", {}), default=str) for entry in history], pa.string()),
            "operationMetrics": pa.array([json.dumps(entry.get("operationMetrics", {}), default=str) for entry in history], pa.string()),
            "engineInfo": pa.array([entry.get("engineInfo") for entry in history], pa.string()),
        })

    def describe_detail(self, command: EmulatorCommand) -> pa.Table:
        table_info = self._delta_table(self.table_resolver.table_name_from_text(command.groups["name"]))
        detail = self.delta_store.detail(table_info.storage_location)
        return pa.table({
            "format": pa.array(["delta"], pa.string()),
            "id": pa.array([detail["id"]], pa.string()),
            "name": pa.array([table_info.full_name], pa.string()),
            "description": pa.array([table_info.comment], pa.string()),
            "location": pa.array([table_info.storage_location], pa.string()),
            "createdAt": pa.array([self._moment(table_info.created_at)], pa.timestamp("ms", tz="UTC")),
            "lastModified": pa.array([self._moment(table_info.updated_at)], pa.timestamp("ms", tz="UTC")),
            "partitionColumns": pa.array([detail["partition_columns"]], pa.list_(pa.string())),
            "numFiles": pa.array([detail["num_files"]], pa.int64()),
            "sizeInBytes": pa.array([detail["size_in_bytes"]], pa.int64()),
            "version": pa.array([detail["version"]], pa.int64()),
        })

    def restore(self, command: EmulatorCommand) -> pa.Table:
        table_info = self._delta_table(self.table_resolver.table_name_from_text(command.groups["name"]))
        version_text = command.groups["version"]
        target = int(version_text) if version_text is not None else self.table_resolver.parse_timestamp(command.groups["timestamp"])
        metrics = self.delta_store.restore(table_info.storage_location, target)
        self.catalog_service.touch_table(table_info.full_name)
        return pa.table({
            "num_removed_files": pa.array([metrics.get("numRemovedFile", 0)], pa.int64()),
            "num_restored_files": pa.array([metrics.get("numRestoredFile", 0)], pa.int64()),
        })

    def optimize(self, command: EmulatorCommand) -> pa.Table:
        table_info = self._delta_table(self.table_resolver.table_name_from_text(command.groups["name"]))
        metrics = self.delta_store.optimize(table_info.storage_location)
        return pa.table({
            "path": pa.array([table_info.storage_location], pa.string()),
            "metrics": pa.array([json.dumps(metrics, default=str)], pa.string()),
        })

    def vacuum(self, command: EmulatorCommand) -> pa.Table:
        table_info = self._delta_table(self.table_resolver.table_name_from_text(command.groups["name"]))
        retention_hours = int(command.groups["hours"]) if command.groups["hours"] is not None else None
        deleted_files = self.delta_store.vacuum(table_info.storage_location, retention_hours)
        return pa.table({
            "path": pa.array([table_info.storage_location], pa.string()),
            "num_deleted_files": pa.array([len(deleted_files)], pa.int64()),
        })

    def _delta_table(self, table_name: TableName) -> TableInfo:
        table_info = self.catalog_service.get_table(table_name.full_name)
        if table_info.table_type == "VIEW":
            raise InvalidParameterValue("EXPECT_TABLE_NOT_VIEW", f"{table_name.quoted} is a view, not a Delta table")
        return table_info

    def _moment(self, epoch_milliseconds: int | None) -> datetime | None:
        return datetime.fromtimestamp(epoch_milliseconds / 1000, tz=timezone.utc) if epoch_milliseconds is not None else None
