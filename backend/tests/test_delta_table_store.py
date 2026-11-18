import pyarrow as pa
import pytest

from drb_emu.lake import DeltaTableStore, LakePathResolver

ORDERS_LOCATION = "dbfs:/tables/orders"


def order_ids(table: pa.Table) -> list[int]:
    return table.sort_by("order_id").column("order_id").to_pylist()


def test_location_without_delta_log_is_not_a_table(delta_store: DeltaTableStore):
    assert not delta_store.exists(ORDERS_LOCATION)


def test_first_write_creates_version_zero(delta_store: DeltaTableStore, orders: pa.Table):
    version = delta_store.write(ORDERS_LOCATION, orders, mode="append")

    assert version == 0
    assert delta_store.exists(ORDERS_LOCATION)
    assert order_ids(delta_store.read(ORDERS_LOCATION)) == [1, 2, 3]


def test_append_adds_version_and_keeps_old_one_readable(delta_store: DeltaTableStore, orders: pa.Table):
    delta_store.write(ORDERS_LOCATION, orders, mode="append")
    version = delta_store.write(ORDERS_LOCATION, orders, mode="append")

    assert version == 1
    assert delta_store.current_version(ORDERS_LOCATION) == 1
    assert delta_store.read(ORDERS_LOCATION).num_rows == 6
    assert delta_store.read(ORDERS_LOCATION, version=0).num_rows == 3


def test_overwrite_replaces_rows(delta_store: DeltaTableStore, orders: pa.Table):
    delta_store.write(ORDERS_LOCATION, orders, mode="append")
    delta_store.write(ORDERS_LOCATION, orders.slice(0, 1), mode="overwrite")

    assert order_ids(delta_store.read(ORDERS_LOCATION)) == [1]


def test_history_has_one_entry_per_commit(delta_store: DeltaTableStore, orders: pa.Table):
    delta_store.write(ORDERS_LOCATION, orders, mode="append")
    delta_store.write(ORDERS_LOCATION, orders, mode="append")

    history = delta_store.history(ORDERS_LOCATION)

    assert len(history) == 2
    assert all("operation" in commit for commit in history)


def test_delete_rows_by_predicate(delta_store: DeltaTableStore, orders: pa.Table):
    delta_store.write(ORDERS_LOCATION, orders, mode="append")

    delta_store.delete_rows(ORDERS_LOCATION, "country = 'DE'")

    assert order_ids(delta_store.read(ORDERS_LOCATION)) == [1, 3]


def test_partitioned_write_creates_partition_folders(delta_store: DeltaTableStore, path_resolver: LakePathResolver, orders: pa.Table):
    delta_store.write(ORDERS_LOCATION, orders, mode="append", partition_by=("country",))

    table_folder = path_resolver.resolve(ORDERS_LOCATION)
    assert (table_folder / "country=PL").is_dir()
    assert (table_folder / "country=DE").is_dir()


def test_external_uri_lands_in_mapped_folder(delta_store: DeltaTableStore, path_resolver: LakePathResolver, orders: pa.Table):
    delta_store.write("s3://sales-bucket/orders", orders, mode="append")

    assert (path_resolver.lake_root / "s3" / "sales-bucket" / "orders" / "_delta_log").is_dir()


def test_unknown_write_mode_is_rejected(delta_store: DeltaTableStore, orders: pa.Table):
    with pytest.raises(ValueError):
        delta_store.write(ORDERS_LOCATION, orders, mode="merge")
