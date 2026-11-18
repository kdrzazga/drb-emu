import pyarrow as pa
from sqlglot import exp

from drb_emu.catalog.catalog_objects import TableInfo
from drb_emu.catalog.unity_catalog_service import UnityCatalogService
from drb_emu.errors import InvalidParameterValue, ResourceAlreadyExists, UnsupportedStatement
from drb_emu.lake import DeltaTableStore
from drb_emu.sql.create_options import CreateOptions
from drb_emu.sql.duckdb_session import DuckDBSession
from drb_emu.sql.table_resolver import TableResolver


class TableWriteHandler:

    def __init__(self, catalog_service: UnityCatalogService, delta_store: DeltaTableStore, session: DuckDBSession, table_resolver: TableResolver):
        self.catalog_service = catalog_service
        self.delta_store = delta_store
        self.session = session
        self.table_resolver = table_resolver
        self.scratch_table_name = "__drb_dml_target"
        self.schema_probe_table_name = "__drb_schema_probe"
        self.write_dialect = "duckdb"

    def create_table(self, create: exp.Create) -> pa.Table:
        options = CreateOptions.of(create)
        if options.is_temporary:
            raise UnsupportedStatement("UNSUPPORTED_STATEMENT", "Temporary tables are not supported, use CREATE TEMP VIEW")
        column_definitions = create.this.expressions if isinstance(create.this, exp.Schema) else []
        target = create.this.this if isinstance(create.this, exp.Schema) else create.this
        table_name = self.table_resolver.table_name(target)
        table_exists = self.catalog_service.table_exists(table_name.full_name)
        if table_exists and options.if_not_exists:
            return pa.table({})
        if table_exists and not options.replace:
            raise ResourceAlreadyExists("TABLE_OR_VIEW_ALREADY_EXISTS", f"The table or view {table_name.quoted} already exists")
        if table_exists and self.catalog_service.get_table(table_name.full_name).table_type == "VIEW":
            raise InvalidParameterValue("WRONG_COMMAND_FOR_OBJECT_TYPE", f"{table_name.quoted} is a view, use CREATE OR REPLACE VIEW")
        data = self._create_table_data(create, column_definitions)
        if table_exists:
            self.catalog_service.delete_table(table_name.full_name)
        if options.location:
            self._prepare_external_location(options, data, create.expression is not None)
            self.catalog_service.create_external_table(table_name.full_name, options.location, options.comment)
        elif data is None:
            raise InvalidParameterValue("INVALID_PARAMETER_VALUE", "CREATE TABLE needs a column list, AS <query> or LOCATION")
        else:
            self.catalog_service.create_managed_table(table_name.full_name, data, options.partition_by, options.comment)
        if create.expression is not None:
            return self._inserted_rows(data.num_rows)
        return pa.table({})

    def insert(self, insert: exp.Insert) -> pa.Table:
        table_info = self._writable_table(self._insert_target(insert))
        target_schema = self.delta_store.schema(table_info.storage_location)
        statement = insert.copy()
        statement_target = self._insert_target(statement)
        overwrite = bool(statement.args.get("overwrite"))
        statement.set("overwrite", None)
        self.session.create_scratch_table(self.scratch_table_name, target_schema.empty_table())
        try:
            self.table_resolver.resolve_references(statement, excluded_table=statement_target)
            self._point_at_scratch_table(statement_target, add_alias=False)
            inserted_rows = self._affected_rows(self.session.execute(statement.sql(dialect=self.write_dialect)))
            new_rows = self._scratch_rows(target_schema)
        finally:
            self.session.drop_scratch_table(self.scratch_table_name)
        operation = "INSERT OVERWRITE" if overwrite else "INSERT"
        partition_by = self.delta_store.partition_columns(table_info.storage_location)
        self.delta_store.write(table_info.storage_location, new_rows, "overwrite" if overwrite else "append", partition_by, operation)
        self.catalog_service.touch_table(table_info.full_name)
        return self._inserted_rows(inserted_rows)

    def update(self, update: exp.Update) -> pa.Table:
        table_info = self._writable_table(update.this)
        statement = update.copy()
        for assignment in statement.expressions:
            self._unqualify_assignment_target(assignment)
        return self._rewrite_table(table_info, statement, statement.this, "UPDATE")

    def delete(self, delete: exp.Delete) -> pa.Table:
        table_info = self._writable_table(delete.this)
        statement = delete.copy()
        return self._rewrite_table(table_info, statement, statement.this, "DELETE")

    def merge(self, merge: exp.Merge) -> pa.Table:
        table_info = self._writable_table(merge.this)
        statement = merge.copy()
        source_alias = statement.args["using"].alias_or_name
        target_columns = [column.name for column in table_info.columns]
        for when in statement.args["whens"].expressions:
            action = when.args.get("then")
            if isinstance(action, exp.Update):
                if any(isinstance(assignment, exp.Star) for assignment in action.expressions):
                    action.set("expressions", [exp.EQ(this=exp.column(column), expression=exp.column(column, table=source_alias)) for column in target_columns])
                for assignment in action.expressions:
                    self._unqualify_assignment_target(assignment)
            elif isinstance(action, exp.Insert) and isinstance(action.this, exp.Star):
                action.set("this", exp.Tuple(expressions=[exp.column(column) for column in target_columns]))
                action.set("expression", exp.Tuple(expressions=[exp.column(column, table=source_alias) for column in target_columns]))
        return self._rewrite_table(table_info, statement, statement.this, "MERGE")

    def _rewrite_table(self, table_info: TableInfo, statement: exp.Expression, statement_target: exp.Table, operation: str) -> pa.Table:
        current_rows = self.delta_store.read(table_info.storage_location)
        self.session.create_scratch_table(self.scratch_table_name, current_rows)
        try:
            self.table_resolver.resolve_references(statement, excluded_table=statement_target)
            self._point_at_scratch_table(statement_target, add_alias=True)
            affected_rows = self._affected_rows(self.session.execute(statement.sql(dialect=self.write_dialect)))
            new_rows = self._scratch_rows(current_rows.schema)
        finally:
            self.session.drop_scratch_table(self.scratch_table_name)
        if affected_rows:
            partition_by = self.delta_store.partition_columns(table_info.storage_location)
            self.delta_store.write(table_info.storage_location, new_rows, "overwrite", partition_by, operation)
            self.catalog_service.touch_table(table_info.full_name)
        return pa.table({"num_affected_rows": pa.array([affected_rows], pa.int64())})

    def _create_table_data(self, create: exp.Create, column_definitions: list[exp.Expression]) -> pa.Table | None:
        if create.expression is not None:
            if not isinstance(create.expression, exp.Query):
                raise UnsupportedStatement("UNSUPPORTED_STATEMENT", "CREATE TABLE AS needs a query")
            return self.session.execute(self.table_resolver.resolve_query(create.expression.copy()))
        if column_definitions:
            return self._empty_table_for(column_definitions)
        return None

    def _empty_table_for(self, column_definitions: list[exp.Expression]) -> pa.Table:
        column_sql = []
        not_null_columns = set()
        for definition in column_definitions:
            column_type = definition.args.get("kind") if isinstance(definition, exp.ColumnDef) else None
            if column_type is None:
                raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"Unsupported column definition: {definition.sql(dialect='databricks')}")
            column_sql.append(f'"{definition.name}" {column_type.sql(dialect=self.write_dialect)}')
            constraints = definition.args.get("constraints") or []
            if any(isinstance(constraint.args.get("kind"), exp.NotNullColumnConstraint) for constraint in constraints):
                not_null_columns.add(definition.name)
        self.session.execute(f'CREATE OR REPLACE TEMP TABLE "{self.schema_probe_table_name}" ({", ".join(column_sql)})')
        try:
            probe_schema = self.session.execute(f'SELECT * FROM "{self.schema_probe_table_name}"').schema
        finally:
            self.session.execute(f'DROP TABLE IF EXISTS "{self.schema_probe_table_name}"')
        return pa.schema([field.with_nullable(field.name not in not_null_columns) for field in probe_schema]).empty_table()

    def _prepare_external_location(self, options: CreateOptions, data: pa.Table | None, is_create_as_select: bool):
        location_has_table = self.delta_store.exists(options.location)
        if location_has_table and is_create_as_select:
            raise InvalidParameterValue("DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION", f"A Delta table already exists at {options.location}")
        if not location_has_table:
            if data is None:
                raise InvalidParameterValue("DELTA_TABLE_NOT_FOUND", f"No Delta table at {options.location} and no columns given")
            self.delta_store.write(options.location, data, "error", options.partition_by, "CREATE TABLE")

    def _writable_table(self, target: exp.Table) -> TableInfo:
        if self.table_resolver.is_session_view(target):
            raise UnsupportedStatement("UNSUPPORTED_STATEMENT", f"Temporary view `{target.name}` cannot be modified")
        if target.args.get("version") is not None:
            raise InvalidParameterValue("INVALID_PARAMETER_VALUE", "Time travel is not allowed on a write target")
        table_info = self.catalog_service.get_table(self.table_resolver.table_name(target).full_name)
        if table_info.table_type == "VIEW":
            raise InvalidParameterValue("EXPECT_TABLE_NOT_VIEW", f"{table_info.full_name} is a view and cannot be modified")
        return table_info

    def _insert_target(self, insert: exp.Insert) -> exp.Table:
        return insert.this.this if isinstance(insert.this, exp.Schema) else insert.this

    def _point_at_scratch_table(self, target: exp.Table, add_alias: bool):
        if add_alias and target.args.get("alias") is None:
            target.set("alias", exp.TableAlias(this=exp.to_identifier(target.name)))
        target.set("this", exp.to_identifier(self.scratch_table_name))
        target.set("db", None)
        target.set("catalog", None)

    def _unqualify_assignment_target(self, assignment: exp.Expression):
        if isinstance(assignment, exp.EQ) and isinstance(assignment.this, exp.Column):
            assignment.set("this", exp.column(assignment.this.name))

    def _scratch_rows(self, target_schema: pa.Schema) -> pa.Table:
        return self.session.execute(f'SELECT * FROM "{self.scratch_table_name}"').cast(target_schema)

    def _affected_rows(self, result: pa.Table) -> int:
        if result.num_columns == 0 or result.num_rows == 0:
            return 0
        return int(result.column(0)[0].as_py())

    def _inserted_rows(self, row_count: int) -> pa.Table:
        return pa.table({
            "num_affected_rows": pa.array([row_count], pa.int64()),
            "num_inserted_rows": pa.array([row_count], pa.int64()),
        })
