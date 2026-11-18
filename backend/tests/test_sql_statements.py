import time

import pyarrow as pa
import pytest

from drb_emu.errors import InvalidParameterValue, ResourceAlreadyExists, ResourceNotEmpty, ResourceNotFound, UnsupportedStatement
from drb_emu.workspace import Workspace


def sql(workspace: Workspace, statement: str) -> list[dict]:
    return workspace.statement_executor.execute(statement).to_pylist()


def column(workspace: Workspace, statement: str, name: str) -> list:
    return [row[name] for row in sql(workspace, statement)]


@pytest.fixture
def orders_workspace(workspace: Workspace) -> Workspace:
    sql(workspace, """
        CREATE TABLE orders (order_id BIGINT, amount DOUBLE, country STRING);
        INSERT INTO orders VALUES (1, 10.0, 'PL'), (2, 20.5, 'DE'), (3, 7.25, 'PL')
    """)
    return workspace


def order_amounts(workspace: Workspace) -> list[tuple]:
    return [(row["order_id"], row["amount"]) for row in sql(workspace, "SELECT order_id, amount FROM orders ORDER BY order_id")]


def test_create_and_show_catalogs(workspace: Workspace):
    sql(workspace, "CREATE CATALOG sales COMMENT 'Sales data'")
    sql(workspace, "CREATE CATALOG IF NOT EXISTS sales")

    assert column(workspace, "SHOW CATALOGS", "catalog") == ["main", "sales"]
    assert workspace.catalog_service.get_catalog("sales").comment == "Sales data"


def test_duplicate_catalog_fails_without_if_not_exists(workspace: Workspace):
    sql(workspace, "CREATE CATALOG sales")

    with pytest.raises(ResourceAlreadyExists):
        sql(workspace, "CREATE CATALOG sales")


def test_drop_catalog_cascade_and_if_exists(workspace: Workspace):
    sql(workspace, "CREATE CATALOG sales; CREATE TABLE sales.default.t AS SELECT 1 AS id")

    with pytest.raises(ResourceNotEmpty):
        sql(workspace, "DROP CATALOG sales")
    sql(workspace, "DROP CATALOG sales CASCADE")
    sql(workspace, "DROP CATALOG IF EXISTS sales")

    assert column(workspace, "SHOW CATALOGS", "catalog") == ["main"]


def test_dropping_current_catalog_returns_to_main(workspace: Workspace):
    sql(workspace, "CREATE CATALOG scratch; USE CATALOG scratch; DROP CATALOG scratch")

    assert workspace.session.current_catalog == "main"


def test_schemas_lifecycle(workspace: Workspace):
    sql(workspace, "CREATE SCHEMA main.sales COMMENT 'Sales'; CREATE DATABASE IF NOT EXISTS sales")

    assert column(workspace, "SHOW SCHEMAS IN main", "databaseName") == ["default", "sales"]
    assert workspace.catalog_service.get_schema("main.sales").comment == "Sales"

    sql(workspace, "CREATE TABLE main.sales.t AS SELECT 1 AS id")
    with pytest.raises(ResourceNotEmpty):
        sql(workspace, "DROP SCHEMA main.sales")
    sql(workspace, "DROP SCHEMA main.sales CASCADE")

    assert column(workspace, "SHOW DATABASES", "databaseName") == ["default"]


def test_use_switches_catalog_and_schema(workspace: Workspace):
    sql(workspace, "CREATE CATALOG sales; CREATE SCHEMA sales.raw")

    sql(workspace, "USE CATALOG sales")
    assert (workspace.session.current_catalog, workspace.session.current_schema) == ("sales", "default")

    sql(workspace, "USE SCHEMA raw")
    assert workspace.session.current_schema == "raw"

    sql(workspace, "USE main.default")
    assert (workspace.session.current_catalog, workspace.session.current_schema) == ("main", "default")


def test_use_unknown_schema_fails(workspace: Workspace):
    with pytest.raises(ResourceNotFound):
        sql(workspace, "USE SCHEMA ghost")


