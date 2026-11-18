from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class MetastoreBase(DeclarativeBase):
    pass


class CatalogRecord(MetastoreBase):
    __tablename__ = "catalogs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    comment: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[int]
    updated_at: Mapped[int]
    schemas: Mapped[list["SchemaRecord"]] = relationship(back_populates="catalog", cascade="all, delete-orphan", order_by="SchemaRecord.name")


class SchemaRecord(MetastoreBase):
    __tablename__ = "schemas"
    __table_args__ = (UniqueConstraint("catalog_id", "name"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("catalogs.id"))
    name: Mapped[str] = mapped_column(String(255))
    comment: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[int]
    updated_at: Mapped[int]
    catalog: Mapped[CatalogRecord] = relationship(back_populates="schemas")
    tables: Mapped[list["TableRecord"]] = relationship(back_populates="schema", cascade="all, delete-orphan", order_by="TableRecord.name")


class TableRecord(MetastoreBase):
    __tablename__ = "tables"
    __table_args__ = (UniqueConstraint("schema_id", "name"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    schema_id: Mapped[str] = mapped_column(ForeignKey("schemas.id"))
    name: Mapped[str] = mapped_column(String(255))
    table_type: Mapped[str] = mapped_column(String(16))
    data_source_format: Mapped[str | None] = mapped_column(String(16))
    storage_location: Mapped[str | None] = mapped_column(Text)
    view_definition: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[int]
    updated_at: Mapped[int]
    schema: Mapped[SchemaRecord] = relationship(back_populates="tables")
    columns: Mapped[list["ColumnRecord"]] = relationship(back_populates="table", cascade="all, delete-orphan", order_by="ColumnRecord.position")


class ColumnRecord(MetastoreBase):
    __tablename__ = "columns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_id: Mapped[str] = mapped_column(ForeignKey("tables.id"))
    name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int]
    type_name: Mapped[str] = mapped_column(String(32))
    type_text: Mapped[str] = mapped_column(Text)
    nullable: Mapped[bool]
    comment: Mapped[str | None] = mapped_column(Text)
    table: Mapped[TableRecord] = relationship(back_populates="columns")
