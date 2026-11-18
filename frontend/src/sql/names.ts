export function quoteIdentifier(name: string): string {
  return `\`${name.replace(/`/g, "``")}\``;
}

export function quotedTableName(catalog: string, schema: string, table: string): string {
  return [catalog, schema, table].map(quoteIdentifier).join(".");
}

export function selectAllStatement(catalog: string, schema: string, table: string): string {
  return `SELECT * FROM ${quotedTableName(catalog, schema, table)} LIMIT 100`;
}

export function splitFullName(fullName: string): [string, string, string] {
  const [catalog = "", schema = "", table = ""] = fullName.split(".");
  return [catalog, schema, table];
}
