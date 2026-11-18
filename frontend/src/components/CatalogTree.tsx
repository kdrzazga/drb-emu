import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, queryKeys } from "../api/client";
import type { TreeTable } from "../api/types";

interface CatalogTreeProps {
  onTableClick?: (catalogName: string, schemaName: string, table: TreeTable) => void;
}

export default function CatalogTree({ onTableClick }: CatalogTreeProps) {
  const tree = useQuery({ queryKey: queryKeys.catalogTree, queryFn: api.getCatalogTree });
  const { catalogName, schemaName, tableName } = useParams();
  const [filterText, setFilterText] = useState("");
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(() => {
    const initiallyExpanded = new Set(["main", "main.default"]);
    if (catalogName) {
      initiallyExpanded.add(catalogName);
    }
    if (catalogName && schemaName) {
      initiallyExpanded.add(`${catalogName}.${schemaName}`);
    }
    return initiallyExpanded;
  });

  const toggle = (key: string) =>
    setExpandedKeys((previous) => {
      const next = new Set(previous);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });

  const needle = filterText.trim().toLowerCase();
  const isNavigating = onTableClick === undefined;

  return (
    <div className="catalog-tree">
      <input
        className="tree-filter"
        placeholder="Filter tables…"
        value={filterText}
        onChange={(event) => setFilterText(event.target.value)}
      />
      {tree.isLoading && <div className="muted padded">Loading…</div>}
      {tree.isError && <div className="error-text padded">{tree.error.message}</div>}
      <ul className="tree">
        {tree.data?.catalogs.map((catalog) => {
          const visibleSchemas = catalog.schemas
            .map((schema) => ({
              schema,
              tables: needle ? schema.tables.filter((table) => table.name.includes(needle)) : schema.tables,
            }))
            .filter(({ schema, tables }) => !needle || tables.length > 0 || schema.name.includes(needle));
          if (needle && visibleSchemas.length === 0 && !catalog.name.includes(needle)) {
            return null;
          }
          const catalogOpen = needle !== "" || expandedKeys.has(catalog.name);
          return (
            <li key={catalog.name}>
              <TreeRow
                depth={0}
                icon="◫"
                label={catalog.name}
                open={catalogOpen}
                onToggle={() => toggle(catalog.name)}
                linkTo={isNavigating ? `/explore/${encodeURIComponent(catalog.name)}` : undefined}
                active={isNavigating && catalogName === catalog.name && !schemaName}
              />
              {catalogOpen && (
                <ul>
                  {visibleSchemas.map(({ schema, tables }) => {
                    const schemaKey = `${catalog.name}.${schema.name}`;
                    const schemaOpen = needle !== "" || expandedKeys.has(schemaKey);
                    return (
                      <li key={schemaKey}>
                        <TreeRow
                          depth={1}
                          icon="▣"
                          label={schema.name}
                          open={schemaOpen}
                          onToggle={() => toggle(schemaKey)}
                          linkTo={isNavigating ? `/explore/${encodeURIComponent(catalog.name)}/${encodeURIComponent(schema.name)}` : undefined}
                          active={isNavigating && catalogName === catalog.name && schemaName === schema.name && !tableName}
                        />
                        {schemaOpen && (
                          <ul>
                            {tables.length === 0 && <li className="tree-empty muted">no tables</li>}
                            {tables.map((table) => (
                              <li key={table.name}>
                                <TreeRow
                                  depth={2}
                                  icon={table.table_type === "VIEW" ? "◇" : "▦"}
                                  label={table.name}
                                  title={`${table.table_type} · ${table.columns.length} columns`}
                                  linkTo={
                                    isNavigating
                                      ? `/explore/${encodeURIComponent(catalog.name)}/${encodeURIComponent(schema.name)}/${encodeURIComponent(table.name)}`
                                      : undefined
                                  }
                                  onSelect={onTableClick ? () => onTableClick(catalog.name, schema.name, table) : undefined}
                                  active={isNavigating && catalogName === catalog.name && schemaName === schema.name && tableName === table.name}
                                />
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface TreeRowProps {
  depth: number;
  icon: string;
  label: string;
  title?: string;
  open?: boolean;
  onToggle?: () => void;
  linkTo?: string;
  onSelect?: () => void;
  active: boolean;
}

function TreeRow({ depth, icon, label, title, open, onToggle, linkTo, onSelect, active }: TreeRowProps) {
  const hasChildren = onToggle !== undefined;
  return (
    <div className={`tree-row${active ? " active" : ""}`} style={{ paddingLeft: 6 + depth * 14 }} title={title}>
      {hasChildren ? (
        <button className="tree-chevron" onClick={onToggle} aria-label={open ? "Collapse" : "Expand"}>
          {open ? "▾" : "▸"}
        </button>
      ) : (
        <span className="tree-chevron" />
      )}
      <span className="tree-icon">{icon}</span>
      {linkTo ? (
        <Link className="tree-label" to={linkTo}>
          {label}
        </Link>
      ) : (
        <button className="tree-label" onClick={onSelect ?? onToggle}>
          {label}
        </button>
      )}
    </div>
  );
}
