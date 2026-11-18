from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from drb_emu.api import statements_router, tables_router
from drb_emu.api.statement_result_formatter import StatementResultFormatter
from drb_emu.lake import LakePathError
from drb_emu.workspace import Workspace


def create_app(lake_root: Path) -> FastAPI:
    workspace = Workspace(lake_root)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        workspace.close()

    app = FastAPI(title="drb-emu", lifespan=lifespan)
    app.state.workspace = workspace
    app.state.result_formatter = StatementResultFormatter()
    app.include_router(statements_router.router)
    app.include_router(tables_router.router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "lake_root": str(workspace.path_resolver.lake_root)}

    @app.exception_handler(LakePathError)
    def invalid_location(_: Request, error: LakePathError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error_code": "INVALID_PARAMETER_VALUE", "message": str(error)})

    return app
