from dataclasses import dataclass

import pyarrow as pa


@dataclass(frozen=True)
class SeedTable:
    name: str
    comment: str
    columns: tuple[tuple[str, pa.DataType], ...]
    rows: list[dict]

    def to_arrow(self) -> pa.Table:
        schema = pa.schema([pa.field(column_name, column_type) for column_name, column_type in self.columns])
        return pa.Table.from_pylist(self.rows, schema=schema)


@dataclass(frozen=True)
class SeedView:
    name: str
    comment: str
    definition: str


@dataclass(frozen=True)
class SeedDataset:
    catalog_name: str
    comment: str
    tables: tuple[SeedTable, ...]
    views: tuple[SeedView, ...]
