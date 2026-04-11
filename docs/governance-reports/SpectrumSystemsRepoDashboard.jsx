import React, { useEffect, useMemo, useState } from 'react';

const exampleSnapshot = {
  generated_at: '2026-04-10T00:00:00Z',
  repo_name: 'spectrum-systems',
  root_counts: {
    files_total: 0,
    runtime_modules: 0,
    tests: 0,
    contracts_total: 0,
    schemas: 0,
    examples: 0,
    docs: 0,
    run_artifacts: 0,
  },
  core_areas: [],
  constitutional_center: [
    'README.md',
    'docs/architecture/system_registry.md',
    'docs/roadmaps/system_roadmap.md',
  ],
  runtime_hotspots: [],
  operational_signals: [],
  key_state: {},
};

const SNAPSHOT_SOURCE = {
  AUTO: 'auto',
  MANUAL: 'manual',
  FALLBACK: 'fallback',
};

function sourceLabel(mode) {
  if (mode === SNAPSHOT_SOURCE.AUTO) {
    return 'Using auto-loaded snapshot';
  }
  if (mode === SNAPSHOT_SOURCE.MANUAL) {
    return 'Using manual snapshot';
  }
  return 'Using fallback example snapshot';
}

export function SpectrumSystemsRepoDashboard() {
  const fallbackText = useMemo(() => JSON.stringify(exampleSnapshot, null, 2), []);
  const [sourceMode, setSourceMode] = useState(SNAPSHOT_SOURCE.FALLBACK);
  const [snapshotText, setSnapshotText] = useState(fallbackText);
  const [loadStatusMessage, setLoadStatusMessage] = useState('');

  useEffect(() => {
    let active = true;

    async function loadSnapshot() {
      try {
        const response = await fetch('/artifacts/dashboard/repo_snapshot.json');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        const prettyPayload = JSON.stringify(payload, null, 2);
        if (!active) {
          return;
        }

        setSnapshotText(prettyPayload);
        setSourceMode(SNAPSHOT_SOURCE.AUTO);
        setLoadStatusMessage('Auto-loaded snapshot from /artifacts/dashboard/repo_snapshot.json');
      } catch (_) {
        if (!active) {
          return;
        }

        setSnapshotText(fallbackText);
        setSourceMode(SNAPSHOT_SOURCE.FALLBACK);
        setLoadStatusMessage('Snapshot file not found; using fallback example');
      }
    }

    loadSnapshot();

    return () => {
      active = false;
    };
  }, [fallbackText]);

  const parseResult = useMemo(() => {
    try {
      return { parsedSnapshot: JSON.parse(snapshotText), parseError: '' };
    } catch (error) {
      return {
        parsedSnapshot: null,
        parseError: error instanceof Error ? error.message : 'Invalid JSON',
      };
    }
  }, [snapshotText]);

  const { parsedSnapshot, parseError } = parseResult;

  const rootCountEntries = parsedSnapshot?.root_counts
    ? Object.entries(parsedSnapshot.root_counts)
    : [];
  const keyStateEntries = parsedSnapshot?.key_state
    ? Object.entries(parsedSnapshot.key_state)
    : [];

  return (
    <section>
      <h2>Spectrum Systems Repo Dashboard</h2>
      <p>{sourceLabel(sourceMode)}</p>
      {loadStatusMessage ? <p>{loadStatusMessage}</p> : null}
      {parseError ? <p>Parse error: {parseError}</p> : null}

      <label htmlFor="repo-snapshot-input">Snapshot JSON</label>
      <textarea
        id="repo-snapshot-input"
        rows={20}
        value={snapshotText}
        onChange={(event) => {
          setSnapshotText(event.target.value);
          setSourceMode(SNAPSHOT_SOURCE.MANUAL);
        }}
      />

      {parsedSnapshot ? (
        <>
          <h3>{parsedSnapshot.repo_name ?? 'Unknown repo'}</h3>
          <p>Generated at: {parsedSnapshot.generated_at ?? 'unknown'}</p>

          <h4>Root counts</h4>
          <ul>
            {rootCountEntries.map(([key, value]) => (
              <li key={key}>
                <strong>{key}:</strong> {String(value)}
              </li>
            ))}
          </ul>

          {keyStateEntries.length > 0 ? (
            <>
              <h4>Operational key state</h4>
              <ul>
                {keyStateEntries.map(([key, value]) => (
                  <li key={key}>
                    <strong>{key}:</strong> {JSON.stringify(value)}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

export default SpectrumSystemsRepoDashboard;
