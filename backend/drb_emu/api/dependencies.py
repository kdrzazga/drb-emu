from fastapi import Request

from drb_emu.api.statement_result_formatter import StatementResultFormatter
from drb_emu.workspace import Workspace


def get_workspace(request: Request) -> Workspace:
    return request.app.state.workspace


def get_result_formatter(request: Request) -> StatementResultFormatter:
    return request.app.state.result_formatter
