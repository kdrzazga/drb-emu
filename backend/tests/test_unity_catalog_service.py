import pyarrow as pa
import pytest

from drb_emu.catalog import UnityCatalogService
from drb_emu.errors import InvalidParameterValue, ResourceAlreadyExists, ResourceNotEmpty, ResourceNotFound
from drb_emu.workspace import Workspace


@pytest.fixture
def catalog_service(workspace: Workspace) -> UnityCatalogService:
    return workspace.catalog_service


def test_default_catalog_and_schema_exist(catalog_service: UnityCatalogService):
    assert [catalog.name for catalog in catalog_service.list_catalogs()] == ["main"]
    assert [schema.name for schema in catalog_service.list_schemas("main")] == ["default"]


def test_default_objects_are_created_once(catalog_service: UnityCatalogService):
    catalog_service.ensure_default_objects()

    assert len(catalog_service.list_catalogs()) == 1


def test_new_catalog_gets_default_schema(catalog_service: UnityCatalogService):
    catalog = catalog_service.create_catalog("Sales", "Sales data")

    assert (catalog.name, catalog.comment) == ("sales", "Sales data")
    assert catalog_service.get_schema("sales.default").full_name == "sales.default"


def test_duplicate_catalog_is_rejected(catalog_service: UnityCatalogService):
    with pytest.raises(ResourceAlreadyExists):
        catalog_service.create_catalog("main")


def test_invalid_name_is_rejected(catalog_service: UnityCatalogService):
    with pytest.raises(InvalidParameterValue):
        catalog_service.create_catalog("bad name")


def test_schema_in_missing_catalog_is_not_found(catalog_service: UnityCatalogService):
    with pytest.raises(ResourceNotFound):
        catalog_service.create_schema("ghost", "sales")


def test_write_creates_managed_table_with_columns(catalog_service: UnityCatalogService, orders: pa.Table):
    table = catalog_service.write_table("main.default.orders", orders, "overwrite")

    assert table.table_type == "MANAGED"
    assert table.data_source_format == "DELTA"
    assert table.storage_location == f"lake:/__managed/main/default/{table.table_id}"
    assert [(column.name, column.type_name, column.type_text) for column in table.columns] == [
        ("order_id", "LONG", "bigint"),
        ("amount", "DOUBLE", "double"),
        ("country", "STRING", "string"),
    ]


def test_write_to_existing_table_appends_and_refreshes_columns(workspace: Workspace, catalog_service: UnityCatalogService, orders: pa.Table):
    catalog_service.write_table("main.default.orders", orders, "overwrite")
    table = catalog_service.write_table("main.default.orders", orders, "append")

    assert workspace.delta_store.read(table.storage_location).num_rows == 6
    assert len(catalog_service.get_table("main.default.orders").columns) == 3


def test_write_to_missing_schema_is_not_found(catalog_service: UnityCatalogService, orders: pa.Table):
    with pytest.raises(ResourceNotFound):
        catalog_service.write_table("main.ghost.orders", orders, "overwrite")


def test_external_table_reads_columns_from_delta_log(workspace: Workspace, catalog_service: UnityCatalogService, orders: pa.Table):
    workspace.delta_store.write("s3://sales-bucket/orders", orders, "overwrite")

    table = catalog_service.create_external_table("main.default.external_orders", "s3://sales-bucket/orders")

    assert table.table_type == "EXTERNAL"
    assert table.storage_location == "s3://sales-bucket/orders"
    assert [column.name for column in table.columns] == ["order_id", "amount", "country"]


def test_external_table_needs_existing_delta_table(catalog_service: UnityCatalogService):
    with pytest.raises(InvalidParameterValue):
        catalog_service.create_external_table("main.default.ghost", "s3://sales-bucket/nothing")


def test_view_with_invalid_sql_is_rejected(catalog_service: UnityCatalogService):
    with pytest.raises(InvalidParameterValue):
        catalog_service.create_view("main.default.broken", "SELECT FROM WHERE (")


def test_duplicate_table_name_is_rejected(catalog_service: UnityCatalogService, orders: pa.Table):
    catalog_service.write_table("main.default.orders", orders, "overwrite")

    with pytest.raises(ResourceAlreadyExists):
        catalog_service.create_view("main.default.orders", "SELECT 1")


def test_cannot_write_into_view(catalog_service: UnityCatalogService, orders: pa.Table):
    catalog_service.create_view("main.default.one", "SELECT 1 AS value")

    with pytest.raises(InvalidParameterValue):
        catalog_service.write_table("main.default.one", orders, "append")


def test_missing_table_reports_table_or_view_not_found(catalog_service: UnityCatalogService):
    with pytest.raises(ResourceNotFound) as raised:
        catalog_service.get_table("main.default.missing")

    assert raised.value.error_code == "TABLE_OR_VIEW_NOT_FOUND"


def test_dropping_managed_table_removes_its_files(workspace: Workspace, catalog_service: UnityCatalogService, orders: pa.Table):
    table = catalog_service.write_table("main.default.orders", orders, "overwrite")
    table_folder = workspace.path_resolver.resolve(table.storage_location)

    catalog_service.delete_table("main.default.orders")

    assert not table_folder.exists()
    assert not catalog_service.table_exists("main.default.orders")


def test_dropping_external_table_keeps_its_files(workspace: Workspace, catalog_service: UnityCatalogService, orders: pa.Table):
    workspace.delta_store.write("s3://sales-bucket/orders", orders, "overwrite")
    catalog_service.create_external_table("main.default.external_orders", "s3://sales-bucket/orders")

    catalog_service.delete_table("main.default.external_orders")

    assert workspace.delta_store.exists("s3://sales-bucket/orders")


def test_non_empty_schema_needs_force(workspace: Workspace, catalog_service: UnityCatalogService, orders: pa.Table):
    catalog_service.create_schema("main", "sales")
    table = catalog_service.write_table("main.sales.orders", orders, "overwrite")

    with pytest.raises(ResourceNotEmpty):
        catalog_service.delete_schema("main.sales")

    catalog_service.delete_schema("main.sales", force=True)

    assert [schema.name for schema in catalog_service.list_schemas("main")] == ["default"]
    assert not workspace.path_resolver.resolve(table.storage_location).exists()


def test_catalog_with_only_default_schema_can_be_dropped(catalog_service: UnityCatalogService):
    catalog_service.create_catalog("scratch")

    catalog_service.delete_catalog("scratch")

    assert [catalog.name for catalog in catalog_service.list_catalogs()] == ["main"]


def test_non_empty_catalog_needs_force(catalog_service: UnityCatalogService, orders: pa.Table):
    catalog_service.create_catalog("sales")
    catalog_service.write_table("sales.default.orders", orders, "overwrite")

    with pytest.raises(ResourceNotEmpty):
        catalog_service.delete_catalog("sales")

    catalog_service.delete_catalog("sales", force=True)

    with pytest.raises(ResourceNotFound):
        catalog_service.get_catalog("sales")


def test_metastore_survives_workspace_restart(tmp_path, orders: pa.Table):
    first_workspace = Workspace(tmp_path / "lake", tmp_path / "metastore" / "metastore.db")
    first_workspace.catalog_service.write_table("main.default.orders", orders, "overwrite")
    first_workspace.close()

    second_workspace = Workspace(tmp_path / "lake", tmp_path / "metastore" / "metastore.db")
    try:
        assert second_workspace.catalog_service.table_exists("main.default.orders")
        assert len(second_workspace.catalog_service.list_catalogs()) == 1
    finally:
        second_workspace.close()
