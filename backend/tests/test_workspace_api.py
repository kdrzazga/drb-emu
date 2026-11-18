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


def test_session_reflects_use_and_temp_views(client: TestClient):
    run_statement(client, "CREATE SCHEMA main.sales; USE main.sales; CREATE TEMP VIEW numbers AS SELECT 1 AS n")

    session = client.get("/api/drb/session").json()

    assert (session["current_catalog"], session["current_schema"]) == ("main", "sales")
    assert session["temporary_views"] == ["numbers"]


def test_catalog_tree_lists_tables_with_columns(client: TestClient):
    run_statement(client, "CREATE SCHEMA main.sales; CREATE TABLE main.sales.orders (order_id BIGINT, amount DOUBLE)")

    catalogs = client.get("/api/drb/catalog-tree").json()["catalogs"]
    main = next(catalog for catalog in catalogs if catalog["name"] == "main")
    sales = next(schema for schema in main["schemas"] if schema["name"] == "sales")

    assert sales["tables"] == [{
        "name": "orders",
        "table_type": "MANAGED",
        "columns": [{"name": "order_id", "type_text": "bigint"}, {"name": "amount", "type_text": "double"}],
    }]


def test_non_finite_floats_and_binary_are_json_safe(client: TestClient):
    body = run_statement(client, "SELECT CAST('NaN' AS DOUBLE) AS nan, CAST('inf' AS DOUBLE) AS inf, CAST('ab' AS BINARY) AS raw")

    assert body["status"]["state"] == "SUCCEEDED"
    assert body["result"]["data_array"] == [["NaN", "Infinity", "6162"]]


def test_timestamps_serialize_to_iso_strings(client: TestClient):
    run_statement(client, "CREATE TABLE t AS SELECT 1 AS id")

    body = run_statement(client, "DESCRIBE HISTORY t")

    assert body["status"]["state"] == "SUCCEEDED"
    assert "T" in body["result"]["data_array"][0][1]
