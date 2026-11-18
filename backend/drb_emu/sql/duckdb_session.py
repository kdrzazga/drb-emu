from pathlib import Path

import duckdb
import pyarrow as pa

from drb_emu.lake.delta_table_store import DeltaTableStore


class DuckDBSession:

    def __init__(self, delta_store: DeltaTableStore):
        self.delta_store = delta_store
        self.connection = duckdb.connect(database=":memory:")
        self.current_catalog = "main"
        self.current_schema = "default"
        self.spark_conf = {"spark.sql.session.timeZone": "UTC", "spark.sql.ansi.enabled": "true"}
        self.registered_views = set()

    def use_catalog(self, catalog: str):
        self.current_catalog = catalog
        self.current_schema = "default"

    def use_schema(self, schema: str):
        self.current_schema = schema

    def register_delta_table(self, view_name: str, location: str | Path, version: int | None = None):
        self.connection.register(view_name, self.delta_store.dataset(location, version))
        self.registered_views.add(view_name)

    def bind_catalog_table(self, internal_view_name: str, location: str | Path, version: int | None):
        self.connection.register(internal_view_name, self.delta_store.dataset(location, version))

    def register_arrow(self, view_name: str, data: pa.Table):
        self.connection.register(view_name, data)
        self.registered_views.add(view_name)

    def unregister(self, view_name: str):
        self.connection.unregister(view_name)
        self.registered_views.discard(view_name)

    def execute(self, sql: str, parameters: list | dict | None = None) -> pa.Table:
        relation = self.connection.sql(sql, params=parameters)
        if relation is None:
            return pa.table({})
        return relation.to_arrow_table()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.close()
