import threading
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from drb_emu.catalog import MetastoreBase, UnityCatalogService
from drb_emu.lake import DeltaTableStore, LakePathResolver
from drb_emu.sql import DuckDBSession
from drb_emu.sql.statement_executor import StatementExecutor
from drb_emu.sql.table_resolver import TableResolver


class Workspace:

    def __init__(self, lake_root: Path, metastore_path: Path):
        lake_root.mkdir(parents=True, exist_ok=True)
        metastore_path.parent.mkdir(parents=True, exist_ok=True)
        self.path_resolver = LakePathResolver(lake_root)
        self.delta_store = DeltaTableStore(self.path_resolver)
        self.metastore_engine = create_engine(f"sqlite:///{metastore_path.resolve().as_posix()}", connect_args={"check_same_thread": False})
        MetastoreBase.metadata.create_all(self.metastore_engine)
        self.catalog_service = UnityCatalogService(sessionmaker(self.metastore_engine), self.path_resolver, self.delta_store)
        self.catalog_service.ensure_default_objects()
        self.session = DuckDBSession(self.delta_store)
        self.table_resolver = TableResolver(self.catalog_service, self.session)
        self.statement_executor = StatementExecutor(self.session, self.table_resolver)
        self.session_lock = threading.Lock()

    def close(self):
        self.session.close()
        self.metastore_engine.dispose()
