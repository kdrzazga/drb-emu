from pathlib import Path

import pytest

from drb_emu.lake import LakePathError, LakePathResolver


@pytest.mark.parametrize(("location", "expected_parts"), [
    ("dbfs:/", ("dbfs",)),
    ("dbfs:/mnt/raw/orders.csv", ("dbfs", "mnt", "raw", "orders.csv")),
    ("/dbfs/mnt/raw", ("dbfs", "mnt", "raw")),
    ("s3://sales-bucket/landing/2026", ("s3", "sales-bucket", "landing", "2026")),
    ("s3a://sales-bucket/landing", ("s3", "sales-bucket", "landing")),
    ("gs://events/day=1", ("gs", "events", "day=1")),
    ("abfss://raw@mystorage.dfs.core.windows.net/events/day=1", ("abfss", "mystorage", "raw", "events", "day=1")),
    ("/Volumes/main/sales/files/in.csv", ("volumes", "main", "sales", "files", "in.csv")),
    ("dbfs:/Volumes/main/sales/files", ("volumes", "main", "sales", "files")),
])
def test_maps_storage_uri_into_lake_folder(path_resolver: LakePathResolver, location: str, expected_parts: tuple):
    assert path_resolver.resolve(location) == path_resolver.lake_root.joinpath(*expected_parts)


@pytest.mark.parametrize("location", [
    "s3://bucket/../../escape",
    "/Volumes/../../escape",
    "dbfs:/..",
    "ftp://host/file",
    "C:/Windows/System32",
    "s3:///no-bucket",
    "abfss://mystorage.dfs.core.windows.net/no-container",
])
def test_rejects_unsupported_or_escaping_location(path_resolver: LakePathResolver, location: str):
    with pytest.raises(LakePathError):
        path_resolver.resolve(location)


def test_accepts_path_inside_lake(path_resolver: LakePathResolver):
    inside = path_resolver.lake_root / "dbfs" / "tmp"
    assert path_resolver.resolve(inside) == inside


def test_rejects_path_outside_lake(path_resolver: LakePathResolver, tmp_path: Path):
    with pytest.raises(LakePathError):
        path_resolver.resolve(tmp_path / "elsewhere")


def test_managed_table_location_is_under_managed_folder(path_resolver: LakePathResolver):
    location = path_resolver.managed_table_location("main", "sales", "a1b2c3")
    assert location == path_resolver.lake_root / "__managed" / "main" / "sales" / "a1b2c3"


def test_volume_location_matches_volumes_uri(path_resolver: LakePathResolver):
    assert path_resolver.volume_location("main", "sales", "files") == path_resolver.resolve("/Volumes/main/sales/files")
