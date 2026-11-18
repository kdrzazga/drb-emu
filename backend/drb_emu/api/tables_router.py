import duckdb
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from drb_emu.api.dependencies import get_workspace
from drb_emu.workspace import Workspace

router = APIRouter(prefix="/api/drb/tables", tags=["tables"])


class RegisterTableRequest(BaseModel):
    view_name: str
    location: str
    version: int | None = None


class WriteTableRequest(BaseModel):
    statement: str
    location: str | None = None
    table_name: str | None = None
    mode: str = "overwrite"
    partition_by: list[str] = []


@router.get("")
def list_registered_tables(workspace: Workspace = Depends(get_workspace)) -> dict:
    return {"tables": sorted(workspace.session.registered_views)}


@router.post("/register")
def register_table(request: RegisterTableRequest, workspace: Workspace = Depends(get_workspace)) -> dict:
    if not workspace.delta_store.exists(request.location):
        raise HTTPException(status_code=404, detail=f"No Delta table at {request.location}")
    with workspace.session_lock:
        workspace.session.register_delta_table(request.view_name, request.location, request.version)
    registered_version = request.version if request.version is not None else workspace.delta_store.current_version(request.location)
    return {"view_name": request.view_name, "location": request.location, "version": registered_version}


@router.delete("/{view_name}")
def unregister_table(view_name: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    if view_name not in workspace.session.registered_views:
        raise HTTPException(status_code=404, detail=f"View {view_name} is not registered")
    with workspace.session_lock:
        workspace.session.unregister(view_name)
    return {"view_name": view_name}


@router.post("/write")
def write_table(request: WriteTableRequest, workspace: Workspace = Depends(get_workspace)) -> dict:
    if (request.location is None) == (request.table_name is None):
        raise HTTPException(status_code=400, detail="Give exactly one of location or table_name")
    try:
        with workspace.session_lock:
            data = workspace.statement_executor.execute(request.statement)
            if request.table_name is not None:
                table_info = workspace.catalog_service.write_table(request.table_name, data, request.mode, tuple(request.partition_by))
                location = table_info.storage_location
            else:
                workspace.delta_store.write(request.location, data, request.mode, tuple(request.partition_by))
                location = request.location
            version = workspace.delta_store.current_version(location)
    except duckdb.Error as error:
        raise HTTPException(status_code=400, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"table_name": request.table_name, "location": location, "version": version, "row_count": data.num_rows}
