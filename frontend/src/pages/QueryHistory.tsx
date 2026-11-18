import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, queryKeys } from "../api/client";
import { ErrorBox } from "../components/ResultsGrid";
import { formatDuration, formatTimestamp } from "../format";

const historySize = 200;
const refreshIntervalMilliseconds = 5000;

type StatusFilter = "ALL" | "FINISHED" | "FAILED";

export default function QueryHistory() {
  const history = useQuery({
    queryKey: queryKeys.history,
    queryFn: () => api.listQueries(historySize),
    refetchInterval: refreshIntervalMilliseconds,
  });
  const [filterText, setFilterText] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const navigate = useNavigate();

  const needle = filterText.trim().toLowerCase();
  const queries = (history.data ?? []).filter(
    (query) => (statusFilter === "ALL" || query.status === statusFilter) && (!needle || query.query_text.toLowerCase().includes(needle)),
  );

  return (
    <div className="detail-page history-page">
      <div className="detail-header">
        <h1>Query History</h1>
        <div className="history-filters">
          <input className="text-input" placeholder="Search query text…" value={filterText} onChange={(event) => setFilterText(event.target.value)} />
          <select className="text-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
            <option value="ALL">All statuses</option>
            <option value="FINISHED">Finished</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
      </div>
      <p className="muted">The last {historySize} statements, newest first. Click a row to open it in the SQL editor.</p>
      {history.isError && <ErrorBox message={history.error.message} />}
      <table className="plain-table history-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Query</th>
            <th>Type</th>
            <th>Started</th>
            <th>Duration</th>
            <th>Rows</th>
          </tr>
        </thead>
        <tbody>
          {queries.map((query) => (
            <tr key={query.query_id} className="clickable" onClick={() => navigate(`/sql?query=${encodeURIComponent(query.query_text)}`)}>
              <td>
                <span className={`badge ${query.status === "FINISHED" ? "badge-ok" : "badge-failed"}`} title={query.error_message ?? undefined}>
                  {query.status}
                </span>
              </td>
              <td className="query-text" title={query.error_message ?? query.query_text}>
                <code>{query.query_text}</code>
                {query.error_message && <div className="error-text">{query.error_message}</div>}
              </td>
              <td>{query.statement_type}</td>
              <td className="nowrap">{formatTimestamp(query.query_start_time_ms)}</td>
              <td className="nowrap">{formatDuration(query.duration)}</td>
              <td>{query.rows_produced ?? "—"}</td>
            </tr>
          ))}
          {history.data && queries.length === 0 && (
            <tr>
              <td colSpan={6} className="muted">
                No queries match.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
