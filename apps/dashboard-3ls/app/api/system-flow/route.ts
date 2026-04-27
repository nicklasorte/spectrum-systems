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

export interface SystemFlowEnvelope {
  state: 'ok' | 'missing' | 'invalid_schema';
  payload: GraphArtifact | null;
  reason: string;
  source_artifact: string;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === 'string');
}

export function isGraphArtifact(value: unknown): value is GraphArtifact {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  if (!Array.isArray(v.active_systems)) return false;
  if (!isStringArray(v.canonical_loop)) return false;
  if (!isStringArray(v.canonical_overlays)) return false;

  for (const row of v.active_systems as unknown[]) {
    if (!row || typeof row !== 'object') return false;
    const r = row as Record<string, unknown>;
    if (typeof r.system_id !== 'string') return false;
    if (!isStringArray(r.upstream)) return false;
    if (!isStringArray(r.downstream)) return false;
  }

  return true;
}

export function resolveSystemFlowEnvelope(graph: unknown): SystemFlowEnvelope {
  if (graph === null) {
    return {
      state: 'missing',
      payload: null,
      reason: `not_found:${GRAPH_PATH}`,
      source_artifact: GRAPH_PATH,
    };
  }

  if (!isGraphArtifact(graph)) {
    return {
      state: 'invalid_schema',
      payload: null,
      reason: 'shape_mismatch',
      source_artifact: GRAPH_PATH,
    };
  }

  return {
    state: 'ok',
    payload: graph,
    reason: 'artifact_loaded',
    source_artifact: GRAPH_PATH,
  };
}

export async function GET() {
  const graph = loadArtifact<unknown>(GRAPH_PATH);
  return NextResponse.json(resolveSystemFlowEnvelope(graph));
}