def test_create_table_with_columns(workspace: Workspace):
    sql(workspace, """
        CREATE TABLE typed (
            id BIGINT NOT NULL, amount DECIMAL(10,2), name STRING, created TIMESTAMP, local_time TIMESTAMP_NTZ,
            tags ARRAY<STRING>, flag BOOLEAN, born DATE
        ) USING DELTA COMMENT 'Typed table'
    """)

    table = workspace.catalog_service.get_table("main.default.typed")

    assert table.comment == "Typed table"
    assert [(column.name, column.type_text) for column in table.columns] == [
        ("id", "bigint"), ("amount", "decimal(10,2)"), ("name", "string"), ("created", "timestamp"),
        ("local_time", "timestamp_ntz"), ("tags", "array<string>"), ("flag", "boolean"), ("born", "date"),
    ]
    assert not table.columns[0].nullable
    assert sql(workspace, "SELECT COUNT(*) AS n FROM typed") == [{"n": 0}]


def test_create_table_twice(workspace: Workspace):
    sql(workspace, "CREATE TABLE t (id INT); CREATE TABLE IF NOT EXISTS t (id INT)")

    with pytest.raises(ResourceAlreadyExists):
        sql(workspace, "CREATE TABLE t (id INT)")


def test_create_table_as_select_reports_inserted_rows(orders_workspace: Workspace):
    result = sql(orders_workspace, "CREATE TABLE polish AS SELECT * FROM orders WHERE country = 'PL'")

    assert result == [{"num_affected_rows": 2, "num_inserted_rows": 2}]
    assert column(orders_workspace, "SELECT order_id FROM polish ORDER BY order_id", "order_id") == [1, 3]


def test_create_or_replace_table(orders_workspace: Workspace):
    sql(orders_workspace, "CREATE OR REPLACE TABLE orders AS SELECT 42 AS answer")

    assert sql(orders_workspace, "SELECT * FROM orders") == [{"answer": 42}]


def test_partitioned_table(workspace: Workspace):
    sql(workspace, "CREATE TABLE events (id INT, day STRING) PARTITIONED BY (day); INSERT INTO events VALUES (1, 'mon'), (2, 'tue')")

    detail = sql(workspace, "DESCRIBE DETAIL events")[0]

    assert detail["partitionColumns"] == ["day"]
    assert sql(workspace, "SELECT COUNT(*) AS n FROM events WHERE day = 'tue'") == [{"n": 1}]


def test_external_table_with_location_keeps_files_on_drop(workspace: Workspace):
    sql(workspace, "CREATE TABLE ext (id INT) LOCATION 's3://bucket/ext'; INSERT INTO ext VALUES (7)")
    sql(workspace, "DROP TABLE ext")
    sql(workspace, "CREATE TABLE ext_again LOCATION 's3://bucket/ext'")

    assert workspace.catalog_service.get_table("main.default.ext_again").table_type == "EXTERNAL"
    assert sql(workspace, "SELECT * FROM ext_again") == [{"id": 7}]


def test_create_table_as_select_into_used_location_fails(workspace: Workspace):
    sql(workspace, "CREATE TABLE ext (id INT) LOCATION 's3://bucket/ext'")

    with pytest.raises(InvalidParameterValue):
        sql(workspace, "CREATE TABLE other LOCATION 's3://bucket/ext' AS SELECT 1 AS id")


def test_views(orders_workspace: Workspace):
    sql(orders_workspace, "CREATE VIEW polish COMMENT 'PL only' AS SELECT * FROM orders WHERE country = 'PL'")
    assert sql(orders_workspace, "SELECT COUNT(*) AS n FROM polish") == [{"n": 2}]

    sql(orders_workspace, "CREATE OR REPLACE VIEW polish AS SELECT * FROM orders WHERE country = 'DE'")
    assert sql(orders_workspace, "SELECT COUNT(*) AS n FROM polish") == [{"n": 1}]

    with pytest.raises(InvalidParameterValue):
        sql(orders_workspace, "DROP TABLE polish")
    sql(orders_workspace, "DROP VIEW polish")

    assert not orders_workspace.catalog_service.table_exists("main.default.polish")


def test_view_over_missing_table_is_rejected(workspace: Workspace):
    with pytest.raises(ResourceNotFound):
        sql(workspace, "CREATE VIEW broken AS SELECT * FROM missing")


