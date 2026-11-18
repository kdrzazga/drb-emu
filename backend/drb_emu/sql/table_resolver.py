from datetime import datetime, timezone

import sqlglot
from sqlglot import exp

from drb_emu.catalog.catalog_objects import TableInfo
from drb_emu.catalog.object_names import SchemaName, TableName, normalize_name
from drb_emu.catalog.unity_catalog_service import UnityCatalogService
from drb_emu.errors import InvalidParameterValue, UnsupportedStatement
from drb_emu.sql.duckdb_session import DuckDBSession


class TableResolver:

    def __init__(self, catalog_service: UnityCatalogService, session: DuckDBSession):
        self.catalog_service = catalog_service
        self.session = session
        self.read_dialect = "databricks"
        self.write_dialect = "duckdb"
        self.max_view_depth = 32
        self.internal_view_prefix = "__uc_"

    def resolve_query(self, query: exp.Query) -> str:
        return self.resolve_references(query).sql(dialect=self.write_dialect)

    def resolve_references(self, expression: exp.Expression, excluded_table: exp.Table | None = None) -> exp.Expression:
        return self._resolve_tables(expression, self.session.current_catalog, self.session.current_schema, 0, excluded_table)

    def table_name(self, table: exp.Table) -> TableName:
        part_names = [part.name for part in table.parts]
        if len(part_names) == 1:
            return TableName(normalize_name(self.session.current_catalog), normalize_name(self.session.current_schema), normalize_name(part_names[0]))
        if len(part_names) == 2:
            return TableName(normalize_name(self.session.current_catalog), normalize_name(part_names[0]), normalize_name(part_names[1]))
        if len(part_names) == 3:
            return TableName(*(normalize_name(part) for part in part_names))
        raise InvalidParameterValue("INVALID_IDENTIFIER", f"Invalid table name '{table.sql(dialect=self.read_dialect)}'")

    def table_name_from_text(self, text: str) -> TableName:
        return self.table_name(exp.to_table(text, dialect=self.read_dialect))

    def schema_name(self, reference: exp.Table) -> SchemaName:
        part_names = [part.name for part in reference.parts]
        if len(part_names) == 1:
            return SchemaName(normalize_name(self.session.current_catalog), normalize_name(part_names[0]))
        if len(part_names) == 2:
            return SchemaName(*(normalize_name(part) for part in part_names))
        raise InvalidParameterValue("INVALID_IDENTIFIER", f"Invalid schema name '{reference.sql(dialect=self.read_dialect)}'")

    def is_session_view(self, table: exp.Table) -> bool:
        return len(table.parts) == 1 and self.session.is_session_object(table.name)

    def _resolve_tables(self, expression: exp.Expression, default_catalog: str, default_schema: str, view_depth: int,
                        excluded_table: exp.Table | None = None) -> exp.Expression:
        if view_depth > self.max_view_depth:
            raise InvalidParameterValue("RECURSIVE_VIEW", f"Views are nested deeper than {self.max_view_depth} levels")
        cte_names = {cte.alias_or_name.lower() for cte in expression.find_all(exp.CTE)}
        for table in list(expression.find_all(exp.Table)):
            if table is excluded_table or not isinstance(table.this, exp.Identifier):
                continue
            if not table.db and (self.session.is_session_object(table.name) or table.name.lower() in cte_names):
                continue
            table_name = TableName(
                normalize_name(table.catalog or default_catalog),
                normalize_name(table.db or default_schema),
                normalize_name(table.name),
            )
            table_info = self.catalog_service.get_table(table_name.full_name)
            table.replace(self._replacement_for(table, table_info, view_depth))
        return expression

    def _replacement_for(self, table: exp.Table, table_info: TableInfo, view_depth: int) -> exp.Expression:
        alias = table.args.get("alias") or exp.TableAlias(this=exp.to_identifier(table.name))
        if table_info.table_type == "VIEW":
            if table.args.get("version") is not None:
                raise UnsupportedStatement("UNSUPPORTED_FEATURE", f"Time travel is not supported on view {table_info.full_name}")
            view_query = sqlglot.parse_one(table_info.view_definition, read=self.read_dialect)
            resolved_view = self._resolve_tables(view_query, table_info.catalog_name, table_info.schema_name, view_depth + 1)
            return exp.Subquery(this=resolved_view, alias=alias)
        snapshot = self._time_travel_snapshot(table)
        internal_view_name = self._internal_view_name(table_info, snapshot)
        self.session.bind_catalog_table(internal_view_name, table_info.storage_location, snapshot)
        replacement = table.copy()
        replacement.set("this", exp.to_identifier(internal_view_name))
        replacement.set("db", None)
        replacement.set("catalog", None)
        replacement.set("version", None)
        replacement.set("alias", alias)
        return replacement

    def _time_travel_snapshot(self, table: exp.Table) -> int | datetime | None:
        version = table.args.get("version")
        if version is None:
            return None
        if version.args.get("kind") != "AS OF" or not isinstance(version.expression, exp.Literal):
            raise UnsupportedStatement("UNSUPPORTED_FEATURE", "Only VERSION AS OF <number> and TIMESTAMP AS OF '<timestamp>' are supported")
        if version.this == "VERSION" and not version.expression.is_string:
            return int(version.expression.this)
        if version.this == "TIMESTAMP" and version.expression.is_string:
            return self.parse_timestamp(version.expression.this)
        raise UnsupportedStatement("UNSUPPORTED_FEATURE", "Only VERSION AS OF <number> and TIMESTAMP AS OF '<timestamp>' are supported")

    def parse_timestamp(self, text: str) -> datetime:
        try:
            moment = datetime.fromisoformat(text)
        except ValueError as error:
            raise InvalidParameterValue("INVALID_TIMESTAMP", f"Cannot parse timestamp '{text}'") from error
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)

    def _internal_view_name(self, table_info: TableInfo, snapshot: int | datetime | None) -> str:
        if snapshot is None:
            return f"{self.internal_view_prefix}{table_info.table_id}"
        if isinstance(snapshot, datetime):
            return f"{self.internal_view_prefix}{table_info.table_id}_t{int(snapshot.timestamp() * 1000)}"
        return f"{self.internal_view_prefix}{table_info.table_id}_v{snapshot}"
