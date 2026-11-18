import pyarrow as pa

from drb_emu.errors import InvalidParameterValue
from drb_emu.sql.duckdb_session import DuckDBSession
from drb_emu.sql.table_resolver import TableResolver


class StatementExecutor:

    def __init__(self, session: DuckDBSession, table_resolver: TableResolver):
        self.session = session
        self.table_resolver = table_resolver

    def execute(self, sql: str, parameters: list | dict | None = None) -> pa.Table:
        resolved_statements = self.table_resolver.resolve(sql)
        if not resolved_statements:
            raise InvalidParameterValue("PARSE_EMPTY_STATEMENT", "The statement is empty")
        statement_parameters = parameters if len(resolved_statements) == 1 else None
        result = pa.table({})
        for statement in resolved_statements:
            result = self.session.execute(statement, statement_parameters)
        return result
