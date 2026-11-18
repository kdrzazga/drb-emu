# drb-emu — design

A local, single-machine emulation of a Databricks workspace in Python: Unity Catalog, a Delta-based data lake, a SQL warehouse, a PySpark-compatible DataFrame API and Lakeview-style dashboards. Not built for big data: correctness and the Databricks "feel" matter, throughput does not.

## Stack

| Concern | Choice |
|---|---|
| Query execution | DuckDB (in-process, Arrow results) |
| SQL dialect translation | sqlglot (`read="databricks"` → `write="duckdb"`) |
| Table format | Delta Lake via delta-rs (`deltalake`) |
| Metastore | SQLite via SQLAlchemy |
| Backend API | FastAPI + pydantic, WebSocket for long results |
| Frontend | React + TypeScript + Vite, Monaco, TanStack Table, ECharts, react-grid-layout |
| Notebook kernels | jupyter_client subprocess kernels |
| Python | 3.14, own venv inside this repo |

## Architecture

```
Frontend: Catalog Explorer | SQL Editor | Notebooks | Dashboards | Query History
                 │ REST (Databricks-shaped paths) + WebSocket
Backend (FastAPI)
  Statement Router ── sqlglot parse ──┬── catalog commands → Unity Catalog service
                                      ├── queries → Resolver → DuckDB
                                      └── DML → DuckDB (compute) → delta-rs (commit)
  Spark emulator ── builds sqlglot ASTs ── same Router
  Unity Catalog service ── SQLite metastore
  Data lake ── local folder posing as object storage
```

## 1. Data lake

- One root folder `lake/` stands in for S3/ADLS.
- A path resolver maps `dbfs:/`, `s3://`, `abfss://` and `/Volumes/<catalog>/<schema>/<volume>/` to folders under `lake/`.
- Tables are real Delta tables written by delta-rs: transaction log, versions, `DESCRIBE HISTORY`, `VERSION AS OF`, `MERGE`, `OPTIMIZE`, `VACUUM`, `RESTORE`.
- Raw files (CSV, JSON, Parquet) in Volumes are read through DuckDB readers.
- `dbutils.fs` (`ls`, `cp`, `mv`, `rm`, `mkdirs`, `head`) on top of the path resolver.

## 2. Unity Catalog

- The SQLite metastore is the single source of truth for metadata.
- Hierarchy: metastore → catalog → schema → table / view / volume / function.
- Tables are managed (`lake/__managed/<catalog>/<schema>/<table_id>`) or external (any lake path); they carry columns, comments and tags.
- Principals (users, groups) and privileges (`USE CATALOG`, `USE SCHEMA`, `SELECT`, `MODIFY`, `CREATE TABLE`, `ALL PRIVILEGES`, ...) inherit down the hierarchy; the current user comes from a request header.
- **Resolver = enforcement point:** it walks the sqlglot AST, checks privileges and rewrites each `catalog.schema.table` into a scan of the table's Delta location. A missing grant raises `PERMISSION_DENIED` before DuckDB runs anything.
- Each resolved statement records table lineage, plus column lineage via `sqlglot.lineage`.
- `information_schema` is a set of virtual views over the metastore.

## 3. SQL layer

1. Parse with `sqlglot.parse(sql, read="databricks")`.
2. Classify each statement:
   - **Catalog commands** (`CREATE CATALOG/SCHEMA/VOLUME`, `GRANT`, `REVOKE`, `SHOW ...`, `DESCRIBE ...`, `USE`, `COMMENT ON`) are handled by the UC service only.
   - **Queries** go through the Resolver, are generated as DuckDB SQL and run in DuckDB; results come back as Arrow.
   - **DML** (`INSERT`, `CTAS`, `MERGE`, `UPDATE`, `DELETE`): DuckDB computes Arrow, delta-rs commits. DuckDB reads Delta, delta-rs owns every write.
   - **Delta utilities** (`DESCRIBE HISTORY`, `OPTIMIZE`, `VACUUM`, `RESTORE`) call delta-rs directly.
3. A function-mapping table covers what sqlglot does not translate (`date_format` patterns, `explode`, `collect_list`, `from_json`, ...). This is where fidelity improves over time.
4. Each session owns a DuckDB connection and its current catalog/schema and Spark conf. Statements run on a worker pool with paged results, and every run goes into query history.

## 4. Spark emulator

- A lazy DataFrame that holds a sqlglot AST.
  - Transformations (`select`, `filter`, `withColumn`, `join`, `groupBy().agg()`, `union`, `orderBy`, `Window`) wrap the tree.
  - Actions (`collect`, `show`, `count`, `toPandas`, `write`) compile it and send it through the SQL router, so permissions, lineage and Delta writes behave the same as in SQL.
