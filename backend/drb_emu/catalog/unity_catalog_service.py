import shutil
import time
from uuid import uuid4

import pyarrow as pa
import sqlglot
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlglot.errors import SqlglotError

from drb_emu.catalog.catalog_objects import CatalogInfo, ColumnInfo, SchemaInfo, TableInfo
from drb_emu.catalog.metastore_records import CatalogRecord, ColumnRecord, SchemaRecord, TableRecord
from drb_emu.catalog.object_names import SchemaName, TableName, normalize_name
from drb_emu.errors import InvalidParameterValue, ResourceAlreadyExists, ResourceNotEmpty, ResourceNotFound
from drb_emu.lake import DeltaTableStore, LakePathResolver
from drb_emu.sql.spark_type_names import SparkTypeNames


class UnityCatalogService:

    def __init__(self, session_factory: sessionmaker, path_resolver: LakePathResolver, delta_store: DeltaTableStore):
        self.session_factory = session_factory
        self.path_resolver = path_resolver
        self.delta_store = delta_store
        self.spark_type_names = SparkTypeNames()
        self.default_owner = "admin"
        self.default_catalog_name = "main"
        self.default_schema_name = "default"
        self.sql_dialect = "databricks"

    def ensure_default_objects(self):
        with self.session_factory() as metastore:
            if self._find_catalog(metastore, self.default_catalog_name) is not None:
                return
        self.create_catalog(self.default_catalog_name, "Default catalog")

    def create_catalog(self, name: str, comment: str | None = None) -> CatalogInfo:
        catalog_name = normalize_name(name)
        with self.session_factory.begin() as metastore:
            if self._find_catalog(metastore, catalog_name) is not None:
                raise ResourceAlreadyExists("CATALOG_ALREADY_EXISTS", f"Catalog '{catalog_name}' already exists")
            now = self._now()
            catalog = CatalogRecord(id=self._new_id(), name=catalog_name, comment=comment, owner=self.default_owner, created_at=now, updated_at=now)
            catalog.schemas.append(self._new_schema_record(self.default_schema_name, "Default schema"))
            metastore.add(catalog)
            metastore.flush()
            return self._catalog_info(catalog)

    def get_catalog(self, name: str) -> CatalogInfo:
        with self.session_factory() as metastore:
            return self._catalog_info(self._require_catalog(metastore, normalize_name(name)))

    def list_catalogs(self) -> list[CatalogInfo]:
        with self.session_factory() as metastore:
            catalogs = metastore.scalars(select(CatalogRecord).order_by(CatalogRecord.name))
            return [self._catalog_info(catalog) for catalog in catalogs]

    def delete_catalog(self, name: str, force: bool = False):
        with self.session_factory.begin() as metastore:
            catalog = self._require_catalog(metastore, normalize_name(name))
            has_content = any(schema.tables or schema.name != self.default_schema_name for schema in catalog.schemas)
            if has_content and not force:
                raise ResourceNotEmpty("CATALOG_NOT_EMPTY", f"Catalog '{catalog.name}' is not empty, use force to delete it")
            managed_locations = [table.storage_location for schema in catalog.schemas for table in schema.tables if table.table_type == "MANAGED"]
            metastore.delete(catalog)
        self._remove_managed_data(managed_locations)

    def create_schema(self, catalog_name: str, name: str, comment: str | None = None) -> SchemaInfo:
        schema_name = normalize_name(name)
        with self.session_factory.begin() as metastore:
            catalog = self._require_catalog(metastore, normalize_name(catalog_name))
            if any(schema.name == schema_name for schema in catalog.schemas):
                raise ResourceAlreadyExists("SCHEMA_ALREADY_EXISTS", f"Schema '{catalog.name}.{schema_name}' already exists")
            schema = self._new_schema_record(schema_name, comment)
            catalog.schemas.append(schema)
            metastore.flush()
            return self._schema_info(schema)

    def get_schema(self, full_name: str) -> SchemaInfo:
        with self.session_factory() as metastore:
            return self._schema_info(self._require_schema(metastore, SchemaName.parse(full_name)))

    def list_schemas(self, catalog_name: str) -> list[SchemaInfo]:
        with self.session_factory() as metastore:
            catalog = self._require_catalog(metastore, normalize_name(catalog_name))
            return [self._schema_info(schema) for schema in catalog.schemas]

    def delete_schema(self, full_name: str, force: bool = False):
        with self.session_factory.begin() as metastore:
            schema = self._require_schema(metastore, SchemaName.parse(full_name))
            if schema.tables and not force:
                raise ResourceNotEmpty("SCHEMA_NOT_EMPTY", f"Schema '{schema.catalog.name}.{schema.name}' is not empty, use force to delete it")
            managed_locations = [table.storage_location for table in schema.tables if table.table_type == "MANAGED"]
            metastore.delete(schema)
        self._remove_managed_data(managed_locations)

    def write_table(self, full_name: str, data: pa.Table, mode: str, partition_by: tuple[str, ...] = ()) -> TableInfo:
        table_name = TableName.parse(full_name)
        with self.session_factory.begin() as metastore:
            schema = self._require_schema(metastore, table_name.schema_name)
            table = self._find_table(metastore, table_name)
            if table is None:
                table_id = self._new_id()
                location = self.path_resolver.managed_table_location(table_name.catalog, table_name.schema, table_id)
                self.delta_store.write(location, data, mode, partition_by)
                table = self._new_table_record(table_id, table_name.table, "MANAGED", location, None, None)
                schema.tables.append(table)
            elif table.table_type == "VIEW":
                raise InvalidParameterValue("EXPECT_TABLE_NOT_VIEW", f"{table_name.quoted} is a view and cannot be written to")
            else:
                self.delta_store.write(table.storage_location, data, mode, partition_by)
                table.updated_at = self._now()
            self._refresh_columns(table)
            metastore.flush()
            return self._table_info(table)

    def create_external_table(self, full_name: str, storage_location: str, comment: str | None = None) -> TableInfo:
        table_name = TableName.parse(full_name)
        if not self.delta_store.exists(storage_location):
            raise InvalidParameterValue("DELTA_TABLE_NOT_FOUND", f"No Delta table at {storage_location}")
        with self.session_factory.begin() as metastore:
            schema = self._require_absent_table(metastore, table_name)
            table = self._new_table_record(self._new_id(), table_name.table, "EXTERNAL", storage_location, None, comment)
            schema.tables.append(table)
            self._refresh_columns(table)
            metastore.flush()
            return self._table_info(table)

    def create_view(self, full_name: str, view_definition: str, comment: str | None = None) -> TableInfo:
        table_name = TableName.parse(full_name)
        try:
            sqlglot.parse_one(view_definition, read=self.sql_dialect)
        except SqlglotError as error:
            raise InvalidParameterValue("PARSE_SYNTAX_ERROR", f"Invalid view definition: {error}") from error
        with self.session_factory.begin() as metastore:
            schema = self._require_absent_table(metastore, table_name)
            table = self._new_table_record(self._new_id(), table_name.table, "VIEW", None, view_definition, comment)
            schema.tables.append(table)
            metastore.flush()
            return self._table_info(table)

    def get_table(self, full_name: str) -> TableInfo:
        table_name = TableName.parse(full_name)
        with self.session_factory() as metastore:
            table = self._find_table(metastore, table_name)
            if table is None:
                raise ResourceNotFound("TABLE_OR_VIEW_NOT_FOUND", f"The table or view {table_name.quoted} cannot be found")
            return self._table_info(table)

    def table_exists(self, full_name: str) -> bool:
        with self.session_factory() as metastore:
            return self._find_table(metastore, TableName.parse(full_name)) is not None

    def list_tables(self, catalog_name: str, schema_name: str) -> list[TableInfo]:
        with self.session_factory() as metastore:
            schema = self._require_schema(metastore, SchemaName(normalize_name(catalog_name), normalize_name(schema_name)))
            return [self._table_info(table) for table in schema.tables]

    def delete_table(self, full_name: str):
        table_name = TableName.parse(full_name)
        with self.session_factory.begin() as metastore:
            table = self._find_table(metastore, table_name)
            if table is None:
                raise ResourceNotFound("TABLE_OR_VIEW_NOT_FOUND", f"The table or view {table_name.quoted} cannot be found")
            managed_locations = [table.storage_location] if table.table_type == "MANAGED" else []
            metastore.delete(table)
        self._remove_managed_data(managed_locations)

    def _find_catalog(self, metastore: Session, catalog_name: str) -> CatalogRecord | None:
        return metastore.scalars(select(CatalogRecord).where(CatalogRecord.name == catalog_name)).one_or_none()

    def _require_catalog(self, metastore: Session, catalog_name: str) -> CatalogRecord:
        catalog = self._find_catalog(metastore, catalog_name)
        if catalog is None:
            raise ResourceNotFound("NO_SUCH_CATALOG_EXCEPTION", f"Catalog '{catalog_name}' was not found")
        return catalog

    def _require_schema(self, metastore: Session, schema_name: SchemaName) -> SchemaRecord:
        schema = metastore.scalars(
            select(SchemaRecord)
            .join(SchemaRecord.catalog)
            .where(CatalogRecord.name == schema_name.catalog, SchemaRecord.name == schema_name.schema)
        ).one_or_none()
        if schema is None:
            raise ResourceNotFound("SCHEMA_NOT_FOUND", f"The schema `{schema_name.catalog}`.`{schema_name.schema}` cannot be found")
        return schema

    def _find_table(self, metastore: Session, table_name: TableName) -> TableRecord | None:
        return metastore.scalars(
            select(TableRecord)
            .join(TableRecord.schema)
            .join(SchemaRecord.catalog)
            .where(CatalogRecord.name == table_name.catalog, SchemaRecord.name == table_name.schema, TableRecord.name == table_name.table)
        ).one_or_none()

    def _require_absent_table(self, metastore: Session, table_name: TableName) -> SchemaRecord:
        schema = self._require_schema(metastore, table_name.schema_name)
        if self._find_table(metastore, table_name) is not None:
            raise ResourceAlreadyExists("TABLE_OR_VIEW_ALREADY_EXISTS", f"The table or view {table_name.quoted} already exists")
        return schema

    def _new_schema_record(self, name: str, comment: str | None) -> SchemaRecord:
        now = self._now()
        return SchemaRecord(id=self._new_id(), name=name, comment=comment, owner=self.default_owner, created_at=now, updated_at=now)

    def _new_table_record(self, table_id: str, name: str, table_type: str, storage_location: str | None,
                          view_definition: str | None, comment: str | None) -> TableRecord:
        now = self._now()
        return TableRecord(
            id=table_id,
            name=name,
            table_type=table_type,
            data_source_format=None if table_type == "VIEW" else "DELTA",
            storage_location=storage_location,
            view_definition=view_definition,
            comment=comment,
            owner=self.default_owner,
            created_at=now,
            updated_at=now,
        )

    def _refresh_columns(self, table: TableRecord):
        arrow_schema = self.delta_store.dataset(table.storage_location).schema
        table.columns.clear()
        for position, field in enumerate(arrow_schema):
            table.columns.append(ColumnRecord(
                name=field.name,
                position=position,
                type_name=self.spark_type_names.type_name(field.type),
                type_text=self.spark_type_names.type_text(field.type),
                nullable=field.nullable,
                comment=None,
            ))

    def _remove_managed_data(self, managed_locations: list[str]):
        for location in managed_locations:
            shutil.rmtree(self.path_resolver.resolve(location), ignore_errors=True)

    def _catalog_info(self, catalog: CatalogRecord) -> CatalogInfo:
        return CatalogInfo(catalog.name, catalog.comment, catalog.owner, catalog.created_at, catalog.updated_at)

    def _schema_info(self, schema: SchemaRecord) -> SchemaInfo:
        return SchemaInfo(
            name=schema.name,
            catalog_name=schema.catalog.name,
            full_name=f"{schema.catalog.name}.{schema.name}",
            comment=schema.comment,
            owner=schema.owner,
            created_at=schema.created_at,
            updated_at=schema.updated_at,
            schema_id=schema.id,
        )

    def _table_info(self, table: TableRecord) -> TableInfo:
        catalog_name = table.schema.catalog.name
        return TableInfo(
            name=table.name,
            catalog_name=catalog_name,
            schema_name=table.schema.name,
            full_name=f"{catalog_name}.{table.schema.name}.{table.name}",
            table_type=table.table_type,
            data_source_format=table.data_source_format,
            storage_location=table.storage_location,
            view_definition=table.view_definition,
            columns=tuple(ColumnInfo(column.name, column.position, column.type_name, column.type_text, column.nullable, column.comment)
                          for column in table.columns),
            comment=table.comment,
            owner=table.owner,
            created_at=table.created_at,
            updated_at=table.updated_at,
            table_id=table.id,
        )

    def _new_id(self) -> str:
        return uuid4().hex

    def _now(self) -> int:
        return int(time.time() * 1000)
