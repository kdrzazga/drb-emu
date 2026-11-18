export interface CatalogInfo {
  name: string;
  comment: string | null;
  owner: string;
  created_at: number;
  updated_at: number;
}

export interface SchemaInfo {
  name: string;
  catalog_name: string;
  full_name: string;
  comment: string | null;
  owner: string;
  created_at: number;
  updated_at: number;
  schema_id: string;
}

export interface ColumnInfo {
  name: string;
  position: number;
  type_name: string;
  type_text: string;
  nullable: boolean;
  comment: string | null;
}

export type TableType = "MANAGED" | "EXTERNAL" | "VIEW";

export interface TableInfo {
  name: string;
  catalog_name: string;
  schema_name: string;
  full_name: string;
  table_type: TableType;
  data_source_format: string | null;
  storage_location: string | null;
  view_definition: string | null;
  columns: ColumnInfo[];
  comment: string | null;
  owner: string;
  created_at: number;
  updated_at: number;
  table_id: string;
}

export interface ResultColumn {
  name: string;
  position: number;
  type_name: string;
  type_text: string;
}

export interface StatementError {
  error_code: string;
  message: string;
}

export interface StatementResponse {
  statement_id: string;
  status: { state: "SUCCEEDED" | "FAILED"; error?: StatementError };
  manifest?: {
    schema: { column_count: number; columns: ResultColumn[] };
    total_row_count: number;
    truncated: boolean;
  };
  result?: { row_count: number; data_array: unknown[][] };
}

export interface QueryInfo {
  query_id: string;
  query_text: string;
  statement_type: string;
  status: "FINISHED" | "FAILED";
  error_message: string | null;
  user_name: string;
  query_start_time_ms: number;
  query_end_time_ms: number;
  duration: number;
  rows_produced: number | null;
}

export interface SessionInfo {
  current_catalog: string;
  current_schema: string;
  temporary_views: string[];
  spark_conf: Record<string, string>;
}

export interface TreeColumn {
  name: string;
  type_text: string;
}

export interface TreeTable {
  name: string;
  table_type: TableType;
  columns: TreeColumn[];
}

export interface TreeSchema {
  name: string;
  tables: TreeTable[];
}

export interface TreeCatalog {
  name: string;
  schemas: TreeSchema[];
}

export interface CatalogTree {
  catalogs: TreeCatalog[];
}
