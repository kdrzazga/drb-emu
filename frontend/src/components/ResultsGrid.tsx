import type { ResultColumn, StatementResponse } from "../api/types";
import { formatCell } from "../format";

const displayRowLimit = 2000;

interface ResultsGridProps {
  columns: ResultColumn[];
  rows: unknown[][];
}

export function ResultsGrid({ columns, rows }: ResultsGridProps) {
  const visibleRows = rows.slice(0, displayRowLimit);
  return (
    <div className="grid-wrapper">
      <table className="results-grid">
        <thead>
          <tr>
            <th className="row-number">#</th>
            {columns.map((column) => (
              <th key={column.position} title={column.type_text}>
                <span className="column-name">{column.name}</span>
                <span className="column-type">{column.type_text}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              <td className="row-number">{rowIndex + 1}</td>
              {row.map((value, columnIndex) => (
                <td key={columnIndex} className={cellClassName(value)}>
                  {formatCell(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > displayRowLimit && (
        <div className="grid-footer muted">
          Showing the first {displayRowLimit} of {rows.length} rows
        </div>
      )}
    </div>
  );
}

function cellClassName(value: unknown): string | undefined {
  if (value === null || value === undefined) {
    return "null-cell";
  }
  if (typeof value === "number") {
    return "number-cell";
  }
  return undefined;
}

interface ErrorBoxProps {
  code?: string;
  message: string;
}

export function ErrorBox({ code, message }: ErrorBoxProps) {
  return (
    <div className="error-box">
      {code && <div className="error-code">{code}</div>}
      <pre className="error-message">{message}</pre>
    </div>
  );
}

interface StatementResultProps {
  response: StatementResponse;
  emptyMessage?: string;
}

export function StatementResult({ response, emptyMessage }: StatementResultProps) {
  if (response.status.state === "FAILED") {
    return <ErrorBox code={response.status.error?.error_code} message={response.status.error?.message ?? "Statement failed"} />;
  }
  const columns = response.manifest?.schema.columns ?? [];
  if (columns.length === 0) {
    return <div className="muted padded">{emptyMessage ?? "Statement executed successfully."}</div>;
  }
  return <ResultsGrid columns={columns} rows={response.result?.data_array ?? []} />;
}
