import Editor, { type OnMount } from "@monaco-editor/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { editor, IDisposable } from "monaco-editor";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, queryKeys } from "../api/client";
import type { StatementResponse } from "../api/types";
import CatalogTree from "../components/CatalogTree";
import { ErrorBox, StatementResult } from "../components/ResultsGrid";
import { formatDuration } from "../format";
import { useColorScheme } from "../hooks/useColorScheme";
import { registerSqlCompletion } from "../monaco/sqlCompletion";
import { quotedTableName } from "../sql/names";

const editorTextStorageKey = "drb-emu.sql-editor.text";
const resultRowLimit = 10000;
const welcomeText = `-- Ctrl+Enter runs the selection, or the whole editor when nothing is selected.
-- Statements are separated by semicolons; the result of the last one is shown.
SHOW TABLES`;

type RunOutcome =
  | { kind: "response"; response: StatementResponse; elapsedMilliseconds: number }
  | { kind: "failure"; message: string };

function readStoredText(): string {
  try {
    return localStorage.getItem(editorTextStorageKey) ?? welcomeText;
  } catch {
    return welcomeText;
  }
}

export default function SqlEditor() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [text, setText] = useState(() => searchParams.get("query") ?? readStoredText());
  const [running, setRunning] = useState(false);
  const [outcome, setOutcome] = useState<RunOutcome | null>(null);
  const queryClient = useQueryClient();
  const colorScheme = useColorScheme();
  const tree = useQuery({ queryKey: queryKeys.catalogTree, queryFn: api.getCatalogTree });
  const session = useQuery({ queryKey: queryKeys.session, queryFn: api.getSession });

  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const runningRef = useRef(false);
  const completionRef = useRef<IDisposable | null>(null);
  const treeRef = useRef(tree.data);
  const sessionRef = useRef(session.data);
  treeRef.current = tree.data;
  sessionRef.current = session.data;

  useEffect(() => {
    const requestedQuery = searchParams.get("query");
    if (requestedQuery !== null) {
      setText(requestedQuery);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    try {
      localStorage.setItem(editorTextStorageKey, text);
    } catch {
      return;
    }
  }, [text]);

  useEffect(() => () => completionRef.current?.dispose(), []);

  const run = useCallback(async () => {
    const editorInstance = editorRef.current;
    const model = editorInstance?.getModel();
    if (!editorInstance || !model || runningRef.current) {
      return;
    }
    const selection = editorInstance.getSelection();
    const selectedText = selection && !selection.isEmpty() ? model.getValueInRange(selection) : "";
    const statement = selectedText.trim() ? selectedText : model.getValue();
    if (!statement.trim()) {
      return;
    }
    runningRef.current = true;
    setRunning(true);
    const startedAt = performance.now();
    try {
      const response = await api.executeStatement(statement, resultRowLimit);
      setOutcome({ kind: "response", response, elapsedMilliseconds: performance.now() - startedAt });
    } catch (error) {
      setOutcome({ kind: "failure", message: error instanceof Error ? error.message : String(error) });
    } finally {
      runningRef.current = false;
      setRunning(false);
      await queryClient.invalidateQueries();
    }
  }, [queryClient]);

  const runRef = useRef(run);
  runRef.current = run;

  const handleMount: OnMount = (editorInstance, monaco) => {
    editorRef.current = editorInstance;
    editorInstance.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
      void runRef.current();
    });
    completionRef.current?.dispose();
    completionRef.current = registerSqlCompletion(monaco, { tree: () => treeRef.current, session: () => sessionRef.current });
    editorInstance.focus();
  };

  const insertAtCursor = (insertedText: string) => {
    const editorInstance = editorRef.current;
    const selection = editorInstance?.getSelection();
    if (!editorInstance || !selection) {
      return;
    }
    editorInstance.executeEdits("schema-browser", [{ range: selection, text: insertedText, forceMoveMarkers: true }]);
    editorInstance.focus();
  };

  return (
    <div className="sql-page">
      <div className="sql-sidebar">
        <div className="panel-title">Schema browser</div>
        <div className="muted panel-hint">Click a table to insert its name.</div>
        <CatalogTree onTableClick={(catalogName, schemaName, table) => insertAtCursor(quotedTableName(catalogName, schemaName, table.name))} />
      </div>
      <div className="sql-workspace">
        <div className="toolbar">
          <button className="primary" onClick={() => void run()} disabled={running}>
            {running ? "Running…" : "▶ Run"}
          </button>
          <span className="muted">Ctrl+Enter · runs the selection when there is one</span>
          <span className="spacer" />
          {session.data && (
            <span className="session-pill" title="Change with USE CATALOG / USE SCHEMA">
              {session.data.current_catalog}.{session.data.current_schema}
            </span>
          )}
        </div>
        <div className="editor-area">
          <Editor
            language="sql"
            value={text}
            onChange={(value) => setText(value ?? "")}
            onMount={handleMount}
            theme={colorScheme === "dark" ? "vs-dark" : "vs"}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap: "on",
              tabSize: 2,
            }}
          />
        </div>
        <div className="results-area">
          <ResultsPanel outcome={outcome} running={running} />
        </div>
      </div>
    </div>
  );
}

function ResultsPanel({ outcome, running }: { outcome: RunOutcome | null; running: boolean }) {
  if (running && !outcome) {
    return <div className="muted padded">Running…</div>;
  }
  if (!outcome) {
    return <div className="muted padded">Results appear here.</div>;
  }
  if (outcome.kind === "failure") {
    return <ErrorBox code="REQUEST_FAILED" message={outcome.message} />;
  }
  const { response, elapsedMilliseconds } = outcome;
  const manifest = response.manifest;
  return (
    <>
      <div className="results-summary">
        <span className={`status-dot ${response.status.state === "SUCCEEDED" ? "ok" : "failed"}`} />
        {response.status.state === "SUCCEEDED" ? (
          <span>
            {manifest?.total_row_count ?? 0} rows
            {manifest?.truncated ? ` (showing the first ${response.result?.row_count})` : ""}
          </span>
        ) : (
          <span>Failed</span>
        )}
        <span className="muted">· {formatDuration(elapsedMilliseconds)}</span>
      </div>
      <StatementResult response={response} />
    </>
  );
}
