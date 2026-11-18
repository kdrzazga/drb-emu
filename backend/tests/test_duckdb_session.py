import duckdb
import pyarrow as pa
import pytest

from drb_emu.lake import DeltaTableStore
from drb_emu.sql import DuckDBSession

ORDERS_LOCATION = "dbfs:/tables/orders"


def test_queries_registered_delta_table(session: DuckDBSession, delta_store: DeltaTableStore, orders: pa.Table):
    delta_store.write(ORDERS_LOCATION, orders, mode="append")
    session.register_delta_table("orders", ORDERS_LOCATION)

    totals = session.execute("SELECT country, SUM(amount) AS total FROM orders GROUP BY country ORDER BY country")

    assert totals.to_pylist() == [{"country": "DE", "total": 20.5}, {"country": "PL", "total": 17.25}]


def test_registers_older_version_for_time_travel(session: DuckDBSession, delta_store: DeltaTableStore, orders: pa.Table):
    delta_store.write(ORDERS_LOCATION, orders, mode="append")
    delta_store.write(ORDERS_LOCATION, orders, mode="append")
    session.register_delta_table("orders_now", ORDERS_LOCATION)
    session.register_delta_table("orders_v0", ORDERS_LOCATION, version=0)

    counts = session.execute("SELECT (SELECT COUNT(*) FROM orders_now) AS now, (SELECT COUNT(*) FROM orders_v0) AS v0")

    assert counts.to_pylist() == [{"now": 6, "v0": 3}]


def test_query_result_can_be_written_back_as_delta(session: DuckDBSession, delta_store: DeltaTableStore, orders: pa.Table):
    session.register_arrow("orders", orders)
    polish_orders = session.execute("SELECT * FROM orders WHERE country = 'PL'")

    delta_store.write("dbfs:/tables/polish_orders", polish_orders, mode="overwrite")

    assert delta_store.read("dbfs:/tables/polish_orders").num_rows == 2


def test_binds_positional_parameters(session: DuckDBSession):
    assert session.execute("SELECT ? + ? AS total", [2, 3]).to_pylist() == [{"total": 5}]


def test_statements_without_result_set_can_be_followed_by_query(session: DuckDBSession):
    session.execute("CREATE TABLE scratch (value INTEGER)")
    session.execute("INSERT INTO scratch VALUES (1), (2)")

    assert session.execute("SELECT SUM(value) AS total FROM scratch").to_pylist() == [{"total": 3}]


def test_unregistered_view_is_gone(session: DuckDBSession, orders: pa.Table):
    session.register_arrow("orders", orders)
    session.unregister("orders")

    assert "orders" not in session.registered_views
    with pytest.raises(duckdb.CatalogException):
        session.execute("SELECT * FROM orders")


def test_use_catalog_resets_schema_to_default(session: DuckDBSession):
    session.use_schema("sales")
    session.use_catalog("dev")

    assert (session.current_catalog, session.current_schema) == ("dev", "default")
