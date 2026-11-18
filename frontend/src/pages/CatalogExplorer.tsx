import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api, queryKeys } from "../api/client";
import CatalogTree from "../components/CatalogTree";
import { Breadcrumbs, Fact } from "../components/DetailParts";
import { ErrorBox } from "../components/ResultsGrid";
import TableDetail from "../components/TableDetail";
import { formatTimestamp } from "../format";

export default function CatalogExplorer() {
  const { catalogName, schemaName, tableName } = useParams();

  return (
    <div className="explorer">
      <div className="explorer-tree">
        <div className="panel-title">Catalog Explorer</div>
        <CatalogTree />
      </div>
      <div className="explorer-detail">
        {catalogName && schemaName && tableName ? (
          <TableDetail key={`${catalogName}.${schemaName}.${tableName}`} catalogName={catalogName} schemaName={schemaName} tableName={tableName} />
        ) : catalogName && schemaName ? (
          <SchemaOverview catalogName={catalogName} schemaName={schemaName} />
        ) : catalogName ? (
          <CatalogOverview catalogName={catalogName} />
        ) : (
          <ExplorerHome />
        )}
      </div>
    </div>
  );
}

function ExplorerHome() {
  const tree = useQuery({ queryKey: queryKeys.catalogTree, queryFn: api.getCatalogTree });
  return (
    <div className="detail-page">
      <h1>Catalogs</h1>
      <p className="muted">Create objects in the SQL editor, e.g. <code>CREATE CATALOG sales</code> or <code>CREATE TABLE main.default.t AS SELECT 1 AS id</code>.</p>
      <table className="plain-table">
        <thead>
          <tr>
            <th>Catalog</th>
            <th>Schemas</th>
            <th>Tables</th>
          </tr>
        </thead>
        <tbody>
          {tree.data?.catalogs.map((catalog) => (
            <tr key={catalog.name}>
              <td>
                <Link to={`/explore/${encodeURIComponent(catalog.name)}`}>{catalog.name}</Link>
              </td>
              <td>{catalog.schemas.length}</td>
              <td>{catalog.schemas.reduce((count, schema) => count + schema.tables.length, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CatalogOverview({ catalogName }: { catalogName: string }) {
  const catalog = useQuery({ queryKey: queryKeys.catalog(catalogName), queryFn: () => api.getCatalog(catalogName) });
  const tree = useQuery({ queryKey: queryKeys.catalogTree, queryFn: api.getCatalogTree });
  const schemas = tree.data?.catalogs.find((treeCatalog) => treeCatalog.name === catalogName)?.schemas ?? [];

  if (catalog.isError) {
    return <ErrorBox message={catalog.error.message} />;
  }
  return (
    <div className="detail-page">
      <Breadcrumbs catalogName={catalogName} />
      <h1>
        <span className="title-icon">◫</span>
        {catalogName}
      </h1>
      {catalog.data && (
        <div className="facts">
          <Fact label="Owner" value={catalog.data.owner} />
          <Fact label="Created" value={formatTimestamp(catalog.data.created_at)} />
          <Fact label="Comment" value={catalog.data.comment ?? "—"} />
        </div>
      )}
      <h2>Schemas</h2>
      <table className="plain-table">
        <thead>
          <tr>
            <th>Schema</th>
            <th>Tables</th>
          </tr>
        </thead>
        <tbody>
          {schemas.map((schema) => (
            <tr key={schema.name}>
              <td>
                <Link to={`/explore/${encodeURIComponent(catalogName)}/${encodeURIComponent(schema.name)}`}>{schema.name}</Link>
              </td>
              <td>{schema.tables.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SchemaOverview({ catalogName, schemaName }: { catalogName: string; schemaName: string }) {
  const fullName = `${catalogName}.${schemaName}`;
  const schema = useQuery({ queryKey: queryKeys.schema(fullName), queryFn: () => api.getSchema(fullName) });
  const tree = useQuery({ queryKey: queryKeys.catalogTree, queryFn: api.getCatalogTree });
  const tables =
    tree.data?.catalogs.find((catalog) => catalog.name === catalogName)?.schemas.find((treeSchema) => treeSchema.name === schemaName)?.tables ?? [];

  if (schema.isError) {
    return <ErrorBox message={schema.error.message} />;
  }
  return (
    <div className="detail-page">
      <Breadcrumbs catalogName={catalogName} schemaName={schemaName} />
      <h1>
        <span className="title-icon">▣</span>
        {schemaName}
      </h1>
      {schema.data && (
        <div className="facts">
          <Fact label="Owner" value={schema.data.owner} />
          <Fact label="Created" value={formatTimestamp(schema.data.created_at)} />
          <Fact label="Comment" value={schema.data.comment ?? "—"} />
        </div>
      )}
      <h2>Tables</h2>
      {tables.length === 0 ? (
        <p className="muted">No tables yet.</p>
      ) : (
        <table className="plain-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Columns</th>
            </tr>
          </thead>
          <tbody>
            {tables.map((table) => (
              <tr key={table.name}>
                <td>
                  <Link to={`/explore/${encodeURIComponent(catalogName)}/${encodeURIComponent(schemaName)}/${encodeURIComponent(table.name)}`}>
                    {table.name}
                  </Link>
                </td>
                <td>
                  <span className={`badge badge-${table.table_type.toLowerCase()}`}>{table.table_type}</span>
                </td>
                <td>{table.columns.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
