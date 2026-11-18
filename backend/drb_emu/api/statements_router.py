from typing import Any
from uuid import uuid4

import duckdb
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from drb_emu.api.dependencies import get_result_formatter, get_workspace
from drb_emu.api.statement_result_formatter import StatementResultFormatter
from drb_emu.errors import DrbError
from drb_emu.workspace import Workspace

router = APIRouter(prefix="/api/2.0/sql/statements", tags=["sql"])


class StatementRequest(BaseModel):
    statement: str
    parameters: list[Any] | dict[str, Any] | None = None
    row_limit: int | None = None


@router.post("")
def execute_statement(request: StatementRequest,
                      workspace: Workspace = Depends(get_workspace),
                      result_formatter: StatementResultFormatter = Depends(get_result_formatter)) -> dict:
    statement_id = str(uuid4())
    try:
        with workspace.session_lock:
            result = workspace.statement_executor.execute(request.statement, request.parameters)
    except DrbError as error:
        return failed_statement(statement_id, error.error_code, error.message)
    except duckdb.Error as error:
        return failed_statement(statement_id, type(error).__name__, str(error))
    return {"statement_id": statement_id, "status": {"state": "SUCCEEDED"}, **result_formatter.format(result, request.row_limit)}


def failed_statement(statement_id: str, error_code: str, message: str) -> dict:
    return {"statement_id": statement_id, "status": {"state": "FAILED", "error": {"error_code": error_code, "message": message}}}
