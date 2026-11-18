import { Link } from "react-router-dom";

interface BreadcrumbsProps {
  catalogName: string;
  schemaName?: string;
  tableName?: string;
}

export function Breadcrumbs({ catalogName, schemaName, tableName }: BreadcrumbsProps) {
  return (
    <div className="breadcrumbs">
      <Link to="/explore">Catalogs</Link>
      <span>/</span>
      <Link to={`/explore/${encodeURIComponent(catalogName)}`}>{catalogName}</Link>
      {schemaName && (
        <>
          <span>/</span>
          <Link to={`/explore/${encodeURIComponent(catalogName)}/${encodeURIComponent(schemaName)}`}>{schemaName}</Link>
        </>
      )}
      {tableName && (
        <>
          <span>/</span>
          <span>{tableName}</span>
        </>
      )}
    </div>
  );
}

export function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <div className="fact-label">{label}</div>
      <div className="fact-value">{value}</div>
    </div>
  );
}
