import React from 'react';
import type { SystemGraphEdge } from '@/lib/systemGraph';
import { SourceBreadcrumbs } from './SourceBreadcrumbs';

interface Props {
  edge: SystemGraphEdge | null;
}

const MISSING = 'Unknown / Missing';

export function EdgeInspector({ edge }: Props) {
  if (!edge) {
    return (
      <div className="border dark:border-slate-700 rounded p-3 text-sm text-gray-600 dark:text-slate-300 bg-white dark:bg-slate-900" data-testid="edge-inspector">
        Hover or click an edge label to inspect dependency.
      </div>
    );
  }

  return (
    <div className="border dark:border-slate-700 rounded p-3 text-sm space-y-2 bg-white dark:bg-slate-900 dark:text-slate-100" data-testid="edge-inspector">
      <header>
        <h3 className="font-semibold">
          Edge: {edge.from} → {edge.to}
        </h3>
      </header>
      <dl className="grid grid-cols-1 gap-y-1 text-xs">
        <div data-testid="edge-inspector-dependency-type">
          <dt className="font-medium inline">dependency type:</dt>{' '}
          <dd className="inline">{edge.dependency_type || edge.edge_type || MISSING}</dd>
        </div>
        <div data-testid="edge-inspector-artifact-backed">
          <dt className="font-medium inline">artifact-backed:</dt>{' '}
          <dd className="inline">{
            (edge.artifact_backed ?? (edge.source_type === 'artifact_store' || edge.source_type === 'repo_registry'))
              ? 'yes (artifact-backed)'
              : 'no (inferred)'
          }</dd>
        </div>
        <div data-testid="edge-inspector-last-validated">
          <dt className="font-medium inline">last validated:</dt>{' '}
          <dd className="inline">{edge.last_validated ?? MISSING}</dd>
        </div>
        <div data-testid="edge-inspector-related-signal">
          <dt className="font-medium inline">related signal:</dt>{' '}
          <dd className="inline">{edge.related_signal ?? 'none recorded'}</dd>
        </div>
      </dl>
      <SourceBreadcrumbs
        artifactPaths={edge.source_artifact_ref ? [edge.source_artifact_ref] : []}
        schemaPaths={[]}
        producingScript={null}
        lastValidated={edge.last_validated}
        testid="edge-inspector-breadcrumbs"
      />
    </div>
  );
}