def test_temporary_views(orders_workspace: Workspace):
    sql(orders_workspace, "CREATE OR REPLACE TEMP VIEW big AS SELECT * FROM orders WHERE amount > 8")

    assert sql(orders_workspace, "SELECT COUNT(*) AS n FROM big") == [{"n": 2}]
    assert ("big", True) in [(row["tableName"], row["isTemporary"]) for row in sql(orders_workspace, "SHOW TABLES")]
    assert column(orders_workspace, "DESCRIBE big", "col_name") == ["order_id", "amount", "country"]

    sql(orders_workspace, "DROP VIEW big")
    assert "big" not in orders_workspace.session.registered_views


def test_show_tables_in_schema(orders_workspace: Workspace):
    sql(orders_workspace, "CREATE SCHEMA main.sales; CREATE TABLE main.sales.t AS SELECT 1 AS id")

    rows = sql(orders_workspace, "SHOW TABLES IN main.sales")

    assert rows == [{"database": "sales", "tableName": "t", "isTemporary": False}]


def test_describe_table_and_extended(orders_workspace: Workspace):
    assert sql(orders_workspace, "DESCRIBE TABLE orders") == [
        {"col_name": "order_id", "data_type": "bigint", "comment": None},
        {"col_name": "amount", "data_type": "double", "comment": None},
        {"col_name": "country", "data_type": "string", "comment": None},
    ]

    extended = {row["col_name"]: row["data_type"] for row in sql(orders_workspace, "DESCRIBE EXTENDED orders")}

    assert extended["Type"] == "MANAGED"
    assert extended["Location"].startswith("lake:/__managed/main/default/")


def test_describe_view_lists_its_columns(orders_workspace: Workspace):
    sql(orders_workspace, "CREATE VIEW totals AS SELECT country, SUM(amount) AS total FROM orders GROUP BY country")

    assert column(orders_workspace, "DESCRIBE totals", "col_name") == ["country", "total"]


def test_comments(orders_workspace: Workspace):
    sql(orders_workspace, """
        COMMENT ON TABLE orders IS 'All orders';
        COMMENT ON SCHEMA main.default IS 'Default things';
        COMMENT ON CATALOG main IS 'It''s the main one'
    """)

    assert orders_workspace.catalog_service.get_table("main.default.orders").comment == "All orders"
    assert orders_workspace.catalog_service.get_schema("main.default").comment == "Default things"
    assert orders_workspace.catalog_service.get_catalog("main").comment == "It's the main one"


def test_set_spark_configuration(workspace: Workspace):
    rows = sql(workspace, "SET spark.sql.shuffle.partitions = 8")

    assert {"key": "spark.sql.shuffle.partitions", "value": "8"} in rows
    assert workspace.session.spark_conf["spark.sql.shuffle.partitions"] == "8"


def test_insert_with_column_list_fills_missing_with_null(orders_workspace: Workspace):
    result = sql(orders_workspace, "INSERT INTO orders (order_id, country) VALUES (4, 'CZ')")

    assert result == [{"num_affected_rows": 1, "num_inserted_rows": 1}]
    assert sql(orders_workspace, "SELECT * FROM orders WHERE order_id = 4") == [{"order_id": 4, "amount": None, "country": "CZ"}]


def test_insert_select_from_same_table_doubles_rows(orders_workspace: Workspace):
    sql(orders_workspace, "INSERT INTO orders SELECT * FROM orders")

    assert sql(orders_workspace, "SELECT COUNT(*) AS n FROM orders") == [{"n": 6}]


def test_insert_overwrite(orders_workspace: Workspace):
    sql(orders_workspace, "INSERT OVERWRITE orders SELECT * FROM orders WHERE country = 'DE'")

    assert order_amounts(orders_workspace) == [(2, 20.5)]


def test_insert_null_into_not_null_column_fails(workspace: Workspace):
    sql(workspace, "CREATE TABLE strict (id BIGINT NOT NULL, note STRING)")

    with pytest.raises(Exception):
        sql(workspace, "INSERT INTO strict (note) VALUES ('no id')")

    assert sql(workspace, "SELECT COUNT(*) AS n FROM strict") == [{"n": 0}]


def test_semicolon_inside_string_does_not_split_statements(workspace: Workspace):
    sql(workspace, "CREATE TABLE notes (text STRING); INSERT INTO notes VALUES ('a;b')")

    assert sql(workspace, "SELECT text FROM notes") == [{"text": "a;b"}]


def test_update(orders_workspace: Workspace):
    result = sql(orders_workspace, "UPDATE orders SET amount = amount * 2 WHERE country = 'PL'")

    assert result == [{"num_affected_rows": 2}]
    assert order_amounts(orders_workspace) == [(1, 20.0), (2, 20.5), (3, 14.5)]


