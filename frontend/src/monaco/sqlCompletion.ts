import type * as Monaco from "monaco-editor";

import type { CatalogTree, SessionInfo, TreeCatalog, TreeTable } from "../api/types";

const sqlKeywords = [
  "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "JOIN", "LEFT JOIN", "INNER JOIN", "ON", "AS",
  "WITH", "UNION ALL", "DISTINCT", "CASE", "WHEN", "THEN", "ELSE", "END", "AND", "OR", "NOT", "IN", "IS NULL", "LIKE",
  "INSERT INTO", "INSERT OVERWRITE", "VALUES", "UPDATE", "SET", "DELETE FROM", "MERGE INTO", "USING", "WHEN MATCHED",
  "WHEN NOT MATCHED", "CREATE TABLE", "CREATE OR REPLACE TABLE", "CREATE VIEW", "CREATE TEMP VIEW", "CREATE SCHEMA",
  "CREATE CATALOG", "DROP TABLE", "DROP VIEW", "DROP SCHEMA", "DROP CATALOG", "USE CATALOG", "USE SCHEMA",
  "SHOW CATALOGS", "SHOW SCHEMAS", "SHOW TABLES", "DESCRIBE", "DESCRIBE HISTORY", "DESCRIBE DETAIL", "COMMENT ON",
  "RESTORE TABLE", "OPTIMIZE", "VACUUM", "VERSION AS OF", "TIMESTAMP AS OF", "PARTITIONED BY", "LOCATION",
  "COUNT", "SUM", "AVG", "MIN", "MAX", "CAST", "COALESCE",
];

interface CompletionSources {
  tree: () => CatalogTree | undefined;
  session: () => SessionInfo | undefined;
}

export function registerSqlCompletion(monaco: typeof Monaco, sources: CompletionSources): Monaco.IDisposable {
  const kinds = monaco.languages.CompletionItemKind;

  return monaco.languages.registerCompletionItemProvider("sql", {
    triggerCharacters: ["."],
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };
      const textBeforeWord = model.getValueInRange({
        startLineNumber: position.lineNumber,
        startColumn: 1,
        endLineNumber: position.lineNumber,
        endColumn: word.startColumn,
      });
      const tree = sources.tree();
      const session = sources.session();
      if (!tree || !session) {
        return { suggestions: [] };
      }
      const suggestion = (label: string, kind: Monaco.languages.CompletionItemKind, detail: string) => ({
        label,
        kind,
        detail,
        insertText: label,
        range,
      });

      const qualifier = /([`\w]+(?:\.[`\w]+)*)\.$/.exec(textBeforeWord)?.[1];
      if (qualifier) {
        const parts = qualifier.split(".").map((part) => part.replace(/`/g, "").toLowerCase());
        const aliases = aliasTargets(model.getValue());
        const resolvedParts = parts.length === 1 && aliases.has(parts[0]) ? (aliases.get(parts[0]) as string[]) : parts;
        const schemas = schemasFor(tree, resolvedParts);
        const tables = tablesFor(tree, session, resolvedParts);
        const columns = columnsFor(tree, session, resolvedParts);
        return {
          suggestions: [
            ...schemas.map((schemaName) => suggestion(schemaName, kinds.Module, "schema")),
            ...tables.map((table) => suggestion(table.name, kinds.Struct, table.table_type.toLowerCase())),
            ...columns.map((column) => suggestion(column.name, kinds.Field, column.type_text)),
          ],
        };
      }

      const currentCatalog = tree.catalogs.find((catalog) => catalog.name === session.current_catalog);
      const currentSchema = currentCatalog?.schemas.find((schema) => schema.name === session.current_schema);
      const columnNames = new Map<string, string>();
      currentSchema?.tables.forEach((table) => table.columns.forEach((column) => columnNames.set(column.name, column.type_text)));
      return {
        suggestions: [
          ...sqlKeywords.map((keyword) => suggestion(keyword, kinds.Keyword, "keyword")),
          ...tree.catalogs.map((catalog) => suggestion(catalog.name, kinds.Folder, "catalog")),
          ...(currentCatalog?.schemas ?? []).map((schema) => suggestion(schema.name, kinds.Module, `schema in ${currentCatalog?.name}`)),
          ...(currentSchema?.tables ?? []).map((table) => suggestion(table.name, kinds.Struct, `${table.table_type.toLowerCase()} in ${session.current_schema}`)),
          ...session.temporary_views.map((view) => suggestion(view, kinds.Struct, "temporary view")),
          ...[...columnNames].map(([name, typeText]) => suggestion(name, kinds.Field, typeText)),
        ],
      };
    },
  });
}

function aliasTargets(sqlText: string): Map<string, string[]> {
  const aliases = new Map<string, string[]>();
  const pattern = /\b(?:from|join|into|using)\s+([`\w]+(?:\.[`\w]+){0,2})\s+(?:as\s+)?([a-z_]\w*)/gi;
  const notAliases = new Set(["where", "on", "join", "left", "right", "inner", "outer", "full", "cross", "group", "order", "limit", "using", "when", "set", "version", "timestamp", "values", "select"]);
  for (const match of sqlText.matchAll(pattern)) {
    const alias = match[2].toLowerCase();
    if (!notAliases.has(alias)) {
      aliases.set(alias, match[1].split(".").map((part) => part.replace(/`/g, "").toLowerCase()));
    }
  }
  return aliases;
}

function schemasFor(tree: CatalogTree, parts: string[]): string[] {
  if (parts.length !== 1) {
    return [];
  }
  return tree.catalogs.find((catalog) => catalog.name === parts[0])?.schemas.map((schema) => schema.name) ?? [];
}

function tablesFor(tree: CatalogTree, session: SessionInfo, parts: string[]): TreeTable[] {
  const [catalogName, schemaName] = parts.length === 2 ? parts : parts.length === 1 ? [session.current_catalog, parts[0]] : [undefined, undefined];
  if (!catalogName || !schemaName) {
    return [];
  }
  return tree.catalogs.find((catalog) => catalog.name === catalogName)?.schemas.find((schema) => schema.name === schemaName)?.tables ?? [];
}

function columnsFor(tree: CatalogTree, session: SessionInfo, parts: string[]) {
  const [catalogName, schemaName, tableName] =
    parts.length === 3
      ? parts
      : parts.length === 2
        ? [session.current_catalog, parts[0], parts[1]]
        : [session.current_catalog, session.current_schema, parts[0]];
  const table = findTable(tree, catalogName, schemaName, tableName);
  return table ? table.columns : [];
}

function findTable(tree: CatalogTree, catalogName: string, schemaName: string, tableName: string): TreeTable | undefined {
  const catalog: TreeCatalog | undefined = tree.catalogs.find((treeCatalog) => treeCatalog.name === catalogName);
  return catalog?.schemas.find((schema) => schema.name === schemaName)?.tables.find((table) => table.name === tableName);
}
