import logging
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

from drb_emu.errors import InvalidParameterValue, UnsupportedStatement

NAME = r"(?P<name>[`\w.-]+)"
COMMENT = r"'(?P<comment>(?:[^']|'')*)'"


@dataclass(frozen=True)
class EmulatorCommand:
    command: str
    groups: dict[str, str | None]
    text: str


class StatementParser:

    def __init__(self):
        self.dialect = Dialect.get_or_raise("databricks")
        logging.getLogger("sqlglot").setLevel(logging.ERROR)
        self.command_patterns = tuple((command, re.compile(pattern, re.IGNORECASE | re.DOTALL)) for command, pattern in (
            ("CREATE_CATALOG", rf"^CREATE\s+CATALOG\s+(?P<if_not_exists>IF\s+NOT\s+EXISTS\s+)?{NAME}(?:\s+COMMENT\s+{COMMENT})?$"),
            ("DROP_CATALOG", rf"^DROP\s+CATALOG\s+(?P<if_exists>IF\s+EXISTS\s+)?{NAME}(?:\s+(?P<mode>CASCADE|RESTRICT))?$"),
            ("SHOW_CATALOGS", r"^SHOW\s+CATALOGS$"),
            ("SHOW_SCHEMAS", rf"^SHOW\s+(?:SCHEMAS|DATABASES)(?:\s+(?:IN|FROM)\s+{NAME})?$"),
            ("SHOW_TABLES", rf"^SHOW\s+TABLES(?:\s+(?:IN|FROM)\s+{NAME})?$"),
            ("COMMENT_ON_CATALOG", rf"^COMMENT\s+ON\s+CATALOG\s+{NAME}\s+IS\s+(?:{COMMENT}|(?P<null>NULL))$"),
            ("DESCRIBE_DETAIL", rf"^(?:DESCRIBE|DESC)\s+DETAIL\s+{NAME}$"),
            ("RESTORE", rf"^RESTORE\s+(?:TABLE\s+)?{NAME}\s+TO\s+(?:VERSION\s+AS\s+OF\s+(?P<version>\d+)|TIMESTAMP\s+AS\s+OF\s+{COMMENT.replace('comment', 'timestamp')})$"),
            ("OPTIMIZE", rf"^OPTIMIZE\s+{NAME}$"),
            ("VACUUM", rf"^VACUUM\s+{NAME}(?:\s+RETAIN\s+(?P<hours>\d+)\s+HOURS)?$"),
        ))

    def split(self, sql: str) -> list[str]:
        try:
            tokens = self.dialect.tokenize(sql)
        except SqlglotError as error:
            raise InvalidParameterValue("PARSE_SYNTAX_ERROR", str(error)) from error
        statements = []
        statement_start = 0
        for token in tokens:
            if token.token_type == TokenType.SEMICOLON:
                statements.append(sql[statement_start:token.start])
                statement_start = token.end + 1
        statements.append(sql[statement_start:])
        return [statement.strip() for statement in statements if statement.strip()]

    def parse(self, statement_text: str) -> EmulatorCommand | exp.Expression:
        for command, pattern in self.command_patterns:
            match = pattern.match(statement_text)
            if match:
                return EmulatorCommand(command, match.groupdict(), statement_text)
        try:
            parsed = sqlglot.parse_one(statement_text, read=self.dialect)
        except SqlglotError as error:
            raise InvalidParameterValue("PARSE_SYNTAX_ERROR", str(error)) from error
        if isinstance(parsed, exp.Command):
            raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"Statement is not supported by the emulator: {statement_text}")
        return parsed