def test_update_with_alias_and_qualified_column(orders_workspace: Workspace):
    sql(orders_workspace, "UPDATE main.default.orders o SET o.amount = 0 WHERE o.order_id = 2")

    assert order_amounts(orders_workspace) == [(1, 10.0), (2, 0.0), (3, 7.25)]


def test_update_keeps_column_types(orders_workspace: Workspace):
    sql(orders_workspace, "UPDATE orders SET amount = 1")

    assert column(orders_workspace, "DESCRIBE orders", "data_type") == ["bigint", "double", "string"]


def test_update_matching_nothing_does_not_commit(orders_workspace: Workspace):
    location = orders_workspace.catalog_service.get_table("main.default.orders").storage_location
    version_before = orders_workspace.delta_store.current_version(location)

    assert sql(orders_workspace, "UPDATE orders SET amount = 0 WHERE country = 'XX'") == [{"num_affected_rows": 0}]
    assert orders_workspace.delta_store.current_version(location) == version_before


def test_delete(orders_workspace: Workspace):
    assert sql(orders_workspace, "DELETE FROM orders WHERE country = 'PL'") == [{"num_affected_rows": 2}]
    assert order_amounts(orders_workspace) == [(2, 20.5)]

    sql(orders_workspace, "DELETE FROM orders")
    assert sql(orders_workspace, "SELECT COUNT(*) AS n FROM orders") == [{"n": 0}]


