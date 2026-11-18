from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from drb_emu.api import create_app


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path / "lake", tmp_path / "metastore" / "metastore.db")) as test_client:
        yield test_client


def run_statement(client: TestClient, statement: str) -> dict:
    return client.post("/api/2.0/sql/statements", json={"statement": statement}).json()


def test_history_lists_newest_first_with_matching_ids(client: TestClient):
    created = run_statement(client, "CREATE TABLE t AS SELECT 1 AS id")
    failed = run_statement(client, "SELECT * FROM missing")

    queries = client.get("/api/2.0/sql/history/queries").json()["res"]

    assert [query["query_id"] for query in queries] == [failed["statement_id"], created["statement_id"]]
    assert [(query["statement_type"], query["status"]) for query in queries] == [("SELECT", "FAILED"), ("CREATE", "FINISHED")]
    assert queries[1]["query_text"] == "CREATE TABLE t AS SELECT 1 AS id"


def test_history_respects_max_results(client: TestClient):
    for number in range(3):
        run_statement(client, f"SELECT {number}")

    queries = client.get("/api/2.0/sql/history/queries", params={"max_results": 2}).json()["res"]

    assert len(queries) == 2


def test_sql_ddl_and_dml_through_statement_api(client: TestClient):
    steps = [
        "CREATE SCHEMA main.sales",
        "CREATE TABLE main.sales.orders (order_id BIGINT, amount DOUBLE)",
        "INSERT INTO main.sales.orders VALUES (1, 10.0), (2, 20.0)",
        "UPDATE main.sales.orders SET amount = amount + 1 WHERE order_id = 2",
    ]
    for step in steps:
        assert run_statement(client, step)["status"]["state"] == "SUCCEEDED", step

    body = run_statement(client, "SELECT order_id, amount FROM main.sales.orders ORDER BY order_id")
    table = client.get("/api/2.1/unity-catalog/tables/main.sales.orders").json()

    assert body["result"]["data_array"] == [[1, 10.0], [2, 21.0]]
    assert [column["type_text"] for column in table["columns"]] == ["bigint", "double"]


def test_not_null_violation_fails_statement(client: TestClient):
    run_statement(client, "CREATE TABLE strict (id BIGINT NOT NULL)")

    body = run_statement(client, "INSERT INTO strict SELECT NULL")

    assert body["status"]["state"] == "FAILED"
