import type {
  CatalogInfo,
  CatalogTree,
  QueryInfo,
  SchemaInfo,
  SessionInfo,
  StatementResponse,
  TableInfo,
} from "./types";

export class ApiError extends Error {
  readonly errorCode: string;

  constructor(errorCode: string, message: string) {
    super(message);
    this.errorCode = errorCode;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body.message ?? (typeof body.detail === "string" ? body.detail : response.statusText);
    throw new ApiError(body.error_code ?? String(response.status), message);
  }
  return body as T;
}

const unityCatalog = "/api/2.1/unity-catalog";

export const api = {
  listCatalogs: () => request<{ catalogs: CatalogInfo[] }>(`${unityCatalog}/catalogs`).then((body) => body.catalogs),
  getCatalog: (name: string) => request<CatalogInfo>(`${unityCatalog}/catalogs/${encodeURIComponent(name)}`),
  listSchemas: (catalogName: string) =>
    request<{ schemas: SchemaInfo[] }>(`${unityCatalog}/schemas?catalog_name=${encodeURIComponent(catalogName)}`).then(
      (body) => body.schemas,
    ),
  getSchema: (fullName: string) => request<SchemaInfo>(`${unityCatalog}/schemas/${encodeURIComponent(fullName)}`),
  getTable: (fullName: string) => request<TableInfo>(`${unityCatalog}/tables/${encodeURIComponent(fullName)}`),
  executeStatement: (statement: string, rowLimit?: number) =>
    request<StatementResponse>("/api/2.0/sql/statements", {
      method: "POST",
      body: JSON.stringify({ statement, row_limit: rowLimit }),
    }),
  listQueries: (maxResults: number) =>
    request<{ res: QueryInfo[] }>(`/api/2.0/sql/history/queries?max_results=${maxResults}`).then((body) => body.res),
  getSession: () => request<SessionInfo>("/api/drb/session"),
  getCatalogTree: () => request<CatalogTree>("/api/drb/catalog-tree"),
};

export const queryKeys = {
  catalogTree: ["catalog-tree"],
  session: ["session"],
  history: ["history"],
  catalog: (name: string) => ["catalog", name],
  schema: (fullName: string) => ["schema", fullName],
  table: (fullName: string) => ["table", fullName],
  tablePreview: (fullName: string, kind: string) => ["table-preview", fullName, kind],
};
