import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from drb_emu.catalog.catalog_objects import TableInfo
from drb_emu.catalog.object_names import TableName, normalize_name
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

    def resolve(self, sql: str) -> list[str]:
        try:
            statements = [statement for statement in sqlglot.parse(sql, read=self.read_dialect) if statement is not None]
        except SqlglotError as error:
            raise InvalidParameterValue("PARSE_SYNTAX_ERROR", str(error)) from error
        return [self._resolve_statement(statement).sql(dialect=self.write_dialect) for statement in statements]

    def _resolve_statement(self, statement: exp.Expression) -> exp.Expression:
        if not isinstance(statement, exp.Query):
            raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"Only queries are supported for now, got {statement.key.upper()}")
        return self._resolve_tables(statement, self.session.current_catalog, self.session.current_schema, 0)

    def _resolve_tables(self, query: exp.Query, default_catalog: str, default_schema: str, view_depth: int) -> exp.Query:
        if view_depth > self.max_view_depth:
            raise InvalidParameterValue("RECURSIVE_VIEW", f"Views are nested deeper than {self.max_view_depth} levels")
        cte_names = {cte.alias_or_name.lower() for cte in query.find_all(exp.CTE)}
        for table in list(query.find_all(exp.Table)):
            if not isinstance(table.this, exp.Identifier):
                continue
            if not table.db and (table.name in self.session.registered_views or table.name.lower() in cte_names):
                continue
            table_name = TableName(
                normalize_name(table.catalog or default_catalog),
                normalize_name(table.db or default_schema),
                normalize_name(table.name),
            )
            table_info = self.catalog_service.get_table(table_name.full_name)
            table.replace(self._replacement_for(table, table_info, view_depth))
        return query

    def _replacement_for(self, table: exp.Table, table_info: TableInfo, view_depth: int) -> exp.Expression:
        alias = table.args.get("alias") or exp.TableAlias(this=exp.to_identifier(table.name))
        if table_info.table_type == "VIEW":
            if table.args.get("version") is not None:
                raise UnsupportedStatement("UNSUPPORTED_FEATURE", f"Time travel is not supported on view {table_info.full_name}")
            view_query = sqlglot.parse_one(table_info.view_definition, read=self.read_dialect)
            resolved_view = self._resolve_tables(view_query, table_info.catalog_name, table_info.schema_name, view_depth + 1)
            return exp.Subquery(this=resolved_view, alias=alias)
        version = self._time_travel_version(table)
        internal_view_name = self._internal_view_name(table_info, version)
        self.session.bind_catalog_table(internal_view_name, table_info.storage_location, version)
        replacement = table.copy()
        replacement.set("this", exp.to_identifier(internal_view_name))
        replacement.set("db", None)
        replacement.set("catalog", None)
        replacement.set("version", None)
        replacement.set("alias", alias)
        return replacement

    def _time_travel_version(self, table: exp.Table) -> int | None:
        version = table.args.get("version")
        if version is None:
            return None
        version_value = version.expression
        is_version_number = isinstance(version_value, exp.Literal) and not version_value.is_string
        if version.this != "VERSION" or version.args.get("kind") != "AS OF" or not is_version_number:
            raise UnsupportedStatement("UNSUPPORTED_FEATURE", "Only VERSION AS OF <number> time travel is supported")
        return int(version_value.this)

    def _internal_view_name(self, table_info: TableInfo, version: int | None) -> str:
        version_suffix = "" if version is None else f"_v{version}"
        return f"{self.internal_view_prefix}{table_info.table_id}{version_suffix}"
