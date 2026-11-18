from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from drb_emu.api.dependencies import get_workspace
from drb_emu.catalog.object_names import TableName
from drb_emu.errors import InvalidParameterValue
from drb_emu.workspace import Workspace

router = APIRouter(prefix="/api/2.1/unity-catalog", tags=["unity-catalog"])


class CreateCatalogRequest(BaseModel):
    name: str
    comment: str | None = None


class CreateSchemaRequest(BaseModel):
    name: str
    catalog_name: str
    comment: str | None = None


class CreateTableRequest(BaseModel):
    name: str
    catalog_name: str
    schema_name: str
    table_type: str
    storage_location: str | None = None
    view_definition: str | None = None
    comment: str | None = None


@router.post("/catalogs")
def create_catalog(request: CreateCatalogRequest, workspace: Workspace = Depends(get_workspace)) -> dict:
    return asdict(workspace.catalog_service.create_catalog(request.name, request.comment))


@router.get("/catalogs")
def list_catalogs(workspace: Workspace = Depends(get_workspace)) -> dict:
    return {"catalogs": [asdict(catalog) for catalog in workspace.catalog_service.list_catalogs()]}


@router.get("/catalogs/{name}")
def get_catalog(name: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    return asdict(workspace.catalog_service.get_catalog(name))


@router.delete("/catalogs/{name}")
def delete_catalog(name: str, force: bool = False, workspace: Workspace = Depends(get_workspace)) -> dict:
    workspace.catalog_service.delete_catalog(name, force)
    return {}


@router.post("/schemas")
def create_schema(request: CreateSchemaRequest, workspace: Workspace = Depends(get_workspace)) -> dict:
    return asdict(workspace.catalog_service.create_schema(request.catalog_name, request.name, request.comment))


@router.get("/schemas")
def list_schemas(catalog_name: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    return {"schemas": [asdict(schema) for schema in workspace.catalog_service.list_schemas(catalog_name)]}


@router.get("/schemas/{full_name}")
def get_schema(full_name: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    return asdict(workspace.catalog_service.get_schema(full_name))


@router.delete("/schemas/{full_name}")
def delete_schema(full_name: str, force: bool = False, workspace: Workspace = Depends(get_workspace)) -> dict:
    workspace.catalog_service.delete_schema(full_name, force)
    return {}


@router.post("/tables")
def create_table(request: CreateTableRequest, workspace: Workspace = Depends(get_workspace)) -> dict:
    full_name = TableName.parse(f"{request.catalog_name}.{request.schema_name}.{request.name}").full_name
    table_type = request.table_type.upper()
    if table_type == "EXTERNAL" and request.storage_location:
        return asdict(workspace.catalog_service.create_external_table(full_name, request.storage_location, request.comment))
    if table_type == "VIEW" and request.view_definition:
        return asdict(workspace.catalog_service.create_view(full_name, request.view_definition, request.comment))
    raise InvalidParameterValue(
        "INVALID_PARAMETER_VALUE",
        "Supported: EXTERNAL with storage_location, VIEW with view_definition. Create managed tables with POST /api/drb/tables/write.",
    )


@router.get("/tables")
def list_tables(catalog_name: str, schema_name: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    return {"tables": [asdict(table) for table in workspace.catalog_service.list_tables(catalog_name, schema_name)]}


@router.get("/tables/{full_name}")
def get_table(full_name: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    return asdict(workspace.catalog_service.get_table(full_name))


@router.delete("/tables/{full_name}")
def delete_table(full_name: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    workspace.catalog_service.delete_table(full_name)
    return {}