def test_merge_upsert_with_stars(orders_workspace: Workspace):
    sql(orders_workspace, """
        CREATE TABLE updates AS SELECT * FROM (VALUES (1, 99.0, 'PL', false), (2, 0.0, 'DE', true), (4, 5.0, 'CZ', false))
            AS updates(order_id, amount, country, deleted)
    """)

    sql(orders_workspace, """
        MERGE INTO orders t USING updates s ON t.order_id = s.order_id
        WHEN MATCHED AND s.deleted THEN DELETE
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

    assert order_amounts(orders_workspace) == [(1, 99.0), (3, 7.25), (4, 5.0)]


def test_merge_with_explicit_columns_and_not_matched_by_source(orders_workspace: Workspace):
    sql(orders_workspace, """
        MERGE INTO orders AS t
        USING (SELECT 1 AS order_id, 1.5 AS amount UNION ALL SELECT 5, 2.5) AS s ON t.order_id = s.order_id
        WHEN MATCHED THEN UPDATE SET t.amount = s.amount
        WHEN NOT MATCHED THEN INSERT (order_id, amount, country) VALUES (s.order_id, s.amount, 'NEW')
        WHEN NOT MATCHED BY SOURCE THEN DELETE
    """)

    assert order_amounts(orders_workspace) == [(1, 1.5), (5, 2.5)]


def test_writing_to_view_or_temp_view_fails(orders_workspace: Workspace):
    sql(orders_workspace, "CREATE VIEW v AS SELECT * FROM orders; CREATE TEMP VIEW tv AS SELECT * FROM orders")

    with pytest.raises(InvalidParameterValue):
        sql(orders_workspace, "DELETE FROM v")
    with pytest.raises(UnsupportedStatement):
        sql(orders_workspace, "INSERT INTO tv VALUES (1, 1.0, 'PL')")


def test_history_names_each_operation(orders_workspace: Workspace):
    sql(orders_workspace, "UPDATE orders SET amount = 1 WHERE order_id = 1")
    sql(orders_workspace, "DELETE FROM orders WHERE order_id = 2")
    sql(orders_workspace, "MERGE INTO orders t USING (SELECT 3 AS order_id) s ON t.order_id = s.order_id WHEN MATCHED THEN DELETE")

    history = sql(orders_workspace, "DESCRIBE HISTORY orders")

    assert [entry["operation"] for entry in history] == ["MERGE", "DELETE", "UPDATE", "INSERT", "CREATE TABLE"]
    assert [entry["version"] for entry in history] == [4, 3, 2, 1, 0]


def test_version_as_of_after_update(orders_workspace: Workspace):
    sql(orders_workspace, "UPDATE orders SET amount = 0")

    assert column(orders_workspace, "SELECT SUM(amount) AS total FROM orders VERSION AS OF 1", "total") == [37.75]


def test_restore_to_version(orders_workspace: Workspace):
    sql(orders_workspace, "DELETE FROM orders WHERE country = 'PL'")

    sql(orders_workspace, "RESTORE TABLE orders TO VERSION AS OF 1")

    assert sql(orders_workspace, "SELECT COUNT(*) AS n FROM orders") == [{"n": 3}]
    assert sql(orders_workspace, "DESCRIBE HISTORY orders")[0]["operation"] == "RESTORE"


def test_restore_to_timestamp(orders_workspace: Workspace):
    after_insert = sql(orders_workspace, "DESCRIBE HISTORY orders")[0]["timestamp"]
    time.sleep(0.05)
    sql(orders_workspace, "DELETE FROM orders")

    sql(orders_workspace, f"RESTORE orders TO TIMESTAMP AS OF '{after_insert.isoformat()}'")

    assert sql(orders_workspace, "SELECT COUNT(*) AS n FROM orders") == [{"n": 3}]


def test_time_travel_before_first_commit_fails(orders_workspace: Workspace):
    with pytest.raises(InvalidParameterValue) as raised:
        sql(orders_workspace, "SELECT * FROM orders TIMESTAMP AS OF '2000-01-01'")

    assert raised.value.error_code == "DELTA_TIMESTAMP_BEFORE_FIRST_COMMIT"


def test_timestamp_as_of_matches_history_timestamps(orders_workspace: Workspace):
    history = sql(orders_workspace, "DESCRIBE HISTORY orders")
    after_insert = history[0]["timestamp"]
    after_create = history[1]["timestamp"]

    assert sql(orders_workspace, f"SELECT COUNT(*) AS n FROM orders TIMESTAMP AS OF '{after_insert.isoformat()}'") == [{"n": 3}]
    if after_create < after_insert:
        assert sql(orders_workspace, f"SELECT COUNT(*) AS n FROM orders TIMESTAMP AS OF '{after_create.isoformat()}'") == [{"n": 0}]


def test_optimize_and_vacuum(orders_workspace: Workspace):
    sql(orders_workspace, "INSERT INTO orders VALUES (4, 1.0, 'CZ'); INSERT INTO orders VALUES (5, 2.0, 'CZ')")

    sql(orders_workspace, "OPTIMIZE orders")
    vacuumed = sql(orders_workspace, "VACUUM orders RETAIN 0 HOURS")[0]

    assert vacuumed["num_deleted_files"] > 0
    assert sql(orders_workspace, "DESCRIBE DETAIL orders")[0]["numFiles"] == 1
    assert sql(orders_workspace, "SELECT COUNT(*) AS n FROM orders") == [{"n": 5}]


def test_describe_detail(orders_workspace: Workspace):
    detail = sql(orders_workspace, "DESCRIBE DETAIL main.default.orders")[0]

    assert (detail["format"], detail["name"], detail["version"]) == ("delta", "main.default.orders", 1)
    assert detail["sizeInBytes"] > 0


def test_unsupported_command_is_reported(workspace: Workspace):
    with pytest.raises(UnsupportedStatement):
        sql(workspace, "SHOW VIEWS")


def test_query_history_records_successes_and_failures(orders_workspace: Workspace):
    with pytest.raises(ResourceNotFound):
        sql(orders_workspace, "SELECT * FROM missing")

    history = orders_workspace.query_history.list_queries(10)

    assert history[0].status == "FAILED"
    assert "missing" in history[0].error_message
    assert [(query.statement_type, query.status) for query in history[1:]] == [("INSERT", "FINISHED")]
    assert history[1].rows_produced == 1


def test_parameters_reach_queries(workspace: Workspace):
    assert workspace.statement_executor.execute("SELECT ? + ? AS total", [1, 2]).to_pylist() == [{"total": 3}]


def test_empty_statement_is_rejected(workspace: Workspace):
    with pytest.raises(InvalidParameterValue):
        sql(workspace, " ; ")


def test_rewrite_preserves_arrow_types(orders_workspace: Workspace):
    location = orders_workspace.catalog_service.get_table("main.default.orders").storage_location
    sql(orders_workspace, "UPDATE orders SET country = 'XX' WHERE order_id = 3")

    written_types = orders_workspace.delta_store.read(location).schema.types

    assert pa.types.is_int64(written_types[0]) and pa.types.is_float64(written_types[1])
