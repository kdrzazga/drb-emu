from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from drb_emu.api import create_app

UC = "/api/2.1/unity-catalog"
ORDERS_STATEMENT = "SELECT * FROM (VALUES (1, 10.0, 'PL'), (2, 20.5, 'DE'), (3, 7.25, 'PL')) AS orders(order_id, amount, country)"


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path / "lake", tmp_path / "metastore" / "metastore.db")) as test_client:
        yield test_client


def run_statement(client: TestClient, statement: str) -> dict:
    return client.post("/api/2.0/sql/statements", json={"statement": statement}).json()


def write_managed_orders(client: TestClient, table_name: str = "main.default.orders") -> dict:
    response = client.post("/api/drb/tables/write", json={"table_name": table_name, "statement": ORDERS_STATEMENT})
    assert response.status_code == 200
    return response.json()


def test_lists_default_catalog(client: TestClient):
    catalogs = client.get(f"{UC}/catalogs").json()["catalogs"]

    assert [catalog["name"] for catalog in catalogs] == ["main"]


def test_catalog_lifecycle(client: TestClient):
    created = client.post(f"{UC}/catalogs", json={"name": "sales", "comment": "Sales data"})

    assert created.status_code == 200
    assert client.get(f"{UC}/catalogs/sales").json()["comment"] == "Sales data"
    assert client.post(f"{UC}/catalogs", json={"name": "sales"}).status_code == 409
    assert client.delete(f"{UC}/catalogs/sales").status_code == 200
    assert client.get(f"{UC}/catalogs/sales").status_code == 404


def test_schema_lifecycle(client: TestClient):
    client.post(f"{UC}/schemas", json={"name": "sales", "catalog_name": "main"})

    schemas = client.get(f"{UC}/schemas", params={"catalog_name": "main"}).json()["schemas"]

    assert [schema["full_name"] for schema in schemas] == ["main.default", "main.sales"]
    assert client.get(f"{UC}/schemas/main.sales").json()["name"] == "sales"
    assert client.delete(f"{UC}/schemas/main.sales").status_code == 200
    assert client.get(f"{UC}/schemas/main.sales").status_code == 404


def test_write_by_table_name_creates_managed_table(client: TestClient):
    written = write_managed_orders(client)
    table = client.get(f"{UC}/tables/main.default.orders").json()

    assert (written["version"], written["row_count"]) == (0, 3)
    assert table["table_type"] == "MANAGED"
    assert table["storage_location"] == written["location"]
    assert [column["name"] for column in table["columns"]] == ["order_id", "amount", "country"]


def test_sql_reads_catalog_table(client: TestClient):
    write_managed_orders(client)

    body = run_statement(client, "SELECT country, COUNT(*) AS n FROM main.default.orders GROUP BY country ORDER BY country")

    assert body["status"]["state"] == "SUCCEEDED"
    assert body["result"]["data_array"] == [["DE", 1], ["PL", 2]]


def test_write_from_catalog_table_into_new_table(client: TestClient):
    write_managed_orders(client)

    written = client.post("/api/drb/tables/write", json={
        "table_name": "main.default.polish_orders",
        "statement": "SELECT * FROM orders WHERE country = 'PL'",
    }).json()

    assert written["row_count"] == 2
    assert run_statement(client, "SELECT COUNT(*) FROM polish_orders")["result"]["data_array"] == [[2]]


def test_write_needs_exactly_one_target(client: TestClient):
    response = client.post("/api/drb/tables/write", json={"statement": ORDERS_STATEMENT})

    assert response.status_code == 400


def test_external_table_registration(client: TestClient):
    client.post("/api/drb/tables/write", json={"location": "s3://sales-bucket/orders", "statement": ORDERS_STATEMENT})

    response = client.post(f"{UC}/tables", json={
        "name": "external_orders",
        "catalog_name": "main",
        "schema_name": "default",
        "table_type": "EXTERNAL",
        "storage_location": "s3://sales-bucket/orders",
    })

    assert response.status_code == 200
    assert run_statement(client, "SELECT COUNT(*) FROM external_orders")["result"]["data_array"] == [[3]]


def test_view_creation_and_query(client: TestClient):
    write_managed_orders(client)

    response = client.post(f"{UC}/tables", json={
        "name": "german_orders",
        "catalog_name": "main",
        "schema_name": "default",
        "table_type": "VIEW",
        "view_definition": "SELECT order_id FROM orders WHERE country = 'DE'",
    })

    assert response.json()["table_type"] == "VIEW"
    assert run_statement(client, "SELECT * FROM main.default.german_orders")["result"]["data_array"] == [[2]]


def test_managed_table_cannot_be_created_through_uc_endpoint(client: TestClient):
    response = client.post(f"{UC}/tables", json={"name": "t", "catalog_name": "main", "schema_name": "default", "table_type": "MANAGED"})

    assert response.status_code == 400


def test_list_and_delete_tables(client: TestClient):
    write_managed_orders(client)

    tables = client.get(f"{UC}/tables", params={"catalog_name": "main", "schema_name": "default"}).json()["tables"]

    assert [table["full_name"] for table in tables] == ["main.default.orders"]
    assert client.delete(f"{UC}/tables/main.default.orders").status_code == 200
    assert client.get(f"{UC}/tables/main.default.orders").status_code == 404


def test_missing_table_error_code(client: TestClient):
    response = client.get(f"{UC}/tables/main.default.missing")

    assert response.status_code == 404
    assert response.json()["error_code"] == "TABLE_OR_VIEW_NOT_FOUND"


def test_unsupported_statement_fails_cleanly(client: TestClient):
    body = run_statement(client, "CREATE TABLE t (id INT)")

    assert body["status"]["state"] == "FAILED"
    assert body["status"]["error"]["error_code"] == "UNSUPPORTED_STATEMENT"
