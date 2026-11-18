from pathlib import Path, PurePosixPath
from urllib.parse import SplitResult, urlsplit


class LakePathError(ValueError):
    pass


class LakePathResolver:

    def __init__(self, lake_root: Path):
        self.lake_root = lake_root.resolve()
        self.bucket_scheme_folders = {"s3": "s3", "s3a": "s3", "s3n": "s3", "gs": "gs"}
        self.azure_schemes = ("abfss", "abfs", "wasbs")
        self.azure_folder = "abfss"
        self.dbfs_folder = "dbfs"
        self.volumes_folder = "volumes"
        self.managed_folder = "__managed"
        self.volumes_prefix = "/Volumes/"
        self.dbfs_fuse_prefix = "/dbfs/"

    def resolve(self, location: str | Path) -> Path:
        if isinstance(location, Path):
            return self._ensure_inside_lake(location)
        if location.startswith(self.volumes_prefix):
            return self._inside_lake(self.volumes_folder, location.removeprefix(self.volumes_prefix))
        if location.startswith(self.dbfs_fuse_prefix):
            return self._inside_lake(self.dbfs_folder, location.removeprefix(self.dbfs_fuse_prefix))
        uri_parts = urlsplit(location)
        scheme = uri_parts.scheme.lower()
        if scheme == "dbfs" and uri_parts.path.startswith(self.volumes_prefix):
            return self._inside_lake(self.volumes_folder, uri_parts.path.removeprefix(self.volumes_prefix))
        if scheme == "dbfs":
            return self._inside_lake(self.dbfs_folder, uri_parts.netloc, uri_parts.path)
        if scheme in self.bucket_scheme_folders:
            return self._resolve_bucket_uri(self.bucket_scheme_folders[scheme], uri_parts, location)
        if scheme in self.azure_schemes:
            return self._resolve_azure_uri(uri_parts, location)
        raise LakePathError(f"Unsupported storage location: {location}")

    def managed_table_location(self, catalog: str, schema: str, table_id: str) -> Path:
        return self._inside_lake(self.managed_folder, catalog, schema, table_id)

    def volume_location(self, catalog: str, schema: str, volume: str) -> Path:
        return self._inside_lake(self.volumes_folder, catalog, schema, volume)

    def _resolve_bucket_uri(self, scheme_folder: str, uri_parts: SplitResult, location: str) -> Path:
        if not uri_parts.netloc:
            raise LakePathError(f"Missing bucket name: {location}")
        return self._inside_lake(scheme_folder, uri_parts.netloc, uri_parts.path)

    def _resolve_azure_uri(self, uri_parts: SplitResult, location: str) -> Path:
        container = uri_parts.username
        host = uri_parts.hostname
        if not container or not host:
            raise LakePathError(f"Expected <container>@<account>.dfs.core.windows.net: {location}")
        storage_account = host.split(".")[0]
        return self._inside_lake(self.azure_folder, storage_account, container, uri_parts.path)

    def _inside_lake(self, *segments: str) -> Path:
        relative_parts = [part for segment in segments for part in PurePosixPath(segment).parts if part != "/"]
        if not relative_parts:
            raise LakePathError("Empty storage location")
        if ".." in relative_parts:
            raise LakePathError(f"Parent directory references are not allowed: {'/'.join(relative_parts)}")
        return self._ensure_inside_lake(self.lake_root.joinpath(*relative_parts))

    def _ensure_inside_lake(self, path: Path) -> Path:
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(self.lake_root):
            raise LakePathError(f"Location escapes the lake root: {path}")
        return resolved_path
