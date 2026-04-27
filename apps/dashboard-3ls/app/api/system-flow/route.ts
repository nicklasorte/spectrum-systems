import { NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';

const GRAPH_PATH = 'artifacts/tls/system_registry_dependency_graph.json';

type GraphSystem = {
  system_id: string;
  upstream: string[];
  downstream: string[];
  artifacts_owned?: string[];
  primary_code_paths?: string[];
  purpose?: string;
};

type GraphArtifact = {
  schema_version?: string;
  phase?: string;
  active_systems?: GraphSystem[];
  canonical_loop?: string[];
  canonical_overlays?: string[];
};

function isGraphArtifact(value: unknown): value is GraphArtifact {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  if (!Array.isArray(v.active_systems)) return false;
  if (!Array.isArray(v.canonical_loop)) return false;
  if (!Array.isArray(v.canonical_overlays)) return false;

  for (const row of v.active_systems as unknown[]) {
    if (!row || typeof row !== 'object') return false;
    const r = row as Record<string, unknown>;
    if (typeof r.system_id !== 'string') return false;
    if (!Array.isArray(r.upstream)) return false;
    if (!Array.isArray(r.downstream)) return false;
  }

  return true;
}

export async function GET() {
  const graph = loadArtifact<unknown>(GRAPH_PATH);

  if (graph === null) {
    return NextResponse.json({ state: 'missing', reason: `not_found:${GRAPH_PATH}`, payload: null }, { status: 200 });
  }

  if (!isGraphArtifact(graph)) {
    return NextResponse.json({ state: 'invalid_schema', reason: 'shape_mismatch', payload: null }, { status: 200 });
  }

  return NextResponse.json({
    state: 'ok',
    payload: graph,
    source_artifact: GRAPH_PATH,
  });
}
