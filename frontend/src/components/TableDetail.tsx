import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, queryKeys } from "../api/client";
import type { StatementResponse, TableInfo } from "../api/types";
import { formatBytes, formatCell, formatTimestamp } from "../format";
import { quotedTableName, selectAllStatement } from "../sql/names";
import { Breadcrumbs, Fact } from "./DetailParts";
import { ErrorBox, StatementResult } from "./ResultsGrid";

type TabName = "columns" | "sample" | "history" | "details";

interface TableDetailProps {
  catalogName: string;
  schemaName: string;
  tableName: string;
}

export default function TableDetail({ catalogName, schemaName, tableName }: TableDetailProps) {
  const fullName = `${catalogName}.${schemaName}.${tableName}`;
  const quotedName = quotedTableName(catalogName, schemaName, tableName);
  const [activeTab, setActiveTab] = useState<TabName>("columns");
  const navigate = useNavigate();
  const table = useQuery({ queryKey: queryKeys.table(fullName), queryFn: () => api.getTable(fullName) });
  const isView = table.data?.table_type === "VIEW";

  const sample = useQuery({
    queryKey: queryKeys.tablePreview(fullName, "sample"),
    queryFn: () => api.executeStatement(`SELECT * FROM ${quotedName} LIMIT 100`),
    enabled: activeTab === "sample",
  });
  const history = useQuery({
    queryKey: queryKeys.tablePreview(fullName, "history"),
    queryFn: () => api.executeStatement(`DESCRIBE HISTORY ${quotedName}`),
    enabled: activeTab === "history" && table.data !== undefined && !isView,
  });
  const detail = useQuery({
    queryKey: queryKeys.tablePreview(fullName, "detail"),
    queryFn: () => api.executeStatement(`DESCRIBE DETAIL ${quotedName}`),
    enabled: activeTab === "details" && table.data !== undefined && !isView,
  });

  if (table.isError) {
    return (
      <div className="detail-page">
        <Breadcrumbs catalogName={catalogName} schemaName={schemaName} tableName={tableName} />
        <ErrorBox message={table.error.message} />
      </div>
    );
  }
  if (!table.data) {
    return <div className="detail-page muted">Loading…</div>;
  }

  const tabs: { name: TabName; label: string }[] = [
    { name: "columns", label: `Columns (${table.data.columns.length})` },
    { name: "sample", label: "Sample data" },
    ...(isView ? [] : [{ name: "history" as TabName, label: "History" }]),
    { name: "details", label: "Details" },
  ];

  return (
    <div className="detail-page">
      <Breadcrumbs catalogName={catalogName} schemaName={schemaName} tableName={tableName} />
      <div className="detail-header">
        <h1>
          <span className="title-icon">{isView ? "◇" : "▦"}</span>
          {tableName}
          <span className={`badge badge-${table.data.table_type.toLowerCase()}`}>{table.data.table_type}</span>
        </h1>
        <button className="primary" onClick={() => navigate(`/sql?query=${encodeURIComponent(selectAllStatement(catalogName, schemaName, tableName))}`)}>
          Open in SQL editor
        </button>
      </div>
      {table.data.comment && <p className="table-comment">{table.data.comment}</p>}
      <div className="tabs">
        {tabs.map((tab) => (
          <button key={tab.name} className={`tab${activeTab === tab.name ? " active" : ""}`} onClick={() => setActiveTab(tab.name)}>
            {tab.label}
          </button>
        ))}
      </div>
      <div className="tab-body">
        {activeTab === "columns" && <ColumnsTable table={table.data} />}
        {activeTab === "sample" && <PreviewResult response={sample.data} error={sample.error} emptyMessage="The table is empty." />}
        {activeTab === "history" && <PreviewResult response={history.data} error={history.error} />}
        {activeTab === "details" && <TableFacts table={table.data} detail={detail.data} />}
      </div>
    </div>
  );
}

function ColumnsTable({ table }: { table: TableInfo }) {
  if (table.columns.length === 0) {
    return <p className="muted">Column information is resolved at query time for views. Open the Sample data tab to see them.</p>;
  }
  return (
    <table className="plain-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Name</th>
          <th>Type</th>
          <th>Nullable</th>
          <th>Comment</th>
        </tr>
      </thead>
      <tbody>
        {table.columns.map((column) => (
          <tr key={column.name}>
            <td className="muted">{column.position + 1}</td>
            <td className="mono">{column.name}</td>
            <td className="mono type-text">{column.type_text}</td>
            <td>{column.nullable ? "yes" : "no"}</td>
            <td>{column.comment ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface PreviewResultProps {
  response: StatementResponse | undefined;
  error: Error | null;
  emptyMessage?: string;
}

function PreviewResult({ response, error, emptyMessage }: PreviewResultProps) {
  if (error) {
    return <ErrorBox message={error.message} />;
  }
  if (!response) {
    return <div className="muted">Loading…</div>;
  }
  if (response.status.state === "SUCCEEDED" && response.result?.row_count === 0 && emptyMessage) {
    return <p className="muted">{emptyMessage}</p>;
  }
  return <StatementResult response={response} />;
}

function TableFacts({ table, detail }: { table: TableInfo; detail: StatementResponse | undefined }) {
  const deltaDetail = firstRowAsRecord(detail);
  return (
    <div className="facts facts-grid">
      <Fact label="Full name" value={table.full_name} />
      <Fact label="Type" value={table.table_type} />
      <Fact label="Format" value={table.data_source_format ?? "—"} />
      <Fact label="Owner" value={table.owner} />
      <Fact label="Created" value={formatTimestamp(table.created_at)} />
      <Fact label="Last modified" value={formatTimestamp(table.updated_at)} />
      <Fact label="Table ID" value={table.table_id} />
      {table.storage_location && <Fact label="Location" value={table.storage_location} />}
      {deltaDetail && (
        <>
          <Fact label="Delta version" value={formatCell(deltaDetail.version)} />
          <Fact label="Files" value={formatCell(deltaDetail.numFiles)} />
          <Fact label="Size" value={typeof deltaDetail.sizeInBytes === "number" ? formatBytes(deltaDetail.sizeInBytes) : "—"} />
          <Fact label="Partition columns" value={Array.isArray(deltaDetail.partitionColumns) && deltaDetail.partitionColumns.length > 0 ? deltaDetail.partitionColumns.join(", ") : "—"} />
        </>
      )}
      {table.view_definition && (
        <div className="fact fact-wide">
          <div className="fact-label">View definition</div>
          <pre className="code-block">{table.view_definition}</pre>
        </div>
      )}
    </div>
  );
}

function firstRowAsRecord(response: StatementResponse | undefined): Record<string, unknown> | null {
  const columns = response?.manifest?.schema.columns;
  const firstRow = response?.result?.data_array[0];
  if (!columns || !firstRow) {
    return null;
  }
  return Object.fromEntries(columns.map((column, index) => [column.name, firstRow[index]]));
}
