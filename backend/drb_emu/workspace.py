import threading
from pathlib import Path

from drb_emu.lake import DeltaTableStore, LakePathResolver
from drb_emu.sql import DuckDBSession


class Workspace:

    def __init__(self, lake_root: Path):
        lake_root.mkdir(parents=True, exist_ok=True)
        self.path_resolver = LakePathResolver(lake_root)
        self.delta_store = DeltaTableStore(self.path_resolver)
        self.session = DuckDBSession(self.delta_store)
        self.session_lock = threading.Lock()

    def close(self):
        self.session.close()
