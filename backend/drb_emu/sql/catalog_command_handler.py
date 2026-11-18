import pyarrow as pa
import sqlglot
from sqlglot import exp

from drb_emu.catalog.object_names import TableName, normalize_name
from drb_emu.catalog.unity_catalog_service import UnityCatalogService
from drb_emu.errors import InvalidParameterValue, ResourceAlreadyExists, ResourceNotFound, UnsupportedStatement
from drb_emu.sql.create_options import CreateOptions
from drb_emu.sql.duckdb_session import DuckDBSession
from drb_emu.sql.spark_type_names import SparkTypeNames
from drb_emu.sql.statement_parser import EmulatorCommand
from drb_emu.sql.table_resolver import TableResolver


class CatalogCommandHandler:

    def __init__(self, catalog_service: UnityCatalogService, session: DuckDBSession, table_resolver: TableResolver):
        self.catalog_service = catalog_service
        self.session = session
        self.table_resolver = table_resolver
        self.spark_type_names = SparkTypeNames()
        self.dialect = "databricks"

    def create_catalog(self, command: EmulatorCommand) -> pa.Table:
        try:
            self.catalog_service.create_catalog(command.groups["name"], self._unescape(command.groups["comment"]))
        except ResourceAlreadyExists:
            if not command.groups["if_not_exists"]:
                raise
        return pa.table({})

    def drop_catalog(self, command: EmulatorCommand) -> pa.Table:
        cascade = (command.groups["mode"] or "").upper() == "CASCADE"
        try:
            self.catalog_service.delete_catalog(command.groups["name"], force=cascade)
        except ResourceNotFound:
            if not command.groups["if_exists"]:
                raise
        if normalize_name(command.groups["name"]) == self.session.current_catalog:
            self.session.use_catalog(self.catalog_service.default_catalog_name)
        return pa.table({})

    def show_catalogs(self) -> pa.Table:
        return pa.table({"catalog": pa.array([catalog.name for catalog in self.catalog_service.list_catalogs()], pa.string())})

    def show_schemas(self, command: EmulatorCommand) -> pa.Table:
        catalog_name = command.groups["name"] or self.session.current_catalog
        schemas = self.catalog_service.list_schemas(catalog_name)
        return pa.table({"databaseName": pa.array([schema.name for schema in schemas], pa.string())})

    def show_tables(self, command: EmulatorCommand) -> pa.Table:
        reference = command.groups["name"]
        schema_name = self.table_resolver.schema_name(exp.to_table(reference, dialect=self.dialect)) if reference else None
        catalog_name = schema_name.catalog if schema_name else self.session.current_catalog
        schema = schema_name.schema if schema_name else self.session.current_schema
        tables = self.catalog_service.list_tables(catalog_name, schema)
        temporary_views = sorted(self.session.registered_views)
        return pa.table({
            "database": pa.array([schema] * len(tables) + [""] * len(temporary_views), pa.string()),
            "tableName": pa.array([table.name for table in tables] + temporary_views, pa.string()),
            "isTemporary": pa.array([False] * len(tables) + [True] * len(temporary_views), pa.bool_()),
        })

    def comment_on_catalog(self, command: EmulatorCommand) -> pa.Table:
        comment = None if command.groups["null"] else self._unescape(command.groups["comment"])
        self.catalog_service.set_comment("CATALOG", command.groups["name"], comment)
        return pa.table({})

    def create_schema(self, create: exp.Create) -> pa.Table:
        schema_name = self.table_resolver.schema_name(create.this)
        options = CreateOptions.of(create)
        try:
            self.catalog_service.create_schema(schema_name.catalog, schema_name.schema, options.comment)
        except ResourceAlreadyExists:
            if not options.if_not_exists:
                raise
        return pa.table({})

    def create_view(self, create: exp.Create) -> pa.Table:
        options = CreateOptions.of(create)
        view_query = create.expression
        if not isinstance(view_query, exp.Query):
            raise InvalidParameterValue("INVALID_VIEW_TEXT", "CREATE VIEW needs AS <query>")
        if options.is_temporary:
            view_name = create.this.name
            if view_name in self.session.registered_views and not options.replace:
                if options.if_not_exists:
                    return pa.table({})
                raise ResourceAlreadyExists("TEMP_TABLE_OR_VIEW_ALREADY_EXISTS", f"Temporary view `{view_name}` already exists")
            self.session.create_temp_view(view_name, self.table_resolver.resolve_query(view_query.copy()))
            return pa.table({})
        table_name = self.table_resolver.table_name(create.this)
        view_definition = view_query.sql(dialect=self.dialect)
        self.table_resolver.resolve_query(view_query.copy())
        if self.catalog_service.table_exists(table_name.full_name):
            if options.if_not_exists:
                return pa.table({})
            if not options.replace:
                raise ResourceAlreadyExists("TABLE_OR_VIEW_ALREADY_EXISTS", f"The table or view {table_name.quoted} already exists")
            self._require_kind(table_name, "VIEW")
            self.catalog_service.delete_table(table_name.full_name)
        self.catalog_service.create_view(table_name.full_name, view_definition, options.comment)
        return pa.table({})

    def drop(self, drop: exp.Drop) -> pa.Table:
        kind = (drop.args.get("kind") or "").upper()
        if_exists = bool(drop.args.get("exists"))
        for target in drop.args.get("tables") or []:
            if kind in ("SCHEMA", "DATABASE"):
                self._drop_schema(target, if_exists, bool(drop.args.get("cascade")))
            elif kind in ("TABLE", "VIEW"):
                self._drop_table_or_view(target, kind, if_exists)
            else:
                raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"DROP {kind} is not supported")
        return pa.table({})

    def use(self, use: exp.Use) -> pa.Table:
        kind = use.args.get("kind")
        kind_name = kind.name.upper() if kind else ""
        if kind_name == "CATALOG":
            catalog = self.catalog_service.get_catalog(use.this.name)
            self.session.use_catalog(catalog.name)
            return pa.table({})
        schema_name = self.table_resolver.schema_name(use.this)
        schema = self.catalog_service.get_schema(schema_name.full_name)
        if schema.catalog_name != self.session.current_catalog:
            self.session.use_catalog(schema.catalog_name)
        self.session.use_schema(schema.name)
        return pa.table({})

    def describe(self, describe: exp.Describe) -> pa.Table:
        target = describe.this
        if not isinstance(target, exp.Table):
            raise UnsupportedStatement("UNSUPPORTED_STATEMENT", "Only DESCRIBE [TABLE] <table> is supported")
        if self.table_resolver.is_session_view(target):
            return self._describe_schema(self.session.execute(f'SELECT * FROM "{target.name}" LIMIT 0').schema)
        table_info = self.catalog_service.get_table(self.table_resolver.table_name(target).full_name)
        if table_info.table_type == "VIEW":
            preview = sqlglot.parse_one(f"SELECT * FROM {TableName.parse(table_info.full_name).quoted} LIMIT 0", read=self.dialect)
            columns = self._describe_schema(self.session.execute(self.table_resolver.resolve_query(preview)).schema)
        else:
            columns = pa.table({
                "col_name": pa.array([column.name for column in table_info.columns], pa.string()),
                "data_type": pa.array([column.type_text for column in table_info.columns], pa.string()),
                "comment": pa.array([column.comment for column in table_info.columns], pa.string()),
            })
        if (describe.args.get("style") or "").upper() != "EXTENDED":
            return columns
        details = (
            ("", "", None),
            ("# Detailed Table Information", "", None),
            ("Catalog", table_info.catalog_name, None),
            ("Database", table_info.schema_name, None),
            ("Table", table_info.name, None),
            ("Type", table_info.table_type, None),
            ("Location", table_info.storage_location or "", None),
            ("Provider", (table_info.data_source_format or "").lower(), None),
            ("Owner", table_info.owner, None),
            ("Comment", table_info.comment or "", None),
            ("View Text", table_info.view_definition or "", None),
        )
        detail_rows = pa.table({
            "col_name": pa.array([row[0] for row in details], pa.string()),
            "data_type": pa.array([row[1] for row in details], pa.string()),
            "comment": pa.array([row[2] for row in details], pa.string()),
        })
        return pa.concat_tables([columns, detail_rows])

    def comment(self, comment: exp.Comment) -> pa.Table:
        kind = (comment.args.get("kind") or "").upper()
        comment_value = None if isinstance(comment.expression, exp.Null) else comment.expression.name
        if kind == "TABLE":
            self.catalog_service.set_comment("TABLE", self.table_resolver.table_name(comment.this).full_name, comment_value)
        elif kind in ("SCHEMA", "DATABASE"):
            self.catalog_service.set_comment("SCHEMA", self.table_resolver.schema_name(comment.this).full_name, comment_value)
        else:
            raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"COMMENT ON {kind} is not supported")
        return pa.table({})

    def set_configuration(self, set_statement: exp.Set) -> pa.Table:
        for set_item in set_statement.expressions:
            assignment = set_item.this
            if not isinstance(assignment, exp.EQ):
                raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"Unsupported SET: {set_item.sql(dialect=self.dialect)}")
            key = ".".join(part.name for part in assignment.this.parts) if isinstance(assignment.this, exp.Column) else assignment.this.name
            self.session.spark_conf[key] = self._configuration_value(assignment.expression)
        return pa.table({
            "key": pa.array(list(self.session.spark_conf), pa.string()),
            "value": pa.array(list(self.session.spark_conf.values()), pa.string()),
        })

    def _drop_schema(self, target: exp.Table, if_exists: bool, cascade: bool):
        schema_name = self.table_resolver.schema_name(target)
        try:
            self.catalog_service.delete_schema(schema_name.full_name, force=cascade)
        except ResourceNotFound:
            if not if_exists:
                raise
        if (schema_name.catalog, schema_name.schema) == (self.session.current_catalog, self.session.current_schema):
            self.session.use_schema(self.catalog_service.default_schema_name)

    def _drop_table_or_view(self, target: exp.Table, kind: str, if_exists: bool):
        if kind == "VIEW" and self.table_resolver.is_session_view(target):
            self.session.unregister(target.name)
            return
        table_name = self.table_resolver.table_name(target)
        if not self.catalog_service.table_exists(table_name.full_name):
            if if_exists:
                return
            raise ResourceNotFound("TABLE_OR_VIEW_NOT_FOUND", f"The table or view {table_name.quoted} cannot be found")
        self._require_kind(table_name, kind)
        self.catalog_service.delete_table(table_name.full_name)

    def _require_kind(self, table_name: TableName, kind: str):
        is_view = self.catalog_service.get_table(table_name.full_name).table_type == "VIEW"
        if kind == "VIEW" and not is_view:
            raise InvalidParameterValue("WRONG_COMMAND_FOR_OBJECT_TYPE", f"{table_name.quoted} is a table, use DROP TABLE")
        if kind == "TABLE" and is_view:
            raise InvalidParameterValue("WRONG_COMMAND_FOR_OBJECT_TYPE", f"{table_name.quoted} is a view, use DROP VIEW")

    def _describe_schema(self, arrow_schema: pa.Schema) -> pa.Table:
        return pa.table({
            "col_name": pa.array([field.name for field in arrow_schema], pa.string()),
            "data_type": pa.array([self.spark_type_names.type_text(field.type) for field in arrow_schema], pa.string()),
            "comment": pa.array([None] * len(arrow_schema), pa.string()),
        })

    def _configuration_value(self, value: exp.Expression) -> str:
        if isinstance(value, exp.Boolean):
            return "true" if value.this else "false"
        if isinstance(value, exp.Literal):
            return value.this
        return value.sql(dialect=self.dialect)

    def _unescape(self, quoted_text: str | None) -> str | None:
        return quoted_text.replace("''", "'") if quoted_text is not None else None
