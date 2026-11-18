from typing import Any
from uuid import uuid4

import duckdb
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from drb_emu.api.dependencies import get_result_formatter, get_workspace
from drb_emu.api.statement_result_formatter import StatementResultFormatter
from drb_emu.workspace import Workspace

router = APIRouter(prefix="/api/2.0/sql/statements", tags=["sql"])


class StatementRequest(BaseModel):
    statement: str
    parameters: list[Any] | None = None
    row_limit: int | None = None


@router.post("")
def execute_statement(request: StatementRequest,
                      workspace: Workspace = Depends(get_workspace),
                      result_formatter: StatementResultFormatter = Depends(get_result_formatter)) -> dict:
    statement_id = str(uuid4())
    try:
        with workspace.session_lock:
            result = workspace.session.execute(request.statement, request.parameters)
    except duckdb.Error as error:
        return {
            "statement_id": statement_id,
            "status": {"state": "FAILED", "error": {"error_code": type(error).__name__, "message": str(error)}},
        }
    return {"statement_id": statement_id, "status": {"state": "SUCCEEDED"}, **result_formatter.format(result, request.row_limit)}
