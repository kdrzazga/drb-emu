import threading
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from drb_emu.catalog import MetastoreBase, UnityCatalogService
from drb_emu.history import QueryHistoryService
from drb_emu.lake import DeltaTableStore, LakePathResolver
from drb_emu.sql import DuckDBSession
from drb_emu.sql.catalog_command_handler import CatalogCommandHandler
from drb_emu.sql.delta_command_handler import DeltaCommandHandler
from drb_emu.sql.statement_executor import StatementExecutor
from drb_emu.sql.statement_parser import StatementParser
from drb_emu.sql.table_resolver import TableResolver
from drb_emu.sql.table_write_handler import TableWriteHandler


class Workspace:

    def __init__(self, lake_root: Path, metastore_path: Path):
        lake_root.mkdir(parents=True, exist_ok=True)
        metastore_path.parent.mkdir(parents=True, exist_ok=True)
        self.path_resolver = LakePathResolver(lake_root)
        self.delta_store = DeltaTableStore(self.path_resolver)
        self.metastore_engine = create_engine(f"sqlite:///{metastore_path.resolve().as_posix()}", connect_args={"check_same_thread": False})
        MetastoreBase.metadata.create_all(self.metastore_engine)
        metastore_sessions = sessionmaker(self.metastore_engine)
        self.catalog_service = UnityCatalogService(metastore_sessions, self.path_resolver, self.delta_store)
        self.catalog_service.ensure_default_objects()
        self.query_history = QueryHistoryService(metastore_sessions)
        self.session = DuckDBSession(self.delta_store)
        self.table_resolver = TableResolver(self.catalog_service, self.session)
        self.statement_executor = StatementExecutor(
            self.session,
            StatementParser(),
            self.table_resolver,
            CatalogCommandHandler(self.catalog_service, self.session, self.table_resolver),
            TableWriteHandler(self.catalog_service, self.delta_store, self.session, self.table_resolver),
            DeltaCommandHandler(self.catalog_service, self.delta_store, self.table_resolver),
            self.query_history,
        )
        self.session_lock = threading.Lock()

    def close(self):
        self.session.close()
        self.metastore_engine.dispose()