- Surface: `SparkSession.builder.getOrCreate()`, `spark.sql`, `spark.table`, `spark.read.format().option().load()`, `functions as F`, `Column`, `Row`, types, `df.write.format("delta").mode().saveAsTable()`, `createOrReplaceTempView`, `spark.catalog`.
- The package is named `drb_emu.spark`, never `pyspark`. An opt-in import hook makes `import pyspark` resolve to it, only inside notebook kernels or when explicitly enabled, so real PySpark can sit side by side for comparison tests.
- Evaluate SQLFrame (PySpark API over DuckDB via sqlglot) as a reference or base before building from scratch.

## 5. Dashboards (Lakeview-style)

- A dashboard is JSON: datasets (named SQL queries), widgets (chart type, field mapping, grid position) and global filters/parameters bound as `:param`.
- Draft/published states.
- A result cache keyed on query, parameters and the Delta versions of the tables read, so it is invalidated exactly when data changes.
- Widgets: bar, line, area, scatter, pie, counter, table, pivot, filter controls.

## 6. Notebooks

- One subprocess kernel per notebook with `spark`, `dbutils` and `display()` pre-loaded.
- `%sql`, `%python` and `%md` cell magics.
- `display(df)` renders the same grid and charts as dashboards.

## 7. API

- Databricks-shaped REST paths (`/api/2.1/unity-catalog/catalogs|schemas|tables|volumes`, `/api/2.0/sql/statements`, `/api/2.0/lakeview/dashboards`), so `databricks-sdk` can eventually be pointed at the emulator.

## Layout

```
drb-emu/
  backend/drb_emu/
    api/          FastAPI routers per area
    catalog/      UC models, service, grants, lineage, information_schema
    lake/         path resolver, volumes, Delta I/O
    sql/          router, resolver, dialect + function mapping, sessions, history
    spark/        SparkSession, DataFrame, Column, functions, types, readers/writers, import hook
    dashboards/
    notebooks/    kernel manager, magics, display()
  backend/tests/
  frontend/       React app
```

## Build order

1. ✅ Lake path resolver, Delta I/O and DuckDB sessions, plus a minimal FastAPI server.
2. ✅ UC metastore and Resolver: three-level names, managed tables, `SELECT`.
3. ✅ SQL router: catalog commands, DML through delta-rs, `MERGE`, time travel, query history.
   - Statements sqlglot cannot parse (`CREATE/DROP CATALOG`, `SHOW ...`, `COMMENT ON CATALOG`, `DESCRIBE DETAIL`, `RESTORE`, `OPTIMIZE`, `VACUUM`) are matched by regex first.
   - `INSERT` runs against an empty DuckDB scratch copy of the target and appends; `UPDATE`/`DELETE`/`MERGE` run against a full scratch copy and overwrite the Delta table. Each commit is tagged `drb.operation` so `DESCRIBE HISTORY` shows `UPDATE`, `DELETE`, `MERGE`.
   - `UPDATE SET *` / `INSERT *` in `MERGE` are expanded by column name before DuckDB sees them.
   - Not yet: `ALTER TABLE`, `SHOW VIEWS`, `information_schema`, column comments, `TIMESTAMP AS OF <expression>`.
4. ✅ Minimal frontend: Catalog Explorer, SQL Editor, results grid, Query History.
   - `frontend/`: Vite + React 18 + TypeScript, Monaco bundled locally (no CDN), React Query, hash routing.
   - Dev: `npm run dev` in `frontend/` (port 5173) proxies `/api` to the FastAPI server on port 8000.
   - Build: `npm run build` writes `frontend/dist`; `python -m drb_emu` then serves the UI at http://127.0.0.1:8000/.
   - Extra backend endpoints for the UI: `GET /api/drb/session`, `GET /api/drb/catalog-tree`.
   - Demo data: `python -m drb_emu.seed [people] [trades] [computer_store] [--replace]` creates three catalogs with
     deterministic generated data (50–2000 rows per table, small dictionary tables excepted) and a few views each.
5. Spark DataFrame API and opt-in `pyspark` import hook.
6. Dashboards.
7. Grant enforcement and lineage UI.
8. Notebooks.

## Known risks

- **Spark vs DuckDB semantics:** integer division, null ordering, case sensitivity, timestamp types, decimal precision and date-format patterns. A comparison suite runs the same workloads against real PySpark (e.g. from `D:\code\python-db`'s venv) and diffs the results.
- **Python 3.14 wheels:** confirm `deltalake`, `pyarrow`, `sqlglot` and `jupyter_client` install on 3.14 before step 1.
- **Writers:** delta-rs handles commit conflicts on a local filesystem, but there is a single writer process by design.
