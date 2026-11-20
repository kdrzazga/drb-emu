import os
from pathlib import Path

import uvicorn

from drb_emu.api import create_app
from drb_emu.education.lecture import LectureAnimation


def main():
    lake_root = Path(os.environ.get("DRB_EMU_LAKE", "lake"))
    metastore_path = Path(os.environ.get("DRB_EMU_METASTORE", "metastore/metastore.db"))
    port = int(os.environ.get("DRB_EMU_PORT", "8000"))

    print("UI avaialble at http://localhost:5173/")

    LectureAnimation().run()
    uvicorn.run(create_app(lake_root, metastore_path), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
