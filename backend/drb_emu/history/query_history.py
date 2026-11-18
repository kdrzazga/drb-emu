from dataclasses import dataclass

from sqlalchemy import String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from drb_emu.catalog.metastore_records import MetastoreBase


class QueryHistoryRecord(MetastoreBase):
    __tablename__ = "query_history"

    sequence: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query_id: Mapped[str] = mapped_column(String(36), unique=True)
    query_text: Mapped[str] = mapped_column(Text)
    statement_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    error_message: Mapped[str | None] = mapped_column(Text)
    user_name: Mapped[str] = mapped_column(String(255))
    started_at: Mapped[int]
    ended_at: Mapped[int]
    rows_produced: Mapped[int | None]


@dataclass(frozen=True)
class QueryInfo:
    query_id: str
    query_text: str
    statement_type: str
    status: str
    error_message: str | None
    user_name: str
    query_start_time_ms: int
    query_end_time_ms: int
    duration: int
    rows_produced: int | None


class QueryHistoryService:

    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def record(self, query: QueryInfo):
        with self.session_factory.begin() as metastore:
            metastore.add(QueryHistoryRecord(
                query_id=query.query_id,
                query_text=query.query_text,
                statement_type=query.statement_type,
                status=query.status,
                error_message=query.error_message,
                user_name=query.user_name,
                started_at=query.query_start_time_ms,
                ended_at=query.query_end_time_ms,
                rows_produced=query.rows_produced,
            ))

    def list_queries(self, max_results: int) -> list[QueryInfo]:
        with self.session_factory() as metastore:
            records = metastore.scalars(
                select(QueryHistoryRecord).order_by(QueryHistoryRecord.sequence.desc()).limit(max_results)
            )
            return [self._query_info(record) for record in records]

    def _query_info(self, record: QueryHistoryRecord) -> QueryInfo:
        return QueryInfo(
            query_id=record.query_id,
            query_text=record.query_text,
            statement_type=record.statement_type,
            status=record.status,
            error_message=record.error_message,
            user_name=record.user_name,
            query_start_time_ms=record.started_at,
            query_end_time_ms=record.ended_at,
            duration=record.ended_at - record.started_at,
            rows_produced=record.rows_produced,
        )
