import pyarrow as pa
import pytest

from drb_emu.errors import InvalidParameterValue, ResourceNotFound, UnsupportedStatement
from drb_emu.workspace import Workspace


@pytest.fixture
def sales_workspace(workspace: Workspace, orders: pa.Table) -> Workspace:
    customers = pa.table({"country": ["PL", "DE"], "country_name": ["Poland", "Germany"]})
    workspace.catalog_service.create_schema("main", "sales")
    workspace.catalog_service.write_table("main.sales.orders", orders, "overwrite")
    workspace.catalog_service.write_table("main.sales.countries", customers, "overwrite")
    return workspace


def query(workspace: Workspace, sql: str) -> list[dict]:
    return workspace.statement_executor.execute(sql).to_pylist()


def test_three_part_name(sales_workspace: Workspace):
    assert query(sales_workspace, "SELECT COUNT(*) AS orders FROM main.sales.orders") == [{"orders": 3}]


def test_two_part_name_uses_current_catalog(sales_workspace: Workspace):
    assert query(sales_workspace, "SELECT COUNT(*) AS orders FROM sales.orders") == [{"orders": 3}]


def test_one_part_name_uses_current_schema(sales_workspace: Workspace):
    sales_workspace.session.use_schema("sales")

    assert query(sales_workspace, "SELECT COUNT(*) AS orders FROM orders") == [{"orders": 3}]


def test_names_are_case_insensitive(sales_workspace: Workspace):
    assert query(sales_workspace, "SELECT COUNT(*) AS orders FROM Main.SALES.Orders") == [{"orders": 3}]


def test_unaliased_table_name_qualifies_columns(sales_workspace: Workspace):
    rows = query(sales_workspace, "SELECT orders.order_id FROM main.sales.orders WHERE orders.country = 'DE'")

    assert rows == [{"order_id": 2}]


def test_join_with_aliases(sales_workspace: Workspace):
    rows = query(sales_workspace, """
        SELECT c.country_name, SUM(o.amount) AS total
        FROM main.sales.orders o JOIN main.sales.countries c ON o.country = c.country
        GROUP BY c.country_name ORDER BY c.country_name
    """)

    assert rows == [{"country_name": "Germany", "total": 20.5}, {"country_name": "Poland", "total": 17.25}]


def test_subquery_tables_are_resolved(sales_workspace: Workspace):
    rows = query(sales_workspace, "SELECT COUNT(*) AS big FROM (SELECT * FROM main.sales.orders WHERE amount > 8)")

    assert rows == [{"big": 2}]


def test_cte_name_is_not_looked_up_in_catalog(sales_workspace: Workspace):
    rows = query(sales_workspace, "WITH polish AS (SELECT * FROM main.sales.orders WHERE country = 'PL') SELECT COUNT(*) AS n FROM polish")

    assert rows == [{"n": 2}]


def test_temporary_view_shadows_catalog(sales_workspace: Workspace):
    sales_workspace.session.use_schema("sales")
    sales_workspace.session.register_arrow("orders", pa.table({"order_id": [99]}))

    assert query(sales_workspace, "SELECT order_id FROM orders") == [{"order_id": 99}]
    assert query(sales_workspace, "SELECT COUNT(*) AS n FROM main.sales.orders") == [{"n": 3}]


def test_view_is_expanded(sales_workspace: Workspace):
    sales_workspace.catalog_service.create_view("main.sales.polish_orders", "SELECT * FROM main.sales.orders WHERE country = 'PL'")

    assert query(sales_workspace, "SELECT COUNT(*) AS n FROM main.sales.polish_orders") == [{"n": 2}]


def test_view_resolves_unqualified_names_in_its_own_schema(sales_workspace: Workspace):
    sales_workspace.catalog_service.create_view("main.sales.german_orders", "SELECT order_id FROM orders WHERE country = 'DE'")

    assert query(sales_workspace, "SELECT * FROM main.sales.german_orders") == [{"order_id": 2}]


def test_nested_views(sales_workspace: Workspace):
    sales_workspace.catalog_service.create_view("main.sales.polish_orders", "SELECT * FROM orders WHERE country = 'PL'")
    sales_workspace.catalog_service.create_view("main.default.big_polish_orders", "SELECT order_id FROM main.sales.polish_orders WHERE amount > 8")

    assert query(sales_workspace, "SELECT * FROM big_polish_orders") == [{"order_id": 1}]


def test_self_referencing_view_is_stopped(sales_workspace: Workspace):
    sales_workspace.catalog_service.create_view("main.default.loop", "SELECT * FROM main.default.loop")

    with pytest.raises(InvalidParameterValue):
        query(sales_workspace, "SELECT * FROM loop")


def test_version_as_of_reads_older_snapshot(sales_workspace: Workspace, orders: pa.Table):
    sales_workspace.catalog_service.write_table("main.sales.orders", orders, "append")

    rows = query(sales_workspace, """
        SELECT (SELECT COUNT(*) FROM main.sales.orders) AS now,
               (SELECT COUNT(*) FROM main.sales.orders VERSION AS OF 0) AS first
    """)

    assert rows == [{"now": 6, "first": 3}]


def test_timestamp_as_of_is_not_supported_yet(sales_workspace: Workspace):
    with pytest.raises(UnsupportedStatement):
        query(sales_workspace, "SELECT * FROM main.sales.orders TIMESTAMP AS OF '2026-01-01'")


def test_missing_table_is_reported(sales_workspace: Workspace):
    with pytest.raises(ResourceNotFound) as raised:
        query(sales_workspace, "SELECT * FROM main.sales.missing")

    assert raised.value.error_code == "TABLE_OR_VIEW_NOT_FOUND"


def test_table_functions_are_left_alone(sales_workspace: Workspace):
    assert query(sales_workspace, "SELECT COUNT(*) AS n FROM range(4)") == [{"n": 4}]


def test_non_query_statement_is_unsupported(sales_workspace: Workspace):
    with pytest.raises(UnsupportedStatement):
        query(sales_workspace, "DROP TABLE main.sales.orders")


def test_syntax_error_is_reported(sales_workspace: Workspace):
    with pytest.raises(InvalidParameterValue) as raised:
        query(sales_workspace, "SELECT FROM WHERE (")

    assert raised.value.error_code == "PARSE_SYNTAX_ERROR"


def test_multiple_statements_return_last_result(sales_workspace: Workspace):
    assert query(sales_workspace, "SELECT 1 AS first; SELECT 2 AS second") == [{"second": 2}]
