import argparse
import os
from pathlib import Path

from drb_emu.errors import ResourceAlreadyExists
from drb_emu.seed.computer_store_dataset import ComputerStoreDataset
from drb_emu.seed.dataset_loader import DatasetLoader
from drb_emu.seed.people_dataset import PeopleDataset
from drb_emu.seed.trades_dataset import TradesDataset
from drb_emu.workspace import Workspace

DATASETS = {
    "people": PeopleDataset,
    "trades": TradesDataset,
    "computer_store": ComputerStoreDataset,
}


def main():
    parser = argparse.ArgumentParser(prog="python -m drb_emu.seed", description="Create demo catalogs with generated data")
    parser.add_argument("datasets", nargs="*", metavar="DATASET", help=f"datasets to create (default: all of {', '.join(DATASETS)})")
    parser.add_argument("--replace", action="store_true", help="drop and recreate catalogs that already exist")
    parser.add_argument("--lake", type=Path, default=Path(os.environ.get("DRB_EMU_LAKE", "lake")))
    parser.add_argument("--metastore", type=Path, default=Path(os.environ.get("DRB_EMU_METASTORE", "metastore/metastore.db")))
    arguments = parser.parse_args()

    unknown_datasets = [name for name in arguments.datasets if name not in DATASETS]
    if unknown_datasets:
        parser.error(f"unknown dataset(s): {', '.join(unknown_datasets)}; choose from {', '.join(DATASETS)}")

    workspace = Workspace(arguments.lake, arguments.metastore)
    loader = DatasetLoader(workspace.catalog_service)
    try:
        for dataset_name in arguments.datasets or list(DATASETS):
            print(f"Seeding {dataset_name}...")
            try:
                loaded_objects = loader.load(DATASETS[dataset_name]().build(), arguments.replace)
            except ResourceAlreadyExists as error:
                print(f"  skipped: {error.message}")
                continue
            for loaded in loaded_objects:
                size = f"{loaded.row_count:>6} rows" if loaded.kind == "table" else "  view"
                print(f"  {size}  {loaded.full_name}")
    finally:
        workspace.close()


if __name__ == "__main__":
    main()
