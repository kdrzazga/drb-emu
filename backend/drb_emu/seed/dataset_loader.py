from dataclasses import dataclass

from drb_emu.catalog import UnityCatalogService
from drb_emu.errors import ResourceAlreadyExists
from drb_emu.seed.seed_dataset import SeedDataset


@dataclass(frozen=True)
class LoadedTable:
    full_name: str
    row_count: int
    kind: str


class DatasetLoader:

    def __init__(self, catalog_service: UnityCatalogService):
        self.catalog_service = catalog_service
        self.schema_name = "default"

    def catalog_exists(self, catalog_name: str) -> bool:
        return any(catalog.name == catalog_name for catalog in self.catalog_service.list_catalogs())

    def load(self, dataset: SeedDataset, replace: bool) -> list[LoadedTable]:
        if self.catalog_exists(dataset.catalog_name):
            if not replace:
                raise ResourceAlreadyExists(
                    "CATALOG_ALREADY_EXISTS",
                    f"Catalog '{dataset.catalog_name}' already exists, run with --replace to drop and recreate it",
                )
            self.catalog_service.delete_catalog(dataset.catalog_name, force=True)
        self.catalog_service.create_catalog(dataset.catalog_name, dataset.comment)
        loaded = []
        for table in dataset.tables:
            full_name = f"{dataset.catalog_name}.{self.schema_name}.{table.name}"
            arrow_table = table.to_arrow()
            self.catalog_service.create_managed_table(full_name, arrow_table, (), table.comment)
            loaded.append(LoadedTable(full_name, arrow_table.num_rows, "table"))
        for view in dataset.views:
            full_name = f"{dataset.catalog_name}.{self.schema_name}.{view.name}"
            self.catalog_service.create_view(full_name, " ".join(view.definition.split()), view.comment)
            loaded.append(LoadedTable(full_name, 0, "view"))
        return loaded
