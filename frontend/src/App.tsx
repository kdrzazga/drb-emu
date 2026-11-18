import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { api, queryKeys } from "./api/client";
import CatalogExplorer from "./pages/CatalogExplorer";
import QueryHistory from "./pages/QueryHistory";
import SqlEditor from "./pages/SqlEditor";

const navigationItems = [
  { path: "/explore", label: "Catalog", icon: "▤" },
  { path: "/sql", label: "SQL Editor", icon: "⌨" },
  { path: "/history", label: "Query History", icon: "↺" },
];

export default function App() {
  const session = useQuery({ queryKey: queryKeys.session, queryFn: api.getSession });

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">◆</span>
          <span className="brand-name">drb-emu</span>
        </div>
        <nav className="navigation">
          {navigationItems.map((item) => (
            <NavLink key={item.path} to={item.path} className={({ isActive }) => `navigation-item${isActive ? " active" : ""}`}>
              <span className="navigation-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          {session.data ? (
            <span className="session-pill" title="Current catalog and schema">
              {session.data.current_catalog}.{session.data.current_schema}
            </span>
          ) : (
            <span className="session-pill offline">{session.isError ? "backend offline" : "connecting…"}</span>
          )}
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/sql" replace />} />
          <Route path="/explore" element={<CatalogExplorer />} />
          <Route path="/explore/:catalogName" element={<CatalogExplorer />} />
          <Route path="/explore/:catalogName/:schemaName" element={<CatalogExplorer />} />
          <Route path="/explore/:catalogName/:schemaName/:tableName" element={<CatalogExplorer />} />
          <Route path="/sql" element={<SqlEditor />} />
          <Route path="/history" element={<QueryHistory />} />
          <Route path="*" element={<Navigate to="/sql" replace />} />
        </Routes>
      </main>
    </div>
  );
}
