from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from drb_emu.api import create_app

ORDERS_STATEMENT = "SELECT * FROM (VALUES (1, 10.0, 'PL'), (2, 20.5, 'DE'), (3, 7.25, 'PL')) AS orders(order_id, amount, country)"


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path / "lake")) as test_client:
        yield test_client


def run_statement(client: TestClient, statement: str, parameters: list | None = None) -> dict:
    response = client.post("/api/2.0/sql/statements", json={"statement": statement, "parameters": parameters})
    assert response.status_code == 200
    return response.json()


def write_orders(client: TestClient, location: str = "dbfs:/tables/orders") -> dict:
    response = client.post("/api/drb/tables/write", json={"location": location, "statement": ORDERS_STATEMENT})
    assert response.status_code == 200
    return response.json()


def test_health_reports_lake_root(client: TestClient, tmp_path: Path):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert Path(body["lake_root"]) == (tmp_path / "lake").resolve()


def test_statement_returns_schema_and_rows(client: TestClient):
    body = run_statement(client, "SELECT 42 AS answer, 'drb' AS name")

    assert body["status"]["state"] == "SUCCEEDED"
    assert [column["name"] for column in body["manifest"]["schema"]["columns"]] == ["answer", "name"]
    assert [column["type_name"] for column in body["manifest"]["schema"]["columns"]] == ["INT", "STRING"]
    assert body["result"]["data_array"] == [[42, "drb"]]


def test_statement_keeps_duplicate_column_names(client: TestClient):
    body = run_statement(client, "SELECT 1 AS value, 2 AS value")

    assert body["result"]["data_array"] == [[1, 2]]


def test_statement_binds_parameters(client: TestClient):
    body = run_statement(client, "SELECT ? * ? AS product", [6, 7])

    assert body["result"]["data_array"] == [[42]]


def test_failed_statement_reports_error(client: TestClient):
    body = run_statement(client, "SELECT * FROM missing_table")

    assert body["status"]["state"] == "FAILED"
    assert "missing_table" in body["status"]["error"]["message"]


def test_row_limit_truncates_result(client: TestClient):
    response = client.post("/api/2.0/sql/statements", json={"statement": "SELECT * FROM range(5)", "row_limit": 2})
    body = response.json()

    assert body["result"]["row_count"] == 2
    assert body["manifest"]["total_row_count"] == 5
    assert body["manifest"]["truncated"]


def test_written_table_can_be_registered_and_queried(client: TestClient):
    written = write_orders(client)
    registered = client.post("/api/drb/tables/register", json={"view_name": "orders", "location": "dbfs:/tables/orders"}).json()

    body = run_statement(client, "SELECT country, COUNT(*) AS orders FROM orders GROUP BY country ORDER BY country")

    assert (written["version"], written["row_count"]) == (0, 3)
    assert registered["version"] == 0
    assert body["result"]["data_array"] == [["DE", 1], ["PL", 2]]
    assert client.get("/api/drb/tables").json() == {"tables": ["orders"]}


def test_register_older_version(client: TestClient):
    write_orders(client)
    client.post("/api/drb/tables/write", json={"location": "dbfs:/tables/orders", "statement": ORDERS_STATEMENT, "mode": "append"})
    client.post("/api/drb/tables/register", json={"view_name": "orders_v0", "location": "dbfs:/tables/orders", "version": 0})

    body = run_statement(client, "SELECT COUNT(*) FROM orders_v0")

    assert body["result"]["data_array"] == [[3]]


def test_register_missing_table_is_not_found(client: TestClient):
    response = client.post("/api/drb/tables/register", json={"view_name": "ghost", "location": "dbfs:/tables/ghost"})

    assert response.status_code == 404


def test_location_outside_lake_is_rejected(client: TestClient):
    response = client.post("/api/drb/tables/register", json={"view_name": "escape", "location": "s3://bucket/../../escape"})

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_PARAMETER_VALUE"


def test_unregister_removes_view(client: TestClient):
    write_orders(client)
    client.post("/api/drb/tables/register", json={"view_name": "orders", "location": "dbfs:/tables/orders"})

    assert client.delete("/api/drb/tables/orders").status_code == 200
    assert client.delete("/api/drb/tables/orders").status_code == 404
    assert client.get("/api/drb/tables").json() == {"tables": []}


def test_write_with_unknown_mode_is_bad_request(client: TestClient):
    response = client.post("/api/drb/tables/write", json={"location": "dbfs:/tables/orders", "statement": ORDERS_STATEMENT, "mode": "merge"})

    assert response.status_code == 400
