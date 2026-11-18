from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from drb_emu.api.dependencies import get_workspace
from drb_emu.workspace import Workspace

router = APIRouter(prefix="/api/2.0/sql/history", tags=["query-history"])


@router.get("/queries")
def list_queries(max_results: int = Query(default=100, ge=1, le=1000), workspace: Workspace = Depends(get_workspace)) -> dict:
    queries = workspace.query_history.list_queries(max_results)
    return {"res": [asdict(query) for query in queries], "has_next_page": False}
