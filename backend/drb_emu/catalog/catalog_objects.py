from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogInfo:
    name: str
    comment: str | None
    owner: str
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class SchemaInfo:
    name: str
    catalog_name: str
    full_name: str
    comment: str | None
    owner: str
    created_at: int
    updated_at: int
    schema_id: str


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    position: int
    type_name: str
    type_text: str
    nullable: bool
    comment: str | None


@dataclass(frozen=True)
class TableInfo:
    name: str
    catalog_name: str
    schema_name: str
    full_name: str
    table_type: str
    data_source_format: str | None
    storage_location: str | None
    view_definition: str | None
    columns: tuple[ColumnInfo, ...]
    comment: str | None
    owner: str
    created_at: int
    updated_at: int
    table_id: str
