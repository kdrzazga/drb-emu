from fastapi import APIRouter, Depends

from drb_emu.api.dependencies import get_workspace
from drb_emu.workspace import Workspace

router = APIRouter(prefix="/api/drb", tags=["workspace"])


@router.get("/session")
def current_session(workspace: Workspace = Depends(get_workspace)) -> dict:
    return {
        "current_catalog": workspace.session.current_catalog,
        "current_schema": workspace.session.current_schema,
        "temporary_views": sorted(workspace.session.registered_views),
        "spark_conf": workspace.session.spark_conf,
    }


@router.get("/catalog-tree")
def catalog_tree(workspace: Workspace = Depends(get_workspace)) -> dict:
    catalog_service = workspace.catalog_service
    return {
        "catalogs": [
            {
                "name": catalog.name,
                "schemas": [
                    {
                        "name": schema.name,
                        "tables": [
                            {
                                "name": table.name,
                                "table_type": table.table_type,
                                "columns": [{"name": column.name, "type_text": column.type_text} for column in table.columns],
                            }
                            for table in catalog_service.list_tables(catalog.name, schema.name)
                        ],
                    }
                    for schema in catalog_service.list_schemas(catalog.name)
                ],
            }
            for catalog in catalog_service.list_catalogs()
        ]
    }
