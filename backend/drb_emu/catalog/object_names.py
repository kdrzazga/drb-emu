import re
from dataclasses import dataclass

from drb_emu.errors import InvalidParameterValue

VALID_NAME = re.compile(r"^[a-z0-9_][a-z0-9_-]*$")


def normalize_name(name: str) -> str:
    normalized = name.strip().strip("`").lower()
    if not VALID_NAME.match(normalized):
        raise InvalidParameterValue("INVALID_IDENTIFIER", f"Invalid object name '{name}'")
    return normalized


def split_full_name(full_name: str, expected_parts: int) -> tuple[str, ...]:
    parts = full_name.split(".")
    if len(parts) != expected_parts:
        raise InvalidParameterValue("INVALID_PARAMETER_VALUE", f"Expected {expected_parts}-part name, got '{full_name}'")
    return tuple(normalize_name(part) for part in parts)


@dataclass(frozen=True)
class SchemaName:
    catalog: str
    schema: str

    @classmethod
    def parse(cls, full_name: str) -> "SchemaName":
        return cls(*split_full_name(full_name, 2))

    @property
    def full_name(self) -> str:
        return f"{self.catalog}.{self.schema}"


@dataclass(frozen=True)
class TableName:
    catalog: str
    schema: str
    table: str

    @classmethod
    def parse(cls, full_name: str) -> "TableName":
        return cls(*split_full_name(full_name, 3))

    @property
    def schema_name(self) -> SchemaName:
        return SchemaName(self.catalog, self.schema)

    @property
    def full_name(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.table}"

    @property
    def quoted(self) -> str:
        return f"`{self.catalog}`.`{self.schema}`.`{self.table}`"
