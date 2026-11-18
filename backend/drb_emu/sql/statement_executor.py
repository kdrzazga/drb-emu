import time
from uuid import uuid4

import pyarrow as pa
from sqlglot import exp

from drb_emu.errors import DrbError, InvalidParameterValue, UnsupportedStatement
from drb_emu.history import QueryHistoryService, QueryInfo
from drb_emu.sql.catalog_command_handler import CatalogCommandHandler
from drb_emu.sql.delta_command_handler import DeltaCommandHandler
from drb_emu.sql.duckdb_session import DuckDBSession
from drb_emu.sql.statement_parser import EmulatorCommand, StatementParser
from drb_emu.sql.table_resolver import TableResolver
from drb_emu.sql.table_write_handler import TableWriteHandler


class StatementExecutor:

    def __init__(self, session: DuckDBSession, statement_parser: StatementParser, table_resolver: TableResolver,
                 catalog_commands: CatalogCommandHandler, table_writes: TableWriteHandler, delta_commands: DeltaCommandHandler,
                 query_history: QueryHistoryService):
        self.session = session
        self.statement_parser = statement_parser
        self.table_resolver = table_resolver
        self.catalog_commands = catalog_commands
        self.table_writes = table_writes
        self.delta_commands = delta_commands
        self.query_history = query_history
        self.user_name = "admin"
        self.emulator_commands = {
            "CREATE_CATALOG": catalog_commands.create_catalog,
            "DROP_CATALOG": catalog_commands.drop_catalog,
            "SHOW_CATALOGS": lambda command: catalog_commands.show_catalogs(),
            "SHOW_SCHEMAS": catalog_commands.show_schemas,
            "SHOW_TABLES": catalog_commands.show_tables,
            "COMMENT_ON_CATALOG": catalog_commands.comment_on_catalog,
            "DESCRIBE_DETAIL": delta_commands.describe_detail,
            "RESTORE": delta_commands.restore,
            "OPTIMIZE": delta_commands.optimize,
            "VACUUM": delta_commands.vacuum,
        }

    def execute(self, sql: str, parameters: list | dict | None = None, query_id: str | None = None) -> pa.Table:
        recorded_query_id = query_id or str(uuid4())
        started_at = self._now()
        statement_type = "UNKNOWN"
        try:
            statement_texts = self.statement_parser.split(sql)
            if not statement_texts:
                raise InvalidParameterValue("PARSE_EMPTY_STATEMENT", "The statement is empty")
            statement_parameters = parameters if len(statement_texts) == 1 else None
            result = pa.table({})
            for statement_text in statement_texts:
                statement = self.statement_parser.parse(statement_text)
                statement_type = self._statement_type(statement)
                result = self._execute_statement(statement, statement_parameters)
        except Exception as error:
            message = error.message if isinstance(error, DrbError) else str(error)
            self._record(recorded_query_id, sql, statement_type, "FAILED", message, started_at, None)
            raise
        self._record(recorded_query_id, sql, statement_type, "FINISHED", None, started_at, result.num_rows)
        return result

    def _execute_statement(self, statement: EmulatorCommand | exp.Expression, parameters: list | dict | None) -> pa.Table:
        if isinstance(statement, EmulatorCommand):
            return self.emulator_commands[statement.command](statement)
        if isinstance(statement, exp.Query):
            return self.session.execute(self.table_resolver.resolve_query(statement), parameters)
        if isinstance(statement, exp.Create):
            return self._create(statement)
        if isinstance(statement, exp.Insert):
            return self.table_writes.insert(statement)
        if isinstance(statement, exp.Update):
            return self.table_writes.update(statement)
        if isinstance(statement, exp.Delete):
            return self.table_writes.delete(statement)
        if isinstance(statement, exp.Merge):
            return self.table_writes.merge(statement)
        if isinstance(statement, exp.Drop):
            return self.catalog_commands.drop(statement)
        if isinstance(statement, exp.Use):
            return self.catalog_commands.use(statement)
        if isinstance(statement, exp.Comment):
            return self.catalog_commands.comment(statement)
        if isinstance(statement, exp.Set):
            return self.catalog_commands.set_configuration(statement)
        if isinstance(statement, exp.Describe):
            if (statement.args.get("style") or "").upper() == "HISTORY":
                return self.delta_commands.describe_history(statement)
            return self.catalog_commands.describe(statement)
        raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"{statement.key.upper()} statements are not supported yet")

    def _create(self, create: exp.Create) -> pa.Table:
        kind = (create.args.get("kind") or "").upper()
        if kind == "TABLE":
            return self.table_writes.create_table(create)
        if kind == "VIEW":
            return self.catalog_commands.create_view(create)
        if kind in ("SCHEMA", "DATABASE"):
            return self.catalog_commands.create_schema(create)
        raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"CREATE {kind} is not supported yet")

    def _statement_type(self, statement: EmulatorCommand | exp.Expression) -> str:
        if isinstance(statement, EmulatorCommand):
            return statement.command.split("_")[0]
        if isinstance(statement, exp.Query):
            return "SELECT"
        return statement.key.upper()

    def _record(self, query_id: str, sql: str, statement_type: str, status: str, error_message: str | None,
                started_at: int, rows_produced: int | None):
        self.query_history.record(QueryInfo(
            query_id=query_id,
            query_text=sql,
            statement_type=statement_type,
            status=status,
            error_message=error_message,
            user_name=self.user_name,
            query_start_time_ms=started_at,
            query_end_time_ms=self._now(),
            duration=0,
            rows_produced=rows_produced,
        ))

    def _now(self) -> int:
        return int(time.time() * 1000)
